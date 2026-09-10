# Bugfix: Primary Lifecycle Classification for Empty Root Sessions (AC+ #3)
**Epic ID:** T-HUB-079-orchestrator-lifecycle-reliability  
**Date:** 2026-09-10  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-079-orchestrator-lifecycle-reliability/qa-20260910-lifecycle-reliability-v5.yaml
---
## 1. QA Root Cause Analysis
During QA review of epic  (), reviewer  identified:
- **AC+ #3 & §0.11 (Primary lifecycle outcome for zero-tool session):** A zero-tool wrapped session exiting with  was classified by  in  as , , . While  in  masked this downstream during companion JSONL serialization, the primary session resilience analysis failed to classify the session as  with a non-empty cause.
- **Root Cause:**
  1.  unconditionally returned  when  and  was absent, without checking whether , , or  were set for wrapped sessions.
  2. In , duplicate transient pattern check blocks overwrote  for pre-action aborts.
  3. In , timestamped wrapper markers ( / ) were not recognized when using strict , and structured CLI result events with  were not flagged as .
---
## 2. Changes Implemented
- :
  - Updated  so that wrapped sessions () without tool actions () and without completion ( / ) deterministically return , , , , and non-empty .
  - Fixed pre-action abort branch ordering so that explicit error reasons (e.g. transient 429/503 or fatal API errors) retain their expected outcomes while pre-action crashes without reason or with prompt syntax/validation errors resolve to .
  - Added plain-text  matcher in  for non-zero exit codes.
- :
  - Normalized , , and  recognition to handle timestamped/wrapper prefixes.
  - Added  detection for structured CLI result events with  or successful  field.
  - Added  classification for truncated JSON lines containing tool invocations or tool results.
- :
  - Ensured  presence always overrides session abort status with  and non-retryable fatal classification.
- :
  - Enhanced  to assert primary  outcome is , , , and  is non-empty.
---
## 3. Verification
Full test suite verification:
bringing up nodes...
bringing up nodes...

........................................................................ [  2%]
........................................................................ [  5%]
........................................................................ [  8%]
........................................................................ [ 11%]
........................................................................ [ 14%]
........................................................................ [ 17%]
........................................................................ [ 20%]
........................................................................ [ 23%]
........................................................................ [ 26%]
........................................................................ [ 29%]
........................................................................ [ 32%]
........................................................................ [ 34%]
..................................s..s.................................. [ 37%]
........................................................................ [ 40%]
........................................................................ [ 43%]
........................................................................ [ 46%]
........................................................................ [ 49%]
..s..................................................................... [ 52%]
........................................................................ [ 55%]
........................................................................ [ 58%]
........................................................................ [ 61%]
........................................................................ [ 64%]
........................................................................ [ 67%]
........................................................................ [ 69%]
........................................................................ [ 72%]
........................................................................ [ 75%]
........................................................................ [ 78%]
.............................................................s.......... [ 81%]
........................................................................ [ 84%]
........................................................................ [ 87%]
........................................................................ [ 90%]
........................................................................ [ 93%]
........................................................................ [ 96%]
........................................................................ [ 99%]
......................                                                   [100%]
=============================== warnings summary ===============================
loop/tests/test_context_loop.py: 4 warnings
loop/tests/test_roadmap_queue.py: 6 warnings
loop/tests/test_epic_transition.py: 5 warnings
loop/tests/test_finish_integrity.py: 3 warnings
loop/tests/test_v2_path_resolution_regressions.py: 1 warning
harness/hooks/tests/test_mb_finish_implement.py: 1 warning
harness/hooks/tests/test_mb_finish_decompose.py: 3 warnings
loop/tests/test_board_sync_epic_regression.py: 1 warning
loop/tests/test_parallel_integration.py: 2 warnings
loop/tests/test_t035_invariants.py: 1 warning
loop/tests/test_finish_receipt_integrity.py: 1 warning
loop/tests/test_finalize_atomic_commit.py: 4 warnings
harness/hooks/tests/test_session_start_autoscaffold.py: 1 warning
harness/hooks/tests/test_stop_gate_fingerprint.py: 1 warning
loop/tests/test_t035_acceptance.py: 1 warning
loop/tests/test_arm_phase_smoke.py: 1 warning
loop/tests/test_mb_finish_paths.py: 2 warnings
loop/tests/test_finish_capability_evidence.py: 1 warning
  /home/aero/PyProject/dev-hub/.claude/hooks/epic/core.py:5101: DeprecationWarning: 'arm_pre_implement_context' is deprecated — use loop.epic_transition instead
    _legacy_warn("arm_pre_implement_context")

loop/tests/test_roadmap_queue.py: 1 warning
loop/tests/test_epic_transition.py: 1 warning
loop/tests/test_context_loop.py: 8 warnings
loop/tests/test_index_fail_closed.py: 3 warnings
harness/hooks/tests/test_mb_finish_analyze.py: 2 warnings
loop/tests/test_board_launch_arm.py: 1 warning
loop/tests/test_board_sync_epic_regression.py: 1 warning
loop/tests/test_reserved_role_epic_id.py: 1 warning
loop/tests/test_sync_cursor_handoff_preserve.py: 1 warning
loop/tests/test_dag_scheduler.py: 3 warnings
loop/tests/test_arm_phase_smoke.py: 1 warning
loop/tests/test_dag_journey.py: 1 warning
  /home/aero/PyProject/dev-hub/.claude/hooks/epic/core.py:4716: DeprecationWarning: 'arm_active_context_from_decompose' is deprecated — use loop.epic_transition instead
    _legacy_warn("arm_active_context_from_decompose")

loop/tests/test_mb_finish_transaction.py: 3 warnings
loop/tests/test_finish_integrity.py: 1 warning
loop/tests/test_context_loop.py: 7 warnings
loop/tests/test_index_fail_closed.py: 1 warning
loop/tests/test_context_finish_projection.py: 1 warning
  /home/aero/PyProject/dev-hub/harness/hooks/epic/core.py:4716: DeprecationWarning: 'arm_active_context_from_decompose' is deprecated — use loop.epic_transition instead
    _legacy_warn("arm_active_context_from_decompose")

loop/tests/test_active_context_lock.py::test_arm_pre_implement_blocked_when_loop_owns_cursor
loop/tests/test_v2_path_resolution_regressions.py::test_analyze_arm_normalizes_v2_md_mirror_to_yaml_sot
  /home/aero/PyProject/dev-hub/harness/hooks/epic/core.py:5101: DeprecationWarning: 'arm_pre_implement_context' is deprecated — use loop.epic_transition instead
    _legacy_warn("arm_pre_implement_context")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
2466 passed, 4 skipped, 78 warnings in 79.36s (0:01:19)
Targeted lifecycle regression test suite:
bringing up nodes...
bringing up nodes...

........................................................................ [ 68%]
................s..s.............                                        [100%]
103 passed, 2 skipped in 17.94s
