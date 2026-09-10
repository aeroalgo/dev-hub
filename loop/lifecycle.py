"""Immutable lifecycle state machine, idempotency key, and lifecycle reducer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import threading
import time
import json
from pathlib import Path
from typing import Any, Sequence
import uuid


class InvocationState(str, Enum):
    """Exhaustive lifecycle states for orchestrator invocations."""

    CREATED = "created"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STALE = "stale"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"
    ABORTED_BEFORE_ACTION = "aborted_before_action"

    @property
    def is_terminal(self) -> bool:
        return self in TERMINAL_STATES

    @property
    def is_passed(self) -> bool:
        return self == InvocationState.PASSED

    @property
    def is_failed(self) -> bool:
        return self == InvocationState.FAILED


TERMINAL_STATES: frozenset[InvocationState] = frozenset({
    InvocationState.PASSED,
    InvocationState.FAILED,
    InvocationState.CANCELLED,
    InvocationState.STALE,
    InvocationState.INFRASTRUCTURE_FAILURE,
    InvocationState.ABORTED_BEFORE_ACTION,
})

NON_TERMINAL_STATES: frozenset[InvocationState] = frozenset({
    InvocationState.CREATED,
    InvocationState.RUNNING,
})

ALL_STATES: frozenset[InvocationState] = TERMINAL_STATES | NON_TERMINAL_STATES


class LifecycleEventType(str, Enum):
    """Canonical lifecycle event types."""

    CREATED = "created"
    STARTED = "started"
    RUNNING = "running"
    HEARTBEAT = "heartbeat"
    TASK_STOP = "task_stop"
    LEASE_EXPIRED = "lease_expired"
    PASSED = "passed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STALE = "stale"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"
    ABORTED_BEFORE_ACTION = "aborted_before_action"


ALLOWED_TRANSITIONS: dict[InvocationState, frozenset[InvocationState]] = {
    InvocationState.CREATED: frozenset({
        InvocationState.RUNNING,
        InvocationState.CANCELLED,
        InvocationState.ABORTED_BEFORE_ACTION,
        InvocationState.STALE,
        InvocationState.INFRASTRUCTURE_FAILURE,
        InvocationState.FAILED,
    }),
    InvocationState.RUNNING: frozenset({
        InvocationState.PASSED,
        InvocationState.FAILED,
        InvocationState.CANCELLED,
        InvocationState.STALE,
        InvocationState.INFRASTRUCTURE_FAILURE,
        InvocationState.ABORTED_BEFORE_ACTION,
    }),
    InvocationState.PASSED: frozenset(),
    InvocationState.FAILED: frozenset(),
    InvocationState.CANCELLED: frozenset(),
    InvocationState.STALE: frozenset(),
    InvocationState.INFRASTRUCTURE_FAILURE: frozenset(),
    InvocationState.ABORTED_BEFORE_ACTION: frozenset(),
}


EVENT_TYPE_TO_TARGET_STATE: dict[LifecycleEventType, InvocationState] = {
    LifecycleEventType.CREATED: InvocationState.CREATED,
    LifecycleEventType.STARTED: InvocationState.RUNNING,
    LifecycleEventType.RUNNING: InvocationState.RUNNING,
    LifecycleEventType.HEARTBEAT: InvocationState.RUNNING,
    LifecycleEventType.TASK_STOP: InvocationState.STALE,
    LifecycleEventType.LEASE_EXPIRED: InvocationState.STALE,
    LifecycleEventType.PASSED: InvocationState.PASSED,
    LifecycleEventType.FAILED: InvocationState.FAILED,
    LifecycleEventType.CANCELLED: InvocationState.CANCELLED,
    LifecycleEventType.STALE: InvocationState.STALE,
    LifecycleEventType.INFRASTRUCTURE_FAILURE: InvocationState.INFRASTRUCTURE_FAILURE,
    LifecycleEventType.ABORTED_BEFORE_ACTION: InvocationState.ABORTED_BEFORE_ACTION,
}

STATE_TO_EVENT_TYPE: dict[InvocationState, LifecycleEventType] = {
    InvocationState.CREATED: LifecycleEventType.CREATED,
    InvocationState.RUNNING: LifecycleEventType.STARTED,
    InvocationState.PASSED: LifecycleEventType.PASSED,
    InvocationState.FAILED: LifecycleEventType.FAILED,
    InvocationState.CANCELLED: LifecycleEventType.CANCELLED,
    InvocationState.STALE: LifecycleEventType.STALE,
    InvocationState.INFRASTRUCTURE_FAILURE: LifecycleEventType.INFRASTRUCTURE_FAILURE,
    InvocationState.ABORTED_BEFORE_ACTION: LifecycleEventType.ABORTED_BEFORE_ACTION,
}

SUPERVISORY_ACTORS: frozenset[str] = frozenset({
    "orchestrator",
    "system",
    "reaper",
    "supervisor",
    "orchestrator:reaper",
    "orchestrator:supervisor",
    "orchestrator:root",
})


class LifecycleError(Exception):
    """Base exception for lifecycle state machine errors."""


class InvalidStateTransitionError(LifecycleError):
    """Raised when an illegal state transition is attempted."""


class UnauthorizedMutationError(LifecycleError):
    """Raised when an unauthorized actor attempts to mutate lifecycle state."""


class InvocationNotFoundError(LifecycleError):
    """Raised when an invocation is not found."""


class LegacyMarkerMigrationError(LifecycleError):
    """Raised when an illegal operation is attempted on a legacy marker (e.g. attempting to convert to PASSED)."""


LEGACY_UNKNOWN: str = "legacy_unknown"


def _parse_legacy_epoch(raw_content: dict[str, Any]) -> int:
    raw_epoch = raw_content.get("epoch")
    if raw_epoch is None:
        return 0
    if isinstance(raw_epoch, bool) or isinstance(raw_epoch, float):
        raise LegacyMarkerMigrationError(
            "Legacy marker contains an invalid epoch; migration failed closed"
        )
    if isinstance(raw_epoch, int):
        if raw_epoch < 0:
            raise LegacyMarkerMigrationError(
                "Legacy marker contains a negative epoch; migration failed closed"
            )
        return raw_epoch
    if isinstance(raw_epoch, str):
        text = raw_epoch.strip()
        if not text or not text.isdigit():
            raise LegacyMarkerMigrationError(
                "Legacy marker contains an invalid epoch; migration failed closed"
            )
        return int(text)
    raise LegacyMarkerMigrationError(
        "Legacy marker contains an invalid epoch; migration failed closed"
    )


class TodoPolicyDecision:
    """Decision and telemetry for a TodoWrite tool request."""

    def __init__(
        self,
        allowed: bool,
        action: str,
        call_count: int,
        diagnostic: str | None = None,
        side_effect: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.allowed = allowed
        self.action = action
        self.call_count = call_count
        self.diagnostic = diagnostic
        self.side_effect = side_effect
        self.metadata = dict(metadata or {})

    def __repr__(self) -> str:
        return (
            f"TodoPolicyDecision(allowed={self.allowed!r}, action={self.action!r}, "
            f"call_count={self.call_count!r}, diagnostic={self.diagnostic!r}, "
            f"side_effect={self.side_effect!r}, metadata={self.metadata!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TodoPolicyDecision):
            return False
        return (
            self.allowed == other.allowed
            and self.action == other.action
            and self.call_count == other.call_count
            and self.diagnostic == other.diagnostic
            and self.side_effect == other.side_effect
            and self.metadata == other.metadata
        )


class TodoLifecycleManager:
    """Enforce the bounded TodoWrite lifecycle for a phase session."""

    def __init__(self, phase: str = "IMPLEMENT", max_allowed: int = 2) -> None:
        self.phase = str(phase or "IMPLEMENT").strip().upper()
        self.max_allowed = max_allowed
        self.call_count = 0
        self.history: list[TodoPolicyDecision] = []

    @staticmethod
    def evaluate_request(
        phase: str,
        current_count: int,
        payload: Any = None,
        max_allowed: int = 2,
    ) -> TodoPolicyDecision:
        """Evaluate one TodoWrite request without mutating lifecycle state."""
        normalized_phase = str(phase or "IMPLEMENT").strip().upper()
        limited_phase = (
            normalized_phase == "IMPLEMENT"
            or normalized_phase.endswith(" IMPLEMENT")
        )
        metadata = {
            "phase": normalized_phase,
            "max_allowed": max_allowed,
            "payload": payload,
        }
        if limited_phase and current_count > max_allowed:
            return TodoPolicyDecision(
                allowed=False,
                action="rejected",
                call_count=current_count,
                diagnostic="todowrite_limit_exceeded",
                side_effect=False,
                metadata=metadata,
            )
        return TodoPolicyDecision(
            allowed=True,
            action="start" if current_count <= 1 else "finish",
            call_count=current_count,
            diagnostic=None,
            side_effect=True,
            metadata=metadata,
        )

    def record_todowrite_request(self, payload: Any = None) -> TodoPolicyDecision:
        """Evaluate and record a TodoWrite request under the phase policy."""
        self.call_count += 1
        decision = self.evaluate_request(
            self.phase,
            self.call_count,
            payload=payload,
            max_allowed=self.max_allowed,
        )
        self.history.append(decision)
        return decision

    def handle_request(self, payload: Any = None, apply: Any = None) -> TodoPolicyDecision:
        """Enforce the policy before applying a TodoWrite side effect."""
        decision = self.record_todowrite_request(payload)
        if decision.allowed and callable(apply):
            apply(payload)
        return decision

    def is_request_allowed(self) -> bool:
        """Check if a subsequent TodoWrite request would be allowed."""
        limited_phase = self.phase == "IMPLEMENT" or self.phase.endswith(" IMPLEMENT")
        if limited_phase and self.call_count >= self.max_allowed:
            return False
        return True

    def reset(self) -> None:
        self.call_count = 0
        self.history.clear()


TodoWritePolicy = TodoLifecycleManager


@dataclass(frozen=True)
class InvocationKey:
    """Immutable idempotency key for an orchestrator invocation."""

    session: str
    phase: str
    step: str
    role: str
    epoch: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.session, str) or not self.session.strip():
            raise ValueError("session must be a non-empty string")
        if not isinstance(self.phase, str) or not self.phase.strip():
            raise ValueError("phase must be a non-empty string")
        if not isinstance(self.step, str) or not self.step.strip():
            raise ValueError("step must be a non-empty string")
        if not isinstance(self.role, str) or not self.role.strip():
            raise ValueError("role must be a non-empty string")
        if not isinstance(self.epoch, int) or self.epoch < 0:
            raise ValueError("epoch must be a non-negative integer")

    @property
    def key(self) -> str:
        return f"{self.session}:{self.phase}:{self.step}:{self.role}:{self.epoch}"

    def as_key(self) -> str:
        return self.key

    def __str__(self) -> str:
        return self.key

    @classmethod
    def from_string(cls, key_str: str) -> InvocationKey:
        parts = key_str.split(":")
        if len(parts) != 5:
            raise ValueError(f"Invalid InvocationKey string: '{key_str}', expected 5 colon-separated parts")
        session, phase, step, role, epoch_str = parts
        try:
            epoch = int(epoch_str)
        except ValueError as exc:
            raise ValueError(f"Invalid epoch in key '{key_str}': {epoch_str}") from exc
        return cls(session=session, phase=phase, step=step, role=role, epoch=epoch)


@dataclass(frozen=True)
class InvocationEvent:
    """Immutable event in the invocation lifecycle."""

    event_id: str
    invocation_key: InvocationKey
    event_type: LifecycleEventType
    target_state: InvocationState
    timestamp: float
    actor: str
    reason: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    receipt: Any | None = None

    @classmethod
    def create(
        cls,
        invocation_key: InvocationKey,
        event_type: LifecycleEventType | str,
        actor: str,
        *,
        target_state: InvocationState | str | None = None,
        reason: str | None = None,
        payload: dict[str, Any] | None = None,
        receipt: Any | None = None,
        timestamp: float | None = None,
        event_id: str | None = None,
    ) -> InvocationEvent:
        if isinstance(event_type, str):
            event_type = LifecycleEventType(event_type)
        if target_state is None:
            target_state = EVENT_TYPE_TO_TARGET_STATE[event_type]
        elif isinstance(target_state, str):
            target_state = InvocationState(target_state)

        return cls(
            event_id=event_id or uuid.uuid4().hex,
            invocation_key=invocation_key,
            event_type=event_type,
            target_state=target_state,
            timestamp=time.time() if timestamp is None else timestamp,
            actor=actor,
            reason=reason,
            payload=dict(payload or {}),
            receipt=receipt,
        )


@dataclass(frozen=True)
class GateReceipt:
    """Immutable gate verification receipt linked to an invocation ID and epoch."""

    invocation_id: str
    epoch: int
    verdict: str
    role: str = ""
    step: str = ""
    session: str = ""
    agent_id: str = ""
    timestamp: float = field(default_factory=time.time)
    details: dict[str, Any] = field(default_factory=dict)
    evidence_sha256: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.invocation_id, str) or not self.invocation_id.strip():
            raise ValueError("invocation_id must be a non-empty string")
        if not isinstance(self.epoch, int) or self.epoch < 0:
            raise ValueError("epoch must be a non-negative integer")
        if not isinstance(self.verdict, str) or not self.verdict.strip():
            raise ValueError("verdict must be a non-empty string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "invocation_id": self.invocation_id,
            "epoch": self.epoch,
            "verdict": self.verdict.upper(),
            "role": self.role,
            "step": self.step,
            "session": self.session,
            "agent_id": self.agent_id or self.role,
            "timestamp": self.timestamp,
            "details": self.details,
            "evidence_sha256": self.evidence_sha256,
        }


def validate_receipt_epoch(
    receipt: Any,
    expected_epoch: int,
    *,
    expected_invocation_id: str | None = None,
) -> bool:
    """Validate that a receipt belongs to the expected epoch and optionally matching invocation_id."""
    if receipt is None:
        return False

    if isinstance(receipt, GateReceipt):
        if receipt.epoch != expected_epoch:
            return False
        if expected_invocation_id is not None and receipt.invocation_id != expected_invocation_id:
            return False
        return True

    if isinstance(receipt, dict):
        if "epoch" not in receipt or receipt["epoch"] is None:
            return False
        try:
            if int(receipt["epoch"]) != int(expected_epoch):
                return False
        except (TypeError, ValueError, OverflowError):
            return False
        if expected_invocation_id is not None:
            if "invocation_id" not in receipt or receipt["invocation_id"] is None:
                return False
            if str(receipt["invocation_id"]) != str(expected_invocation_id):
                return False
        return True

    if hasattr(receipt, "epoch"):
        epoch_val = getattr(receipt, "epoch")
        if epoch_val is None:
            return False
        try:
            if int(epoch_val) != int(expected_epoch):
                return False
        except (TypeError, ValueError, OverflowError):
            return False
        if expected_invocation_id is not None:
            if not hasattr(receipt, "invocation_id"):
                return False
            inv_id = getattr(receipt, "invocation_id")
            if inv_id is None or str(inv_id) != str(expected_invocation_id):
                return False
        return True

    return False


@dataclass(frozen=True)
class InvocationStatusView:
    """Read-only status representation for parent and external observers."""

    invocation_id: str
    key: str
    state: InvocationState
    is_terminal: bool
    owner: str
    created_at: float
    updated_at: float
    reason: str | None = None
    receipt: Any | None = None
    first_action_taken: bool = False
    first_action_at: float | None = None
    lease_expires_at: float | None = None
    last_heartbeat_at: float | None = None
    lease_duration_sec: float | None = None

    def is_lease_expired(self, now: float | None = None) -> bool:
        if self.is_terminal or self.lease_expires_at is None:
            return False
        current = time.time() if now is None else now
        return current >= self.lease_expires_at


@dataclass(frozen=True)
class InvocationRecord:
    """Immutable container for an invocation state, protected from direct mutation."""

    key: InvocationKey
    invocation_id: str
    state: InvocationState
    owner: str
    created_at: float
    updated_at: float
    reason: str | None = None
    receipt: Any | None = None
    first_action_taken: bool = False
    first_action_at: float | None = None
    lease_duration_sec: float | None = None
    lease_expires_at: float | None = None
    last_heartbeat_at: float | None = None
    events: tuple[InvocationEvent, ...] = field(default_factory=tuple)

    @property
    def is_terminal(self) -> bool:
        return self.state.is_terminal

    @property
    def status_view(self) -> InvocationStatusView:
        return InvocationStatusView(
            invocation_id=self.invocation_id,
            key=self.key.key,
            state=self.state,
            is_terminal=self.is_terminal,
            owner=self.owner,
            created_at=self.created_at,
            updated_at=self.updated_at,
            reason=self.reason,
            receipt=self.receipt,
            first_action_taken=self.first_action_taken,
            first_action_at=self.first_action_at,
            lease_expires_at=self.lease_expires_at,
            last_heartbeat_at=self.last_heartbeat_at,
            lease_duration_sec=self.lease_duration_sec,
        )

    def is_lease_expired(self, now: float | None = None) -> bool:
        if self.is_terminal or self.lease_expires_at is None:
            return False
        current = time.time() if now is None else now
        return current >= self.lease_expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "invocation_id": self.invocation_id,
            "key": self.key.key,
            "state": self.state.value,
            "is_terminal": self.is_terminal,
            "owner": self.owner,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "reason": self.reason,
            "receipt": self.receipt,
            "first_action_taken": self.first_action_taken,
            "first_action_at": self.first_action_at,
            "lease_duration_sec": self.lease_duration_sec,
            "lease_expires_at": self.lease_expires_at,
            "last_heartbeat_at": self.last_heartbeat_at,
            "event_count": len(self.events),
        }


class LifecycleReducer:
    """Durable reducer state machine validating transitions and enforcing idempotency with thread-safety."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._change_condition = threading.Condition(self._lock)
        self._by_key: dict[InvocationKey, InvocationRecord] = {}
        self._by_id: dict[str, InvocationRecord] = {}

    def get_or_create_invocation(
        self,
        key: InvocationKey,
        owner: str,
        *,
        invocation_id: str | None = None,
        created_at: float | None = None,
        lease_duration_sec: float | None = None,
    ) -> tuple[InvocationRecord, bool]:
        """Get existing invocation for key, or atomically register a new one in CREATED state.

        Returns (record, created_flag).
        """
        with self._lock:
            if key in self._by_key:
                return self._by_key[key], False

            now = time.time() if created_at is None else created_at
            if invocation_id is None:
                digest = hashlib.sha256(key.key.encode("utf-8")).hexdigest()[:16]
                invocation_id = f"inv-{digest}"

            expires_at = (now + lease_duration_sec) if lease_duration_sec is not None else None

            initial_event = InvocationEvent.create(
                invocation_key=key,
                event_type=LifecycleEventType.CREATED,
                actor=owner,
                target_state=InvocationState.CREATED,
                timestamp=now,
                payload={"lease_duration_sec": lease_duration_sec} if lease_duration_sec else {},
            )

            record = InvocationRecord(
                key=key,
                invocation_id=invocation_id,
                state=InvocationState.CREATED,
                owner=owner,
                created_at=now,
                updated_at=now,
                lease_duration_sec=lease_duration_sec,
                lease_expires_at=expires_at,
                events=(initial_event,),
            )

            self._by_key[key] = record
            self._by_id[invocation_id] = record
            self._change_condition.notify_all()
            return record, True

    def create_or_get_invocation(
        self,
        key: InvocationKey,
        owner: str,
        *,
        invocation_id: str | None = None,
        created_at: float | None = None,
        lease_duration_sec: float | None = None,
    ) -> tuple[InvocationRecord, bool]:
        """Alias for get_or_create_invocation."""
        return self.get_or_create_invocation(
            key,
            owner,
            invocation_id=invocation_id,
            created_at=created_at,
            lease_duration_sec=lease_duration_sec,
        )

    def launch(
        self,
        key: InvocationKey,
        owner: str,
        *,
        invocation_id: str | None = None,
        lease_duration_sec: float | None = None,
    ) -> InvocationRecord:
        """Launch or retrieve an invocation record stably."""
        record, _ = self.get_or_create_invocation(
            key,
            owner,
            invocation_id=invocation_id,
            lease_duration_sec=lease_duration_sec,
        )
        return record

    def get_invocation(self, key_or_id: InvocationKey | str) -> InvocationRecord | None:
        with self._lock:
            if isinstance(key_or_id, InvocationKey):
                return self._by_key.get(key_or_id)
            if isinstance(key_or_id, str):
                if key_or_id in self._by_id:
                    return self._by_id[key_or_id]
                try:
                    key = InvocationKey.from_string(key_or_id)
                    return self._by_key.get(key)
                except ValueError:
                    return None
            return None

    def get_status(self, key_or_id: InvocationKey | str) -> InvocationStatusView | None:
        record = self.get_invocation(key_or_id)
        if record is None:
            return None
        return record.status_view

    @staticmethod
    def _has_recorded_tool_action(record: InvocationRecord) -> bool:
        """Return whether the record contains immutable evidence of a tool action."""
        if record.first_action_taken or record.first_action_at is not None:
            return True
        for event in record.events:
            payload = event.payload
            if payload.get("tool_action_recorded") or payload.get("tool_action"):
                return True
            try:
                if int(payload.get("tool_actions_count", 0)) > 0:
                    return True
            except (TypeError, ValueError):
                continue
            actions = payload.get("tool_actions")
            if isinstance(actions, (list, tuple, set, dict)) and actions:
                return True
        return False

    def await_gate(
        self,
        key_or_id: InvocationKey | str,
        *,
        timeout_sec: float | None = None,
        poll_interval_sec: float = 0.05,
    ) -> InvocationStatusView | None:
        """Wait until an invocation reaches a terminal state, or timeout expires.

        Returns the typed InvocationStatusView without any filesystem access.
        """
        deadline = (time.time() + timeout_sec) if timeout_sec is not None else None

        with self._lock:
            while True:
                record = self.get_invocation(key_or_id)
                if record is None:
                    return None
                if record.is_terminal:
                    return record.status_view

                if deadline is not None:
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        return record.status_view
                    wait_time = min(remaining, poll_interval_sec if poll_interval_sec > 0 else remaining)
                else:
                    wait_time = poll_interval_sec if poll_interval_sec > 0 else None

                self._change_condition.wait(timeout=wait_time)

    def apply_event(self, event: InvocationEvent) -> InvocationRecord:
        """Apply an immutable event to reduce state atomically."""
        with self._lock:
            record = self.get_invocation(event.invocation_key)
            if record is None:
                raise InvocationNotFoundError(f"Invocation not found for key: {event.invocation_key}")

            # Validate lifecycle actor authorization
            is_owner = (event.actor == record.owner)
            is_supervisor = (
                event.actor in SUPERVISORY_ACTORS
                or event.actor.startswith("orchestrator")
                or event.actor.startswith("system")
                or event.actor.startswith("supervisor")
            )
            can_mutate = is_owner or (
                is_supervisor
                and event.target_state in {
                    InvocationState.STALE,
                    InvocationState.INFRASTRUCTURE_FAILURE,
                    InvocationState.CANCELLED,
                    InvocationState.ABORTED_BEFORE_ACTION,
                }
            )

            if not can_mutate:
                raise UnauthorizedMutationError(
                    f"Actor '{event.actor}' is not authorized to mutate invocation '{record.invocation_id}' (owner='{record.owner}')"
                )

            if event.target_state == InvocationState.ABORTED_BEFORE_ACTION:
                if record.state not in {InvocationState.CREATED, InvocationState.RUNNING}:
                    raise InvalidStateTransitionError(
                        f"Cannot abort invocation '{record.invocation_id}' before action from state '{record.state.value}'"
                    )
                if self._has_recorded_tool_action(record) or self._has_recorded_tool_action(
                    InvocationRecord(
                        key=record.key,
                        invocation_id=record.invocation_id,
                        state=record.state,
                        owner=record.owner,
                        created_at=record.created_at,
                        updated_at=record.updated_at,
                        reason=record.reason,
                        receipt=record.receipt,
                        first_action_taken=bool(event.payload.get("first_action_taken", False)),
                        first_action_at=event.payload.get("first_action_at"),
                        lease_duration_sec=record.lease_duration_sec,
                        lease_expires_at=record.lease_expires_at,
                        last_heartbeat_at=record.last_heartbeat_at,
                        events=(event,),
                    )
                ):
                    raise InvalidStateTransitionError(
                        f"Cannot abort invocation '{record.invocation_id}' after a tool action was recorded"
                    )

            # Handle Heartbeat event (does not change state, updates lease and heartbeat timestamp)
            if event.event_type == LifecycleEventType.HEARTBEAT:
                if record.is_terminal:
                    raise InvalidStateTransitionError(
                        f"Cannot heartbeat terminal invocation '{record.invocation_id}' (state='{record.state.value}')"
                    )
                lease_dur = event.payload.get("lease_duration_sec") or record.lease_duration_sec
                new_lease_exp = (event.timestamp + lease_dur) if lease_dur is not None else record.lease_expires_at
                new_record = InvocationRecord(
                    key=record.key,
                    invocation_id=record.invocation_id,
                    state=record.state,
                    owner=record.owner,
                    created_at=record.created_at,
                    updated_at=event.timestamp,
                    reason=record.reason,
                    receipt=record.receipt,
                    first_action_taken=record.first_action_taken,
                    first_action_at=record.first_action_at,
                    lease_duration_sec=lease_dur,
                    lease_expires_at=new_lease_exp,
                    last_heartbeat_at=event.timestamp,
                    events=record.events + (event,),
                )
                self._by_key[record.key] = new_record
                self._by_id[record.invocation_id] = new_record
                return new_record

            # If already at target state and no action payload update
            if record.state == event.target_state and not event.payload.get("first_action_taken"):
                return record

            # Validate legal transition if changing state
            if record.state != event.target_state:
                allowed = ALLOWED_TRANSITIONS.get(record.state, frozenset())
                if event.target_state not in allowed:
                    raise InvalidStateTransitionError(
                        f"Illegal state transition from '{record.state.value}' to '{event.target_state.value}' for invocation '{record.invocation_id}'"
                    )

            first_action = record.first_action_taken
            first_action_at = record.first_action_at

            if "first_action_taken" in event.payload:
                first_action = bool(event.payload["first_action_taken"])
                if first_action and not first_action_at:
                    first_action_at = event.payload.get("first_action_at") or event.timestamp
                elif not first_action:
                    first_action_at = None
            elif event.target_state == InvocationState.ABORTED_BEFORE_ACTION:
                first_action = False
                first_action_at = None

            reason_str = event.reason if event.reason is not None else record.reason
            if event.target_state == InvocationState.ABORTED_BEFORE_ACTION and not reason_str:
                reason_str = "aborted before first action"

            new_record = InvocationRecord(
                key=record.key,
                invocation_id=record.invocation_id,
                state=event.target_state,
                owner=record.owner,
                created_at=record.created_at,
                updated_at=event.timestamp,
                reason=reason_str,
                receipt=event.receipt if event.receipt is not None else record.receipt,
                first_action_taken=first_action,
                first_action_at=first_action_at,
                lease_duration_sec=record.lease_duration_sec,
                lease_expires_at=record.lease_expires_at,
                last_heartbeat_at=record.last_heartbeat_at,
                events=record.events + (event,),
            )

            self._by_key[record.key] = new_record
            self._by_id[record.invocation_id] = new_record
            self._change_condition.notify_all()
            return new_record

    def transition(
        self,
        key_or_id: InvocationKey | str,
        target_state: InvocationState | str,
        actor: str,
        *,
        reason: str | None = None,
        receipt: Any | None = None,
        first_action_taken: bool | None = None,
        payload: dict[str, Any] | None = None,
        timestamp: float | None = None,
    ) -> InvocationRecord:
        with self._lock:
            record = self.get_invocation(key_or_id)
            if record is None:
                raise InvocationNotFoundError(f"Invocation not found for: {key_or_id}")

            if isinstance(target_state, str):
                target_state = InvocationState(target_state)

            if target_state == InvocationState.ABORTED_BEFORE_ACTION:
                if record.state not in {InvocationState.CREATED, InvocationState.RUNNING}:
                    raise InvalidStateTransitionError(
                        f"Cannot abort invocation '{record.invocation_id}' before action from state '{record.state.value}'"
                    )
                if self._has_recorded_tool_action(record):
                    raise InvalidStateTransitionError(
                        f"Cannot abort invocation '{record.invocation_id}' after a tool action was recorded"
                    )

            event_payload = dict(payload or {})
            if first_action_taken is not None:
                event_payload["first_action_taken"] = first_action_taken

            event_type = STATE_TO_EVENT_TYPE[target_state]

            event = InvocationEvent.create(
                invocation_key=record.key,
                event_type=event_type,
                target_state=target_state,
                actor=actor,
                reason=reason,
                payload=event_payload,
                receipt=receipt,
                timestamp=timestamp,
            )
            return self.apply_event(event)

    def start(self, key_or_id: InvocationKey | str, actor: str) -> InvocationRecord:
        return self.transition(key_or_id, InvocationState.RUNNING, actor)

    def pass_invocation(
        self,
        key_or_id: InvocationKey | str,
        actor: str,
        receipt: Any | None = None,
    ) -> InvocationRecord:
        record = self.get_invocation(key_or_id)
        if record is not None and receipt is not None:
            if not validate_receipt_epoch(receipt, record.key.epoch):
                raise InvalidStateTransitionError(
                    f"Receipt epoch mismatch or untagged receipt for invocation '{record.invocation_id}' (expected epoch {record.key.epoch})"
                )
        return self.transition(key_or_id, InvocationState.PASSED, actor, receipt=receipt)

    def fail_invocation(
        self,
        key_or_id: InvocationKey | str,
        actor: str,
        reason: str | None = None,
    ) -> InvocationRecord:
        return self.transition(key_or_id, InvocationState.FAILED, actor, reason=reason)

    def cancel(
        self,
        key_or_id: InvocationKey | str,
        actor: str,
        reason: str | None = None,
    ) -> InvocationRecord:
        return self.transition(key_or_id, InvocationState.CANCELLED, actor, reason=reason)

    def mark_stale(
        self,
        key_or_id: InvocationKey | str,
        actor: str,
        reason: str | None = None,
    ) -> InvocationRecord:
        return self.transition(key_or_id, InvocationState.STALE, actor, reason=reason)

    def mark_infrastructure_failure(
        self,
        key_or_id: InvocationKey | str,
        actor: str,
        reason: str | None = None,
    ) -> InvocationRecord:
        return self.transition(key_or_id, InvocationState.INFRASTRUCTURE_FAILURE, actor, reason=reason)

    def abort_before_action(
        self,
        key_or_id: InvocationKey | str,
        actor: str,
        reason: str | None = None,
    ) -> InvocationRecord:
        clean_reason = (reason or "").strip() or "aborted before first action"
        return self.transition(
            key_or_id,
            InvocationState.ABORTED_BEFORE_ACTION,
            actor,
            reason=clean_reason,
            first_action_taken=False,
        )

    def heartbeat(
        self,
        key_or_id: InvocationKey | str,
        actor: str,
        *,
        timestamp: float | None = None,
        lease_duration_sec: float | None = None,
    ) -> InvocationRecord:
        """Send a heartbeat to extend the owner lease for an active invocation."""
        with self._lock:
            record = self.get_invocation(key_or_id)
            if record is None:
                raise InvocationNotFoundError(f"Invocation not found for: {key_or_id}")
            if record.is_terminal:
                raise InvalidStateTransitionError(
                    f"Cannot send heartbeat to terminal invocation '{record.invocation_id}' (state='{record.state.value}')"
                )
            now = time.time() if timestamp is None else timestamp
            duration = lease_duration_sec if lease_duration_sec is not None else record.lease_duration_sec
            event = InvocationEvent.create(
                invocation_key=record.key,
                event_type=LifecycleEventType.HEARTBEAT,
                target_state=record.state,
                actor=actor,
                timestamp=now,
                payload={"lease_duration_sec": duration, "heartbeat_at": now},
            )
            return self.apply_event(event)

    def check_lease_expired(
        self,
        key_or_id: InvocationKey | str,
        *,
        now: float | None = None,
    ) -> bool:
        """Check if an invocation's lease has expired."""
        with self._lock:
            record = self.get_invocation(key_or_id)
            if record is None:
                return False
            return record.is_lease_expired(now=now)

    def reap_stale(
        self,
        key_or_id: InvocationKey | str,
        actor: str = "orchestrator",
        *,
        now: float | None = None,
        reason: str = "lease expired",
    ) -> InvocationRecord:
        """Transition an expired or abandoned invocation to STALE."""
        return self.transition(
            key_or_id,
            InvocationState.STALE,
            actor=actor,
            reason=reason,
            timestamp=now,
        )

    def reap_stale_invocations(
        self,
        *,
        now: float | None = None,
        actor: str = "orchestrator",
        reason: str = "lease expired",
    ) -> list[InvocationRecord]:
        """Scan and reap all non-terminal invocations whose lease has expired."""
        with self._lock:
            reaped: list[InvocationRecord] = []
            for record in list(self._by_key.values()):
                if not record.is_terminal and record.is_lease_expired(now=now):
                    reaped.append(self.reap_stale(record.key, actor=actor, now=now, reason=reason))
            return reaped

    def handle_crash(
        self,
        key_or_id: InvocationKey | str,
        actor: str = "orchestrator",
        *,
        reason: str = "process crash without stop event",
        target_state: InvocationState = InvocationState.INFRASTRUCTURE_FAILURE,
    ) -> InvocationRecord:
        """Terminalize a crashed session deterministically without marker deletion."""
        return self.transition(
            key_or_id,
            target_state,
            actor=actor,
            reason=reason,
        )

    def handle_task_stop(
        self,
        key_or_id: InvocationKey | str,
        actor: str,
        *,
        reason: str | None = "TaskStop received",
        target_state: InvocationState = InvocationState.STALE,
    ) -> InvocationRecord:
        """Terminalize a stopped task cleanly, preventing restart loops."""
        with self._lock:
            record = self.get_invocation(key_or_id)
            if record is None:
                raise InvocationNotFoundError(f"Invocation not found for: {key_or_id}")
            if isinstance(target_state, str):
                target_state = InvocationState(target_state)
            if target_state != InvocationState.STALE:
                raise InvalidStateTransitionError(
                    "TaskStop events must transition invocations to STALE"
                )
            event = InvocationEvent.create(
                invocation_key=record.key,
                event_type=LifecycleEventType.TASK_STOP,
                target_state=target_state,
                actor=actor,
                reason=reason or "TaskStop received",
            )
            return self.apply_event(event)

    def task_stop(
        self,
        key_or_id: InvocationKey | str,
        actor: str,
        *,
        reason: str | None = "TaskStop received",
        target_state: InvocationState = InvocationState.STALE,
    ) -> InvocationRecord:
        """Alias for handle_task_stop."""
        return self.handle_task_stop(key_or_id, actor, reason=reason, target_state=target_state)

    def record_first_action(
        self,
        key_or_id: InvocationKey | str,
        actor: str,
        *,
        timestamp: float | None = None,
    ) -> InvocationRecord:
        """Mark that the invocation has performed its first tool action."""
        with self._lock:
            record = self.get_invocation(key_or_id)
            if record is None:
                raise InvocationNotFoundError(f"Invocation not found for: {key_or_id}")
            now = time.time() if timestamp is None else timestamp
            if record.first_action_taken:
                return record
            target_state = InvocationState.RUNNING if record.state == InvocationState.CREATED else record.state
            event = InvocationEvent.create(
                invocation_key=record.key,
                event_type=LifecycleEventType.RUNNING,
                target_state=target_state,
                actor=actor,
                timestamp=now,
                payload={"first_action_taken": True, "first_action_at": now},
            )
            return self.apply_event(event)

    def ingest_legacy_marker(
        self,
        marker_input: str | Path | dict[str, Any] | bytes,
        actor: str = "orchestrator:migration",
    ) -> tuple[InvocationRecord, LegacyMarkerResult]:
        """Ingest and migrate a legacy marker into the reducer, ensuring it never becomes PASSED."""
        migration_res = migrate_legacy_marker(marker_input)
        raw = migration_res.raw_content
        session = "legacy"
        phase = "legacy"
        step = "legacy_marker"
        role = "migrated"
        epoch = 0
        if isinstance(raw, dict):
            session = str(raw.get("session") or raw.get("session_id") or session)
            phase = str(raw.get("phase") or phase)
            step = str(raw.get("step") or raw.get("step_id") or step)
            role = str(raw.get("role") or raw.get("actor") or role)
            epoch = _parse_legacy_epoch(raw)

        key = InvocationKey(session=session, phase=phase, step=step, role=role, epoch=epoch)
        existing = self.get_invocation(key)
        if existing is not None and existing.state != InvocationState.FAILED:
            digest = hashlib.sha256(
                f"{migration_res.source}:{key.key}".encode("utf-8")
            ).hexdigest()[:12]
            base_role = role
            for collision in range(1, 101):
                suffix = f":legacy_unknown:{digest}"
                if collision > 1:
                    suffix += f":{collision}"
                candidate = InvocationKey(
                    session=session,
                    phase=phase,
                    step=step,
                    role=f"{base_role}{suffix}",
                    epoch=epoch,
                )
                candidate_existing = self.get_invocation(candidate)
                if candidate_existing is None or candidate_existing.state == InvocationState.FAILED:
                    key = candidate
                    break
            else:
                raise LegacyMarkerMigrationError(
                    "Legacy marker quarantine key collision; migration failed closed"
                )
        requested_invocation_id = migration_res.invocation_id
        if requested_invocation_id and self.get_invocation(requested_invocation_id) is not None:
            requested_invocation_id = None
        record, _ = self.get_or_create_invocation(
            key,
            owner=actor,
            invocation_id=requested_invocation_id,
        )
        if record.state == InvocationState.PASSED:
            raise LegacyMarkerMigrationError(
                "Legacy marker ingestion cannot return a PASSED invocation"
            )
        if not record.is_terminal:
            record = self.transition(
                key,
                migration_res.migrated_state,
                actor=actor,
                reason=migration_res.reason,
                payload={"diagnostic_status": LEGACY_UNKNOWN, "legacy_source": migration_res.source},
            )
        return record, migration_res


