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


@dataclass
class Cursor:
    schema: str = "loop-cursor/v1"
    revision: int = 0
    epic_id: str = ""
    role: str = "back"
    phase: str = ""
    step_id: str = ""
    status: CursorStatus = CursorStatus.ACTIVE
    attempt: int = 0
    session_id: str = ""
    last_error: str | None = None
    updated_at: str = field(default_factory=utc_now)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Cursor":
        status = str(payload.get("status") or CursorStatus.ACTIVE.value)
        try:
            status_value = CursorStatus(status)
        except ValueError as exc:
            raise ValueError(f"invalid cursor status: {status!r}") from exc
        return cls(
            schema=str(payload.get("schema") or "loop-cursor/v1"),
            revision=int(payload.get("revision") or 0),
            epic_id=str(payload.get("epic_id") or ""),
            role=str(payload.get("role") or "back"),
            phase=str(payload.get("phase") or ""),
            step_id=str(payload.get("step_id") or ""),
            status=status_value,
            attempt=int(payload.get("attempt") or 0),
            session_id=str(payload.get("session_id") or ""),
            last_error=(str(payload["last_error"]) if payload.get("last_error") else None),
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
            "status": self.status.value,
            "attempt": self.attempt,
            "session_id": self.session_id,
            "last_error": self.last_error,
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


@dataclass(frozen=True)
class RuntimeResult:
    runtime: str
    exit_code: int
    log_path: Path
    timed_out: bool = False
    interrupted: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.interrupted

