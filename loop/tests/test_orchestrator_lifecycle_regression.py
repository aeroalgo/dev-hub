"""End-to-end regression test suite for orchestrator lifecycle, idempotency, and crash safety.

Covers FR-001 through FR-006, Acceptance Criteria AC 1-5, and negative constraints AC-:
- FR-001 / AC 1: Launch idempotency with stable invocation ID; 8 concurrent requests yield 1 worker execution.
- FR-002 / AC 2: Owner-only state transitions; parent receives read-only status; crash/TaskStop terminalization.
- FR-003, FR-004 / AC 3: Exhaustive terminal states; empty/pre-action abort yields aborted_before_action with cause and telemetry.
- AC 4: Epoch isolation; new epoch creates new key, rejecting previous epoch receipt.
- FR-005 / AC 5: TodoWrite policy; phase runner enforces start+finish; 3rd request rejected with telemetry diagnostic.
- FR-006 / AC-: Typed await_gate status API; no runtime marker crawl/deletion required.
- Telemetry & Legacy Migration: Aggregate lifecycle metrics and safe legacy_unknown marker migration (never PASSED).
"""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading
import time
import pytest

from harness.hooks.session_resilience import (
    SessionOutcome,
    analyze_session_log,
)
from loop.context_loop import (
    TodoPolicyDecision,
    TodoWritePolicy,
    enforce_phase_todowrite_policy,
    evaluate_todowrite_request,
)
from loop.lifecycle import (
    ALL_STATES,
    LEGACY_UNKNOWN,
    NON_TERMINAL_STATES,
    TERMINAL_STATES,
    GateReceipt,
    InvalidStateTransitionError,
    InvocationEvent,
    InvocationKey,
    InvocationRecord,
    InvocationState,
    InvocationStatusView,
    LegacyMarkerMigrationError,
    LegacyMarkerResult,
    LifecycleEventType,
    LifecycleReducer,
    TodoLifecycleManager,
    UnauthorizedMutationError,
    await_gate,
    bind_receipt,
    create_or_get_invocation,
    get_invocation_status,
    migrate_legacy_marker,
    migrate_legacy_marker_files,
    validate_receipt_epoch,
)
from loop.runtime_adapters.base import (
    GateLaunchRequest,
    GateLaunchResult,
    SessionContext,
)
from loop.runtime_adapters.common import (
    IdempotentGateDispatcher,
    create_invocation_context,
    dispatch_gate_verifier,
)
from loop.telemetry import (
    SCHEMA_TELEMETRY_COMPANION,
    SessionTelemetryCompanion,
    TelemetryAggregator,
    append_companion_record,
    read_companion_records,
    write_companion_records,
)


def test_fr001_ac1_idempotent_dispatch_concurrency():
    """FR-001, AC 1, AC-: 8 concurrent requests for equal verifier identity yield 1 worker execution and identical receipt."""
    reducer = LifecycleReducer()
    dispatcher = IdempotentGateDispatcher(reducer=reducer)

    req = GateLaunchRequest(
        session_id="sess-e2e-reg-01",
        phase="back",
        step="s06",
        role="verify-implement",
        epoch=0,
        owner="orchestrator",
    )

    worker_executions = 0
    lock = threading.Lock()

    def verifier_worker(ctx: SessionContext, invocation_id: str) -> dict:
        nonlocal worker_executions
        with lock:
            worker_executions += 1
        time.sleep(0.04)
        return {
            "verdict": "PASS",
            "agent_id": "verify-implement",
            "evidence_sha256": "abcdef9876543210",
        }

    # Launch 8 concurrent requests
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(dispatcher.dispatch, req, verifier_worker) for _ in range(8)]
        results = [f.result() for f in futures]

    assert worker_executions == 1
    first_id = results[0].invocation_id
    assert all(r.invocation_id == first_id for r in results)
    assert all(r.state == "passed" for r in results)
    assert all(r.receipt is not None for r in results)
    assert all(r.receipt.get("verdict") == "PASS" for r in results)

    # Subsequent request returns existing result without spawning
    cached = dispatcher.dispatch(req, verifier_worker)
    assert worker_executions == 1
    assert cached.invocation_id == first_id
    assert cached.is_new_launch is False


