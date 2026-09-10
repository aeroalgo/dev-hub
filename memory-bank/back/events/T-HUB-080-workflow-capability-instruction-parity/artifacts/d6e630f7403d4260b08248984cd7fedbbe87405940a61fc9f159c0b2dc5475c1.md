# Bugfix: Instruction Capability Evidence Parity and Inventory Classifier Tightening
**Epic ID:** T-HUB-080-workflow-capability-instruction-parity  
**Date:** 2026-09-10  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-080-workflow-capability-instruction-parity/qa-20260910-capability-instruction-parity-retest.yaml  

---

## 1. QA Root Cause Analysis
During BACK QA verification for epic `T-HUB-080-workflow-capability-instruction-parity`, the following issues were identified:
1. **AC+1/6 (`harness/cursor/rules/integration_developer/mainrule-core.mdc:17`):** The scenario test section contained `managed: declared HTTP/API capability evidence` and lacked explicit `capability_checks` and typed evidence wording.
2. **AC-1/2 (`loop/tests/test_stack_profile_instruction_inventory.py`):** `MANAGED_SCOPE_PAT` exempted any runner line mentioning generic `managed projects` or capability markers even when an unqualified runner command was used, making the classifier non-fail-closed when mixed commands were provided.
3. **DSH entrypoint inventory gap (`loop/tests/test_stack_profile_instruction_inventory.py:108, :378`):** `DSH.md` was omitted from `get_active_corpus_files` and `test_entrypoints_inventory`.

Additionally, §0.11 link validation detected an erroneous file extension `.claude/instructions/program-loop.mdc` (canonical is `.claude/instructions/program-loop.md`) in `harness/cursor/rules/integration_developer/mainrule-core.mdc` and its mirror.

---

## 2. Changes Implemented
- `harness/cursor/rules/integration_developer/mainrule-core.mdc` & `.cursor/rules/integration_developer/mainrule-core.mdc`:
  - Updated line 17 to explicitly require `capability_checks` with typed evidence: `Hub (dev-hub self-test) pytest HTTP outcome (контракт; managed: declare capability_checks with typed evidence)`.
  - Fixed §0.11 link target from `.claude/instructions/program-loop.mdc` to `.claude/instructions/program-loop.md`.
- `loop/tests/test_stack_profile_instruction_inventory.py`:
  - Added `base / "DSH.md"" to `get_active_corpus_files` and `"DSH.md"" to `test_entrypoints_inventory`.
  - Tightened `MANAGED_SCOPE_PAT` and expanded `NEGATIVE_PAT` (covering Russian and English anti-fallback / prohibition phrasing) to ensure fail-closed classification on unqualified runner actions.
  - Added mixed negative fixtures (`Managed capability_checks: run bin/pytest -q --tb=line`, `Declare capability_checks and execute bin/pytest directly`, `capability_checks: run pytest`, `In managed roots, use capability_checks with cargo test`, `capability_checks: bin/pytest -q --tb=line`, `For managed projects with capability_checks, execute pytest`).
  - Restored diagnostic-shape and representative unrewritten-sample assertions using injected fixtures, while keeping the real active corpus assertion fail-closed with `assert not all_violations`.

---

## 3. Verification
- `bin/pytest loop/tests/test_stack_profile_instruction_inventory.py harness/hooks/tests/test_role_core_contract.py harness/hooks/tests/test_role_core_mode_regression.py -v` — PASS.
- Active corpus inventory scan (223 files including `DSH.md`) reports 0 unqualified runner action violations.
