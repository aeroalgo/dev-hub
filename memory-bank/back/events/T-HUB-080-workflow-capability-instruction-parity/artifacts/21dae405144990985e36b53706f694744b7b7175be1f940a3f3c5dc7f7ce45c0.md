# Bugfix: Legacy Authority and CapabilityCheckSpec Validation Gap
**Epic ID:** T-HUB-080-workflow-capability-instruction-parity  
**Date:** 2026-09-10  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-080-workflow-capability-instruction-parity/qa-20260910-legacy-authority-test-gap.yaml  

---

## 1. QA Root Cause Analysis
During BACK QA verification for epic `T-HUB-080-workflow-capability-instruction-parity`, the following blocker was reported:
- Deletion of `test_sunset_a_b_c_i_scans_have_no_live_legacy_authority` left a test coverage gap where invalid target/selector and legacy authority in `CapabilityCheckSpec` and hook test commands were not validated in `loop/tests/test_stack_profile_instruction_inventory.py`.

## 2. Changes Implemented
- `loop/tests/test_stack_profile_instruction_inventory.py`:
  - Restored `test_sunset_a_b_c_i_scans_have_no_live_legacy_authority` with explicit validations:
    1. Rejection of empty target and invalid capability selector in `CapabilityCheckSpec`.
    2. Rejection of managed project test commands (`cargo test --all-targets`, `npm run test`) by `is_allowed_test_command`.
    3. Verification that `ALLOWED_TEST_PREFIXES` contains no live managed runners (e.g. `cargo`).

## 3. Verification
- `bin/pytest loop/tests/test_stack_profile_instruction_inventory.py -q --tb=line` (16 passed)
- `bin/pytest harness/hooks/tests/test_epic_yaml_capability_evidence.py harness/hooks/tests/test_tests_format_managed_capabilities.py harness/hooks/tests/test_role_core_contract.py -q --tb=line` (19 passed)
- `python3 -m loop.cli.runtime_sync --check` (No drift detected)
