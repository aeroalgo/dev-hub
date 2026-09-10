# Bugfix: Context loop regression on QA pass completion

## Root cause
В  ветка  безусловно сохраняла  (QA), игнорируя результат редюсера  /  (когда все шаги декомпозиции выполнены и зафиксирован валидный QA pass). В результате  ошибочно формировал сессию  вместо завершения эпика .

## Fix
- В  добавлена проверка  перед обработкой демоута  и сохранением armed фазы.

## Verify
- Targeted tests: ============================= test session starts ==============================
platform linux -- Python 3.12.11, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/aero/PyProject/dev-hub
configfile: pytest.ini
plugins: logfire-4.41.0, anyio-4.15.0, xdist-3.8.0, timeout-2.4.0
timeout: 120.0s
timeout method: signal
timeout func_only: False
created: 4/4 workers
4 workers [118 items]

........................................................................ [ 61%]
..............................................                           [100%]
=============================== warnings summary ===============================
loop/tests/test_context_loop.py::test_sync_cursor_skips_implement_when_analyze_pending
loop/tests/test_context_loop.py::test_prepare_recovers_projection_conflict_by_clearing_checkpoint
loop/tests/test_context_loop.py::test_prepare_keeps_analyze_when_gate_pending
loop/tests/test_context_loop.py::test_prepare_does_not_promote_analyze_from_artifact_without_receipt
  /home/aero/PyProject/dev-hub/.claude/hooks/epic/core.py:5129: DeprecationWarning: 'arm_pre_implement_context' is deprecated — use loop.epic_transition instead
    _legacy_warn("arm_pre_implement_context")

loop/tests/test_session_finalize_identity.py::test_check_after_continues_on_analyze_after_decompose
loop/tests/test_context_loop.py::test_extract_shard_paths_includes_harness_files
loop/tests/test_handoff_phase_gates.py::test_prepare_completes_when_qa_pass_despite_legacy_reflect_handoff
loop/tests/test_finish_bugfix.py::test_prepare_session_keeps_bugfix_when_qa_failed
  /home/aero/PyProject/dev-hub/loop/mb_load/schemas.py:20: UserWarning: Field name "schema" in "MbLoadRequest" shadows an attribute in parent "BaseModel"
    class MbLoadRequest(BaseModel):

loop/tests/test_session_finalize_identity.py::test_check_after_continues_on_analyze_after_decompose
loop/tests/test_context_loop.py::test_extract_shard_paths_includes_harness_files
loop/tests/test_handoff_phase_gates.py::test_prepare_completes_when_qa_pass_despite_legacy_reflect_handoff
loop/tests/test_finish_bugfix.py::test_prepare_session_keeps_bugfix_when_qa_failed
  /home/aero/PyProject/dev-hub/loop/mb_load/schemas.py:28: UserWarning: Field name "schema" in "MbLoadResult" shadows an attribute in parent "BaseModel"
    class MbLoadResult(BaseModel):

loop/tests/test_context_loop.py::test_dag_fanout_arms_dependency_ready_node
loop/tests/test_context_loop.py::test_prepare_rebuilds_derived_projection
loop/tests/test_context_loop.py::test_arm_clears_stale_checkpoint
loop/tests/test_context_loop.py::test_epic_done_rejected_without_qa_pass
loop/tests/test_context_loop.py::test_arm_overwrites_blocked_foreign_context
loop/tests/test_context_loop.py::test_arm_done_when_qa_pass_exists
loop/tests/test_context_loop.py::test_arm_epic_done_after_qa_pass
loop/tests/test_context_loop.py::test_degraded_prompt_epic_finished_only_after_qa_pass
  /home/aero/PyProject/dev-hub/.claude/hooks/epic/core.py:4744: DeprecationWarning: 'arm_active_context_from_decompose' is deprecated — use loop.epic_transition instead
    _legacy_warn("arm_active_context_from_decompose")

loop/tests/test_context_loop.py::test_prepare_syncs_cursor_from_index_yaml_sot
loop/tests/test_context_loop.py::test_check_after_repairs_fingerprint_when_index_already_completed
loop/tests/test_context_loop.py::test_epic_done_rejected_without_qa_pass
loop/tests/test_context_loop.py::test_check_after_rewrites_premature_epic_done
loop/tests/test_context_loop.py::test_check_after_rewrites_premature_epic_done_to_audit
loop/tests/test_context_loop.py::test_prepare_stale_complete_status_without_artifacts_does_not_finish
loop/tests/test_context_loop.py::test_record_abort_resyncs_armed_step_on_retryable_abort
  /home/aero/PyProject/dev-hub/harness/hooks/epic/core.py:4744: DeprecationWarning: 'arm_active_context_from_decompose' is deprecated — use loop.epic_transition instead
    _legacy_warn("arm_active_context_from_decompose")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 118 passed, 27 warnings in 4.60s =======================
