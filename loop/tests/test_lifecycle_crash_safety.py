"""Tests for reducer-owned terminalization, lease expiry, crash safety, and pre-action abort telemetry."""

from __future__ import annotations

import json
from pathlib import Path
import time
import pytest

from harness.hooks.session_resilience import (
    SessionOutcome,
    analyze_session_log,
    load_last_session,
    write_last_session,
)
from loop.lifecycle import (
    InvalidStateTransitionError,
    InvocationKey,
    InvocationRecord,
    InvocationState,
    LifecycleEventType,
    LifecycleReducer,
    UnauthorizedMutationError,
)


def test_lease_expiry_stale_transition() -> None:
    """cp1: Lease expiry or process crash deterministically transitions invocation to stale/infrastructure_failure."""
    reducer = LifecycleReducer()
    owner = "worker:engine-1"
    key = InvocationKey(session="sess-crash-1", phase="back", step="s03", role="worker", epoch=0)

    # 1. Launch with owner lease duration
    record = reducer.launch(key, owner=owner, lease_duration_sec=10.0)
    assert record.state == InvocationState.CREATED
    assert record.lease_duration_sec == 10.0
    assert record.lease_expires_at is not None
    assert record.is_lease_expired(now=record.created_at + 5.0) is False
    assert record.is_lease_expired(now=record.created_at + 15.0) is True

    # 2. Transition to RUNNING and send heartbeat
    reducer.start(key, actor=owner)
    hb_time = record.created_at + 8.0
    hb_record = reducer.heartbeat(key, actor=owner, timestamp=hb_time, lease_duration_sec=10.0)
    assert hb_record.last_heartbeat_at == hb_time
    assert hb_record.lease_expires_at == hb_time + 10.0
    assert hb_record.is_lease_expired(now=hb_time + 5.0) is False
    assert hb_record.is_lease_expired(now=hb_time + 12.0) is True

    # 3. Check lease expiration and reap stale
    expiry_time = hb_time + 15.0
    assert reducer.check_lease_expired(key, now=expiry_time) is True

    stale_record = reducer.reap_stale(
        key,
        actor="orchestrator",
        now=expiry_time,
        reason="lease expired: worker heartbeat stopped",
    )
    assert stale_record.state == InvocationState.STALE
    assert stale_record.is_terminal is True
    assert "lease expired" in (stale_record.reason or "")

    # Terminal state forbids further transitions
    with pytest.raises(InvalidStateTransitionError):
        reducer.start(key, actor=owner)

    with pytest.raises(InvalidStateTransitionError):
        reducer.heartbeat(key, actor=owner)

    # Re-launch with same key returns existing stale invocation (no duplicate spawn, no marker deletion needed)
    relaunch = reducer.launch(key, owner=owner)
    assert relaunch.invocation_id == stale_record.invocation_id
    assert relaunch.state == InvocationState.STALE
    assert relaunch.is_terminal is True

    # 4. Test reaper batch sweep
    r2 = LifecycleReducer()
    k1 = InvocationKey(session="s-sweep-1", phase="back", step="s03", role="w1", epoch=0)
    k2 = InvocationKey(session="s-sweep-2", phase="back", step="s03", role="w2", epoch=0)
    r2.launch(k1, owner="w1", lease_duration_sec=5.0)
    r2.launch(k2, owner="w2", lease_duration_sec=100.0)

    reaped = r2.reap_stale_invocations(now=time.time() + 10.0, actor="orchestrator:reaper")
    assert len(reaped) == 1
    assert reaped[0].key == k1
    assert reaped[0].state == InvocationState.STALE
    assert r2.get_status(k2).state == InvocationState.CREATED

    # 5. Test crash handling without stop event
    k_crash = InvocationKey(session="s-crash-proc", phase="back", step="s03", role="w-crash", epoch=0)
    r2.launch(k_crash, owner="w-crash")
    r2.start(k_crash, actor="w-crash")

    crashed = r2.handle_crash(
        k_crash,
        actor="orchestrator",
        reason="process crash: sigkill without stop event",
    )
    assert crashed.state == InvocationState.INFRASTRUCTURE_FAILURE
    assert crashed.is_terminal is True
    assert crashed.reason == "process crash: sigkill without stop event"


def test_task_stop_terminalization() -> None:
    """cp2: TaskStop event cleanly terminalizes invocation and prevents uncontrolled restart loops."""
    reducer = LifecycleReducer()
    owner = "worker:task-runner"
    key = InvocationKey(session="sess-stop-1", phase="back", step="s03", role="worker", epoch=0)

    # 1. Launch and start invocation
    record = reducer.launch(key, owner=owner)
    record = reducer.start(key, actor=owner)
    assert record.state == InvocationState.RUNNING

    # 2. TaskStop arrives via handle_task_stop and task_stop methods
    stopped_record = reducer.handle_task_stop(
        key,
        actor="orchestrator",
        reason="TaskStop: cancelled by user request",
    )
    assert stopped_record.state == InvocationState.STALE
    assert stopped_record.is_terminal is True
    assert stopped_record.reason == "TaskStop: cancelled by user request"

    # Also test direct task_stop alias method
    k_stop2 = InvocationKey(session="sess-stop-2", phase="back", step="s03", role="worker", epoch=0)
    reducer.launch(k_stop2, owner=owner)
    reducer.start(k_stop2, actor=owner)
    stopped2 = reducer.task_stop(k_stop2, actor="orchestrator", reason="TaskStop: interrupt signal")
    assert stopped2.state == InvocationState.STALE
    assert stopped2.is_terminal is True
    assert stopped2.reason == "TaskStop: interrupt signal"

    # Verify event history contains task_stop event
    event_types = [e.event_type for e in stopped_record.events]
    assert LifecycleEventType.TASK_STOP in event_types

    # 3. Subsequent restart attempt on the same key is prevented
    with pytest.raises(InvalidStateTransitionError):
        reducer.start(key, actor=owner)

    with pytest.raises(InvalidStateTransitionError):
        reducer.pass_invocation(key, actor=owner)

    # Re-launch returns the terminal STALE record
    idempotent_get = reducer.launch(key, owner=owner)
    assert idempotent_get.invocation_id == stopped_record.invocation_id
    assert idempotent_get.state == InvocationState.STALE

    # 4. Legitimate new epoch is isolated from the stopped invocation
    new_epoch_key = InvocationKey(session="sess-stop-1", phase="back", step="s03", role="worker", epoch=1)
    new_record = reducer.launch(new_epoch_key, owner=owner)
    assert new_record.invocation_id != stopped_record.invocation_id
    assert new_record.state == InvocationState.CREATED
    assert new_record.is_terminal is False


