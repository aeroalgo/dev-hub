# BUGFIX: T-HUB-068-start-finish-transaction-boundary

- **Date:** 2026-09-06
- **Epic:** T-HUB-068-start-finish-transaction-boundary
- **Role:** BACK
- **Phase:** BUGFIX
- **QA source:** memory-bank/back/qa/T-HUB-068-start-finish-transaction-boundary/qa-20260906-start-finish-transaction-boundary.yaml

## QA Issues & Root Cause

### ISS-001: finish_handoff forbidden check breaks legacy tests and pack integration
- **Root Cause:** In T-HUB-068, `finish_handoff` was intentionally hardened to be internal-only and require a valid `recovery_token` matching the active transaction journal (`FinishTxRecord`). Existing unit/integration tests (`test_mb_finish_handoff.py`, `test_pack_integration.py`, `test_finish_bugfix.py`) invoked `finish_handoff` directly without setting up an active transaction journal or providing a recovery token.
- **Fix:** Updated test cases to set up a prepared transaction journal with matching `recovery_token`, aligning test harnesses with FR-007 / US-002 requirements while preserving tokenless rejection tests in `test_mb_finish_transaction.py`.

### ISS-002: prepare_session cursor sync flag race with recover_finish_transaction
- **Root Cause:** In `loop/mb_finish/transaction.py`, `recover_finish_transaction` had a fallback block that re-armed `activeContext` when no journal was present. This caused `prepare_session`'s subsequent `sync_cursor_from_index` call to report `synced=False` (`already_aligned`) instead of letting `sync_cursor_from_index` perform the canonical sync and return `synced=True`.
- **Fix:** Removed the redundant unjournaled re-arm fallback from `recover_finish_transaction`, allowing `sync_cursor_from_index` (SoT) to handle cursor synchronization cleanly during `prepare_session`.

## Verification Evidence
- `bin/pytest harness/hooks/tests/test_mb_finish_handoff.py harness/hooks/tests/test_mb_finish_legacy_purge.py loop/tests/test_pack_integration.py loop/tests/test_finish_bugfix.py loop/tests/test_context_loop.py -q --tb=line` -> 100% PASS
- `bin/pytest loop/tests/test_mb_finish_transaction.py -q --tb=line` -> 100% PASS
- Full suite: `bin/pytest -q --tb=line` -> 2104 passed, 3 skipped (100% PASS)
