# Bugfix: Layout v2 Fallback Purge and Suite Alignment
**Epic ID:** T-HUB-087-epic-layout-v2-fallback-purge  
**Date:** 2026-09-11  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-087-epic-layout-v2-fallback-purge/qa-20260911-fallback-purge.yaml

---

## 1. QA Root Cause Analysis
During full test suite execution in BACK QA (`bin/pytest -q --tb=line`), 26 suite test files were flagged as failing or requiring queue-backed verification following the v2 layout fallback purge and migration of runtime paths to canonical `memory-bank/<role>/<phase>/<epic_id>/` structure:
1. **Epic layout v2 canonical path resolution:** Purge of legacy v1 fallbacks required verifying that all runtime and test harnesses resolve v2 layout paths directly without fallback attempts.
2. **Bugfix queue integration:** Integration of `bugfix-queue.yaml` as the canonical status cursor for bugfix processing with strict sequential resolution and full test suite verification.
3. **Full test suite execution:** Verified and confirmed all 26 test suites pass under the current layout v2 architecture and bugfix queue contract.

---

## 2. Changes Implemented (AC+)
- `memory-bank/back/bugfix/T-HUB-087-epic-layout-v2-fallback-purge/bugfix-queue.yaml`: All 26 queue items (`BF-001` through `BF-026`) are `done`; queue verification is `pass` with `bin/pytest -q --tb=line`.
- Queue target files processed: `loop/tests/test_epic_transition.py`, `loop/tests/test_roadmap_queue.py`, `loop/tests/test_convergence_categories.py`, `loop/tests/test_board_launch_arm.py`, `loop/tests/test_board_sync_cli.py`, `loop/tests/test_board_sync_scan_gates.py`, `loop/tests/test_implement_hub_alias.py`, `harness/hooks/tests/test_mb_finish_decompose.py`, `loop/tests/test_board_sync_epic_regression.py`, `loop/tests/test_incidents_tier0.py`, `loop/tests/test_reserved_role_epic_id.py`, `loop/tests/test_t035_invariants.py`, `loop/tests/test_convergence_cli.py`, `loop/tests/test_convergence_engine.py`, `loop/tests/test_finish_receipt_integrity.py`, `loop/tests/test_state_recovery.py`, `loop/tests/test_context_finish_projection.py`, `loop/tests/test_finalize_atomic_commit.py`, `harness/hooks/tests/test_mcp_load_parity.py`, `loop/tests/test_projection_identity.py`, `loop/tests/test_gate_atomic_finish.py`, `harness/hooks/tests/test_stop_gate_fingerprint.py`, `loop/tests/test_formula_integration.py`, `loop/tests/test_t035_acceptance.py`, `loop/tests/test_dag_journey.py`, and `loop/tests/test_phase_epoch.py`.

---

## 3. Non-Goals / Fallback Purge (AC−)
- No reinstatement of v1 layout fallback paths or legacy dual-path resolution.
- No `try new except legacy` constructs for path resolution.
- No bypassing of `bugfix-queue.yaml` sequential execution order or verification status.
- No modification of files outside the allowed scope of this bugfix task.

---

## 4. External Refs / Orphan Check (§0.11)
- Verified all references to `bugfix-queue.yaml` align with `epic-bugfix-queue/v1` schema across `loop/bugfix_queue.py`, `harness/hooks/epic/core.py`, and `loop/paths/epic_layout.py`.
- Confirmed zero orphan external references or phantom paths introduced.

---

## 5. Blockers Resolved
All 26 blockers from the QA report have been resolved in `bugfix-queue.yaml`:
- BF-001: `loop/tests/test_epic_transition.py` — PASS
- BF-002: `loop/tests/test_roadmap_queue.py` — PASS
- BF-003: `loop/tests/test_convergence_categories.py` — PASS
- BF-004: `loop/tests/test_board_launch_arm.py` — PASS
- BF-005: `loop/tests/test_board_sync_cli.py` — PASS
- BF-006: `loop/tests/test_board_sync_scan_gates.py` — PASS
- BF-007: `loop/tests/test_implement_hub_alias.py` — PASS
- BF-008: `harness/hooks/tests/test_mb_finish_decompose.py` — PASS
- BF-009: `loop/tests/test_board_sync_epic_regression.py` — PASS
- BF-010: `loop/tests/test_incidents_tier0.py` — PASS
- BF-011: `loop/tests/test_reserved_role_epic_id.py` — PASS
- BF-012: `loop/tests/test_t035_invariants.py` — PASS
- BF-013: `loop/tests/test_convergence_cli.py` — PASS
- BF-014: `loop/tests/test_convergence_engine.py` — PASS
- BF-015: `loop/tests/test_finish_receipt_integrity.py` — PASS
- BF-016: `loop/tests/test_state_recovery.py` — PASS
- BF-017: `loop/tests/test_context_finish_projection.py` — PASS
- BF-018: `loop/tests/test_finalize_atomic_commit.py` — PASS
- BF-019: `harness/hooks/tests/test_mcp_load_parity.py` — PASS
- BF-020: `loop/tests/test_projection_identity.py` — PASS
- BF-021: `loop/tests/test_gate_atomic_finish.py` — PASS
- BF-022: `harness/hooks/tests/test_stop_gate_fingerprint.py` — PASS
- BF-023: `loop/tests/test_formula_integration.py` — PASS
- BF-024: `loop/tests/test_t035_acceptance.py` — PASS
- BF-025: `loop/tests/test_dag_journey.py` — PASS
- BF-026: `loop/tests/test_phase_epoch.py` — PASS

---

## 6. Verification Evidence
- `bin/pytest loop/tests/test_epic_transition.py -q --tb=line` — PASS
- `bin/pytest harness/hooks/tests/ -q` — PASS (80 passed)
- `bin/pytest -q --tb=line` — PASS (full test suite green)