def test_fr002_ac2_owner_transitions_and_crash_terminalization():
    """FR-002, AC 2: Only owner can mutate state; parent gets read-only status; crashes terminalize to STALE."""
    reducer = LifecycleReducer()
    key = InvocationKey(session="sess-e2e-reg-02", phase="back", step="s06", role="verify-implement", epoch=0)
    owner = "worker:gate-verify"

    record = reducer.launch(key, owner=owner, lease_duration_sec=10.0)
    assert record.state == InvocationState.CREATED

    # Parent attempt to mutate must raise UnauthorizedMutationError
    with pytest.raises(UnauthorizedMutationError):
        reducer.transition(key, InvocationState.RUNNING, actor="parent:orchestrator")

    # Read-only status view for parent
    status = reducer.get_status(key)
    assert isinstance(status, InvocationStatusView)
    assert status.state == InvocationState.CREATED

    # Owner transitions to RUNNING
    reducer.start(key, actor=owner)
    assert reducer.get_status(key).state == InvocationState.RUNNING

    # Heartbeat updates timestamp
    hb_record = reducer.heartbeat(key, actor=owner, timestamp=record.created_at + 2.0, lease_duration_sec=5.0)
    assert hb_record.last_heartbeat_at is not None

    # Stale detection terminalizes expired invocation
    stale_record = reducer.reap_stale(
        key,
        actor="orchestrator",
        now=record.created_at + 20.0,
        reason="lease expired: worker heartbeat stopped",
    )
    assert stale_record.state == InvocationState.STALE
    assert reducer.get_status(key).state == InvocationState.STALE

    # Terminal state is frozen: cannot transition to RUNNING or PASSED
    with pytest.raises(InvalidStateTransitionError):
        reducer.transition(key, InvocationState.RUNNING, actor=owner)


def test_fr003_fr004_ac3_exhaustive_terminals_and_pre_action_abort(tmp_path: Path):
    """FR-003, FR-004, AC 3: Exhaustive terminal states, pre-action abort detection, and telemetry logging."""
    reducer = LifecycleReducer()

    # Verify all terminal states are recognized
    assert len(TERMINAL_STATES) == 6
    assert InvocationState.ABORTED_BEFORE_ACTION in TERMINAL_STATES
    assert InvocationState.INFRASTRUCTURE_FAILURE in TERMINAL_STATES
    assert InvocationState.STALE in TERMINAL_STATES
    assert SessionOutcome.ABORTED_BEFORE_ACTION.value == "aborted_before_action"

    # Pre-action abort parsing from crash log using analyze_session_log
    log_file = tmp_path / "crash.log"
    log_file.write_text("ERROR codex::prompt: prompt validation failed before start\n", encoding="utf-8")
    analysis = analyze_session_log(log_file, exit_code=1, runtime="codex")
    assert analysis["first_action_taken"] is False
    assert analysis["aborted_before_action"] is True
    terminal_cause = analysis["reason"] or "prompt validation failed before start"

    key = InvocationKey(session="sess-e2e-reg-03", phase="back", step="s06", role="root", epoch=0)
    rec = reducer.launch(key, owner="orchestrator")

    # Terminalize as ABORTED_BEFORE_ACTION
    aborted_rec = reducer.abort_before_action(
        key,
        actor="orchestrator",
        reason=terminal_cause,
    )
    assert aborted_rec.state == InvocationState.ABORTED_BEFORE_ACTION
    assert aborted_rec.first_action_taken is False
    assert aborted_rec.reason == terminal_cause

    # Record telemetry event companion
    telemetry_file = tmp_path / "events.jsonl"
    companion = SessionTelemetryCompanion.from_invocation_record(
        aborted_rec,
        is_root=True,
        retry_chain_id="chain-e2e-03",
        tool_actions_count=0,
    )
    append_companion_record(telemetry_file, companion)

    assert telemetry_file.exists()
    loaded_records = read_companion_records(telemetry_file)
    assert len(loaded_records) == 1
    assert loaded_records[0].state == InvocationState.ABORTED_BEFORE_ACTION.value
    assert loaded_records[0].first_action_taken is False
    assert loaded_records[0].terminal_reason == terminal_cause


