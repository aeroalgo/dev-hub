# BUGFIX T-HUB-071-stop-gate-test-identity-alignment

## Meta
- Date: 2026-09-06
- Epic: `T-HUB-071-session-identity-lock`
- Source: QA `memory-bank/back/qa/T-HUB-071-session-identity-lock/qa-20260906-session-identity-lock.yaml` (issue QA-FAIL-001)

## Root Cause
When session identity lock was introduced in T-HUB-071, `session_start_payload` enforces fail-closed validation on `resolve_session_identity` comparing activeContext frontmatter (`epic_id`), projection, and state.
In `loop/tests/test_stop_gate.py::test_session_start_payload_requires_epic_loop`, the fixture wrote `activeContext.md` without frontmatter (or with default `T-HUB-057`), while the plan path was `memory-bank/back/plan/decompose-ssp/index.md` which resolves epic to `ssp`.
This resulted in `code: epic_mismatch` drift HALT diagnostic instead of standard session start banner payload.

## Fix
Aligned `activeContext.md` frontmatter in `test_session_start_payload_requires_epic_loop` to `epic_id: ssp`, ensuring strict identity alignment with the decompose plan path.

## Evidence
- `bin/pytest loop/tests/test_stop_gate.py -k test_session_start_payload_requires_epic_loop -q --tb=short` -> 1 passed
- Full suite `bin/pytest -q --tb=line` -> 2168 passed, 3 skipped (100% green)
