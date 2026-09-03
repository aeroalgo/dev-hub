# BACK BUGFIX — T-HUB-057-loop-session-json-contract — loop-tests-suite-repair

- **Дата:** 2026-09-03
- **Источник:** `memory-bank/back/qa/T-HUB-057-loop-session-json-contract/qa-20260903-001.yaml`, Blocker #1
- **Эпик:** `T-HUB-057-loop-session-json-contract`
- **Статус:** исправление подтверждено полным прогоном suite; 0 failures

## Симптом

QA зафиксировал blocker `suite-not-green`: полный backend suite завершился с 22 failures в `loop/tests/` из-за ужесточения контракта loop-handoff/v1, state.json и finish_tool_missing.

## Root cause

1. `prepare_session` в `loop/context_loop.py` преждевременно завершался с `halt: True` при ошибках валидации формы activeContext вместо перехода в режим восстановления (`degraded: True`) до достижения лимита `degraded_max`.
2. `subagent-stop.py` валидировал loop-gate-verdict/v1 даже при передаче прямого вердикта без текстового сообщения, вызывая schema validation failure.
3. Устаревшие тесты в `loop/tests/` (`test_context_loop.py`, `test_handoff_strict_flag.py`, `test_mb_load_session.py`) использовали устаревшие моки и не передавали валидный loop-handoff/v1 frontmatter.

## Исправление

1. В `loop/context_loop.py` восстановлен degraded recovery путь при обнаружении ошибок валидации формы activeContext.
2. В `harness/hooks/subagent-stop.py` проверка loop-gate-verdict/v1 адаптирована для прямой передачи вердиктов.
3. В `loop/tests/` обновлены тестовые окружения и добавлены frontmatter и analyze-pass заглушки.

## Проверка исправления

- `bin/pytest loop/ harness/ -q --tb=line` — 1611 passed, 2 skipped (0 failures).

## Delta

- `loop/context_loop.py`
- `harness/hooks/subagent-stop.py`
- `loop/tests/test_context_loop.py`
- `loop/tests/test_handoff_strict_flag.py`
- `loop/tests/test_mb_load_session.py`
- `memory-bank/back/bugfix/T-HUB-057-loop-session-json-contract/bugfix-20260903-loop-tests-suite-repair.md`

## Acceptance

- [x] Полный pytest suite зелёный (0 failures).
- [x] Деградированный контекст корректно восстанавливается.
- [x] Все 22 падающих теста исправлены.

## Следующий шаг

Повторный `BACK QA` эпика T-HUB-057-loop-session-json-contract.