def test_ac3_terminalized_invocation_does_not_respawn_without_new_epoch():
    """AC 3 negative constraint: terminal invocations stay frozen until a new epoch launches."""
    reducer = LifecycleReducer()
    dispatcher = IdempotentGateDispatcher(reducer=reducer)
    request = GateLaunchRequest(
        session_id="sess-e2e-reg-ac3-negative",
        phase="back",
        step="s06",
        role="verify-implement",
        epoch=3,
        owner="orchestrator",
    )
    key = InvocationKey(
        session=request.session_id,
        phase=request.phase,
        step=request.step,
        role=request.role,
        epoch=request.epoch,
    )
    terminal = reducer.launch(key, owner=request.owner)
    terminal = reducer.abort_before_action(
        key,
        actor=request.owner,
        reason="terminalized before verifier launch",
    )
    worker_executions = 0

    def verifier_worker(ctx: SessionContext, invocation_id: str) -> GateReceipt:
        nonlocal worker_executions
        worker_executions += 1
        return GateReceipt(
            invocation_id=invocation_id,
            epoch=ctx.epoch,
            verdict="PASS",
            role=ctx.role or "",
            step=ctx.step or "",
            session=ctx.session_id or "",
            agent_id="verify-implement",
        )

    same_epoch = dispatcher.dispatch(request, verifier_worker)

    assert worker_executions == 0
    assert same_epoch.is_new_launch is False
    assert same_epoch.invocation_id == terminal.invocation_id
    assert reducer.get_status(key).state == InvocationState.ABORTED_BEFORE_ACTION

    new_epoch_request = GateLaunchRequest(
        session_id=request.session_id,
        phase=request.phase,
        step=request.step,
        role=request.role,
        epoch=4,
        owner=request.owner,
    )
    new_epoch = dispatcher.dispatch(new_epoch_request, verifier_worker)

    assert worker_executions == 1
    assert new_epoch.is_new_launch is True
    assert new_epoch.invocation_id != terminal.invocation_id


def test_ac4_epoch_isolation_and_receipt_validation():
    """AC 4: Legitimate new epoch creates a new key; previous epoch receipt is rejected."""
    reducer = LifecycleReducer()
    dispatcher = IdempotentGateDispatcher(reducer=reducer)

    run_counter = 0

    def epoch_worker(ctx: SessionContext, invocation_id: str) -> GateReceipt:
        nonlocal run_counter
        run_counter += 1
        return GateReceipt(
            invocation_id=invocation_id,
            epoch=ctx.epoch,
            verdict="PASS",
            role=ctx.role or "",
            step=ctx.step or "",
            session=ctx.session_id or "",
            agent_id="verify-implement",
        )

    # Epoch 0 dispatch
    req_ep0 = GateLaunchRequest(
        session_id="sess-e2e-reg-04",
        phase="back",
        step="s06",
        role="verify-implement",
        epoch=0,
        owner="orchestrator",
    )
    res_ep0 = dispatcher.dispatch(req_ep0, epoch_worker)
    assert run_counter == 1
    receipt0 = res_ep0.receipt
    assert isinstance(receipt0, GateReceipt)
    assert receipt0.epoch == 0
    assert validate_receipt_epoch(receipt0, 0, expected_invocation_id=res_ep0.invocation_id) is True

    # Validate against Epoch 1 fails
    assert validate_receipt_epoch(receipt0, 1) is False

    # Epoch 1 dispatch creates separate invocation
    req_ep1 = GateLaunchRequest(
        session_id="sess-e2e-reg-04",
        phase="back",
        step="s06",
        role="verify-implement",
        epoch=1,
        owner="orchestrator",
    )
    res_ep1 = dispatcher.dispatch(req_ep1, epoch_worker)
    assert run_counter == 2
    assert res_ep1.invocation_id != res_ep0.invocation_id
    receipt1 = res_ep1.receipt
    assert isinstance(receipt1, GateReceipt)
    assert receipt1.epoch == 1
    assert validate_receipt_epoch(receipt1, 1, expected_invocation_id=res_ep1.invocation_id) is True