@dataclass(frozen=True)
class LegacyMarkerResult:
    """Diagnostic outcome of migrating a legacy unverified marker record."""

    source: str
    diagnostic_status: str = LEGACY_UNKNOWN
    migrated_state: InvocationState = InvocationState.FAILED
    reason: str = "legacy_unknown: legacy marker migrated as unverified diagnostic"
    is_passed: bool = False
    raw_content: Any = None
    invocation_id: str | None = None

    def __post_init__(self) -> None:
        if self.is_passed or self.migrated_state == InvocationState.PASSED:
            raise LegacyMarkerMigrationError(
                "Legacy markers cannot be converted to PASSED; must be legacy_unknown"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "diagnostic_status": self.diagnostic_status,
            "migrated_state": self.migrated_state.value,
            "reason": self.reason,
            "is_passed": self.is_passed,
            "raw_content": self.raw_content,
            "invocation_id": self.invocation_id,
        }


def migrate_legacy_marker(
    marker_input: str | Path | dict[str, Any] | bytes,
    *,
    source_name: str | None = None,
) -> LegacyMarkerResult:
    """Migrate an unverified legacy marker into a diagnostic legacy_unknown record.

    Guarantees that a legacy marker is NEVER implicitly or explicitly converted to PASSED.
    """
    raw_content: dict[str, Any] = {}
    source = source_name or ""

    if isinstance(marker_input, Path) or (isinstance(marker_input, str) and (Path(marker_input).exists() or "/" in marker_input or marker_input.endswith((".json", ".marker", ".pass", ".txt")))):
        path = Path(marker_input)
        if path.exists() and path.is_file():
            source = str(path)
            content_str = path.read_text(encoding="utf-8", errors="replace").strip()
            try:
                parsed = json.loads(content_str)
                raw_content = dict(parsed) if isinstance(parsed, dict) else {"raw_payload": parsed}
            except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
                raw_content = {"raw_text": content_str}
        else:
            source = str(marker_input)
            try:
                parsed = json.loads(str(marker_input))
                raw_content = dict(parsed) if isinstance(parsed, dict) else {"raw_payload": parsed}
            except (json.JSONDecodeError, ValueError):
                raw_content = {"raw_text": str(marker_input)}
    elif isinstance(marker_input, dict):
        source = source or "in-memory-dict"
        raw_content = dict(marker_input)
    elif isinstance(marker_input, bytes):
        source = source or "bytes"
        try:
            decoded = marker_input.decode("utf-8", errors="replace")
            parsed = json.loads(decoded)
            raw_content = dict(parsed) if isinstance(parsed, dict) else {"raw_payload": parsed}
        except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
            raw_content = {"raw_bytes": marker_input.hex()}
    else:
        source = source or str(marker_input)
        try:
            parsed = json.loads(str(marker_input))
            raw_content = dict(parsed) if isinstance(parsed, dict) else {"raw_payload": parsed}
        except (json.JSONDecodeError, ValueError):
            raw_content = {"raw_text": str(marker_input)}

    inv_id = None
    if isinstance(raw_content, dict):
        inv_id = raw_content.get("invocation_id") or raw_content.get("id")

    if not source:
        source = "legacy_marker"

    if isinstance(raw_content, dict):
        _parse_legacy_epoch(raw_content)

    return LegacyMarkerResult(
        source=source,
        diagnostic_status=LEGACY_UNKNOWN,
        migrated_state=InvocationState.FAILED,
        reason=f"legacy_unknown: legacy marker from {source} migrated as unverified diagnostic (never passed)",
        is_passed=False,
        raw_content=raw_content,
        invocation_id=str(inv_id) if inv_id else None,
    )


