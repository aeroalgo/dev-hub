"""Runtime-neutral lifecycle for managed gate subagents.

Claude Code calls this lifecycle through its native SubagentStart/SubagentStop
hooks.  Runtimes without those callbacks (currently Codex native
``multi_agent``) feed normalized spawn/wait items into the same object.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
from typing import Any, NamedTuple

from loop.gate_identity import GateIdentity
from loop.runtime_adapters.agent_contract import get_agent_contract_adapter


_AGENT_TYPE_RE = re.compile(
    r"(?im)^\s*(?:agent_type|subagent_type)\s*[:=]\s*([a-z0-9_-]+)"
)
_AT_AGENT_RE = re.compile(r"@([a-z][a-z0-9_-]+)", re.IGNORECASE)
_REVIEWER_ALIASES = {"reviewer", "verify-qa"}
_IMPLEMENT_ALIASES = {"verify", "verify-implement"}
_BUGFIX_ALIASES = {"verify-bugfix"}
_ANALYZE_ALIASES = {"analyze-verify"}
_STEP_ID_RE = re.compile(r"^[sera]\d{2}$", re.IGNORECASE)


class PendingSubagent(NamedTuple):
    agent_type: str
    spawn_tool_use_id: str | None = None
    identity: GateIdentity | None = None


def rewrite_spawn_prompt(
    prompt: str | None,
    identity: GateIdentity | dict[str, Any] | None = None,
) -> str:
    """Prepend GATE_IDENTITY SoT block to prompt if not already present.

    Used for pending-bind / telemetry and PreToolUse-equivalent rewrite of an
    in-memory spawn item. Live Codex child delivery happens via
    ``spawn_validate.ensure_gate_identity_prompt`` → PreToolUse ``updatedInput``
    (stream_filter observe alone is not a delivery channel).
    """
    if identity is None:
        return str(prompt or "")
    raw = str(prompt or "").strip()
    if "GATE_IDENTITY session_id=" in raw:
        return str(prompt or "")
    inject = GateIdentity.inject_text(identity)
    if not raw:
        return inject
    return inject + "\n" + raw


@dataclass(frozen=True)
class SubagentCompletion:
    """A normalized completed managed child."""

    agent_type: str
    message: str
    verdict: str
    tool_use_id: str | None = None
    thread_id: str | None = None
    spawn_tool_use_id: str | None = None


@dataclass(frozen=True)
class LifecycleAction:
    """Result of applying one normalized child completion."""

    agent_type: str
    verdict: str
    start_exit_code: int
    stop_exit_code: int
    finish: dict[str, Any] | None = None
    stderr: str = ""


def normalize_agent_type(raw: str | None) -> str | None:
    token = str(raw or "").strip().lower()
    if not token:
        return None
    return {
        "verify": "verify-implement",
        "reviewer": "verify-qa",
        "explore": "explorer",
    }.get(token, token)


def infer_agent_type(
    prompt: str | None,
    message: str | None = None,
    *,
    fence: Any = None,
) -> str | None:
    """Infer the managed child only from transport metadata or valid evidence."""
    if fence is not None:
        agent = normalize_agent_type(getattr(fence, "agent_id", None))
        if agent:
            return agent
    text = f"{prompt or ''}\n{message or ''}"
    match = _AGENT_TYPE_RE.search(text)
    if match:
        return normalize_agent_type(match.group(1))
    for match in _AT_AGENT_RE.finditer(prompt or ""):
        agent = normalize_agent_type(match.group(1))
        if agent:
            return agent
    prompt_text = prompt or ""
    if re.search(r"(?i)gate-repair", prompt_text):
        return "gate-repair"
    if re.search(r"(?im)^\s*BLOCKERS:\s*$", prompt_text) and re.search(
        r"(?im)^\s*ALLOW\s+WRITE:\s*$", prompt_text
    ):
        return "gate-repair"
    if re.search(r"(?i)\b(?:BACK\s+)?QA\b|\bQA\s+review\b|\breview\b", prompt_text):
        return "verify-qa"
    if re.search(r"(?i)verify-bugfix|BUGFIX\s+review", prompt_text):
        return "verify-bugfix"
    if re.search(r"(?i)verify-implement|IMPLEMENT\s+review", prompt_text):
        return "verify-implement"
    return None


def _hook_environment(runtime_id: str, session_id: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["EPIC_LOOP"] = "1"
    env["EPIC_RUNTIME"] = runtime_id
    env.setdefault("EPIC_RUNTIME_RESOLVED", runtime_id)
    sid = str(session_id or "").strip() or str(env.get("EPIC_RUNNER_SESSION_ID") or "").strip()
    if sid:
        env["EPIC_RUNNER_SESSION_ID"] = sid
    return env


def _hook_path(name: str) -> Path:
    return Path(__file__).resolve().parents[2] / "harness" / "hooks" / name


def _run_hook(
    name: str,
    payload: dict[str, Any],
    *,
    cwd: str | Path,
    runtime_id: str,
    session_id: str | None = None,
) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(_hook_path(name))],
        input=json.dumps(payload, ensure_ascii=False),
        cwd=str(cwd),
        env=_hook_environment(runtime_id, session_id=session_id),
        capture_output=True,
        text=True,
        check=False,
    )
    stderr = result.stderr or ""
    # Never write hook diagnostics into a JSONL pipe; callers surface them
    # on the human-readable console stream instead.
    return result.returncode, stderr


def _record_agent_key(agent_type: str) -> str:
    return "reviewer" if agent_type in _REVIEWER_ALIASES else agent_type


def _verifier_identity_key(
    cwd: str | Path,
    session_id: str,
    completion: SubagentCompletion,
) -> str:
    try:
        from harness.hooks._lib import current_gate_identity

        identity = current_gate_identity(str(cwd), session_id)
        sid = str(identity.get("session_id") or session_id or "nosession").strip()
        step = str(identity.get("step") or "").strip()
        epoch = str(identity.get("phase_epoch") or "").strip()
        role = str(identity.get("role") or "").strip()
    except Exception:
        sid = str(session_id or "nosession").strip()
        step = ""
        epoch = ""
        role = ""
    agent = _record_agent_key(completion.agent_type)
    verdict = str(completion.verdict).upper()
    return f"{sid}:{role}:{step}:{epoch}:{agent}:{verdict}"


def _already_processed(cwd: str | Path, session_id: str, completion: SubagentCompletion) -> bool:
    """Prevent the end-of-session fallback from replaying a live completion."""
    if not session_id:
        return False
    try:
        from harness.hooks._lib import load_state, verdict_dedupe_key

        state = load_state(session_id, str(cwd))
        seen = state.get("verdict_recorded_agents") or []
        agent_key = _record_agent_key(completion.agent_type)

        if completion.tool_use_id:
            key_tool = verdict_dedupe_key(
                session_id,
                agent_key,
                tool_use_id=completion.tool_use_id,
                verdict=completion.verdict,
            )
            if key_tool in seen:
                return True

        key_ident = verdict_dedupe_key(
            session_id,
            agent_key,
            verdict=completion.verdict,
        )
        if key_ident in seen:
            return True

        if state.get(f"{agent_key}_done") and str(state.get(f"{agent_key}_verdict") or "").upper() == str(completion.verdict).upper():
            return True

        return False
    except Exception:
        return False


def _finish_tool_matches(
    state: dict[str, Any],
    *,
    prefix: str,
) -> bool:
    finish = state.get("last_finish_tool")
    if not isinstance(finish, dict):
        return False
    name = str(finish.get("name") or "")
    if not name.startswith(prefix):
        return False
    finish_run = str(finish.get("phase_run_id") or "").strip()
    current_run = str(state.get("phase_run_id") or "").strip()
    if finish_run and current_run and finish_run != current_run:
        return False
    return True


def _result_dump(result: Any) -> dict[str, Any]:
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if isinstance(result, dict):
        return result
    return {"ok": False, "diagnostic_codes": ["auto_finish_invalid_result"]}


def gate_atomic_finish(
    cwd: str | Path,
    *,
    agent_type: str,
    verdict: str,
    session_id: str,
) -> dict[str, Any] | None:
    """Atomically mb-finish after a valid gate PASS (IMPLEMENT / BUGFIX / QA / ANALYZE).

    Shared by Claude SubagentStop and Codex SubagentLifecycle. Artifact must
    already be on disk before verify is spawned; verify PASS is the finish
    boundary. FAIL / demoted PASS does not finish.

    AUDIT has no verify_agent — finish is parent-driven via ``mb-finish audit``;
    prompts enforce stop-after ``ok: true`` (no subagent PASS trigger).
    """
    _ = session_id
    norm = str(agent_type or "").strip().lower()
    if str(verdict).upper() != "PASS":
        return None
    if norm not in (
        _REVIEWER_ALIASES | _IMPLEMENT_ALIASES | _BUGFIX_ALIASES | _ANALYZE_ALIASES
    ):
        return None

    try:
        from harness.hooks.epic.core import load_epic_state
        from loop.mb_finish.schemas import MbFinishRequest

        state = load_epic_state(cwd)
        if not state.get("active"):
            return None

        # Demoted PASS must never finish even if the local stop variable was
        # briefly promoted (scope heuristic) before mirror re-coerced FAIL.
        receipt = state.get("last_verify_receipt") or state.get("last_verify_evidence") or {}
        state_verdict = str(state.get("last_verify_verdict") or "").upper()
        if (
            isinstance(receipt, dict)
            and receipt.get("demoted_from_pass")
            and state_verdict != "PASS"
        ):
            try:
                from harness.hooks.epic.core import verify_pass_step_blockers

                armed = str(state.get("armed_step") or "").strip() or None
                live = verify_pass_step_blockers(cwd, step_id=armed)
                can_recheck = bool(
                    armed and str(state.get("armed_decompose") or "").strip()
                )
            except Exception:
                live = []
                can_recheck = False
            if can_recheck and not live:
                return {
                    "ok": False,
                    "diagnostic_codes": ["verify_demoted_stale"],
                    "error": (
                        "prior demoted verify PASS is stale; "
                        "re-run @verify for a fresh autonomous PASS before finish"
                    ),
                }
            detail_src = live or list(receipt.get("demote_blockers") or [])
            detail = "; ".join(str(b) for b in detail_src) or "step incomplete"
            return {
                "ok": False,
                "diagnostic_codes": ["verify_demoted_pass"],
                "error": (
                    "demoted verify PASS cannot auto-finish; "
                    f"{detail}; fix implement shard and re-verify"
                ),
            }

        if norm in _REVIEWER_ALIASES:
            phase = str(state.get("phase") or state.get("armed_step") or "").upper()
            if phase != "QA":
                return None
            if _finish_tool_matches(state, prefix="mb-finish qa"):
                return {"ok": True, "already_finished": True}
            from loop.mb_finish.impl import finish_qa

            result = finish_qa(
                MbFinishRequest(
                    phase="QA",
                    step_id="QA",
                    done_summary="verify-qa PASS; QA finished by shared gate lifecycle",
                    cwd=str(cwd),
                )
            )
            return _result_dump(result)

        if norm in _ANALYZE_ALIASES:
            phase = str(state.get("phase") or state.get("armed_step") or "").upper()
            if phase != "ANALYZE":
                return None
            if _finish_tool_matches(state, prefix="mb-finish analyze"):
                return {"ok": True, "already_finished": True}
            if str(state.get("last_verify_verdict") or "").upper() != "PASS":
                return {
                    "ok": False,
                    "diagnostic_codes": ["verify_pass_missing"],
                    "error": "analyze-verify PASS required before auto analyze finish",
                }
            from loop.mb_finish.impl import finish_analyze

            result = finish_analyze(
                MbFinishRequest(
                    phase="ANALYZE",
                    step_id="ANALYZE",
                    done_summary=(
                        "analyze-verify PASS; ANALYZE finished by shared gate lifecycle"
                    ),
                    cwd=str(cwd),
                )
            )
            return _result_dump(result)

        if norm in _BUGFIX_ALIASES:
            phase = str(state.get("phase") or state.get("armed_step") or "").upper()
            if phase != "BUGFIX":
                return None
            if _finish_tool_matches(state, prefix="mb-finish bugfix"):
                return {"ok": True, "already_finished": True}
            if str(state.get("last_verify_verdict") or "").upper() != "PASS":
                return {
                    "ok": False,
                    "diagnostic_codes": ["verify_pass_missing"],
                    "error": "verify PASS required before auto bugfix finish",
                }
            from loop.mb_finish.impl import finish_bugfix

            result = finish_bugfix(
                MbFinishRequest(
                    phase="BUGFIX",
                    step_id="BUGFIX",
                    done_summary="verify-bugfix PASS; BUGFIX finished by shared gate lifecycle",
                    cwd=str(cwd),
                )
            )
            return _result_dump(result)

        if _finish_tool_matches(state, prefix="mb-finish implement"):
            return {"ok": True, "already_finished": True}
        step_id = str(state.get("armed_step") or "").strip()
        if not _STEP_ID_RE.match(step_id):
            return {
                "ok": False,
                "diagnostic_codes": ["armed_step_missing"],
                "error": f"implement auto-finish requires armed sNN step, got {step_id!r}",
            }
        if str(state.get("last_verify_verdict") or "").upper() != "PASS":
            return {
                "ok": False,
                "diagnostic_codes": ["verify_pass_missing"],
                "error": "verify PASS required before auto implement finish",
            }
        from loop.mb_finish.finish_implement import finish_implement_step

        result = finish_implement_step(
            MbFinishRequest(
                phase="IMPLEMENT",
                step_id=step_id,
                done_summary=(
                    f"verify-implement PASS; {step_id} finished by shared gate lifecycle"
                ),
                cwd=str(cwd),
            )
        )
        return _result_dump(result)
    except Exception as exc:
        code = "auto_qa_finish_failed"
        if norm in _IMPLEMENT_ALIASES:
            code = "auto_implement_finish_failed"
        elif norm in _BUGFIX_ALIASES:
            code = "auto_bugfix_finish_failed"
        elif norm in _ANALYZE_ALIASES:
            code = "auto_analyze_finish_failed"
        return {"ok": False, "diagnostic_codes": [code], "error": str(exc)}


def auto_finish_after_gate(
    cwd: str | Path,
    *,
    agent_type: str,
    verdict: str,
    session_id: str,
) -> dict[str, Any] | None:
    """Alias for gate_atomic_finish (backward-compatible)."""
    return gate_atomic_finish(
        cwd,
        agent_type=agent_type,
        verdict=verdict,
        session_id=session_id,
    )


def _finish_status_from_stop(
    cwd: str | Path,
    *,
    agent_type: str,
    verdict: str,
    stop_rc: int,
    stop_err: str,
) -> dict[str, Any] | None:
    """Surface stop-hook auto-finish outcome without invoking finish a second time."""
    if str(verdict or "").upper() != "PASS":
        return None
    err = stop_err or ""
    if "automatic mb-finish completed" in err or "FINISH ok" in err:
        return {"ok": True}
    if "automatic mb-finish did not complete" in err:
        codes: list[str] = []
        match = re.search(r"did not complete:\s*([^\n(]+)", err)
        if match:
            codes = [part.strip() for part in match.group(1).split(",") if part.strip()]
        return {
            "ok": False,
            "diagnostic_codes": codes or ["auto_finish_failed"],
            "error": err.strip()[-300:] or "automatic mb-finish did not complete",
        }
    if stop_rc != 0:
        return None
    try:
        from harness.hooks.epic.core import load_epic_state

        state = load_epic_state(cwd)
    except Exception:
        return None
    prefixes = {
        "verify-implement": "mb-finish implement",
        "verify-bugfix": "mb-finish bugfix",
        "verify-qa": "mb-finish qa",
        "analyze-verify": "mb-finish analyze",
    }
    norm = normalize_agent_type(agent_type) or str(agent_type or "").strip().lower()
    prefix = prefixes.get(norm)
    if prefix and _finish_tool_matches(state, prefix=prefix):
        return {"ok": True, "already_finished": True}
    return None


class SubagentLifecycle:
    """Consume normalized collaboration items and invoke shared gate hooks."""

    def __init__(self, cwd: str | Path, session_id: str, runtime_id: str) -> None:
        self.cwd = str(cwd)
        self.session_id = str(session_id or "")
        self.runtime_id = runtime_id
        self._pending: dict[str, PendingSubagent] = {}
        self._completed: set[str] = set()
        self._lock = threading.Lock()

    def get_gate_identity(self) -> GateIdentity:
        try:
            from harness.hooks.epic.core import load_epic_state
            state = load_epic_state(self.cwd)
        except Exception:
            state = None
        return GateIdentity.expected(state, session_id=self.session_id)

    @property
    def pending_threads(self) -> dict[str, PendingSubagent]:
        with self._lock:
            return dict(self._pending)

    def get_pending_identity(self, thread_id: str) -> GateIdentity | None:
        with self._lock:
            pending = self._pending.get(str(thread_id).strip())
            if pending is not None:
                return pending.identity
            return None

    def _start_and_stop(self, completion: SubagentCompletion) -> LifecycleAction:
        start_payload = {
            "agent_type": completion.agent_type,
            "prompt": f"agent_type={completion.agent_type}",
            "cwd": self.cwd,
            "session_id": self.session_id,
            "runtime_id": self.runtime_id,
            "tool_use_id": completion.spawn_tool_use_id or completion.thread_id or "",
            "thread_id": completion.thread_id or "",
        }
        start_rc, start_err = _run_hook(
            "subagent-start.py",
            start_payload,
            cwd=self.cwd,
            runtime_id=self.runtime_id,
            session_id=self.session_id,
        )
        if start_rc != 0:
            return LifecycleAction(
                completion.agent_type,
                completion.verdict,
                start_rc,
                start_rc,
                stderr=start_err,
            )

        stop_payload = {
            "agent_type": completion.agent_type,
            "cwd": self.cwd,
            "session_id": self.session_id,
            "runtime_id": self.runtime_id,
            "tool_use_id": completion.tool_use_id or "",
            "thread_id": completion.thread_id or "",
            "last_assistant_message": completion.message,
            "verdict": completion.verdict,
        }
        stop_rc, stop_err = _run_hook(
            "subagent-stop.py",
            stop_payload,
            cwd=self.cwd,
            runtime_id=self.runtime_id,
            session_id=self.session_id,
        )
        # Claude parity: subagent-stop.py already runs gate_atomic_finish on PASS.
        # Do not call gate_atomic_finish again here — a second call races the
        # finish-boundary / parent turn and historically returned confusing
        # verify_pass_missing when the parent ignored stop and re-ran mb-finish.
        finish = _finish_status_from_stop(
            self.cwd,
            agent_type=completion.agent_type,
            verdict=completion.verdict,
            stop_rc=stop_rc,
            stop_err=stop_err,
        )
        return LifecycleAction(
            completion.agent_type,
            completion.verdict,
            start_rc,
            stop_rc,
            finish,
            stderr=stop_err or start_err,
        )

    def process_item(self, item: dict[str, Any]) -> list[LifecycleAction]:
        """Process one adapter-normalized ``spawn_agent``/``wait`` item."""
        with self._lock:
            return self._process_item(item)

    def _process_item(self, item: dict[str, Any]) -> list[LifecycleAction]:
        tool = str(item.get("tool") or "").strip()
        if tool == "spawn_agent":
            sot = self.get_gate_identity()
            prompt = str(item.get("prompt") or "")
            rewritten = rewrite_spawn_prompt(prompt, sot)
            if rewritten != prompt:
                item["prompt"] = rewritten
                prompt = rewritten
            hint = infer_agent_type(prompt)
            spawn_id = str(item.get("id") or "").strip() or None
            for thread_id in item.get("receiver_thread_ids") or []:
                thread = str(thread_id).strip()
                if thread:
                    self._pending[thread] = PendingSubagent(
                        agent_type=hint or "",
                        spawn_tool_use_id=spawn_id,
                        identity=sot,
                    )
            return []
        if tool != "wait":
            return []

        states = item.get("agents_states")
        if not isinstance(states, dict):
            return []
        actions: list[LifecycleAction] = []
        wait_id = str(item.get("id") or "").strip() or None
        for thread_id, state in states.items():
            if not isinstance(state, dict):
                continue
            if str(state.get("status") or "").lower() not in {"completed", "failed", "error", "closed"}:
                continue
            thread = str(thread_id).strip()
            message = str(state.get("message") or state.get("output") or state.get("result") or "")
            fence = get_agent_contract_adapter(self.runtime_id).parse_gate_verdict(message)
            if fence is None:
                continue
            pending = self._pending.get(thread, PendingSubagent("", None, None))
            agent_type = normalize_agent_type(pending.agent_type) or infer_agent_type(None, message, fence=fence)
            if not agent_type:
                continue
            completion = SubagentCompletion(
                agent_type=agent_type,
                message=message,
                verdict=str(fence.verdict).upper(),
                tool_use_id=wait_id,
                thread_id=thread,
                spawn_tool_use_id=pending.spawn_tool_use_id,
            )
            identity_key = _verifier_identity_key(self.cwd, self.session_id, completion)
            thread_dedupe = f"{thread}:{wait_id or ''}:{completion.verdict}"
            if (
                identity_key in self._completed
                or thread_dedupe in self._completed
                or _already_processed(self.cwd, self.session_id, completion)
            ):
                self._pending.pop(thread, None)
                continue
            self._completed.add(identity_key)
            self._completed.add(thread_dedupe)
            if completion.tool_use_id:
                self._completed.add(
                    f"{self.session_id}:{_record_agent_key(completion.agent_type)}:{completion.tool_use_id}"
                )
            actions.append(self._start_and_stop(completion))
            self._pending.pop(thread, None)
        return actions