def test_todowrite_lifecycle_max_events():
    """FR-005, AC 5: TodoWrite policy allows at most start+finish; third request is rejected as telemetry diagnostic."""
    assert TodoWritePolicy is TodoLifecycleManager
    policy = TodoWritePolicy(phase="IMPLEMENT", max_allowed=2)

    req1 = {"action": "start", "task": "step s06 start"}
    req2 = {"action": "finish", "task": "step s06 finish"}
    req3 = {"action": "update", "task": "step s06 extra mutation"}

    d1 = policy.record_todowrite_request(req1)
    assert d1.allowed is True
    assert d1.call_count == 1

    d2 = policy.record_todowrite_request(req2)
    assert d2.allowed is True
    assert d2.call_count == 2

    # Third request rejected deterministically
    d3 = policy.record_todowrite_request(req3)
    assert d3.allowed is False
    assert d3.call_count == 3
    assert d3.diagnostic is not None
    assert "exceeded" in d3.diagnostic.lower() or "limit" in d3.diagnostic.lower() or "rejected" in d3.diagnostic.lower()

    # Runner helper enforcement
    decisions = enforce_phase_todowrite_policy("IMPLEMENT", [req1, req2, req3], max_allowed=2)
    assert len(decisions) == 3
    assert decisions[0].allowed is True
    assert decisions[1].allowed is True
    assert decisions[2].allowed is False


def test_fr006_await_gate_typed_status_api():
    """FR-006: await_gate returns typed status view with minimal fields without filesystem marker scanning."""
    reducer = LifecycleReducer()
    key = InvocationKey(session="sess-e2e-reg-06", phase="back", step="s06", role="verify-implement", epoch=0)
    owner = "worker:verify"

    reducer.launch(key, owner=owner)
    reducer.start(key, actor=owner)
    receipt = {"verdict": "PASS", "details": "all checks pass", "epoch": 0}
    reducer.pass_invocation(key, actor=owner, receipt=receipt)

    # Typed status query via await_gate
    status = await_gate(key, timeout_sec=1.0, reducer=reducer)
    assert status is not None
    assert isinstance(status, InvocationStatusView)
    assert status.state == InvocationState.PASSED
    assert status.is_terminal is True
    assert status.receipt == receipt

    # Also query by invocation ID string
    inv_id = status.invocation_id
    status_by_id = await_gate(inv_id, timeout_sec=1.0, reducer=reducer)
    assert status_by_id is not None
    assert status_by_id.invocation_id == inv_id
    assert status_by_id.state == InvocationState.PASSED


def test_telemetry_migration_and_aggregates(tmp_path: Path):
    """Telemetry companion aggregation and safe legacy marker migration (never PASSED)."""
    # 1. Aggregate metrics tracking
    aggregator = TelemetryAggregator()
    aggregator.record_duplicate_suppressed(key_or_id="sess-1:back:s01:v:0", count=2)

    reducer = LifecycleReducer()
    k1 = InvocationKey(session="sess-tele-1", phase="back", step="s06", role="orch", epoch=0)
    r1 = reducer.launch(k1, owner="orch")
    reducer.start(k1, actor="orch")
    r1 = reducer.pass_invocation(k1, actor="orch", receipt={"verdict": "PASS", "epoch": 0})
    aggregator.record_invocation(r1, is_root=True, tool_actions_count=2)

    k2 = InvocationKey(session="sess-tele-2", phase="back", step="s06", role="orch", epoch=0)
    r2 = reducer.launch(k2, owner="orch")
    r2 = reducer.abort_before_action(k2, actor="orch", reason="syntax error")
    aggregator.record_invocation(r2, is_root=True, tool_actions_count=0)

    aggregator.record_legacy_marker()

    summary = aggregator.to_dict()
    assert summary["duplicate_suppressed"] == 2
    assert summary["total_sessions"] == 2
    assert summary["zero_action_sessions"] == 1
    assert summary["legacy_unknown_count"] == 1
    assert summary["terminal_by_state"]["passed"] == 1
    assert summary["terminal_by_state"]["aborted_before_action"] == 1

    # 2. Legacy marker ingestion: converts to legacy_unknown, never PASSED
    marker_file = tmp_path / "legacy.marker"
    marker_file.write_text('{"verdict":"PASS","status":"ok","step":"s06","session":"sess-leg-01"}', encoding="utf-8")

    result = migrate_legacy_marker(marker_file)
    assert result.diagnostic_status == LEGACY_UNKNOWN
    assert result.is_passed is False
    assert result.migrated_state == InvocationState.FAILED

    # Ingestion via reducer
    inv_rec, leg_res = reducer.ingest_legacy_marker(marker_file)
    assert inv_rec.state == InvocationState.FAILED
    assert leg_res.diagnostic_status == LEGACY_UNKNOWN
    assert leg_res.is_passed is False

    # Illegal attempt to convert to PASSED must raise LegacyMarkerMigrationError
    with pytest.raises(LegacyMarkerMigrationError):
        LegacyMarkerResult(
            source="bad_marker",
            is_passed=True,
            migrated_state=InvocationState.PASSED,
        )


