# Bugfix: Sunset Purge Test Mismatch Reconciliation
**Epic ID:** T-HUB-080-workflow-capability-instruction-parity  
**Date:** 2026-09-10  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-080-workflow-capability-instruction-parity/qa-20260910-sunset-purge-mismatch.yaml  

---

## 1. QA Root Cause Analysis
During BACK QA verification for epic `T-HUB-080-workflow-capability-instruction-parity`, the following blocker was reported:
- s05 implement artifact `s05-legacy-fallback-purge.yaml` declared the deletion of `test_sunset_a_b_c_i_scans_have_no_live_legacy_authority` (as planned in the s05 decompose step / sunset inventory), but the test function remained in `loop/tests/test_stack_profile_instruction_inventory.py` with partial legacy symbol assertions.

## 2. Changes Implemented
- `loop/tests/test_stack_profile_instruction_inventory.py`:
  - Removed obsolete test function `test_sunset_a_b_c_i_scans_have_no_live_legacy_authority`.
  - Full Kind A, B, C, and I inventory scans (`test_corpus_inventory`, `test_synthetic_fixtures`, `test_front_parent_only_boundary`, etc.) and capability checks validation tests continue to comprehensively verify capability and instruction parity without keeping dead partial symbols.

## 3. Verification
- `bin/pytest loop/tests/test_stack_profile_instruction_inventory.py -q --tb=line` (15 passed)
- `bin/pytest harness/hooks/tests/test_epic_yaml_capability_evidence.py harness/hooks/tests/test_tests_format_managed_capabilities.py harness/hooks/tests/test_role_core_contract.py -q --tb=line` (19 passed)
- `python3 -m loop.cli.runtime_sync --check` (No drift detected)
