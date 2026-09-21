from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class CursorStatus(StrEnum):
    ACTIVE = "active"
    RETRY = "retry"
    HALTED = "halted"
    COMPLETE = "complete"


STATE_SCHEMA = "loop-state/v2"


@dataclass(frozen=True)
class FailureRecord:
    category: str
    code: str
    message: str
    retryable: bool
    attempt: int
    recorded_at: str = field(default_factory=utc_now)
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FailureRecord":
        return cls(
            category=str(payload.get("category") or "unknown"),
            code=str(payload.get("code") or "unknown"),
            message=str(payload.get("message") or ""),
            retryable=bool(payload.get("retryable")),
            attempt=int(payload.get("attempt") or 0),
            recorded_at=str(payload.get("recorded_at") or utc_now()),
            details=dict(payload.get("details") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "attempt": self.attempt,
            "recorded_at": self.recorded_at,
            "details": self.details,
        }


@dataclass
class Cursor:
    schema: str = STATE_SCHEMA
    revision: int = 0
    epic_id: str = ""
    role: str = "back"
    phase: str = ""
    step_id: str = ""
    phase_epoch: int = 0
    status: CursorStatus = CursorStatus.ACTIVE
    attempt: int = 0
    session_id: str = ""
    failure: FailureRecord | None = None
    updated_at: str = field(default_factory=utc_now)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Cursor":
        schema = str(payload.get("schema") or "")
        if schema != STATE_SCHEMA:
            raise ValueError(f"unsupported cursor schema: {schema or '<missing>'}; migrate state explicitly")
        if "last_error" in payload:
            raise ValueError("legacy cursor field last_error is not accepted by loop-state/v2")
        status = str(payload.get("status") or CursorStatus.ACTIVE.value)
        try:
            status_value = CursorStatus(status)
        except ValueError as exc:
            raise ValueError(f"invalid cursor status: {status!r}") from exc
        return cls(
            schema=schema,
            revision=int(payload.get("revision") or 0),
            epic_id=str(payload.get("epic_id") or ""),
            role=str(payload.get("role") or "back"),
            phase=str(payload.get("phase") or ""),
            step_id=str(payload.get("step_id") or ""),
            phase_epoch=int(payload.get("phase_epoch") or 0),
            status=status_value,
            attempt=int(payload.get("attempt") or 0),
            session_id=str(payload.get("session_id") or ""),
            failure=(FailureRecord.from_dict(payload["failure"]) if isinstance(payload.get("failure"), dict) else None),
            updated_at=str(payload.get("updated_at") or utc_now()),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "revision": self.revision,
            "epic_id": self.epic_id,
            "role": self.role,
            "phase": self.phase,
            "step_id": self.step_id,
            "phase_epoch": self.phase_epoch,
            "status": self.status.value,
            "attempt": self.attempt,
            "session_id": self.session_id,
            "failure": self.failure.to_dict() if self.failure else None,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class Transition:
    event: str
    reason: str
    phase: str
    step_id: str
    status: CursorStatus
    attempt: int
    changed: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    revision: int = 0
    tx_id: str | None = None


@dataclass(frozen=True)
class RuntimeResult:
    runtime: str
    exit_code: int
    log_path: Path
    message: str | None = None
    timed_out: bool = False
    interrupted: bool = False
    idle_timed_out: bool = False
    collaboration_wait_timed_out: bool = False
    elapsed_sec: float = 0.0
    heartbeat_count: int = 0

    @property
    def hung(self) -> bool:
        """Whether the runtime was stopped by an inactivity watchdog."""
        return self.idle_timed_out or self.collaboration_wait_timed_out

    @property
    def ok(self) -> bool:
        return (
            self.exit_code == 0
            and not self.timed_out
            and not self.hung
            and not self.interrupted
        )