def migrate_legacy_marker_files(
    paths_or_dir: str | Path | Sequence[str | Path],
) -> list[LegacyMarkerResult]:
    """Migrate multiple legacy marker files or directories containing marker files."""
    results: list[LegacyMarkerResult] = []

    if isinstance(paths_or_dir, (str, Path)):
        p = Path(paths_or_dir)
        if p.is_dir():
            marker_files = sorted(
                [f for f in p.rglob("*") if f.is_file() and (
                    f.suffix in {".marker", ".pass", ".gate", ".json"} or "marker" in f.name.lower() or "gate" in f.name.lower()
                )]
            )
            for f in marker_files:
                results.append(migrate_legacy_marker(f))
            return results
        paths = [p]
    else:
        paths = [Path(p) for p in paths_or_dir]

    for p in paths:
        if p.is_file():
            results.append(migrate_legacy_marker(p))
    return results


_DEFAULT_REDUCER: LifecycleReducer | None = None
_DEFAULT_REDUCER_LOCK = threading.Lock()


def get_default_reducer() -> LifecycleReducer:
    """Get the process-wide default LifecycleReducer singleton."""
    global _DEFAULT_REDUCER
    if _DEFAULT_REDUCER is None:
        with _DEFAULT_REDUCER_LOCK:
            if _DEFAULT_REDUCER is None:
                _DEFAULT_REDUCER = LifecycleReducer()
    return _DEFAULT_REDUCER


