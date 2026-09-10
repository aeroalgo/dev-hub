"""Telemetry companion schema, aggregation counters, and session companion records."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import time
from typing import Any, Sequence

from loop.lifecycle import (
    LEGACY_UNKNOWN,
    InvocationKey,
    InvocationRecord,
    InvocationState,
    InvocationStatusView,
    LegacyMarkerResult,
    migrate_legacy_marker,
)

SCHEMA_TELEMETRY_COMPANION = "session-telemetry-companion/v1"


@dataclass(frozen=True)
class SessionTelemetryCompanion:
    """Structured companion JSONL record capturing machine-readable telemetry for a session."""

    invocation_id: str
    session_id: str
    invocation_key: str
    role: str
    step: str
    phase: str
    owner: str
    state: str
    is_root: bool = True
    terminal_state: str | None = None
    terminal_reason: str | None = None
    first_action_taken: bool = False
    first_action_at: float | None = None
    retry_chain_id: str | None = None
    retry_count: int = 0
    epoch: int = 0
    tool_actions_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    closed_at: float | None = None
    duration_sec: float | None = None
    lease_expires_at: float | None = None
    last_heartbeat_at: float | None = None
    diagnostic_code: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_TELEMETRY_COMPANION

    def __post_init__(self) -> None:
        if not isinstance(self.invocation_id, str) or not self.invocation_id.strip():
            raise ValueError("invocation_id must be a non-empty string")
        if not isinstance(self.session_id, str) or not self.session_id.strip():
            raise ValueError("session_id must be a non-empty string")
        if not self.first_action_taken and self.first_action_at is not None:
            raise ValueError("first_action_at must be None when first_action_taken is False")
        if not self.first_action_taken and self.tool_actions_count > 0:
            raise ValueError("tool_actions_count must be 0 when first_action_taken is False")
        if self.first_action_taken and (self.first_action_at is None or self.tool_actions_count == 0):
            raise ValueError("first_action_taken=True requires non-None first_action_at and tool_actions_count > 0")

    @property
    def is_terminal(self) -> bool:
        if self.terminal_state is not None:
            return True
        try:
            return InvocationState(self.state).is_terminal
        except ValueError:
            return False

    @property
    def is_zero_action(self) -> bool:
        return not self.first_action_taken and self.first_action_at is None and self.tool_actions_count == 0

    @property
    def timestamps(self) -> dict[str, float | None]:
        return {
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "first_action_at": self.first_action_at,
            "closed_at": self.closed_at,
            "lease_expires_at": self.lease_expires_at,
            "last_heartbeat_at": self.last_heartbeat_at,
        }

    @property
    def retry_relation(self) -> dict[str, Any]:
        return {
            "retry_chain_id": self.retry_chain_id,
            "retry_count": self.retry_count,
            "epoch": self.epoch,
            "is_retry": bool(self.retry_count > 0 or self.epoch > 0 or self.retry_chain_id),
        }

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["timestamps"] = self.timestamps
        d["is_terminal"] = self.is_terminal
        d["is_zero_action"] = self.is_zero_action
        d["retry_relation"] = self.retry_relation
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def to_jsonl_line(self) -> str:
        return self.to_json() + "\n"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionTelemetryCompanion:
        cleaned = dict(data)
        cleaned.pop("timestamps", None)
        cleaned.pop("is_terminal", None)
        cleaned.pop("is_zero_action", None)
        retry_relation = cleaned.pop("retry_relation", None)
        if isinstance(retry_relation, dict):
            for field_name in ("retry_chain_id", "retry_count", "epoch"):
                if field_name in retry_relation:
                    cleaned[field_name] = retry_relation[field_name]
        if "schema" in cleaned and "schema_version" not in cleaned:
            cleaned["schema_version"] = cleaned.pop("schema")
        return cls(**cleaned)

    @classmethod
    def from_json(cls, json_str: str) -> SessionTelemetryCompanion:
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_invocation_record(
        cls,
        record: InvocationRecord,
        *,
        is_root: bool = True,
        retry_chain_id: str | None = None,
        tool_actions_count: int = 0,
        closed_at: float | None = None,
        diagnostic_code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionTelemetryCompanion:
        key = record.key
        duration = None
        close_ts = closed_at
        if record.is_terminal:
            if close_ts is None:
                close_ts = record.updated_at
            duration = max(0.0, close_ts - record.created_at)

        terminal_state = record.state.value if record.is_terminal else None
        terminal_reason = record.reason if record.is_terminal else None

        action_taken = bool(record.first_action_taken or tool_actions_count > 0 or record.first_action_at is not None)
        effective_action_at = record.first_action_at if action_taken else None
        effective_action_count = tool_actions_count if action_taken else 0
        if action_taken:
            if effective_action_count == 0:
                effective_action_count = 1
            if effective_action_at is None:
                effective_action_at = record.updated_at

        return cls(
            invocation_id=record.invocation_id,
            session_id=key.session,
            invocation_key=key.key,
            role=key.role,
            step=key.step,
            phase=key.phase,
            owner=record.owner,
            state=record.state.value,
            is_root=is_root,
            terminal_state=terminal_state,
            terminal_reason=terminal_reason,
            first_action_taken=action_taken,
            first_action_at=effective_action_at,
            retry_chain_id=retry_chain_id,
            retry_count=key.epoch,
            epoch=key.epoch,
            tool_actions_count=effective_action_count,
            created_at=record.created_at,
            updated_at=record.updated_at,
            closed_at=close_ts,
            duration_sec=duration,
            lease_expires_at=record.lease_expires_at,
            last_heartbeat_at=record.last_heartbeat_at,
            diagnostic_code=diagnostic_code,
            metadata=dict(metadata or {}),
        )


def append_companion_record(file_path: str | Path, record: SessionTelemetryCompanion) -> None:
    """Append a companion telemetry record to a JSONL file."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(record.to_jsonl_line())


