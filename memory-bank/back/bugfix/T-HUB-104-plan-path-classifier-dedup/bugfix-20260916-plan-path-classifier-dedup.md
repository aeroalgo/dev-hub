# Bugfix: Hook Registration Parity, Classifier Assertion Deduplication, and Case Sensitivity Restoration
**Epic ID:** T-HUB-104-plan-path-classifier-dedup  
**Date:** 2026-09-16  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-104-plan-path-classifier-dedup/qa-20260916-plan-path-classifier-dedup-r2.yaml

---

## 1. QA Root Cause Analysis
During BACK QA review rounds for `T-HUB-104-plan-path-classifier-dedup`, four issues were identified across hook registration parity, classifier test deduplication, and classifier case-sensitivity/boundary parity:
1. **Hook Registration Parity (BF-001, BF-002):**
   - 4 failures in `harness/hooks/tests/test_hook_registration_consolidation.py` and 1 failure in `loop/tests/test_hub_link_harness.py`.
   - *Root Cause:* `.claude/settings.json` contained references to obsolete individual hook scripts instead of canonical consolidated dispatchers (`pretool-dispatch.py`, `posttool-dispatch.py`).
2. **Classifier Assertions Deduplication (BF-003):**
   - Redundant unit assert checks on `is_markdown_plan_path` remained in `loop/tests/test_mb_load_session.py:530` after parametrized characterization matrix was introduced.
   - *Root Cause:* Direct classifier unit asserts were kept inside the integration test `test_path_only_classifier_and_load_session_plan_md`.
3. **Classifier Case-Sensitivity and Boundary Behavior (BF-004):**
   - `_MARKDOWN_PLAN_PATTERN` in `loop/mb_load/plan_section.py:17` used `re.IGNORECASE` and wildcard matching, deviating from original case-sensitive `session.py:is_markdown_plan_path` behavior.
   - *Root Cause:* Consolidated regex compilation flag `re.IGNORECASE` was inadvertently applied to `_MARKDOWN_PLAN_PATTERN`, and subpatterns allowed prefix dashes without alphanumeric body.

---

## 2. Changes Implemented (AC+)
- `.claude/settings.json`: Restored canonical configuration matching `harness/manifest.yaml` (dispatchers only).
- `loop/tests/test_mb_load_session.py`: Removed redundant unit assertions from `test_path_only_classifier_and_load_session_plan_md` (line 530), relying on characterization matrix in `test_plan_path_classifier_characterization.py`.
- `loop/mb_load/plan_section.py`: Removed `re.IGNORECASE` from `_MARKDOWN_PLAN_PATTERN` (lines 17-19) and adjusted subpattern bounds `plan-[^/\\]+\.md`, `gap-[^/\\]+\.md`, `analyze-[^/\\]+\.md` to preserve exact case-sensitive matching identical to original `session.py` implementation.
- `loop/tests/test_plan_path_classifier_characterization.py`: Added explicit case-sensitivity and boundary characterization test cases to freeze deny matrix.
- `memory-bank/back/bugfix/T-HUB-104-plan-path-classifier-dedup/bugfix-queue.yaml`: Updated all items (`BF-001` .. `BF-004`) to `done` with targeted verification evidence, and verification status to `pass`.

---

## 3. Non-Goals / Fallback Purge (AC−)
- No fallback scripts or shims re-created.
- No dual classifier implementation bodies.
- Single owner for `is_markdown_plan_path` in `loop/mb_load/plan_section.py` preserved.
- Deny matrix semantics preserved without regression.

---

## 4. Integration Rule Counterparts (§0.11)
- **Settings / Manifest Parity:** `.claude/settings.json` strictly reflects `harness/manifest.yaml`.
- **State / Queue Parity:** `bugfix-queue.yaml` and bugfix report are fully synchronized.
- **Test Matrix:** Parametrized characterization matrix covers both `is_whole_plan_path` and `is_markdown_plan_path`.

---

## 5. Blockers Resolved
- `BF-001`: 4 failures in `harness/hooks/tests/test_hook_registration_consolidation.py` — Resolved (7 passed).
- `BF-002`: 1 failure in `loop/tests/test_hub_link_harness.py` — Resolved (5 passed).
- `BF-003`: Duplicated classifier asserts in `loop/tests/test_mb_load_session.py:530` — Resolved (20 passed).
- `BF-004`: Case sensitivity and boundary behavior in `loop/mb_load/plan_section.py` — Resolved (76 passed).

---

## 6. Verification
- Targeted verification:
  ```bash
  bin/pytest loop/tests/test_plan_path_classifier_characterization.py loop/tests/test_mb_load_session.py loop/tests/test_plan_jump_context_policy.py -q --tb=line
  ```
  Result: 76 passed in 2.15s.
- Full repository test suite (`verification.command`):
  ```bash
  bin/pytest -q --tb=line
  ```
  Result: 3005 passed, 4 skipped in 133.65s.