def reset_default_reducer() -> LifecycleReducer:
    """Reset the default LifecycleReducer singleton (primarily for testing)."""
    global _DEFAULT_REDUCER
    with _DEFAULT_REDUCER_LOCK:
        _DEFAULT_REDUCER = LifecycleReducer()
        return _DEFAULT_REDUCER


def create_or_get_invocation(
    key: InvocationKey | str | None = None,
    owner: str = "orchestrator",
    *,
    session: str | None = None,
    phase: str | None = None,
    step: str | None = None,
    role: str | None = None,
    epoch: int = 0,
    reducer: LifecycleReducer | None = None,
    invocation_id: str | None = None,
    created_at: float | None = None,
    lease_duration_sec: float | None = None,
) -> tuple[InvocationRecord, bool]:
    """Atomically create a new invocation record in CREATED state or retrieve existing record.

    Guarantees idempotency based on (session, phase, step, role, epoch).
    Returns (record, is_new_created).
    """
    target_reducer = reducer or get_default_reducer()

    if isinstance(key, InvocationKey):
        inv_key = key
    elif isinstance(key, str):
        inv_key = InvocationKey.from_string(key)
    elif key is None:
        if session is None or phase is None or step is None or role is None:
            raise ValueError("When key is not provided, session, phase, step, and role are required.")
        inv_key = InvocationKey(session=session, phase=phase, step=step, role=role, epoch=epoch)
    else:
        raise TypeError(f"Invalid key type: {type(key)}")

    return target_reducer.get_or_create_invocation(
        inv_key,
        owner=owner,
        invocation_id=invocation_id,
        created_at=created_at,
        lease_duration_sec=lease_duration_sec,
    )


