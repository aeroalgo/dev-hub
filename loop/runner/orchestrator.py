"""Outer orchestration loop, lifecycle coordination, and action decision machine."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from loop.halt_logic import decide_after_action
from loop.runner import (
    ContextPort,
    RunAction,
    RunOutcome,
    RunnerConfig,
    SessionPort,
    SessionRequest,
    SessionResult,
)
from loop.runner.output import (
    format_abort_diagnostic,
    format_check_after_summary,
    format_cleared_incidents,
    format_dag_fanout,
    format_loop_complete,
    format_prepare_summary,
    format_pruned_logs,
    format_roadmap_advance,
    format_session_banner,
    format_session_exit,
    format_session_model_info,
    format_transient_cap_reached,
    format_transient_reprepare_complete,
    format_transient_reprepare_resync,
    format_transient_retry,
)
from loop.runner.ownership import RunnerLease
from loop.runner.session import SessionInvoker


class IncidentTracker:
    """Handles open incident clearance, trace logging, and Tier-1 self-healing."""

    def __init__(self, *, tier1_enabled: bool = True) -> None:
        self.tier1_enabled = tier1_enabled

    def clear_open_on_start(self, project_root: Path) -> Mapping[str, Any]:
        """Clear leftover open incidents on process start."""
        try:
            from loop.epic_paths import epic_dir
            from loop.incidents.store import resolve_all_open_incidents

            edir = epic_dir(project_root)
            if not edir.is_dir():
                return {"ok": True, "cleared_count": 0, "diagnostic_codes": []}
            cleared = resolve_all_open_incidents(edir)
            codes: set[str] = set()
            for rec in cleared:
                codes.update(rec.diagnostic_codes or [])
            return {
                "ok": True,
                "cleared_count": len(cleared),
                "diagnostic_codes": sorted(codes),
            }
        except Exception:
            return {"ok": True, "cleared_count": 0, "diagnostic_codes": []}

    def record_trace(
        self,
        project_root: Path,
        *,
        phase: str,
        action: str,
        decide: str,
        episode_id: str = "",
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        """Append a trace record for auditability."""
        try:
            from loop.epic_paths import epic_dir
            from loop.incidents.trace import append_trace

            edir = epic_dir(project_root)
            append_trace(
                edir,
                phase=phase,
                action=action,
                decide=decide,
                episode_id=episode_id,
                detail=dict(detail or {}),
            )
        except Exception:
            pass

    def attempt_tier1(self, project_root: Path) -> bool:
        """Attempt Tier-1 automated self-healing if eligible open incidents exist."""
        if not self.tier1_enabled or os.environ.get("EPIC_INCIDENT_TIER1") == "0":
            return False
        try:
            from loop.epic_paths import epic_dir
            from loop.incidents.store import list_open_incidents, resolve_incident
            from loop.incidents.tier1_runner import run_tier1_session, should_attempt_tier1

            edir = epic_dir(project_root)
            open_incs = list_open_incidents(edir)
            if not open_incs:
                return False
            inc = open_incs[0]
            if should_attempt_tier1(inc, edir):
                res = run_tier1_session(inc, edir, project_root)
                if res.success:
                    resolve_incident(
                        edir,
                        inc.incident_id,
                        resolution={"resolution_tier": "tier1", "resolution_action": "tier1_autofix"},
                    )
                    return True
        except Exception:
            return False
        return False


class ContextLoopPort(ContextPort):
    """Default ContextPort delegating directly to loop.context_loop and roadmap_queue."""

    def prepare_session(
        self,
        cwd: str | Path,
        *,
        model: str | None = None,
        runtime: str | None = None,
        _chain_depth: int = 0,
    ) -> Mapping[str, Any]:
        import loop.context_loop as cl

        return cl.prepare_session(cwd, model=model, runtime=runtime, _chain_depth=_chain_depth)

    def check_after(
        self,
        cwd: str | Path,
        *,
        fingerprint_before: str | None = None,
    ) -> Mapping[str, Any]:
        import loop.context_loop as cl

        return cl.check_after(cwd, fingerprint_before=fingerprint_before)

    def record_abort(
        self,
        cwd: str | Path,
        *,
        log_path: str | Path,
        exit_code: int,
        attempt: int = 1,
        runtime: str = "claude",
    ) -> Mapping[str, Any]:
        import loop.context_loop as cl

        return cl.record_abort(
            cwd,
            log_path=log_path,
            exit_code=exit_code,
            attempt=attempt,
            runtime=runtime,
        )

    def roadmap_advance(
        self,
        cwd: str | Path,
    ) -> Mapping[str, Any]:
        import loop.roadmap_queue as rq

        return rq.roadmap_advance(cwd)

    def dag_fanout(
        self,
        cwd: str | Path,
    ) -> Mapping[str, Any]:
        import loop.context_loop as cl

        return cl.dag_fanout(cwd)


class LoopRunner:
    """Outer supervision loop runner coordinating session lifecycle and action transitions."""

    def __init__(
        self,
        config: RunnerConfig,
        *,
        context_port: ContextPort | None = None,
        session_invoker: SessionPort | None = None,
        incident_tracker: IncidentTracker | None = None,
        lease: RunnerLease | None = None,
        stdout: Callable[[str], None] | None = None,
        stderr: Callable[[str], None] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self.config = config
        self.context_port = context_port or ContextLoopPort()
        self.session_invoker = session_invoker or SessionInvoker()
        self.incident_tracker = incident_tracker or IncidentTracker()
        self.lease = lease or RunnerLease.from_config(config)
        self.stdout = stdout or (lambda s: (sys.stdout.write(s), sys.stdout.flush()))
        self.stderr = stderr or (lambda s: (sys.stderr.write(s), sys.stderr.flush()))
        self.sleeper = sleeper or time.sleep

    def prune_logs(self, state_dir: Path, keep: int = 10) -> tuple[int, int]:
        """Prune old session log files beyond the retention limit."""
        keep_val = max(1, keep)
        if not state_dir.is_dir():
            return 0, 0
        logs = sorted(
            state_dir.glob("session-*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        removed = 0
        for path in logs[keep_val:]:
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
        kept = min(keep_val, len(logs))
        return removed, kept

    def reprepare_for_transient_retry(
        self,
        next_try: int,
        prev_step: str | None = None,
    ) -> tuple[int, Mapping[str, Any]]:
        """Re-prepare context during a transient retry attempt.

        Returns (code, prep_data) where:
          0: re-prepared ok, proceed with next session
          2: epic completed during retry, skip stale retry
          1: prepare failed / stopped, resume outer loop
        """
        runtime_name = getattr(self.config.runtime, "epic_runtime", "claude")
        prep = self.context_port.prepare_session(
            self.config.project_root,
            model=self.config.cli_model,
            runtime=runtime_name,
        )
        self.stdout(format_prepare_summary(prep, verbose=self.config.verbose) + "\n")

        if prep.get("complete"):
            prep_stop = prep.get("stop", "")
            if prep_stop == "EPIC_DONE":
                self.stdout(
                    format_transient_reprepare_complete(
                        prep.get("armed_step"), prev_step
                    )
                    + "\n"
                )
                return 2, prep
            self.stderr(
                f"==> WARN: transient retry prepare stopped (stop={prep_stop or '?'}) — resume outer loop\n"
            )
            return 1, prep

        if not prep.get("ok"):
            if prep.get("halt"):
                self.stderr("==> HALT: transient retry prepare fail-closed\n")
                if prep.get("reason"):
                    self.stderr(f"==> reason: {prep['reason']}\n")
                return 1, prep
            self.stderr("==> WARN: transient retry prepare failed — resume outer loop\n")
            if prep.get("reason"):
                self.stderr(f"==> reason: {prep['reason']}\n")
            return 1, prep

        armed_step = prep.get("armed_step", "")
        self.stdout(
            format_transient_reprepare_resync(armed_step, prev_step) + "\n"
        )
        return 0, prep

    def run(self) -> RunOutcome:
        """Execute outer loop supervision until completion, halt, or interrupt."""
        with self.lease:
            # Clear open incidents on startup
            cleared = self.incident_tracker.clear_open_on_start(self.config.project_root)
            if cleared.get("cleared_count"):
                self.stdout(
                    format_cleared_incidents(
                        cleared["cleared_count"],
                        cleared.get("diagnostic_codes", []),
                    )
                    + "\n"
                )

            iteration = 0
            while True:
                iteration += 1
                self.stdout(format_session_banner(iteration) + "\n")

                # 1. Prune old session logs
                keep_logs = int(os.environ.get("EPIC_SESSION_LOG_KEEP", 10))
                removed, kept = self.prune_logs(self.config.state_dir, keep=keep_logs)
                if removed > 0:
                    self.stdout(format_pruned_logs(removed, kept) + "\n")

                # 2. Context prepare
                runtime_name = getattr(self.config.runtime, "epic_runtime", "claude")
                prep = self.context_port.prepare_session(
                    self.config.project_root,
                    model=self.config.cli_model,
                    runtime=runtime_name,
                )
                self.stdout(format_prepare_summary(prep, verbose=self.config.verbose) + "\n")

                if prep.get("complete"):
                    prep_stop = prep.get("stop", "")
                    if prep_stop == "EPIC_DONE" and os.environ.get("EPIC_CHAIN_ROADMAP") == "1":
                        advance_fn = getattr(self.context_port, "roadmap_advance", None)
                        if advance_fn:
                            adv = advance_fn(self.config.project_root)
                            self.stdout(format_roadmap_advance(adv, verbose=self.config.verbose) + "\n")
                            if adv.get("ok") and adv.get("armed"):
                                continue
                            if adv.get("complete"):
                                self.stdout(format_loop_complete("roadmap queue") + "\n")
                                return RunOutcome(action=RunAction.COMPLETE, exit_code=0, reason="roadmap_queue")
                            self.stderr("==> ERROR: roadmap-advance failed after prepare EPIC_DONE (rc=1)\n")
                            return RunOutcome(action=RunAction.HALT, exit_code=1, reason="roadmap_advance_failed")
                    self.stdout(format_loop_complete("stop marker") + "\n")
                    return RunOutcome(action=RunAction.COMPLETE, exit_code=0, reason="stop_marker")

                if not prep.get("ok"):
                    if prep.get("halt"):
                        diags = ",".join(prep.get("diagnostic_codes") or [])
                        self.stderr(f"==> HALT: prepare fail-closed (diagnostic_codes={diags or 'none'})\n")
                        if prep.get("reason"):
                            self.stderr(f"==> reason: {prep['reason']}\n")
                        return RunOutcome(action=RunAction.HALT, exit_code=prep.get("exit_code") or 1, reason=prep.get("reason"))
                    self.stderr("==> WARN: prepare failed — retrying outer loop\n")
                    self.sleeper(20)
                    continue

                # 3. Resolve session execution parameters
                runtime_id = prep.get("runtime") or runtime_name
                runtime_extras = prep.get("runtime_extras") or {}
                session_model = prep.get("model") or self.config.cli_model
                loop_phase = prep.get("loop_phase") or prep.get("phase") or ""
                armed_step = prep.get("armed_step") or ""
                model_source = prep.get("model_source") or ""
                fingerprint_before = prep.get("fingerprint") or ""
                prompt_file_str = prep.get("prompt_file") or ""
                prompt_file = Path(prompt_file_str) if prompt_file_str else self.config.state_dir / "prompt.txt"

                self.stdout(
                    format_session_model_info(session_model, loop_phase, armed_step, model_source) + "\n"
                )

                if not session_model:
                    self.stderr(
                        "==> HALT: model_required: pass --model or set PROJECT_LOOP_<PHASE>_MODEL (silent default forbidden)\n"
                    )
                    return RunOutcome(action=RunAction.HALT, exit_code=2, reason="model_required")

                # 4. Inner session execution & transient retry loop
                transient_try = 0
                max_transient = getattr(self.config.runtime, "transient_retry_max", 3)
                max_subagent = getattr(self.config.runtime, "subagent_retry_max", 3)
                subagent_retries = 0
                resume_outer = False

                while True:
                    transient_try += 1
                    session_tag = str(iteration) if transient_try == 1 else f"{iteration}-t{transient_try}"
                    session_log = self.config.state_dir / f"session-{session_tag}.log"

                    timeout_sec = getattr(self.config.runtime, "session_timeout_sec", 300)
                    kill_grace_sec = getattr(self.config.runtime, "session_kill_grace_sec", 10)
                    heartbeat_sec = getattr(self.config.runtime, "status_heartbeat_sec", None)
                    idle_timeout_sec = getattr(self.config.runtime, "stream_idle_timeout_sec", None)

                    req = SessionRequest(
                        session_id=f"session-{session_tag}",
                        prompt_file=prompt_file,
                        runtime_id=runtime_id,
                        phase=loop_phase,
                        model=session_model,
                        mode="headless" if self.config.headless else "interactive",
                        log_file=session_log,
                        timeout_sec=timeout_sec,
                        kill_grace_sec=kill_grace_sec,
                        heartbeat_sec=heartbeat_sec,
                        idle_timeout_sec=idle_timeout_sec,
                        permission_mode=self.config.permission_mode,
                        extra_args=self.config.extra_args,
                        project_root=self.config.project_root,
                        hub_root=self.config.hub_root,
                        runtime_extras=runtime_extras,
                    )

                    result = self.session_invoker.invoke(req)

                    if result.exit_code in (130, 143) or result.interrupted:
                        self.stderr("==> loop aborted by user interrupt (SIGINT/SIGTERM)\n")
                        return RunOutcome(action=RunAction.HALT, exit_code=130, reason="user_interrupt")

                    self.stdout(
                        format_session_exit(runtime_id, result.exit_code, transient_try, max_transient) + "\n"
                    )

                    rec = self.context_port.record_abort(
                        self.config.project_root,
                        log_path=session_log,
                        exit_code=result.exit_code,
                        attempt=transient_try,
                        runtime=runtime_id,
                    )

                    if rec.get("ok"):
                        # Session execution clean; proceed to check-after
                        break

                    retryable = bool(rec.get("retryable"))
                    backoff = int(rec.get("backoff_sec") or 0)
                    reason = str(rec.get("reason") or "")

                    retry_limit = max_transient
                    retry_count = transient_try
                    is_subagent_timeout = (reason == "native collaboration wait timeout")
                    if is_subagent_timeout:
                        retry_limit = max_subagent
                        retry_count = subagent_retries

                    if retryable and transient_try < max_transient and retry_count < retry_limit:
                        if is_subagent_timeout:
                            subagent_retries += 1
                        for line in format_transient_retry(
                            reason,
                            backoff,
                            is_subagent=is_subagent_timeout,
                            subagent_attempt=subagent_retries if is_subagent_timeout else None,
                            max_subagent=max_subagent if is_subagent_timeout else None,
                        ):
                            self.stdout(line + "\n")

                        if backoff > 0:
                            self.sleeper(backoff)

                        reprep_rc, reprep_json = self.reprepare_for_transient_retry(
                            transient_try + 1, prev_step=armed_step
                        )
                        if reprep_rc == 2:
                            # Epic complete during transient abort
                            if os.environ.get("EPIC_CHAIN_ROADMAP") == "1":
                                advance_fn = getattr(self.context_port, "roadmap_advance", None)
                                if advance_fn:
                                    adv = advance_fn(self.config.project_root)
                                    self.stdout(format_roadmap_advance(adv, verbose=self.config.verbose) + "\n")
                                    if adv.get("complete"):
                                        self.stdout(format_loop_complete("roadmap queue") + "\n")
                                        return RunOutcome(action=RunAction.COMPLETE, exit_code=0, reason="roadmap_queue")
                                    if not (adv.get("ok") and adv.get("armed")):
                                        self.stderr("==> ERROR: roadmap-advance failed after transient EPIC_DONE\n")
                                        return RunOutcome(action=RunAction.HALT, exit_code=1, reason="roadmap_advance_failed")
                            resume_outer = True
                            break

                        if reprep_rc != 0:
                            resume_outer = True
                            break

                        # Re-prepare successful: refresh session execution variables
                        runtime_id = reprep_json.get("runtime") or runtime_name
                        runtime_extras = reprep_json.get("runtime_extras") or {}
                        session_model = reprep_json.get("model") or self.config.cli_model
                        loop_phase = reprep_json.get("loop_phase") or reprep_json.get("phase") or ""
                        armed_step = reprep_json.get("armed_step") or ""
                        model_source = reprep_json.get("model_source") or ""
                        fingerprint_before = reprep_json.get("fingerprint") or ""
                        prompt_file_str = reprep_json.get("prompt_file") or ""
                        prompt_file = Path(prompt_file_str) if prompt_file_str else self.config.state_dir / "prompt.txt"

                        if not session_model:
                            self.stderr(
                                "==> HALT: model_required: pass --model or set PROJECT_LOOP_<PHASE>_MODEL (silent default forbidden)\n"
                            )
                            return RunOutcome(action=RunAction.HALT, exit_code=2, reason="model_required")

                        continue

                    if retryable:
                        for line in format_transient_cap_reached(reason):
                            self.stderr(line + "\n")
                        resume_outer = True
                        break

                    outcome = rec.get("outcome")
                    if outcome == "permanent_failure" or reason.startswith("model_substitution"):
                        self.stderr(f"==> reason: {reason}\\n")
                        if reason.startswith("model_substitution"):
                            self.stderr("==> HALT: model/config fail-closed (no silent downgrade)\n")
                            self.stderr(
                                "==> fix: allow requested model in org/OmniRoute, or unset PROJECT_LOOP_<PHASE>_MODEL / pass a reachable CLI MODEL\n"
                            )
                        elif reason == "command not found":
                            self.stderr("==> HALT: runtime binary missing (fail-closed)\n")
                            self.stderr("==> fix: install runtime CLI or set CODEX_BIN / CLAUDE_PATH / DSH_PATH\n")
                        else:
                            self.stderr("==> HALT: permanent session failure (fail-closed)\n")
                        return RunOutcome(action=RunAction.HALT, exit_code=1, reason=reason)

                    self.stderr("==> SESSION ABORTED (non-retryable) — resuming outer loop\n")
                    self.stderr(format_abort_diagnostic(rec.get("reason"), rec.get("abort_kind")) + "\n")
                    resume_outer = True
                    break

                if resume_outer:
                    continue

                # 5. Check after session execution
                after_json = self.context_port.check_after(
                    self.config.project_root, fingerprint_before=fingerprint_before
                )
                self.stdout(format_check_after_summary(after_json, verbose=self.config.verbose) + "\n")

                after_action = decide_after_action(dict(after_json))
                ep_id = after_json.get("episode_id", "") if isinstance(after_json, dict) else ""
                self.incident_tracker.record_trace(
                    self.config.project_root,
                    phase="decide",
                    action="decide_after_action",
                    decide=after_action,
                    episode_id=ep_id,
                    detail=after_json,
                )

                # 6. Action transition handling
                if after_action == "continue":
                    if after_json.get("retry_fingerprint_stall"):
                        self.stderr("==> WARN: fingerprint stall — spawning next session (autonomy retry)\n")
                        self.sleeper(2)
                    continue

                if after_action == "halt":
                    if self.incident_tracker.attempt_tier1(self.config.project_root):
                        self.stdout("==> TIER1 session succeeded; retrying outer loop\n")
                        continue

                    after_stop = after_json.get("stop", "")
                    after_reason = after_json.get("reason", "")
                    if after_stop.startswith("NEED_HUMAN") or after_stop.startswith("need_human"):
                        self.stderr(f"==> HALT: need_human — {after_stop}\n")
                    elif after_stop:
                        self.stderr(f"==> HALT: {after_stop}\n")
                    elif after_reason:
                        self.stderr(f"==> HALT: {after_reason}\n")
                    else:
                        self.stderr("==> HALT: check-after fail-closed\n")
                    return RunOutcome(
                        action=RunAction.HALT,
                        exit_code=1,
                        reason=after_stop or after_reason or "check_after_halt",
                    )

                if after_action == "complete":
                    # Check session boundary
                    checkpoint_file = self.config.project_root / "runtime/dev-hub/epic/checkpoint.json"
                    if checkpoint_file.is_file():
                        try:
                            chk = json.loads(checkpoint_file.read_text())
                            if chk.get("session_boundary") in (True, "True", "true"):
                                self.stdout("==> SESSION_BOUNDARY: step finalized with session_boundary gate\n")
                        except Exception:
                            pass

                    if os.environ.get("EPIC_CHAIN_ROADMAP") == "1":
                        advance_fn = getattr(self.context_port, "roadmap_advance", None)
                        if advance_fn:
                            adv = advance_fn(self.config.project_root)
                            self.stdout(format_roadmap_advance(adv, verbose=self.config.verbose) + "\n")
                            if adv.get("ok") and adv.get("armed"):
                                continue
                            if adv.get("complete"):
                                self.stdout(format_loop_complete("roadmap queue") + "\n")
                                return RunOutcome(action=RunAction.COMPLETE, exit_code=0, reason="roadmap_queue")
                            self.stderr("==> ERROR: roadmap-advance failed (rc=1)\n")
                            return RunOutcome(action=RunAction.HALT, exit_code=1, reason="roadmap_advance_failed")

                    fanout_fn = getattr(self.context_port, "dag_fanout", None)
                    if fanout_fn:
                        fanout = fanout_fn(self.config.project_root)
                        self.stdout(format_dag_fanout(fanout, verbose=self.config.verbose) + "\n")
                        if fanout.get("complete"):
                            self.stdout(format_loop_complete("DAG journey") + "\n")
                            return RunOutcome(action=RunAction.COMPLETE, exit_code=0, reason="dag_journey")
                        if fanout.get("ok"):
                            continue
                        self.stderr("==> WARN: DAG fanout failed — retrying outer loop\n")
                        self.sleeper(20)
                        continue

                    self.stdout(format_loop_complete("complete") + "\n")
                    return RunOutcome(action=RunAction.COMPLETE, exit_code=0, reason="complete")


__all__ = [
    "ContextLoopPort",
    "IncidentTracker",
    "LoopRunner",
]