def test_aborted_before_action_telemetry(tmp_path: Path) -> None:
    """cp3: Root session terminated before first action records aborted_before_action and non-empty cause."""
    # 0. Test SessionOutcome enum variants
    assert SessionOutcome.ABORTED_BEFORE_ACTION.value == "aborted_before_action"
    assert SessionOutcome.STALE.value == "stale"
    assert SessionOutcome.INFRASTRUCTURE_FAILURE.value == "infrastructure_failure"

    reducer = LifecycleReducer()
    owner = "worker:root"
    key = InvocationKey(session="sess-pre-action", phase="back", step="s03", role="root", epoch=0)

    # 1. Empty root session created but aborted before any tool action
    record = reducer.launch(key, owner=owner)
    assert record.state == InvocationState.CREATED
    assert record.first_action_taken is False
    assert record.first_action_at is None

    # Abort before action with empty or None reason gets non-empty default
    aborted_record = reducer.abort_before_action(
        key,
        actor="orchestrator",
        reason="prompt dies before action: unhandled syntax error",
    )
    assert aborted_record.state == InvocationState.ABORTED_BEFORE_ACTION
    assert aborted_record.is_terminal is True
    assert aborted_record.first_action_taken is False
    assert aborted_record.first_action_at is None
    assert aborted_record.reason == "prompt dies before action: unhandled syntax error"

    # Empty reason fallback
    k_empty_reason = InvocationKey(session="sess-empty-reason", phase="back", step="s03", role="root", epoch=0)
    reducer.launch(k_empty_reason, owner=owner)
    aborted_default = reducer.abort_before_action(k_empty_reason, actor="orchestrator", reason=None)
    assert aborted_default.reason is not None
    assert len(aborted_default.reason.strip()) > 0

    # 2. Session with action taken records first_action_at and first_action_taken=True
    k_active = InvocationKey(session="sess-took-action", phase="back", step="s03", role="root", epoch=0)
    reducer.launch(k_active, owner=owner)
    t_action = 1000.0
    active_record = reducer.record_first_action(k_active, actor=owner, timestamp=t_action)
    assert active_record.first_action_taken is True
    assert active_record.first_action_at == t_action
    assert active_record.state == InvocationState.RUNNING

    # 3. Test session_resilience log analysis for zero-tool session
    zero_tool_log = tmp_path / "zero_tool_session.log"
    zero_tool_log.write_text(
        "SESSION_START session=s-zero mode=headless command=codex\n"
        "ERROR codex::prompt: prompt validation failed before start\n"
        "SESSION_END session=s-zero exit_code=1 elapsed=0.2s\n",
        encoding="utf-8",
    )

    analysis = analyze_session_log(zero_tool_log, exit_code=1, runtime="codex")
    assert analysis["aborted"] is True
    assert analysis["first_action_taken"] is False
    assert analysis["aborted_before_action"] is True
    assert analysis["reason"] is not None
    assert len(analysis["reason"].strip()) > 0

    # Test session_resilience log analysis for session WITH tool action
    tool_log = tmp_path / "tool_session.log"
    tool_log.write_text(
        "SESSION_START session=s-tool mode=headless command=codex\n"
        '{"type":"item.started","item":{"type":"command_execution","id":"cmd-1"}}\n'
        '{"type":"item.completed","item":{"type":"command_execution","status":"completed"}}\n'
        "SESSION_END session=s-tool exit_code=1 elapsed=1.5s\n",
        encoding="utf-8",
    )

    analysis_with_tools = analyze_session_log(tool_log, exit_code=1, runtime="codex")
    assert analysis_with_tools["aborted"] is True
    assert analysis_with_tools["first_action_taken"] is True
    assert analysis_with_tools["aborted_before_action"] is False

    # 4. Persistence in write_last_session and load_last_session with SessionOutcome variants
    for outcome_val in (
        SessionOutcome.ABORTED_BEFORE_ACTION.value,
        SessionOutcome.STALE.value,
        SessionOutcome.INFRASTRUCTURE_FAILURE.value,
    ):
        marker_path = write_last_session(
            tmp_path,
            track="epic",
            status="aborted",
            outcome=outcome_val,
            reason=f"test outcome {outcome_val}",
            step_id="s03",
            plan_id="T-HUB-079",
            first_action_taken=False,
            first_action_at=None,
        )
        loaded = load_last_session(tmp_path, track="epic")
        assert loaded is not None
        assert loaded["outcome"] == outcome_val
        assert loaded["first_action_taken"] is False
        assert loaded["reason"] == f"test outcome {outcome_val}"
        assert loaded["step_id"] == "s03"
