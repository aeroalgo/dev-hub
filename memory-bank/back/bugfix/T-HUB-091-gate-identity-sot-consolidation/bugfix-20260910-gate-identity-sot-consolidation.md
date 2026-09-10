# Bugfix: Gate Identity SoT and Harness Runtime Parity Consolidation
**Epic ID:** T-HUB-091-gate-identity-sot-consolidation  
**Date:** 2026-09-10  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-091-gate-identity-sot-consolidation/qa-20260910-gate-identity-sot-consolidation.yaml

---

## 1. QA Root Cause Analysis
During full test suite execution in BACK QA (`bin/pytest -q --tb=line`), 12 test failures occurred across harness hooks, context loop, runtime sync parity, finish receipt integrity, and decompose finish transitions.

Root causes identified:
1. **Codex agent parity drift (`test_check_codex_parity_full_set`, `test_runtime_sync_cli_check_full_set_succeeds`, `test_parity_source_is_agents_glob_not_allowlist_only`):** Materialized `.codex/agents/*.toml` and `*.policy.json` were out of sync with updated instruction surfaces and policy fingerprints.
2. **Local variable scope shadowing (`test_posttool_fail_then_pass_mirrors_epic_last_verify`, `test_posttool_mirror_error_logs_stderr_and_saves_state`):** `harness/hooks/agent-posttool.py` imported `load_state` inside an inner branch in `main()`, causing `UnboundLocalError` when accessing `load_state` at the top level of `main()`.
3. **Role casing sensitivity in receipt matching (`test_finish_succeeds_with_valid_current_verifier_receipt`):** `GateIdentity` resolved `armed_role` as lowercase `'back'`, while the verifier receipt contained uppercase `'BACK'`, causing `match_gate_evidence` / `validate_verifier_receipt` to fail with `verdict_stale`.
4. **Premature DECOMPOSE rearm condition in prepare_session (`test_prepare_does_not_promote_analyze_from_artifact_without_receipt`):** `prepare_session` checked `decompose_verify_pass_ready` whenever `armed_step == "ANALYZE"`, incorrectly reverting ANALYZE states to DECOMPOSE instead of validating ANALYZE completion without receipt.
5. **Missing manual authority flag in synthetic decompose test fixtures (`test_finish_decompose_arm`, `test_finish_decompose_armed_step`, `test_finish_decompose_infers_decompose_from_active_context_when_state_missing`):** Test cases in `test_mb_finish_decompose.py` did not include verifier pass evidence matching `finish_decompose` finish gates.

---

## 2. Changes Implemented
- `harness/hooks/agent-posttool.py`:
  - Removed inner shadowed `load_state` import from `main()`, relying on module-level import to prevent `UnboundLocalError`.
- `loop/gate_identity.py`, `harness/hooks/_lib.py`, `harness/hooks/gate_receipt.py`:
  - Normalized `role` handling and made `role` matching case-insensitive in `match_gate_evidence` and `validate_verifier_receipt`.
- `loop/context_loop.py`:
  - Corrected `prepare_session` rearm guard to only revert from `mode: ANALYZE` to `DECOMPOSE` when `armed_step == "DECOMPOSE"` and `decompose_verify_pass_ready` is false.
- `harness/hooks/tests/test_mb_finish_decompose.py`:
  - Updated synthetic decompose finish fixtures to provide valid `last_verify_verdict` and evidence.
- `.codex/agents/`:
  - Materialized all Codex agent configs and policy files via `bin/runtime-sync --apply`.

---

## 3. Verification
- `bin/pytest loop/tests/test_runtime_sync_check.py loop/tests/test_codex_hooks_bridge.py -v` — PASS (23 passed)
- `bin/pytest loop/tests/test_agent_hooks.py -v` — PASS (25 passed)
- `bin/pytest loop/tests/test_finish_receipt_integrity.py -v` — PASS (5 passed)
- `bin/pytest harness/hooks/tests/test_mb_finish_decompose.py -v` — PASS (6 passed)
- `bin/pytest loop/tests/test_context_loop.py::test_prepare_does_not_promote_analyze_from_artifact_without_receipt -v` — PASS (1 passed)
- `bin/pytest -q --tb=line` — PASS (2370 passed, 4 skipped, 78 warnings)
