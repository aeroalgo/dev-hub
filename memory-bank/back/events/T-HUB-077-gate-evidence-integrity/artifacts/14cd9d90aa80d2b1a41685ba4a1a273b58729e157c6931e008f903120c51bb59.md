# Bugfix: Fix test suite regression fixtures under fail-closed receipt enforcement

**Epic ID:** T-HUB-077-gate-evidence-integrity  
**Date:** 2026-09-07  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-077-gate-evidence-integrity/qa-20260907-gate-evidence-integrity.yaml

---

## 1. QA Root Cause Analysis

Under the implementation of fail-closed runtime verifier receipts (FR-001–FR-007):
1. `test_finish_boundary_pretool.py`: Subprocess test environment inherited global `DEV_HUB` / `HUB_ROOT` environment variables causing runtime state path lookup to redirect outside the test `tmp_path`.
2. `test_stop_gate.py`: Direct state mutation assertion checked obsolete `state_projection_forbidden` instead of updated `runtime_gate_write_forbidden`.
3. `test_finish_bugfix.py`: BUGFIX test fixture recorded manual authority without projection rebuild, failing digest verification against runtime receipt.
4. `test_finish_integrity.py`: `finalize-step` tests passed legacy `manual` authority fixtures which were rejected under fail-closed non-manual authority enforcement for non-bugfix steps. Also `_verify_pass_ready_for_step` checked `_projection_digest` instead of `receipt_digest` for structured receipts.

---

## 2. Changes Implemented

- `harness/hooks/epic/core.py`: Updated `_verify_pass_ready_for_step` for `BUGFIX` step to properly inspect `evidence.get("receipt_digest")` for `loop-verifier-receipt/v1` schema.
- `harness/hooks/tests/test_finish_boundary_pretool.py`: Removed inherited `DEV_HUB` and `HUB_ROOT` in test runner subprocess environment so `state_path` is scoped to `tmp_path`.
- `loop/tests/test_stop_gate.py`: Updated assertion to check `runtime_gate_write_forbidden`.
- `loop/tests/test_finish_bugfix.py`: Updated fixture to rebuild projection and issue valid `loop-verifier-receipt/v1` receipt.
- `loop/tests/test_finish_integrity.py`: Updated test fixtures to provide valid autonomous verifier receipt evidence and asserted `matched` diagnostic.

---

## 3. Verification

Full regression suite:
```
bin/pytest -q --tb=line
2313 passed, 3 skipped, 82 warnings in 216.24s (0:03:36)
```
Targeted regression files:
- `harness/hooks/tests/test_finish_boundary_pretool.py` — PASS
- `loop/tests/test_finish_bugfix.py` — PASS
- `loop/tests/test_finish_integrity.py` — PASS
- `loop/tests/test_stop_gate.py` — PASS
