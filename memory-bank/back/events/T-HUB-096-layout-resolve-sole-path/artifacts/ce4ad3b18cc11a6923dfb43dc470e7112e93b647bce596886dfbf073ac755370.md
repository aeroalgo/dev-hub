# Bugfix: Layout Resolve Sole Path Suite Alignment
**Epic ID:** T-HUB-096-layout-resolve-sole-path  
**Date:** 2026-09-14  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-096-layout-resolve-sole-path/qa-20260914-layout-resolve-sole-path.yaml

---

## 1. QA Root Cause Analysis
During full test suite execution in BACK QA (`bin/pytest -q --tb=line`), 7 suite tests failed:
- `loop/tests/test_board_sync_sync.py`:
  - `test_obsolete_step_card_deleted_on_epic_sync`
  - `test_done_epic_archive_all`
  - `test_done_epic_preserves_unrelated_cards`
  - `test_sync_generation_increment`
- `loop/tests/test_board_sync_epic_regression.py`:
  - `test_e2e_pending_steps_emit_single_epic_card_pending_to_epic`
  - `test_e2e_step_era_cards_archived_on_sync`
  - `test_e2e_epic_done_maps_to_todo`

**Root Cause:**
In T-HUB-096, `plan_path()` and memory-bank resolution were updated to use canonical layout v2 paths (`memory-bank/{role}/plan/{epic}/md/plan.md` and `memory-bank/{role}/plan/{epic}/yaml/decompose-index.yaml`). The test helper functions `_card`, `_set_status`, and `_project` in `loop/tests/test_board_sync_sync.py` (which are also shared and imported by `loop/tests/test_board_sync_epic_regression.py`) were creating legacy flat layout files (`memory-bank/back/plan/plan-T-DEMO.md` and `memory-bank/back/plan/decompose-{epic}/index.yaml`). When `scan_gates` attempted to resolve roadmap entries during test execution, `roadmap_queue.select_next_epic` failed with `plan missing`, causing `run_sync` to fail-closed and return 0 operations and empty archives.

---

## 2. Changes Implemented (AC+)
- `loop/tests/test_board_sync_sync.py`: Updated `_card`, `_set_status`, and `_project` test fixtures to use canonical layout v2 paths (`memory-bank/back/plan/{epic}/yaml/decompose-index.yaml` and `memory-bank/back/plan/{epic}/md/plan.md`).
- `memory-bank/back/bugfix/T-HUB-096-layout-resolve-sole-path/bugfix-queue.yaml`: Updated items `BF-001` and `BF-002` to `done`; full suite verification executed and marked `pass` (2902 passed, 4 skipped in 96.63s).

---

## 3. Non-Goals / Fallback Purge (AC−)
- No legacy flat v1 layout fallback restored; canonical layout v2 path resolution preserved.
- No exception silencing or loose fallback masks added.
- No changes outside test fixture setups in `loop/tests/test_board_sync_sync.py`.

---

## 4. Integration Rule Counterparts (§0.11)
External refs and system counterparts verified against orphaned references:
- **API / Protocol:** `run_sync`, `scan_gates`, and `scan_mb` layout v2 scan conventions verified.
- **Environment variables:** `EPIC_LOOP` and runtime configs validated.
- **Storage & State:** `memory-bank/back/bugfix/T-HUB-096-layout-resolve-sole-path/bugfix-queue.yaml` and `bugfix-20260914-layout-resolve-sole-path.md`.
- **Orphan check:** Zero dangling references or orphan paths introduced.

---

## 5. Blockers Resolved
- BF-001: `loop/tests/test_board_sync_sync.py` (8 passed) — PASS
- BF-002: `loop/tests/test_board_sync_epic_regression.py` (6 passed) — PASS

---

## 6. Verification
- Targeted item checks:
  ```bash
  bin/pytest loop/tests/test_board_sync_sync.py -q --tb=line
  bin/pytest loop/tests/test_board_sync_epic_regression.py -q --tb=line
  ```
- Full repository test suite (`verification.command`):
  ```bash
  bin/pytest -q --tb=line
  ```
  Result: 2902 passed, 4 skipped in 96.63s.