def get_invocation_status(
    key_or_id: InvocationKey | str,
    *,
    reducer: LifecycleReducer | None = None,
) -> InvocationStatusView | None:
    """Get a read-only status view of an invocation by key or ID."""
    target_reducer = reducer or get_default_reducer()
    return target_reducer.get_status(key_or_id)


def await_gate(
    key_or_id: InvocationKey | str,
    *,
    timeout_sec: float | None = None,
    poll_interval_sec: float = 0.05,
    reducer: LifecycleReducer | None = None,
) -> InvocationStatusView | None:
    """Wait for an invocation to reach a terminal state and return its typed status."""
    target_reducer = reducer or get_default_reducer()
    return target_reducer.await_gate(
        key_or_id,
        timeout_sec=timeout_sec,
        poll_interval_sec=poll_interval_sec,
    )


def bind_receipt(
    record_or_key: InvocationRecord | InvocationKey | str,
    receipt_data: Any,
    actor: str,
    *,
    reducer: LifecycleReducer | None = None,
) -> InvocationRecord:
    """Link a completed gate receipt to an invocation record, verifying epoch match."""
    target_reducer = reducer or get_default_reducer()
    record = target_reducer.get_invocation(record_or_key)
    if record is None:
        raise InvocationNotFoundError(f"Cannot bind receipt to non-existent invocation: {record_or_key}")

    if not validate_receipt_epoch(receipt_data, record.key.epoch, expected_invocation_id=record.invocation_id):
        raise InvalidStateTransitionError(
            f"Receipt epoch/invocation mismatch for invocation '{record.invocation_id}' (key epoch {record.key.epoch})"
        )

    final_receipt = receipt_data
    if isinstance(receipt_data, dict):
        enriched = dict(receipt_data)
        if "invocation_id" not in enriched:
            enriched["invocation_id"] = record.invocation_id
        if "epoch" not in enriched:
            enriched["epoch"] = record.key.epoch
        final_receipt = enriched

    return target_reducer.pass_invocation(record.key, actor=actor, receipt=final_receipt)
