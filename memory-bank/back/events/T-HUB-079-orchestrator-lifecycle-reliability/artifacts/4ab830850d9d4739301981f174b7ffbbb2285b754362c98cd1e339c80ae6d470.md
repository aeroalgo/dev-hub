# Bugfix: Resolve AC+3 zero-tool session handling, AC+4 untagged receipt epoch check, and AC+2 TaskStop terminalization
**Epic ID:** T-HUB-079-orchestrator-lifecycle-reliability  
**Date:** 2026-09-10  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-079-orchestrator-lifecycle-reliability/qa-20260910-lifecycle-reliability-v3.yaml

---

## 1. QA Root Cause Analysis
During QA review of epic `T-HUB-079-orchestrator-lifecycle-reliability`, three blocker defects were identified:

1. **AC+3 (Zero-tool session classification):** In `loop/context_loop.py:3146`, `write_session_telemetry_companion` evaluated `terminal_state = "passed" if not analysis.get("aborted") ...` before checking `first_action_taken`. Consequently, clean-exiting sessions with zero tool actions were incorrectly marked as `passed` instead of `aborted_before_action` with a non-empty cause.
2. **AC+4 (Untagged receipt bypass in pass_invocation):** In `loop/lifecycle.py:940-952`, `pass_invocation()` only invoked `validate_receipt_epoch()` when `has_epoch_tag` was True. When an untagged receipt (e.g., a dictionary without an explicit `"epoch"` key) was passed, epoch validation was skipped entirely, allowing untagged receipts to satisfy invocations and bypassing epoch isolation.
3. **AC+2 (TaskStop default state and checkpoint deletion):** In `loop/lifecycle.py:1091-1105`, `handle_task_stop()` and `task_stop()` defaulted `target_state` to `InvocationState.CANCELLED` instead of `InvocationState.STALE` (as required by AC+2: "Crash/TaskStop is terminalized as stale/infrastructure_failure"). Additionally, `record_abort()` in `loop/context_loop.py:3477` called `clear_runner_checkpoint()`, deleting runner checkpoint files on terminal failure rather than preserving state without marker deletion.

---

## 2. Changes Implemented

- `loop/lifecycle.py`:
  - Updated `pass_invocation()` to strictly enforce `validate_receipt_epoch(receipt, record.key.epoch)` whenever `receipt is not None`, rejecting untagged receipts and mismatched epochs with `InvalidStateTransitionError`.
  - Changed default `target_state` in `handle_task_stop()` and `task_stop()` to `InvocationState.STALE`.
- `loop/context_loop.py`:
  - Updated `write_session_telemetry_companion()` to prioritize `first_action_taken` so that sessions with zero tool actions deterministically receive `terminal_state="aborted_before_action"` and default non-empty cause `terminal_reason="aborted before first action: zero tool actions recorded"`.
  - Removed `clear_runner_checkpoint()` invocation from `record_abort()` terminal abort path to ensure runner checkpoints and forensic markers are preserved on terminal halt.
- `loop/tests/test_lifecycle_crash_safety.py`:
  - Updated `test_task_stop_terminalization` assertions to verify `InvocationState.STALE`.
- `loop/tests/test_lifecycle_reducer.py`:
  - Added explicit `"epoch": 0` tags to test receipts in `test_legal_state_transitions` and `test_idempotency_and_epoch_isolation`.
- `loop/tests/test_await_gate_api.py`:
  - Added explicit `"epoch": 0` tags to test receipts in `test_await_gate_timeout_and_pass` and `test_await_gate_concurrent_polls_resolve_identically`.
- `loop/tests/test_context_loop.py`:
  - Updated `test_record_abort_401_banned_is_permanent_not_retryable_halt` to assert checkpoint preservation on terminal halt.
- `loop/tests/test_orchestrator_lifecycle_regression.py`:
  - Added regression test `test_bugfix_zero_tool_session_exit_0_classified_as_aborted_before_action` (AC+3).
  - Added regression test `test_bugfix_pass_invocation_rejects_untagged_receipt` (AC+4).
  - Added regression test `test_bugfix_task_stop_defaults_to_stale_and_no_checkpoint_cleared` (AC+2).

---

## 3. Verification

Targeted lifecycle regression test suite:
```
bin/pytest loop/tests/test_lifecycle*.py loop/tests/test_orchestrator_lifecycle_regression.py loop/tests/test_await_gate_api.py -q --tb=line
38 passed in 2.30s
```

Full repository test suite:
```
bin/pytest -q --tb=line
2508 passed
```
