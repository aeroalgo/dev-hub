"""Unit tests for immutable lifecycle state machine, idempotency key, and LifecycleReducer."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
import pytest

from loop.lifecycle import (
    ALL_STATES,
    NON_TERMINAL_STATES,
    TERMINAL_STATES,
    InvalidStateTransitionError,
    InvocationEvent,
    InvocationKey,
    InvocationRecord,
    InvocationState,
    InvocationStatusView,
    LifecycleEventType,
    LifecycleReducer,
    UnauthorizedMutationError,
)


def test_schema_and_types():
    """cp1: Verify InvocationKey, InvocationState, and lifecycle event schemas."""
    # 1. InvocationKey initialization and validation
    key = InvocationKey(session="sess-100", phase="back", step="s01", role="verifier", epoch=0)
    assert key.session == "sess-100"
    assert key.phase == "back"
    assert key.step == "s01"
    assert key.role == "verifier"
    assert key.epoch == 0
    assert key.key == "sess-100:back:s01:verifier:0"
    assert key.as_key() == "sess-100:back:s01:verifier:0"
    assert str(key) == "sess-100:back:s01:verifier:0"

    # Test from_string helper
    parsed_key = InvocationKey.from_string("sess-100:back:s01:verifier:0")
    assert parsed_key == key

    # Invalid InvocationKey cases
    with pytest.raises(ValueError):
        InvocationKey(session="", phase="back", step="s01", role="verifier", epoch=0)
    with pytest.raises(ValueError):
        InvocationKey(session="sess-100", phase=" ", step="s01", role="verifier", epoch=0)
    with pytest.raises(ValueError):
        InvocationKey(session="sess-100", phase="back", step="", role="verifier", epoch=0)
    with pytest.raises(ValueError):
        InvocationKey(session="sess-100", phase="back", step="s01", role="", epoch=0)
    with pytest.raises(ValueError):
        InvocationKey(session="sess-100", phase="back", step="s01", role="verifier", epoch=-1)

    # 2. InvocationState verification
    expected_states = {
        "created",
        "running",
        "passed",
        "failed",
        "cancelled",
        "stale",
        "infrastructure_failure",
        "aborted_before_action",
    }
    assert {s.value for s in InvocationState} == expected_states
    assert {s.value for s in ALL_STATES} == expected_states

    # Terminal states
    expected_terminals = {
        InvocationState.PASSED,
        InvocationState.FAILED,
        InvocationState.CANCELLED,
        InvocationState.STALE,
        InvocationState.INFRASTRUCTURE_FAILURE,
        InvocationState.ABORTED_BEFORE_ACTION,
    }
    assert TERMINAL_STATES == expected_terminals
    assert NON_TERMINAL_STATES == {InvocationState.CREATED, InvocationState.RUNNING}

    for state in TERMINAL_STATES:
        assert state.is_terminal is True
    for state in NON_TERMINAL_STATES:
        assert state.is_terminal is False

    assert InvocationState.PASSED.is_passed is True
    assert InvocationState.RUNNING.is_passed is False
    assert InvocationState.FAILED.is_failed is True
    assert InvocationState.CANCELLED.is_failed is False

    # 3. InvocationEvent and LifecycleEventType
    event = InvocationEvent.create(
        invocation_key=key,
        event_type=LifecycleEventType.STARTED,
        actor="verifier:child",
        payload={"first_action_taken": True},
    )
    assert event.invocation_key == key
    assert event.event_type == LifecycleEventType.STARTED
    assert event.target_state == InvocationState.RUNNING
    assert event.actor == "verifier:child"
    assert event.payload["first_action_taken"] is True
    assert isinstance(event.event_id, str)
    assert len(event.event_id) > 0


def test_legal_state_transitions():
    """cp2: LifecycleReducer validates transitions and forbids unauthorized mutations."""
    reducer = LifecycleReducer()
    key = InvocationKey(session="sess-200", phase="back", step="s01", role="verifier", epoch=0)
    owner = "worker:v1"
    parent_actor = "parent:orchestrator"

    record = reducer.launch(key, owner=owner)
    assert record.state == InvocationState.CREATED
    assert record.owner == owner

    # Immutability check: direct modification on InvocationRecord must be impossible
    with pytest.raises((FrozenInstanceError, AttributeError)):
        record.state = InvocationState.RUNNING  # type: ignore[misc]

    # Unauthorized mutation attempt by parent must be rejected
    with pytest.raises(UnauthorizedMutationError):
        reducer.transition(key, InvocationState.RUNNING, actor=parent_actor)

    with pytest.raises(UnauthorizedMutationError):
        reducer.start(key, actor=parent_actor)

    with pytest.raises(UnauthorizedMutationError):
        event = InvocationEvent.create(
            invocation_key=key,
            event_type=LifecycleEventType.STARTED,
            actor=parent_actor,
        )
        reducer.apply_event(event)

    # Illegal transition: created -> passed directly without running
    with pytest.raises(InvalidStateTransitionError):
        reducer.transition(key, InvocationState.PASSED, actor=owner)

    # Legal transition: created -> running
    record = reducer.start(key, actor=owner)
    assert record.state == InvocationState.RUNNING
    assert record.first_action_taken is True

    # Read-only status view for parent
    status = reducer.get_status(key)
    assert isinstance(status, InvocationStatusView)
    assert status.state == InvocationState.RUNNING
    assert status.is_terminal is False
    assert status.owner == owner

    # Legal transition: running -> passed (with receipt)
    receipt = {"verdict": "PASS", "agent_id": "verify-implement"}
    record = reducer.pass_invocation(key, actor=owner, receipt=receipt)
    assert record.state == InvocationState.PASSED
    assert record.is_terminal is True
    assert record.receipt == receipt

    # Terminal state is immutable: transitions out of terminal state must fail
    with pytest.raises(InvalidStateTransitionError):
        reducer.transition(key, InvocationState.RUNNING, actor=owner)

    with pytest.raises(InvalidStateTransitionError):
        reducer.fail_invocation(key, actor=owner, reason="retry attempt")

    with pytest.raises(InvalidStateTransitionError):
        reducer.cancel(key, actor=owner)

    # Verify other terminal transitions from created / running
    for terminal_target in (
        InvocationState.CANCELLED,
        InvocationState.ABORTED_BEFORE_ACTION,
        InvocationState.STALE,
        InvocationState.INFRASTRUCTURE_FAILURE,
        InvocationState.FAILED,
    ):
        r = LifecycleReducer()
        k = InvocationKey(session="s", phase="p", step="st", role="r", epoch=0)
        rec = r.launch(k, owner="w1")
        rec = r.transition(k, terminal_target, actor="w1", reason="test terminalization")
        assert rec.state == terminal_target
        assert rec.is_terminal is True
        # Cannot transition away from terminal
        with pytest.raises(InvalidStateTransitionError):
            r.transition(k, InvocationState.RUNNING, actor="w1")


def test_idempotency_and_epoch_isolation():
    """cp3: Repeated requests return existing invocation; epoch isolation creates new keys."""
    reducer = LifecycleReducer()
    owner = "verifier:gate"

    # 1. Concurrent and sequential requests for the same verifier identity yield 1 invocation and identical ID
    key_epoch0 = InvocationKey(
        session="sess-active",
        phase="back",
        step="s01",
        role="verify-implement",
        epoch=0,
    )

    # Test concurrent race protection: 8 parallel threads
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(reducer.launch, key_epoch0, owner) for _ in range(8)]
        records = [f.result() for f in futures]

    stable_id = records[0].invocation_id
    assert all(r.invocation_id == stable_id for r in records)

    # Transition to RUNNING then PASSED
    reducer.start(key_epoch0, actor=owner)
    receipt_data = {"schema": "loop-gate-verdict/v1", "verdict": "PASS"}
    reducer.pass_invocation(key_epoch0, actor=owner, receipt=receipt_data)

    # Subsequent launch calls return the existing completed invocation without spawning or resetting
    subsequent_launch = reducer.launch(key_epoch0, owner=owner)
    assert subsequent_launch.invocation_id == stable_id
    assert subsequent_launch.state == InvocationState.PASSED
    assert subsequent_launch.receipt == receipt_data

    # 2. Legitimate new epoch creates a new key; old result cannot satisfy it
    key_epoch1 = InvocationKey(
        session="sess-active",
        phase="back",
        step="s01",
        role="verify-implement",
        epoch=1,
    )

    epoch1_record = reducer.launch(key_epoch1, owner=owner)
    assert epoch1_record.invocation_id != stable_id
    assert epoch1_record.state == InvocationState.CREATED
    assert epoch1_record.receipt is None
    assert epoch1_record.is_terminal is False

    # Old result in epoch0 is still intact and separate
    epoch0_status = reducer.get_status(key_epoch0)
    assert epoch0_status.state == InvocationState.PASSED
    assert epoch0_status.receipt == receipt_data

    # Epoch 1 transitions independently
    reducer.start(key_epoch1, actor=owner)
    epoch1_record = reducer.fail_invocation(key_epoch1, actor=owner, reason="Verification failed in epoch 1")
    assert epoch1_record.state == InvocationState.FAILED

    # Epoch 2 creates another distinct invocation
    key_epoch2 = InvocationKey(
        session="sess-active",
        phase="back",
        step="s01",
        role="verify-implement",
        epoch=2,
    )
    epoch2_record = reducer.launch(key_epoch2, owner=owner)
    assert epoch2_record.invocation_id not in (stable_id, epoch1_record.invocation_id)
    assert epoch2_record.state == InvocationState.CREATED