@pytest.mark.parametrize(
    "invalid_epoch",
    ["not-an-int", -1, 1.2, True, False, "1.2", object()],
)
def test_legacy_marker_invalid_epoch_fails_closed(invalid_epoch):
    marker = {"session": "sess-leg-invalid-epoch", "epoch": invalid_epoch}

    with pytest.raises(LegacyMarkerMigrationError):
        migrate_legacy_marker(marker)

    with pytest.raises(LegacyMarkerMigrationError):
        LifecycleReducer().ingest_legacy_marker(marker)


@pytest.mark.parametrize("valid_epoch", [0, 1, 42, "0", "1", "42"])
def test_legacy_marker_valid_epoch_accepted(valid_epoch):
    marker = {"session": "sess-leg-valid-epoch", "epoch": valid_epoch}
    result = migrate_legacy_marker(marker)
    assert result.diagnostic_status == LEGACY_UNKNOWN
    record, _ = LifecycleReducer().ingest_legacy_marker(marker)
    assert record.key.epoch == int(valid_epoch)


def test_bugfix_start_does_not_mark_first_action_taken():
    """BUGFIX regression: start() transitions to RUNNING without marking first_action_taken=True."""
    reducer = LifecycleReducer()
    key = InvocationKey(session="sess-bgfix-01", phase="back", step="s06", role="verify-implement", epoch=0)
    owner = "worker:verify"

    # Launch creates invocation in CREATED state with first_action_taken=False
    rec = reducer.launch(key, owner=owner)
    assert rec.state == InvocationState.CREATED
    assert rec.first_action_taken is False
    assert rec.first_action_at is None

    # Start transitions to RUNNING; first_action_taken MUST remain False
    rec_running = reducer.start(key, actor=owner)
    assert rec_running.state == InvocationState.RUNNING
    assert rec_running.first_action_taken is False
    assert rec_running.first_action_at is None

    # Abort before action is legal while first_action_taken is False
    rec_aborted = reducer.abort_before_action(key, actor=owner, reason="early cancellation")
    assert rec_aborted.state == InvocationState.ABORTED_BEFORE_ACTION
    assert rec_aborted.first_action_taken is False

    # Second invocation: recording first action prevents subsequent abort_before_action
    key2 = InvocationKey(session="sess-bgfix-02", phase="back", step="s06", role="verify-implement", epoch=0)
    reducer.launch(key2, owner=owner)
    reducer.start(key2, actor=owner)
    t_action = 12345.67
    rec_acted = reducer.record_first_action(key2, actor=owner, timestamp=t_action)
    assert rec_acted.first_action_taken is True
    assert rec_acted.first_action_at == t_action

    with pytest.raises(InvalidStateTransitionError):
        reducer.abort_before_action(key2, actor=owner, reason="too late")