def write_companion_records(file_path: str | Path, records: Sequence[SessionTelemetryCompanion]) -> None:
    """Write a sequence of companion telemetry records to a JSONL file."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(r.to_jsonl_line())


def read_companion_records(file_path: str | Path) -> list[SessionTelemetryCompanion]:
    """Read companion telemetry records from a JSONL file."""
    path = Path(file_path)
    if not path.exists():
        return []
    records: list[SessionTelemetryCompanion] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(SessionTelemetryCompanion.from_json(line))
    return records


@dataclass
class TelemetryAggregator:
    """Aggregates metrics: duplicate-suppressed, terminal-by-cause, zero-action sessions, retry chains."""

    total_sessions: int = 0
    root_sessions: int = 0
    subagent_sessions: int = 0
    duplicate_suppressed: int = 0
    zero_action_sessions: int = 0
    legacy_unknown_count: int = 0
    terminal_by_cause: dict[str, int] = field(default_factory=dict)
    terminal_by_state: dict[str, int] = field(default_factory=dict)
    retry_chains: dict[str, list[str]] = field(default_factory=dict)
    sessions: list[SessionTelemetryCompanion] = field(default_factory=list)

    @property
    def duplicate_suppressed_count(self) -> int:
        return self.duplicate_suppressed

    def record_session(self, companion: SessionTelemetryCompanion) -> None:
        """Record a session companion record and update aggregate metrics."""
        self.sessions.append(companion)
        self.total_sessions += 1

        if companion.is_root:
            self.root_sessions += 1
        else:
            self.subagent_sessions += 1

        if companion.is_zero_action:
            self.zero_action_sessions += 1

        if companion.state:
            self.terminal_by_state[companion.state] = self.terminal_by_state.get(companion.state, 0) + 1

        if companion.terminal_reason:
            cause = companion.terminal_reason
            self.terminal_by_cause[cause] = self.terminal_by_cause.get(cause, 0) + 1
        elif companion.terminal_state:
            cause = companion.terminal_state
            self.terminal_by_cause[cause] = self.terminal_by_cause.get(cause, 0) + 1

        if companion.retry_chain_id:
            if companion.retry_chain_id not in self.retry_chains:
                self.retry_chains[companion.retry_chain_id] = []
            self.retry_chains[companion.retry_chain_id].append(companion.invocation_id)

    def record_invocation(
        self,
        record: InvocationRecord,
        *,
        is_root: bool = True,
        retry_chain_id: str | None = None,
        tool_actions_count: int = 0,
        closed_at: float | None = None,
    ) -> SessionTelemetryCompanion:
        """Create and record companion from an InvocationRecord."""
        companion = SessionTelemetryCompanion.from_invocation_record(
            record,
            is_root=is_root,
            retry_chain_id=retry_chain_id,
            tool_actions_count=tool_actions_count,
            closed_at=closed_at,
        )
        self.record_session(companion)
        return companion

    def record_duplicate_suppressed(self, key_or_id: str | InvocationKey | None = None, count: int = 1) -> None:
        """Record duplicate requests suppressed by idempotency."""
        self.duplicate_suppressed += count

    def record_legacy_marker(self, marker_res: LegacyMarkerResult | None = None) -> None:
        """Record a migrated legacy marker."""
        self.legacy_unknown_count += 1
        self.terminal_by_cause[LEGACY_UNKNOWN] = self.terminal_by_cause.get(LEGACY_UNKNOWN, 0) + 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_sessions": self.total_sessions,
            "root_sessions": self.root_sessions,
            "subagent_sessions": self.subagent_sessions,
            "duplicate_suppressed": self.duplicate_suppressed,
            "duplicate-suppressed": self.duplicate_suppressed,
            "zero_action_sessions": self.zero_action_sessions,
            "zero-action-sessions": self.zero_action_sessions,
            "legacy_unknown_count": self.legacy_unknown_count,
            "terminal_by_cause": dict(self.terminal_by_cause),
            "terminal_by_state": dict(self.terminal_by_state),
            "retry_chains": {k: list(v) for k, v in self.retry_chains.items()},
            "retry_chain_count": len(self.retry_chains),
        }

    def get_summary(self) -> dict[str, Any]:
        return self.to_dict()

    @classmethod
    def from_records(cls, records: Sequence[SessionTelemetryCompanion]) -> TelemetryAggregator:
        aggregator = cls()
        for r in records:
            aggregator.record_session(r)
        return aggregator

    @classmethod
    def from_jsonl(cls, file_path: str | Path) -> TelemetryAggregator:
        records = read_companion_records(file_path)
        return cls.from_records(records)
