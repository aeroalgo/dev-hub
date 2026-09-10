# Bugfix: Fix start() first_action_taken initialization and bind_receipt() epoch isolation

**Epic ID:** T-HUB-079-orchestrator-lifecycle-reliability  
**Date:** 2026-09-09  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-079-orchestrator-lifecycle-reliability/qa-20260909-orchestrator-lifecycle-reliability.yaml

---

## 1. QA Root Cause Analysis
During QA review of epic `T-HUB-079-orchestrator-lifecycle-reliability`, the following defects were identified:
1. `start()` transitioned an invocation from `CREATED` to `RUNNING` with `first_action_taken=True`, and `apply_event()` automatically forced `first_action = True` on any transition to `RUNNING`. This violated the lifecycle contract where transitioning to `RUNNING` indicates execution start but not tool action execution; actions must be explicitly recorded via `record_first_action()` or action payload events. This prevented valid pre-action aborts after entering `RUNNING`.
2. `validate_receipt_epoch()` accepted untagged dicts where the `epoch` key was missing or None (and untagged `invocation_id` when `expected_invocation_id` was specified), returning `True`. Consequently, `bind_receipt()` allowed unvalidated, untagged receipts to bind to invocations, breaking epoch isolation.
3. `_qa_work_block` in `loop/context_loop.py` rendered `текущей команды` instead of `выбранного workflow`, failing unit test assertions.

---

## 2. Changes Implemented
- `loop/lifecycle.py`:
  - Fixed `start()` to transition to `InvocationState.RUNNING` without setting `first_action_taken=True`.
  - Updated `apply_event()` so entering `RUNNING` does not automatically toggle `first_action = True`; `first_action_taken` is updated only via explicit payload or `record_first_action()`.
  - Updated `apply_event()` state check to process action payloads when already in `RUNNING` state.
  - Updated `validate_receipt_epoch()` to strictly require `epoch` (and `invocation_id` when `expected_invocation_id` is supplied) on dicts and objects, failing closed on untagged inputs.
  - Updated `pass_invocation()` to validate epoch matching on tagged receipts without mutating raw dictionary keys.
  - Ensured `bind_receipt()` validates epoch and invocation ID before passing the invocation.
- `loop/telemetry.py`:
  - Updated `SessionTelemetryCompanion.from_invocation_record()` to set `action_taken = bool(record.first_action_taken or tool_actions_count > 0 or record.first_action_at is not None)`.
- `loop/context_loop.py`:
  - Updated `_qa_work_block` prompt string to match canonical canon wording.
- `loop/tests/test_lifecycle_reducer.py`:
  - Updated lifecycle test assertions to verify that `start()` leaves `first_action_taken=False` until `record_first_action()` is called.
- `loop/tests/test_orchestrator_lifecycle_regression.py`:
  - Added regression test `test_bugfix_start_does_not_mark_first_action_taken`.
  - Added regression test `test_bugfix_bind_receipt_and_validate_receipt_epoch_rejects_untagged_dicts`.

---

## 3. Verification
Targeted regression suite:
```
bin/pytest loop/tests/test_orchestrator_lifecycle_regression.py loop/tests/test_lifecycle_reducer.py loop/tests/test_context_loop.py
7 passed
```

Full repository suite:
```
bin/pytest -q --tb=line
2508 passed
```
