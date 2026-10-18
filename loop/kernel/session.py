from __future__ import annotations

import re
import time
from dataclasses import dataclass
from enum import StrEnum

from .engine import LoopEngine, TransitionError
from .model import RuntimeResult, Transition
from .runtime import Runtime

_RATE_LIMIT_RE = re.compile(
    r"(?i)(?:\b429\b|too many requests|rate[_ ]?limit(?:ed|ing)?|resource[_ ]?exhausted)"
)


class SessionOutcome(StrEnum):
    COMMITTED = "committed"
    STATE_CHANGED = "state_changed"
    PROGRESS_CONTINUE = "progress_continue"
    STEP_RESTARTED = "step_restarted"
    SESSION_ROTATED = "session_rotated"
    USER_INTERRUPT = "user_interrupt"
    TIMEOUT = "timeout"
    RUNTIME_FAILURE = "runtime_failure"
    FINISH_NOT_COMMITTED = "finish_not_committed"


@dataclass(frozen=True)
class SessionRun:
    outcome: SessionOutcome
    result: RuntimeResult | None
    transition: Transition | None
    reason: str
    return_code: int


class SessionSupervisor:
    """Owns session outcome classification and bounded retry policy.

    HARD: one runtime process per GATE_IDENTITY. Soft retries mint a new
    session_id and return SESSION_ROTATED so the outer cli rebuilds the prompt
    and starts a new process. Never re-enter work under the same session_id.

    Provider rate limits (429) are non-retryable: halt immediately. Retrying
    only multiplies provider load while the quota window is still hot.
    """

    def __init__(self, engine: LoopEngine, runtime: Runtime, *, timeout: int, max_attempts: int, backoff: float):
        self.engine = engine
        self.runtime = runtime
        self.timeout = max(1, timeout)
        self.max_attempts = max(1, max_attempts)
        self.backoff = max(0.0, backoff)

    @staticmethod
    def _details(result: RuntimeResult) -> dict[str, object]:
        return {
            "runtime": result.runtime,
            "exit_code": result.exit_code,
            "log_path": str(result.log_path),
            "timed_out": result.timed_out,
            "idle_timed_out": result.idle_timed_out,
            "collaboration_wait_timed_out": result.collaboration_wait_timed_out,
            "hung": result.hung,
            "elapsed_sec": result.elapsed_sec,
            "heartbeat_count": result.heartbeat_count,
            "interrupted": result.interrupted,
            "message": result.message,
        }

    @staticmethod
    def _is_rate_limited(result: RuntimeResult) -> bool:
        message = result.message or ""
        if _RATE_LIMIT_RE.search(message):
            return True
        try:
            text = result.log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        # Bound scan: rate-limit errors land at the end of short/failed sessions.
        return bool(_RATE_LIMIT_RE.search(text[-8000:]))

    def _sleep_before_retry(self, *, attempt: int, step_restart: bool = False) -> None:
        if self.backoff <= 0:
            return
        # Session rotate: attempt * backoff. Step restart: longer cool-down so we
        # do not immediately burn another max_attempts burst against a hot provider.
        multiplier = max(1, attempt)
        if step_restart:
            multiplier = max(multiplier, self.max_attempts) * 2
        time.sleep(self.backoff * multiplier)

    @staticmethod
    def _state_changed(result: RuntimeResult | None, status: str, transition: Transition | None) -> SessionRun:
        return SessionRun(
            SessionOutcome.COMMITTED if status == "complete" else SessionOutcome.STATE_CHANGED,
            result,
            transition,
            "cursor advanced by another boundary",
            0 if status == "complete" else 1,
        )

    def run_step(self, prompt: str, *, model: str, project, session_id: str | None = None) -> SessionRun:
        cursor = self.engine.store.read()
        if cursor is None:
            raise TransitionError("cursor does not exist; run start first")
        if cursor.status.value == "complete":
            return SessionRun(SessionOutcome.COMMITTED, None, None, "already complete", 0)
        if cursor.status.value == "halted":
            return SessionRun(SessionOutcome.STATE_CHANGED, None, None, "cursor halted", 1)

        # Always bind the log to the live cursor session_id (never a frozen caller id).
        live_session = cursor.session_id
        if session_id and session_id != live_session:
            # Stale caller id is ignored; GATE_IDENTITY is cursor-owned.
            pass
        attempt_id = cursor.attempt + 1
        log_path = self.engine.store.session_log(
            f"{live_session}-{cursor.phase.lower()}-"
            f"{cursor.step_id.lower()}-attempt-{attempt_id}"
        )
        result = self.runtime.run(prompt, model=model, project=project, log_path=log_path, timeout=self.timeout)
        updated = self.engine.store.read()
        if updated is None:
            raise TransitionError("cursor disappeared after session")
        if updated.revision != cursor.revision:
            # Mid-session boundary already rotated/restarted the step — outer cli
            # must rebuild prompt under the new GATE_IDENTITY.
            if updated.session_id != live_session:
                return SessionRun(
                    SessionOutcome.SESSION_ROTATED
                    if updated.status.value != "halted"
                    else SessionOutcome.STATE_CHANGED,
                    result,
                    None,
                    "session_rotated_by_boundary",
                    0 if updated.status.value != "halted" else 1,
                )
            return self._state_changed(result, updated.status.value, None)
        if result.interrupted or result.exit_code in (130, 143):
            transition = self.engine.halt(
                "user_interrupt",
                expected_revision=cursor.revision,
                details=self._details(result),
                failure_category="session",
                failure_code="user_interrupt",
            )
            if not transition.changed:
                return self._state_changed(result, transition.status.value, transition)
            return SessionRun(SessionOutcome.USER_INTERRUPT, result, transition, "user_interrupt", 130)

        if result.ok:
            # Machine close: artifacts / validate-verdict stamp prove the phase is
            # done even when the agent exits with prose "готово" and skips finish.
            auto = self.engine.try_session_auto_finish(updated)
            if auto is not None and auto.changed:
                return SessionRun(
                    SessionOutcome.COMMITTED,
                    result,
                    auto,
                    auto.reason or "session-auto-finish",
                    0,
                )
            # BUGFIX canon: one open item per session is allowed. Exiting after a
            # partial queue close must continue the phase — not finish_not_committed
            # → retry_exhausted halt.
            if updated.phase == "BUGFIX" and self.engine._bugfix_has_open_items(updated):
                try:
                    rearm = self.engine.rearm_active(
                        reason="bugfix_items_remaining",
                        expected_revision=cursor.revision,
                    )
                except TransitionError:
                    rearm = None
                if rearm is not None and rearm.changed:
                    return SessionRun(
                        SessionOutcome.PROGRESS_CONTINUE,
                        result,
                        rearm,
                        "bugfix_items_remaining",
                        0,
                    )
            outcome = SessionOutcome.FINISH_NOT_COMMITTED
            reason = "finish_not_committed"
            code = "finish_not_committed"
            if updated.phase == "DECOMPOSE":
                from .index import decompose_yaml_problems

                problems = decompose_yaml_problems(
                    self.engine.paths.project, updated.role, updated.epic_id
                )
                if problems:
                    reason = "finish_not_committed: " + "; ".join(problems[:5])
                    code = "decompose_tree_invalid"
                else:
                    reason = (
                        "finish_not_committed: decompose tree parses but verify-decompose "
                        "PASS was not accepted / finish did not advance to ANALYZE — "
                        "FORBIDDEN claim DECOMPOSE done; fix gate rejection and re-finish"
                    )
        elif result.timed_out or result.hung:
            outcome = SessionOutcome.TIMEOUT
            if result.idle_timed_out:
                reason = "session_idle_timeout"
                code = "session_idle_timeout"
            elif result.collaboration_wait_timed_out:
                reason = "collaboration_wait_timeout"
                code = "collaboration_wait_timeout"
            else:
                reason = "session_timeout"
                code = "session_timeout"
        else:
            outcome = SessionOutcome.RUNTIME_FAILURE
            reason = f"runtime_exit_{result.exit_code}"
            code = "runtime_exit"
        if result.message:
            reason = f"{reason}: {result.message}"

        # Provider quota is not fixed by minting new sessions — halt fail-closed.
        if outcome != SessionOutcome.FINISH_NOT_COMMITTED and self._is_rate_limited(result):
            halt_reason = f"provider_rate_limited:{code}:{reason}"
            transition = self.engine.halt(
                halt_reason,
                expected_revision=cursor.revision,
                details={"code": "provider_rate_limited", "trigger": "rate_limit", **self._details(result)},
                failure_category="session",
                failure_code="provider_rate_limited",
            )
            if not transition.changed:
                return self._state_changed(result, transition.status.value, transition)
            return SessionRun(
                SessionOutcome.RUNTIME_FAILURE,
                result,
                transition,
                halt_reason,
                1,
            )

        # Soft retry = new session_id + return to outer cli (new process + new prompt).
        # Never re-invoke runtime under the same GATE_IDENTITY in this call.
        retry = self.engine.retry(
            reason,
            expected_revision=cursor.revision,
            details={"code": code, **self._details(result)},
        )
        if not retry.changed:
            return self._state_changed(result, retry.status.value, retry)
        if retry.attempt >= self.max_attempts:
            restarted = self.engine.restart_step(
                f"session_attempts_exhausted:{code}:{reason}",
                expected_revision=retry.revision,
                details={"code": code, "trigger": "session_attempts_exhausted", **self._details(result)},
            )
            if not restarted.changed:
                return self._state_changed(result, restarted.status.value, restarted)
            if restarted.status.value == "halted":
                return SessionRun(outcome, result, restarted, restarted.reason, 1)
            self._sleep_before_retry(attempt=max(1, retry.attempt), step_restart=True)
            return SessionRun(
                SessionOutcome.STEP_RESTARTED,
                result,
                restarted,
                restarted.reason or "step_restarted",
                0,
            )
        self._sleep_before_retry(attempt=max(1, retry.attempt), step_restart=False)
        return SessionRun(
            SessionOutcome.SESSION_ROTATED,
            result,
            retry,
            f"session_rotated:{reason}",
            0,
        )


__all__ = ["SessionOutcome", "SessionRun", "SessionSupervisor"]
