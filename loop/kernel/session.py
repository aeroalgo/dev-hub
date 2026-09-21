from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum

from .engine import LoopEngine, TransitionError
from .model import RuntimeResult, Transition
from .runtime import Runtime


class SessionOutcome(StrEnum):
    COMMITTED = "committed"
    STATE_CHANGED = "state_changed"
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
    """Owns session outcome classification and bounded retry policy."""

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
    def _state_changed(result: RuntimeResult | None, status: str, transition: Transition | None) -> SessionRun:
        return SessionRun(
            SessionOutcome.COMMITTED if status == "complete" else SessionOutcome.STATE_CHANGED,
            result,
            transition,
            "cursor advanced by another boundary",
            0 if status == "complete" else 1,
        )

    def run_step(self, prompt: str, *, model: str, project, session_id: str | None = None) -> SessionRun:
        for _ in range(self.max_attempts):
            cursor = self.engine.store.read()
            if cursor is None:
                raise TransitionError("cursor does not exist; run start first")
            if cursor.status.value == "complete":
                return SessionRun(SessionOutcome.COMMITTED, None, None, "already complete", 0)
            if cursor.status.value == "halted":
                return SessionRun(SessionOutcome.STATE_CHANGED, None, None, "cursor halted", 1)
            attempt_id = cursor.attempt + 1
            log_path = self.engine.store.session_log(
                f"{session_id or cursor.session_id}-{cursor.phase.lower()}-"
                f"{cursor.step_id.lower()}-attempt-{attempt_id}"
            )
            result = self.runtime.run(prompt, model=model, project=project, log_path=log_path, timeout=self.timeout)
            updated = self.engine.store.read()
            if updated is None:
                raise TransitionError("cursor disappeared after session")
            if updated.revision != cursor.revision:
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
                outcome = SessionOutcome.FINISH_NOT_COMMITTED
                reason = "finish_not_committed"
                code = "finish_not_committed"
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
            retry = self.engine.retry(
                reason,
                expected_revision=cursor.revision,
                details={"code": code, **self._details(result)},
            )
            if not retry.changed:
                return self._state_changed(result, retry.status.value, retry)
            if retry.attempt >= self.max_attempts:
                halted = self.engine.halt(
                    reason,
                    expected_revision=retry.revision,
                    details={"code": "retry_exhausted", **self._details(result)},
                    failure_category="session",
                    failure_code="retry_exhausted",
                )
                if not halted.changed:
                    return self._state_changed(result, halted.status.value, halted)
                return SessionRun(outcome, result, halted, reason, 1)
            if self.backoff:
                time.sleep(self.backoff * (2 ** max(0, retry.attempt - 1)))
        raise TransitionError("session supervisor exited without an outcome")


__all__ = ["SessionOutcome", "SessionRun", "SessionSupervisor"]
