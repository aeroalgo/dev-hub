# Bugfix: Roadmap Cadence Replan and Refactor Block Lifecycle Fixes
**Epic ID:** T-HUB-093-roadmap-cadence-replan-refactor-block
**Date:** 2026-09-12
**Author:** BACK BUGFIX
**Source:** memory-bank/back/qa/T-HUB-093-roadmap-cadence-replan-refactor-block/qa-20260912-roadmap-cadence-replan-refactor-block.yaml

---

## 1. QA Root Cause Analysis
During BACK QA review of epic `T-HUB-093-roadmap-cadence-replan-refactor-block`, 3 blockers were identified:
1. **BF-001 (replan terminal duplicate):** In `loop/roadmap_cadence.py:advance_replan`, advancing an epic that already has a terminal replan outcome recorded in `state.replan_outcomes` was not rejected, allowing duplicate/stale replan updates.
2. **BF-002 (resync non-feature leak):** In `loop/roadmap_queue.py:roadmap_advance`, during non-idle phases (such as `resync`), only `item_kind == "feature"` was paused, allowing non-feature epics to be armed instead of enforcing fail-closed blocking for the whole phase.
3. **BF-003 (idle refactor arm denial):** In `loop/roadmap_queue.py:roadmap_advance`, the idle path lacked a check for `item_kind == "refactor"`, which could arm refactor epics before transitioning to the cadence `refactor` phase.

---

## 2. Changes Implemented (AC+)
- `loop/roadmap_cadence.py`: In `advance_replan`, added validation `if resolved_epic in state.replan_outcomes:` raising `ValueError(f"cannot advance replan: epic {resolved_epic!r} already has terminal replan outcome {existing.outcome!r}")` to reject duplicate replan operations on already terminal pair IDs.
- `loop/roadmap_queue.py`: In `roadmap_advance`, made non-idle phase handling unconditionally fail-closed by removing `if item_kind == "feature":`, so all tasks are blocked during `resync` and non-idle cadence phases.
- `loop/roadmap_queue.py`: In `roadmap_advance`, added an explicit check in the idle path denying `item_kind == "refactor"` with `error: "refactor_in_idle_denied"` and stop `NEED_HUMAN: refactor_in_idle_denied`.
- `loop/tests/test_roadmap_cadence.py`: Added test assertion in `test_advance_replan_validation` verifying duplicate `advance_replan` on an epic with an existing outcome raises `ValueError`.
- `loop/tests/test_roadmap_queue.py`: Added `test_roadmap_advance_resync_blocks_non_feature` and `test_roadmap_advance_denies_refactor_in_idle`.
- `memory-bank/back/bugfix/T-HUB-093-roadmap-cadence-replan-refactor-block/bugfix-queue.yaml`: Completed BF-001, BF-002, and BF-003 with passing evidence and timestamps.

---

## 3. Non-Goals / Fallback Purge (AC−)
- No refactor-before-replan path allowed.
- No replan-of-replan permitted.
- No carry FR steps between epics.
- No implementing from-queue resync here (deferred to T-HUB-094).
- Unrelated tests or modules untouched.

---

## 4. Integration Rule Counterparts (§0.11)
- **API / Schemas:** `RoadmapCadenceState`, `ReplanOutcomeRecord`, and `loop-gate-verdict/v1` schemas validated.
- **State files:** `memory-bank/back/roadmap/cadence.yaml`, `memory-bank/back/roadmap/queue.yaml`, `memory-bank/back/bugfix/T-HUB-093-roadmap-cadence-replan-refactor-block/bugfix-queue.yaml`.
- **Test counterparts:** `loop/tests/test_roadmap_cadence.py` (20 tests passed) and `loop/tests/test_roadmap_queue.py` (50 tests passed).
- **Orphan check:** No dangling references, phantom variables, or broken imports created.

---

## 5. Blockers Resolved
- **BF-001:** `loop/roadmap_cadence.py` duplicate replan outcome rejected — PASS
- **BF-002:** `loop/roadmap_queue.py` fail-closed non-idle phase advance — PASS
- **BF-003:** `loop/roadmap_queue.py` idle refactor arm denial — PASS

---

## 6. Verification
- Targeted verification:
  ```bash
  bin/pytest loop/tests/test_roadmap_cadence.py -q --tb=line
  bin/pytest loop/tests/test_roadmap_queue.py -q --tb=line
  ```
  Output: 20 passed in `test_roadmap_cadence.py`, 50 passed in `test_roadmap_queue.py`.
- Full test suite verification:
  ```bash
  bin/pytest -q --tb=line
  ```
  Output: 2873 passed, 3 skipped in 94.19s.
