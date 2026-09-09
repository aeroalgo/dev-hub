"""Unit tests for idempotent gate/verifier dispatch, epoch isolation, and receipt linkage."""

from concurrent.futures import ThreadPoolExecutor
import threading
import time
import pytest

from loop.lifecycle import (
    GateReceipt,
    InvocationKey,
    InvocationState,
    LifecycleReducer,
    bind_receipt,
    create_or_get_invocation,
    get_invocation_status,
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


def test_stable_invocation_id_pre_launch():
    """cp1: Dispatcher invokes create_or_get_invocation, returning stable invocation_id pre-launch."""
    reducer = LifecycleReducer()
    session_id = "sess-dispatch-01"
    phase = "back"
    step = "s02"
    role = "verify-implement"
    epoch = 0

    # 1. create_or_get_invocation directly yields stable invocation_id in CREATED state
    key = InvocationKey(session=session_id, phase=phase, step=step, role=role, epoch=epoch)
    record, is_new = create_or_get_invocation(key, owner="orchestrator", reducer=reducer)

    assert is_new is True
    assert record.state == InvocationState.CREATED
    assert record.invocation_id.startswith("inv-")
    stable_id = record.invocation_id

    # 2. Repeated call returns same invocation_id and is_new is False
    record2, is_new2 = create_or_get_invocation(key, owner="orchestrator", reducer=reducer)
    assert is_new2 is False
    assert record2.invocation_id == stable_id
    assert record2.state == InvocationState.CREATED

    # 3. get_invocation_status returns read-only status view with matching fields
    status = get_invocation_status(key, reducer=reducer)
    assert status is not None
    assert status.invocation_id == stable_id
    assert status.state == InvocationState.CREATED
    assert status.is_terminal is False

    # Also check get_invocation_status by invocation_id
    status_by_id = get_invocation_status(stable_id, reducer=reducer)
    assert status_by_id is not None
    assert status_by_id.invocation_id == stable_id

    # 4. create_invocation_context creates SessionContext with stable invocation_id and epoch
    ctx, inv_id, is_new3 = create_invocation_context(
        session_id=session_id,
        phase=phase,
        step=step,
        role=role,
        epoch=epoch,
        prompt="verify prompt",
        reducer=reducer,
    )
    assert is_new3 is False
    assert inv_id == stable_id
    assert ctx.invocation_id == stable_id
    assert ctx.epoch == epoch
    assert ctx.session_id == session_id
    assert ctx.phase == phase
    assert ctx.step == step
    assert ctx.role == role


def test_eight_concurrent_launches_single_worker():
    """cp2: Eight concurrent/sequential launch requests for same verifier yield 1 worker execution and shared receipt."""
    reducer = LifecycleReducer()
    dispatcher = IdempotentGateDispatcher(reducer=reducer)

    request = GateLaunchRequest(
        session_id="sess-concurrent-02",
        phase="back",
        step="s02",
        role="verify-implement",
        epoch=0,
        owner="orchestrator",
    )

    execution_count = 0
    lock = threading.Lock()

    def dummy_worker(ctx: SessionContext, invocation_id: str) -> dict:
        nonlocal execution_count
        with lock:
            execution_count += 1
        time.sleep(0.05)
        return {
            "verdict": "PASS",
            "agent_id": "verify-implement",
            "evidence_sha256": "abcdef123456",
        }

    # Run 8 concurrent dispatch requests
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            executor.submit(dispatcher.dispatch, request, dummy_worker)
            for _ in range(8)
        ]
        results = [f.result() for f in futures]

    # Exactly one execution across all 8 requests
    assert execution_count == 1

    # All 8 results must share the exact same invocation_id, state, and receipt
    first_id = results[0].invocation_id
    assert all(r.invocation_id == first_id for r in results)
    assert all(r.state == "passed" for r in results)
    assert all(r.receipt is not None for r in results)
    assert all(r.receipt.get("verdict") == "PASS" for r in results)
    assert all(r.receipt.get("epoch") == 0 for r in results)
    assert all(r.receipt.get("invocation_id") == first_id for r in results)

    # Subsequent sequential dispatch request also immediately returns the same completed receipt
    subsequent_result = dispatcher.dispatch(request, dummy_worker)
    assert execution_count == 1  # Still 1, worker was not run again
    assert subsequent_result.invocation_id == first_id
    assert subsequent_result.is_new_launch is False
    assert subsequent_result.state == "passed"
    assert subsequent_result.receipt["verdict"] == "PASS"


