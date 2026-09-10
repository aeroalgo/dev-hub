# Bugfix: Template Parity Rigor and Full Sunset Legacy Corpus Scanner
**Epic ID:** T-HUB-080-workflow-capability-instruction-parity  
**Date:** 2026-09-10  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-080-workflow-capability-instruction-parity/qa-20260910-template-parity-legacy-scan-gap.yaml  

---

## 1. QA Root Cause Analysis
During BACK QA verification for epic `T-HUB-080-workflow-capability-instruction-parity`, the following blockers were identified:
1. `B1 (AC+4)`: `test_templates_inventory` in `loop/tests/test_stack_profile_instruction_inventory.py:485` checked only for the absence of unqualified runner actions rather than enforcing exact structural, schema, header, and section parity across all canonical artifact templates (`plan.md`, `decompose/epic-step.yaml`, `decompose/legacy-purge-step.yaml`, `decompose/index.yaml`, `implement/epic-step.yaml`, `qa/epic-step.yaml`, `refactor/epic-step.yaml`, `security/epic-step.yaml`, `analyze/epic-analyze.yaml`, `audit/epic-audit.yaml`, `integration-plan.md`, `finish-doc-router.md`).
2. `B2 (AC+5)`: `test_sunset_a_b_c_i_scans_have_no_live_legacy_authority` in `loop/tests/test_stack_profile_instruction_inventory.py:531` imported validator modules but did not execute a comprehensive active corpus scan against sunset legacy patterns across Kind A (live validator authority execution), Kind B (anti-fallback patterns across all active files), Kind C (silent defaults / unqualified runners across the entire active corpus), and Kind I (all 15 sunset instruction patterns across rules, skills, entrypoints, templates, and operator docs).

## 2. Changes Implemented
- `loop/tests/test_stack_profile_instruction_inventory.py`:
  1. Enhanced `test_templates_inventory`:
     - Added strict structural schema and key validation for all canonical YAML templates (`decompose/epic-step.yaml`, `decompose/legacy-purge-step.yaml`, `decompose/index.yaml`, `implement/epic-step.yaml`, `qa/epic-step.yaml`, `refactor/epic-step.yaml`, `security/epic-step.yaml`, `analyze/epic-analyze.yaml`, `audit/epic-audit.yaml`, `roadmap-queue.yaml`), asserting exact schema names, required top-level keys, and required capability check evidence and hub-scoped markers.
     - Added strict Markdown section header and body parity validation for all canonical Markdown templates (`plan.md`, `integration-plan.md`, `finish-doc-router.md`, `tasks-log-month.md`, `constitution.md`, `idea-pipeline.md`, `decompose/index.md`).
  2. Maintained `test_entrypoints_and_templates_have_semantic_destination_parity`:
     - Asserts exact destination parity between source entrypoints and runtime files (`AGENTS.md`, `CLAUDE.md`, `DSH.md`, `main.md`).
     - Verifies 1:1 projection content equality between canonical `harness/cursor/templates/` and runtime `.cursor/templates/`.
  3. Expanded `test_sunset_a_b_c_i_scans_have_no_live_legacy_authority`:
     - **Kind A**: Executed live `CapabilityCheckSpec` validation, unmanaged runner rejection (`is_allowed_test_command`), `validate_tests_entries`, and `implement_ready_for_finalize_doc` checks.
     - **Kind B**: Scanned the entire active corpus (>=200 files across rules, skills, entrypoints, templates, docs) to ensure zero silent fallback to generic/raw runners when capability checks fail or are unconfigured.
     - **Kind C**: Automated full corpus regex scanning of all active rules, skills, entrypoints, templates, and operator docs to guarantee zero silent default runner patterns, unqualified HTTP scenarios, or hardcoded presence allowlists.
     - **Kind I**: Scanned each of the 15 sunset patterns (inv-i-01 through inv-i-15) against its declared active target AND across the entire active corpus, ensuring no line contains live legacy authority without proper classification.
     - **Live finalize validation**: Asserted a capability-checks implement document is accepted and a raw `pytest` test command is rejected by `implement_ready_for_finalize_doc`.

## 3. Verification
- `bin/pytest loop/tests/test_stack_profile_instruction_inventory.py -q --tb=line` (19 passed)
- `python3 -m loop.cli.runtime_sync --check` (No drift detected)