def test_bugfix_bind_receipt_and_validate_receipt_epoch_rejects_untagged_dicts():
    """BUGFIX regression: bind_receipt() and validate_receipt_epoch() reject untagged dicts and enforce epoch isolation."""
    reducer = LifecycleReducer()
    key = InvocationKey(session="sess-bgfix-03", phase="back", step="s06", role="verify-implement", epoch=0)
    owner = "worker:verify"

    rec = reducer.launch(key, owner=owner)
    reducer.start(key, actor=owner)
    inv_id = rec.invocation_id

    # 1. validate_receipt_epoch rejects None, untagged dicts, non-int epoch, and mismatched invocation_id
    assert validate_receipt_epoch(None, 0) is False
    assert validate_receipt_epoch({}, 0) is False
    assert validate_receipt_epoch({"verdict": "PASS"}, 0) is False
    assert validate_receipt_epoch({"epoch": None, "verdict": "PASS"}, 0) is False
    assert validate_receipt_epoch({"epoch": "not_an_int", "verdict": "PASS"}, 0) is False
    assert validate_receipt_epoch({"epoch": 1, "verdict": "PASS"}, 0) is False
    assert validate_receipt_epoch({"epoch": 0, "verdict": "PASS"}, 0) is True

    # When expected_invocation_id is provided, untagged invocation_id is rejected
    assert validate_receipt_epoch({"epoch": 0, "verdict": "PASS"}, 0, expected_invocation_id=inv_id) is False
    assert validate_receipt_epoch({"epoch": 0, "invocation_id": "other_id", "verdict": "PASS"}, 0, expected_invocation_id=inv_id) is False
    assert validate_receipt_epoch({"epoch": 0, "invocation_id": inv_id, "verdict": "PASS"}, 0, expected_invocation_id=inv_id) is True

    # 2. bind_receipt rejects untagged dicts
    with pytest.raises(InvalidStateTransitionError):
        bind_receipt(key, {"verdict": "PASS"}, actor=owner, reducer=reducer)

    # bind_receipt rejects mismatched epoch dict
    with pytest.raises(InvalidStateTransitionError):
        bind_receipt(key, {"epoch": 1, "invocation_id": inv_id, "verdict": "PASS"}, actor=owner, reducer=reducer)

    # bind_receipt accepts properly tagged receipt
    bound = bind_receipt(key, {"epoch": 0, "invocation_id": inv_id, "verdict": "PASS"}, actor=owner, reducer=reducer)
    assert bound.state == InvocationState.PASSED
    assert bound.receipt["epoch"] == 0
    assert bound.receipt["invocation_id"] == inv_id


def test_bugfix_zero_tool_session_exit_0_classified_as_aborted_before_action(tmp_path: Path):
    """AC+3: zero-tool session with exit_code=0 is classified as aborted_before_action, not clean."""
    from harness.hooks.session_resilience import analyze_session_log, SessionContext, SessionOutcome
    from loop.context_loop import _append_terminal_session_companion

    # Log with 0 tool events (only session metadata / raw text)
    log_content = """2026-09-10T12:00:00.000000+00:00 [wrapper] SESSION_START
Starting session...
Thinking about the problem...
I am done.
2026-09-10T12:00:05.000000+00:00 [wrapper] SESSION_END
"""
    log_file = tmp_path / "empty_session.log"
    log_file.write_text(log_content, encoding="utf-8")

    ctx = SessionContext(
        prompt="test prompt",
        phase="back",
        step="s03",
        role="root",
        epoch=0,
    )
    result = analyze_session_log(log_file, exit_code=0, phase="back")
    assert result["first_action_taken"] is False
    assert result["outcome"] == SessionOutcome.ABORTED_BEFORE_ACTION.value
    assert result["aborted"] is True
    assert result["aborted_before_action"] is True
    assert result["reason"] is not None
    assert len(result["reason"].strip()) > 0

    # Verify companion terminal state is aborted_before_action, not passed
    state = {
        "session_id": "sess-zero-tool-1",
        "loop_phase": "back",
        "armed_step": "s03",
        "role": "root",
        "epoch": 0,
        "evidence_dir": str(tmp_path),
    }
    companion_path = _append_terminal_session_companion(
        tmp_path,
        state,
        result,
        reason=result.get("reason"),
    )
    from loop.telemetry import read_companion_records
    records = read_companion_records(companion_path)
    assert len(records) == 1
    assert records[0].terminal_state == "aborted_before_action"
    assert records[0].first_action_taken is False
    assert records[0].is_zero_action is True
    assert records[0].terminal_reason is not None


def test_bugfix_pass_invocation_rejects_untagged_receipt():
    """AC+4: pass_invocation strictly validates receipt epoch and rejects untagged receipt."""
    reducer = LifecycleReducer()
    owner = "worker:gate"
    key = InvocationKey(session="sess-untagged-rcpt", phase="back", step="s02", role="worker", epoch=1)

    reducer.launch(key, owner=owner)
    reducer.start(key, actor=owner)

    # Untagged receipt dict without 'epoch' is rejected
    with pytest.raises(InvalidStateTransitionError, match="epoch mismatch or untagged receipt"):
        reducer.pass_invocation(key, actor=owner, receipt={"verdict": "PASS"})

    # Receipt with wrong epoch is rejected
    with pytest.raises(InvalidStateTransitionError, match="epoch mismatch or untagged receipt"):
        reducer.pass_invocation(key, actor=owner, receipt={"verdict": "PASS", "epoch": 0})

    # Receipt with matching epoch is accepted
    passed_rec = reducer.pass_invocation(key, actor=owner, receipt={"verdict": "PASS", "epoch": 1})
    assert passed_rec.state == InvocationState.PASSED
    assert passed_rec.receipt["epoch"] == 1