def test_receipt_epoch_isolation():
    """cp3: Receipt contains invocation_id and epoch; epoch change rejects old receipt and starts new cycle."""
    reducer = LifecycleReducer()
    dispatcher = IdempotentGateDispatcher(reducer=reducer)

    execution_count = 0

    def worker_epoch(ctx: SessionContext, invocation_id: str) -> GateReceipt:
        nonlocal execution_count
        execution_count += 1
        return GateReceipt(
            invocation_id=invocation_id,
            epoch=ctx.epoch,
            verdict="PASS",
            role=ctx.role or "",
            step=ctx.step or "",
            session=ctx.session_id or "",
            agent_id="verify-implement",
        )

    # 1. Launch in epoch 0
    req_epoch0 = GateLaunchRequest(
        session_id="sess-epoch-03",
        phase="back",
        step="s02",
        role="verify-implement",
        epoch=0,
        owner="orchestrator",
    )

    res_epoch0 = dispatcher.dispatch(req_epoch0, worker_epoch)
    assert execution_count == 1
    assert res_epoch0.state == "passed"
    receipt0 = res_epoch0.receipt
    assert isinstance(receipt0, GateReceipt)
    assert receipt0.epoch == 0
    assert receipt0.invocation_id == res_epoch0.invocation_id
    assert receipt0.verdict == "PASS"

    # Receipt validation helper tests
    assert validate_receipt_epoch(receipt0, 0, expected_invocation_id=res_epoch0.invocation_id) is True
    # Receipt from epoch 0 is rejected when validated against epoch 1
    assert validate_receipt_epoch(receipt0, 1) is False
    assert validate_receipt_epoch(receipt0, 0, expected_invocation_id="inv-wrong-id") is False

    # 2. Re-dispatch in epoch 0 returns existing result without re-running worker
    res_epoch0_cached = dispatcher.dispatch(req_epoch0, worker_epoch)
    assert execution_count == 1
    assert res_epoch0_cached.invocation_id == res_epoch0.invocation_id
    assert res_epoch0_cached.is_new_launch is False

    # 3. Launch in epoch 1 -> old receipt cannot satisfy it; new cycle starts
    req_epoch1 = GateLaunchRequest(
        session_id="sess-epoch-03",
        phase="back",
        step="s02",
        role="verify-implement",
        epoch=1,
        owner="orchestrator",
    )

    res_epoch1 = dispatcher.dispatch(req_epoch1, worker_epoch)
    assert execution_count == 2
    assert res_epoch1.state == "passed"
    assert res_epoch1.invocation_id != res_epoch0.invocation_id
    assert res_epoch1.is_new_launch is True

    receipt1 = res_epoch1.receipt
    assert isinstance(receipt1, GateReceipt)
    assert receipt1.epoch == 1
    assert receipt1.invocation_id == res_epoch1.invocation_id

    # Receipt 1 validates for epoch 1 but fails for epoch 0
    assert validate_receipt_epoch(receipt1, 1, expected_invocation_id=res_epoch1.invocation_id) is True
    assert validate_receipt_epoch(receipt1, 0) is False

    # Epoch 0 record in reducer remains intact and unchanged
    epoch0_status = reducer.get_status(req_epoch0.invocation_key)
    assert epoch0_status is not None
    assert epoch0_status.state == InvocationState.PASSED
    assert epoch0_status.receipt.epoch == 0
    assert epoch0_status.invocation_id == res_epoch0.invocation_id

    # Epoch 1 record in reducer is also intact
    epoch1_status = reducer.get_status(req_epoch1.invocation_key)
    assert epoch1_status is not None
    assert epoch1_status.state == InvocationState.PASSED
    assert epoch1_status.receipt.epoch == 1
    assert epoch1_status.invocation_id == res_epoch1.invocation_id

    # 4. bind_receipt rejects mismatched epoch receipt
    with pytest.raises(Exception):
        bind_receipt(
            req_epoch1.invocation_key,
            receipt_data=receipt0,
            actor="orchestrator",
            reducer=reducer,
        )
