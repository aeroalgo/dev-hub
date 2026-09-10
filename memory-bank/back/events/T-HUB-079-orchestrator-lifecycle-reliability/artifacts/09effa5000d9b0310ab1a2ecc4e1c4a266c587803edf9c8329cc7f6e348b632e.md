# Bugfix: Enforce STALE for TASK_STOP lifecycle transitions
**Epic ID:** T-HUB-079-orchestrator-lifecycle-reliability  
**Date:** 2026-09-10  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-079-orchestrator-lifecycle-reliability/qa-20260910-lifecycle-reliability-v4.yaml
---
## 1. QA Root Cause Analysis
During QA review of epic `T-HUB-079-orchestrator-lifecycle-reliability` (`qa-20260910-lifecycle-reliability-v4.yaml`), one blocker defect was identified:
- **AC-1 (TASK_STOP target state enforcement):** `handle_task_stop()` and its `task_stop()` alias accepted `target_state=InvocationState.CANCELLED`, allowing a TaskStop call to terminalize an invocation as cancelled instead of `InvocationState.STALE`.

**QA naming note:** The QA reference `STATE_TRANSITIONS` corresponds to the implementation mapping `EVENT_TYPE_TO_TARGET_STATE` in `loop/lifecycle.py`.

---
## 2. Changes Implemented
- `loop/lifecycle.py`:
  - Kept `EVENT_TYPE_TO_TARGET_STATE[LifecycleEventType.TASK_STOP]` mapped to `InvocationState.STALE`.
  - Enforced `InvocationState.STALE` in `handle_task_stop()`; `task_stop()` inherits the same guard.
- `loop/tests/test_lifecycle_crash_safety.py`:
  - Updated `test_task_stop_terminalization` to assert that `LifecycleEventType.TASK_STOP` is explicitly recorded in `event_types`.
- `loop/tests/test_orchestrator_lifecycle_regression.py`:
  - Added regression test `test_bugfix_task_stop_event_type_maps_to_stale` verifying that `LifecycleEventType.TASK_STOP` maps to `InvocationState.STALE` and reduces cleanly.
  - Added regression coverage that both TaskStop APIs reject `InvocationState.CANCELLED`.

---
## 3. Verification
Targeted lifecycle regression test suite:
```
bin/pytest loop/tests/test_lifecycle*.py loop/tests/test_orchestrator_lifecycle_regression.py -q --tb=line
37 passed in 2.14s
```
