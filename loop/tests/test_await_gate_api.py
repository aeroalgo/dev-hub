"""Unit tests for typed parent gate status API (await_gate and get_invocation_status)."""

from concurrent.futures import ThreadPoolExecutor
import threading
import time
import pytest

from loop.lifecycle import (
    InvocationKey,
    InvocationState,
    InvocationStatusView,
    LifecycleReducer,
    await_gate,
    create_or_get_invocation,
    get_invocation_status,
)


def test_typed_status_lookup():
    """cp1: Functions await_gate and get_invocation_status return typed status without filesystem scans."""
    reducer = LifecycleReducer()
    session_id = "sess-await-01"
    phase = "back"
    step = "s04"
    role = "verify-implement"
    epoch = 0

    key = InvocationKey(session=session_id, phase=phase, step=step, role=role, epoch=epoch)
    record, is_new = create_or_get_invocation(key, owner="worker:gate-1", reducer=reducer)
    assert is_new is True
    inv_id = record.invocation_id

    # 1. get_invocation_status returns typed InvocationStatusView by key and by invocation_id
    status_by_key = get_invocation_status(key, reducer=reducer)
    assert status_by_key is not None
    assert isinstance(status_by_key, InvocationStatusView)
    assert status_by_key.invocation_id == inv_id
    assert status_by_key.key == key.key
    assert status_by_key.state == InvocationState.CREATED
    assert status_by_key.is_terminal is False
    assert status_by_key.owner == "worker:gate-1"
    assert status_by_key.receipt is None
    assert status_by_key.reason is None

    status_by_id = get_invocation_status(inv_id, reducer=reducer)
    assert status_by_id is not None
    assert status_by_id == status_by_key

    # Non-existent key or ID returns None
    assert get_invocation_status("non-existent-inv-id", reducer=reducer) is None
    assert get_invocation_status(InvocationKey(session="s", phase="p", step="st", role="r", epoch=99), reducer=reducer) is None

    # 2. await_gate with timeout on non-terminal invocation returns current status view
    status_timed_out = await_gate(key, timeout_sec=0.05, poll_interval_sec=0.01, reducer=reducer)
    assert status_timed_out is not None
    assert isinstance(status_timed_out, InvocationStatusView)
    assert status_timed_out.is_terminal is False
    assert status_timed_out.state == InvocationState.CREATED

    # 3. await_gate with background transition to terminal PASSED
    def background_worker():
        time.sleep(0.05)
        reducer.start(key, actor="worker:gate-1")
        time.sleep(0.05)
        reducer.pass_invocation(
            key,
            actor="worker:gate-1",
            receipt={"schema": "loop-gate-verdict/v1", "verdict": "PASS", "details": "all checks pass", "epoch": 0},
        )

    t = threading.Thread(target=background_worker)
    t.start()

    start_wait = time.time()
    terminal_status = await_gate(key, timeout_sec=2.0, poll_interval_sec=0.01, reducer=reducer)
    t.join()

    assert terminal_status is not None
    assert isinstance(terminal_status, InvocationStatusView)
    assert terminal_status.is_terminal is True
    assert terminal_status.state == InvocationState.PASSED
    assert terminal_status.receipt is not None
    assert terminal_status.receipt["verdict"] == "PASS"
    assert terminal_status.invocation_id == inv_id

    # 4. Subsequent await_gate on already-terminal invocation returns immediately
    immediate_status = await_gate(inv_id, timeout_sec=5.0, reducer=reducer)
    assert immediate_status is not None
    assert immediate_status.is_terminal is True
    assert immediate_status.state == InvocationState.PASSED

    # 5. Non-existent invocation in await_gate returns None
    assert await_gate("non-existent-key", timeout_sec=0.05, reducer=reducer) is None


def test_await_gate_terminal_failures():
    """Verify await_gate handles FAILED, CANCELLED, and INFRASTRUCTURE_FAILURE terminal states."""
    reducer = LifecycleReducer()

    # Failed case
    k_fail = InvocationKey(session="sess-f", phase="back", step="s04", role="verify-implement", epoch=0)
    reducer.launch(k_fail, owner="w1")
    reducer.start(k_fail, actor="w1")
    reducer.fail_invocation(k_fail, actor="w1", reason="assertion failed")

    status_fail = await_gate(k_fail, reducer=reducer)
    assert status_fail is not None
    assert status_fail.state == InvocationState.FAILED
    assert status_fail.is_terminal is True
    assert status_fail.reason == "assertion failed"

    # Infrastructure failure case
    k_infra = InvocationKey(session="sess-infra", phase="back", step="s04", role="verify-implement", epoch=0)
    rec_infra = reducer.launch(k_infra, owner="w2")
    reducer.mark_infrastructure_failure(k_infra, actor="orchestrator", reason="worker crash")

    status_infra = await_gate(rec_infra.invocation_id, reducer=reducer)
    assert status_infra is not None
    assert status_infra.state == InvocationState.INFRASTRUCTURE_FAILURE
    assert status_infra.is_terminal is True
    assert status_infra.reason == "worker crash"


def test_concurrent_await_gate():
    """Verify multiple concurrent awaiters all receive the resolved typed status."""
    reducer = LifecycleReducer()
    key = InvocationKey(session="sess-concurrent-await", phase="back", step="s04", role="verify-qa", epoch=0)
    rec = reducer.launch(key, owner="qa-worker")

    def run_await(timeout: float):
        return await_gate(key, timeout_sec=timeout, poll_interval_sec=0.01, reducer=reducer)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(run_await, 2.0) for _ in range(5)]

        time.sleep(0.05)
        reducer.start(key, actor="qa-worker")
        time.sleep(0.05)
        reducer.pass_invocation(key, actor="qa-worker", receipt={"verdict": "PASS", "epoch": 0})

        results = [f.result() for f in futures]

    assert len(results) == 5
    assert all(r is not None and r.state == InvocationState.PASSED for r in results)
    assert all(r.invocation_id == rec.invocation_id for r in results)
