# Bugfix: Classifier Line-Joining Adversarial Hole and Parity Check Rigor
**Epic ID:** T-HUB-080-workflow-capability-instruction-parity  
**Date:** 2026-09-10  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-080-workflow-capability-instruction-parity/qa-20260910-classifier-adversarial-parity-gap.yaml  

---

## 1. QA Root Cause Analysis
During BACK QA verification for epic `T-HUB-080-workflow-capability-instruction-parity`, the following blockers were reported:
1. `AC−-1/AC−-3`: `classify_instruction_line` unconditionally combined the current line with the previous line (`combined = f"{prev_line} {line}".strip()`) before evaluating negative and read-only patterns. If `prev_line` contained a negative statement or read-only guard (e.g. `FORBIDDEN: raw runner fallback` or `Do not run pytest`), a subsequent line containing an unqualified runner action (`bin/pytest loop/tests/`) would be falsely allowed. Adversarial test coverage for this multi-line bypass was missing.
2. `AC-7/AC−-5`: `test_role_command_skills_parity` verified only keyword presence (`"capability_checks" in text or "managed" in text.lower()`) rather than full policy text and semantic equivalence across runtime skill copies and entrypoints (`AGENTS.md`, `CLAUDE.md`, `DSH.md`, `main.md`).

## 2. Changes Implemented
- `loop/tests/test_stack_profile_instruction_inventory.py`:
  1. Updated `classify_instruction_line`:
     - Evaluates `NEGATIVE_PAT`, `READONLY_PAT`, `PARENT_ONLY_PAT`, `HUB_SCOPE_PAT`, and `MANAGED_SCOPE_PAT` directly on `line`.
     - Ensures `prev_line` never qualifies a runner line if `prev_line` contains negative guards or read-only statements.
     - Enhanced `NEGATIVE_PAT` to recognize `не запускать/не запускайте/не запускай`.
  2. Added `test_adversarial_classifier_fixtures` covering 12 adversarial negative/read-only multi-line pairs to verify that negative preceding lines never mask subsequent runner commands.
  3. Upgraded `test_role_command_skills_parity` to assert strict text equality (`codex_text == claude_text`) and explicit `capability_checks` / `dev-hub` policy markers.
  4. Added `test_entrypoints_parity` verifying exact section equivalence of `## Root classification & Testing` across `AGENTS.md`, `CLAUDE.md`, `DSH.md`, and `harness/instructions/main.md`.

## 3. Verification
- `bin/pytest loop/tests/test_stack_profile_instruction_inventory.py -q --tb=line` (18 passed)
- `bin/pytest harness/hooks/tests/test_epic_yaml_capability_evidence.py harness/hooks/tests/test_tests_format_managed_capabilities.py harness/hooks/tests/test_role_core_contract.py -q --tb=line` (19 passed)
- `python3 -m loop.cli.runtime_sync --check`
