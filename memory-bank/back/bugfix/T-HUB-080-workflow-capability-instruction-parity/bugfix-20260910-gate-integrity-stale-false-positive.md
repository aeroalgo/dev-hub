# Bugfix: False gate_integrity:verdict_stale on successful session close

## Root cause
`_terminal_integrity_diagnostic` возвращал **первый** integrity-токен (`verdict_stale` / `verdict_wrong_step`) из любой `mb-finish`/`finalize-step`/`stop-gate` команды в логе. `analyze_session_log` безусловно превращал это в `gate_integrity:*` transient abort (`backoff_sec=0`), даже когда:
1. поздний `mb-finish` завершился с `ok: true` / exit 0;
2. handoff уже записан (BUGFIX→QA);
3. outer process exit=0.

Из-за этого loop печатал `TRANSIENT API abort` (misleading label для любого retryable) и сразу ретраил parent.

## Fix
- Terminal diagnostic = **last wins**.
- Успешный terminal finish (`"ok": true` + non-failed exit) очищает earlier diagnostic.
- Неразрешённый last fail по-прежнему даёт `gate_integrity:*`.

## Files
- `harness/hooks/session_resilience.py`
- `loop/tests/test_gate_integrity_finish_clear.py`
- `loop/loop.sh` (label: gate_integrity ≠ API abort)

## Verify
`bin/pytest loop/tests/test_gate_integrity_finish_clear.py loop/tests/test_runtime_session_evidence.py -q --tb=line`
