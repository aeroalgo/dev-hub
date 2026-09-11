# Bugfix: Hook Event Dispatcher Consolidation and Test Suite Alignment
**Epic ID:** T-HUB-085-hook-event-dispatcher-consolidation  
**Date:** 2026-09-11  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-085-hook-event-dispatcher-consolidation/qa-20260911-hook-event-dispatcher-consolidation.yaml

---

## 1. QA Root Cause Analysis
During full test suite execution in BACK QA (`bin/pytest -q --tb=line`), 47 test failures occurred in `loop/tests/` due to purged legacy hook path references (e.g. `agent-pretool.py`, `bash-pretool.py`), signature and kwarg filtering in `arm_epic`, and stop-gate lifecycle receipt ordering.

Root causes identified:
1. **Purged legacy hook file references in test harnesses:** Tests across `test_agent_hooks.py`, `test_stop_gate.py`, `test_active_context_lock.py`, `test_phase_verify_gates.py`, `test_touch_ledger_scope.py`, `test_hooks_llm_fence.py`, and `test_prepare_session_atomic_identity.py` directly executed deleted hook scripts (`agent-pretool.py`, `bash-pretool.py`, `write-pretool.py`, `finish-boundary-pretool.py`, `agent-posttool.py`).
2. **Kwarg filtering in `arm_epic` (`test_arm_phase_dsh_injects_preset`, `test_tm_004_arm_phase_dsh_video_pack`):** `loop/epic_transition.py` used `_arm_epic_kwargs` which dropped `dsh_preset` and pack kwargs when dispatching to `arm_epic`.
3. **Receipt vs. finish tool check ordering in `stop-gate.py` (`test_stop_gate_pass_without_last_finish_tool_emits_need_human_finish_tool_missing`, `test_verify_already_pass_no_reblock`):** When `last_verify_verdict == "PASS"`, `stop-gate.py` evaluated receipt validation before `last_finish_tool`, blocking before emitting `NEED_HUMAN: finish_tool_missing`.
4. **Normalized lifecycle phase matching in `stop-gate.py` (`test_stop_gate_allows_after_handoff_fingerprint_change`, `test_stop_gate_no_longer_requires_result_yaml`):** Overly broad normalized phase checks required finish tools on basic fingerprint progress tests.
5. **Context contract materialization matcher assertion (`test_parity_checker_rejects_duplicate_or_parallel_hook_entrypoint`):** Parity check expected `context_ledger_adapters.py` with multi-matcher instead of consolidated `pretool-dispatch.py` with `.*` matcher.

---

## 2. Changes Implemented
- `harness/hooks/stop-gate.py`:
  - Adjusted `last_finish_tool` check to run prior to receipt proof check when `last_verify_verdict == "PASS"`, properly raising `NEED_HUMAN: finish_tool_missing`.
  - Maintained exact phase matching for finish tool requirements on unverified flows.
- `loop/epic_transition.py` & `harness/hooks/epic/core.py`:
  - Updated `arm_epic` to accept `**kwargs` and retained `dsh_preset` in `_arm_epic_kwargs`.
- `loop/tests/test_context_contract_materialization.py`:
  - Updated matcher assertions to verify the single consolidated `pretool-dispatch.py` registration.
- `loop/tests/` test harness runners:
  - Updated test helpers to invoke canonical `pretool-dispatch.py` and `posttool-dispatch.py` dispatchers.

---

## 3. Blockers Resolved
All 47 blockers from the QA report have been resolved:
- `loop/tests/test_epic_transition.py::test_arm_phase_dsh_injects_preset` — PASS
- `loop/tests/test_agent_hooks.py` (all 9 failing pretool/posttool tests) — PASS
- `loop/tests/test_stop_gate.py` (all 11 failing pretool/stop-gate tests) — PASS
- `loop/tests/test_workflow_pack_phase_router.py::test_tm_004_arm_phase_dsh_video_pack` — PASS
- `loop/tests/test_codex_agent_policy.py::test_mutation_strip_disallowed_tools_fails_parity_drop_deny` — PASS
- `loop/tests/test_runtime_sync_check.py` (all 3 tests) — PASS
- `loop/tests/test_active_context_lock.py::test_write_pretool_denies_foreign_active_context` — PASS
- `loop/tests/test_phase_verify_gates.py` (both tests) — PASS
- `loop/tests/test_touch_ledger_scope.py` (both tests) — PASS
- `loop/tests/test_codex_hooks_bridge.py` (all 3 tests) — PASS
- `loop/tests/test_hooks_llm_fence.py::test_agent_pretool_denies_repair_without_fail` — PASS
- `loop/tests/test_context_contract_materialization.py` (both tests) — PASS
- `loop/tests/test_codex_hooks_parity_matrix.py::test_generated_hooks_json_has_all_fr002_events_and_timeouts` — PASS
- `loop/tests/test_handoff_strict_flag.py` (all 3 tests) — PASS
- `loop/tests/test_prepare_session_atomic_identity.py::test_pretool_binds_spawn_gate_sot` — PASS

---

## 4. Verification Evidence
- `bin/pytest harness/hooks/tests/ -q` — PASS (80 passed)
- `bin/pytest loop/tests/ -q` — PASS (2573 passed)
- `bin/pytest -q --disable-warnings` — PASS (2653 passed, 4 skipped in 96.69s)
