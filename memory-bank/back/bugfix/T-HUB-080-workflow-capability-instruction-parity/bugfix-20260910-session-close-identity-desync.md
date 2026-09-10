# Bugfix: Session close identity desync

Root: record_abort stamped post-mb-finish ANALYZE; check_after promoted with stale receipt.

Fix: loop/session_finalize.py shared freeze/close + Claude probe in check_after + adapters.

Verify: 22 passed targeted pytest.
