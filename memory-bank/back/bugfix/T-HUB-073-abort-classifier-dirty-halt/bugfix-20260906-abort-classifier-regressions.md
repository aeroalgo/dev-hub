# BUGFIX: Abort classifier regression fixes in fallback and codex resilience

- **Date:** 2026-09-06
- **Epic:** T-HUB-073-abort-classifier-dirty-halt
- **Source:** QA Fix Plan (`memory-bank/back/qa/T-HUB-073-abort-classifier-dirty-halt/qa-20260906-abort-classifier-dirty-halt-fail.yaml`)

## Root Cause
1. `loop/tests/test_hooks_llm_fallback.py`: Тест `test_all_flags_off_zero_llm_calls` проверял `classify_abort(text_abort)` на неизвестном тексте (`abort_unknown.txt`) с устаревшим ожиданием `'transient'`. По спецификации T-HUB-073 (FR-010) неизвестные ошибки классифицируются fail-closed как `'fatal'`.
2. `harness/hooks/session_resilience.py`: В `_TRANSIENT_ABORT_PATTERNS` отсутствовал шаблон `r"(?i)^\s*(?:session\s+)?aborted\s*$"`, из-за чего строка `Session aborted by user signal.` в логе сессии Codex (`codex_session_aborted.log`), возвращающая причину `'aborted'`, классифицировалась как `UNKNOWN_FAILURE` вместо `TRANSIENT_ABORT`.

## Fix
1. `harness/hooks/session_resilience.py`: Добавлен pattern `re.compile(r"(?i)^\s*(?:session\s+)?aborted\s*$")` в `_TRANSIENT_ABORT_PATTERNS`.
2. `loop/tests/test_hooks_llm_fallback.py`: Обновлено утверждение в `test_all_flags_off_zero_llm_calls` на `assert res_abort == "fatal"`.

## Verification
- Unit: `bin/pytest loop/tests/test_hooks_llm_fallback.py loop/tests/test_session_resilience_codex.py -q --tb=short` (9 passed)
- Full suite: `bin/pytest -q --tb=line` (2192 passed, 3 skipped, 80 warnings)