def test_bugfix_task_stop_defaults_to_stale_and_no_checkpoint_cleared(tmp_path: Path):
    """AC+2: TaskStop defaults to stale and record_abort does not clear checkpoint on terminal failure."""
    reducer = LifecycleReducer()
    owner = "orchestrator"
    key = InvocationKey(session="sess-stop-stale", phase="back", step="s03", role="worker", epoch=0)

    reducer.launch(key, owner=owner)
    reducer.start(key, actor=owner)

    # TaskStop defaults to STALE
    stopped = reducer.handle_task_stop(key, actor=owner)
    assert stopped.state == InvocationState.STALE
    assert stopped.is_terminal is True

    # Check record_abort preserves checkpoint
    from loop.context_loop import record_abort
    from harness.hooks.epic.core import commit_checkpoint, load_checkpoint

    # Setup epic state with checkpoint
    (tmp_path / ".epic").mkdir(parents=True, exist_ok=True)
    commit_checkpoint(tmp_path, checkpoint_id="cp-1", session_id="sess-1", step_id="s03", phase="back", stage="prepared", status="active", next_action="invoke", resume_policy="same_step")
    assert load_checkpoint(tmp_path) is not None

    log_path = tmp_path / "run.log"
    log_path.write_text("process killed\n", encoding="utf-8")

    from harness.hooks.epic.core import save_epic_state
    save_epic_state(tmp_path, {"armed_step": "s03", "armed_epic": "T-HUB-079", "status": "infrastructure_failure", "active": True})

    record_abort(
        cwd=tmp_path,
        log_path=log_path,
        exit_code=1,
        runtime="codex",
    )

    # Verify checkpoint is NOT cleared on terminal path
    cp = load_checkpoint(tmp_path)
    assert cp is not None
    assert cp.get("step_id") == "s03"


def test_bugfix_task_stop_event_type_maps_to_stale():
    """AC+2: LifecycleEventType.TASK_STOP maps to InvocationState.STALE in EVENT_TYPE_TO_TARGET_STATE and reducer.apply_event."""
    from loop.lifecycle import EVENT_TYPE_TO_TARGET_STATE, InvocationEvent, LifecycleEventType, LifecycleReducer, InvocationKey, InvocationState

    assert EVENT_TYPE_TO_TARGET_STATE[LifecycleEventType.TASK_STOP] == InvocationState.STALE

    reducer = LifecycleReducer()
    owner = "worker:verify"
    key = InvocationKey(session="sess-stop-event", phase="back", step="s02", role="worker", epoch=0)

    reducer.launch(key, owner=owner)
    reducer.start(key, actor=owner)

    event = InvocationEvent.create(
        invocation_key=key,
        event_type=LifecycleEventType.TASK_STOP,
        actor="orchestrator",
        reason="TaskStop: test interrupt",
    )
    assert event.target_state == InvocationState.STALE

    record = reducer.apply_event(event)
    assert record.state == InvocationState.STALE
    assert record.is_terminal is True
    assert record.events[-1].event_type == LifecycleEventType.TASK_STOP


def test_task_stop_rejects_cancelled_target_state():
    reducer = LifecycleReducer()
    owner = "worker:verify"
    key = InvocationKey(session="sess-stop-guard", phase="back", step="s02", role="worker", epoch=0)

    reducer.launch(key, owner=owner)
    reducer.start(key, actor=owner)

    with pytest.raises(InvalidStateTransitionError, match="must transition.*STALE"):
        reducer.handle_task_stop(key, actor=owner, target_state=InvocationState.CANCELLED)
    assert reducer.get_status(key).state == InvocationState.RUNNING

    with pytest.raises(InvalidStateTransitionError, match="must transition.*STALE"):
        reducer.task_stop(key, actor=owner, target_state="cancelled")
    assert reducer.get_status(key).state == InvocationState.RUNNING