- Full suite: bringing up nodes...
bringing up nodes...

........................................................................ [  2%]
........................................................................ [  5%]
........................................................................ [  8%]
........................................................................ [ 11%]
........................................................................ [ 14%]
........................................................................ [ 17%]
........................................................................ [ 20%]
..............................................................s..s...... [ 23%]
........................................................................ [ 25%]
........................................................................ [ 28%]
........................................................................ [ 31%]
........................................................................ [ 34%]
........................................................................ [ 37%]
........................................................................ [ 40%]
........................................................................ [ 43%]
........................................................................ [ 46%]
........................................................................ [ 48%]
.................................................................s...... [ 51%]
........................................................................ [ 54%]
........................................................................ [ 57%]
........................................................................ [ 60%]
........................................................................ [ 63%]
........................................................................ [ 66%]
........................................................................ [ 69%]
........................................................................ [ 72%]
........................................................................ [ 74%]
........................................................................ [ 77%]
........................................................................ [ 80%]
........................................s............................... [ 83%]
........................................................................ [ 86%]
........................................................................ [ 89%]
........................................................................ [ 92%]
........................................................................ [ 95%]
........................................................................ [ 97%]
..................................................                       [100%]
=============================== warnings summary ===============================
loop/tests/test_context_loop.py: 4 warnings
loop/tests/test_epic_transition.py: 5 warnings
loop/tests/test_roadmap_queue.py: 6 warnings
loop/tests/test_finish_integrity.py: 3 warnings
loop/tests/test_v2_path_resolution_regressions.py: 1 warning
harness/hooks/tests/test_mb_finish_implement.py: 1 warning
harness/hooks/tests/test_mb_finish_decompose.py: 3 warnings
loop/tests/test_parallel_integration.py: 2 warnings
loop/tests/test_board_sync_epic_regression.py: 1 warning
loop/tests/test_t035_invariants.py: 1 warning
loop/tests/test_finish_receipt_integrity.py: 1 warning
loop/tests/test_finalize_atomic_commit.py: 4 warnings
harness/hooks/tests/test_session_start_autoscaffold.py: 1 warning
harness/hooks/tests/test_stop_gate_fingerprint.py: 1 warning
loop/tests/test_gate_atomic_finish.py: 1 warning
loop/tests/test_t035_acceptance.py: 1 warning
loop/tests/test_arm_phase_smoke.py: 1 warning
loop/tests/test_mb_finish_paths.py: 2 warnings
loop/tests/test_finish_capability_evidence.py: 1 warning
  /home/aero/PyProject/dev-hub/.claude/hooks/epic/core.py:5129: DeprecationWarning: 'arm_pre_implement_context' is deprecated — use loop.epic_transition instead
    _legacy_warn("arm_pre_implement_context")

loop/tests/test_context_loop.py: 8 warnings
loop/tests/test_epic_transition.py: 1 warning
loop/tests/test_roadmap_queue.py: 1 warning
loop/tests/test_index_fail_closed.py: 3 warnings
harness/hooks/tests/test_mb_finish_analyze.py: 2 warnings
loop/tests/test_board_launch_arm.py: 1 warning
loop/tests/test_reserved_role_epic_id.py: 1 warning
loop/tests/test_board_sync_epic_regression.py: 1 warning
loop/tests/test_sync_cursor_handoff_preserve.py: 1 warning
loop/tests/test_dag_scheduler.py: 3 warnings
loop/tests/test_arm_phase_smoke.py: 1 warning
loop/tests/test_dag_journey.py: 1 warning
  /home/aero/PyProject/dev-hub/.claude/hooks/epic/core.py:4744: DeprecationWarning: 'arm_active_context_from_decompose' is deprecated — use loop.epic_transition instead
    _legacy_warn("arm_active_context_from_decompose")

loop/tests/test_context_loop.py: 7 warnings
loop/tests/test_finish_integrity.py: 1 warning
loop/tests/test_mb_finish_transaction.py: 3 warnings
loop/tests/test_index_fail_closed.py: 1 warning
loop/tests/test_context_finish_projection.py: 1 warning
  /home/aero/PyProject/dev-hub/harness/hooks/epic/core.py:4744: DeprecationWarning: 'arm_active_context_from_decompose' is deprecated — use loop.epic_transition instead
    _legacy_warn("arm_active_context_from_decompose")

loop/tests/test_active_context_lock.py::test_arm_pre_implement_blocked_when_loop_owns_cursor
loop/tests/test_v2_path_resolution_regressions.py::test_analyze_arm_normalizes_v2_md_mirror_to_yaml_sot
  /home/aero/PyProject/dev-hub/harness/hooks/epic/core.py:5129: DeprecationWarning: 'arm_pre_implement_context' is deprecated — use loop.epic_transition instead
    _legacy_warn("arm_pre_implement_context")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
2494 passed, 4 skipped, 79 warnings in 99.96s (0:01:39)
