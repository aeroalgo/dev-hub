# BACK BUGFIX — T-HUB-049-workflow-pack-phase-router — fix-qa-work-block-rule-dir

- **Дата:** 2026-09-04
- **Источник:** `memory-bank/back/qa/T-HUB-049-workflow-pack-phase-router/qa-20260904-workflow-pack-phase-router.yaml`, Issue ISS-001
- **Эпик:** `T-HUB-049-workflow-pack-phase-router`
- **Статус:** исправление подтверждено полным прогоном suite; 0 failures

## Симптом

QA зафиксировал blocker ISS-001: в `loop/context_loop.py:_qa_work_block` происходил NameError из-за неинициализированной переменной `rule_dir`.

## Root cause

В функции `_qa_work_block(role: str, epic_id: str)` формировался f-string с интерполяцией `{rule_dir}`, но переменная `rule_dir` не была предварительно вычислена через `_decompose_role_rule_dir(role)`.

## Исправление

1. В `loop/context_loop.py` добавлено определение `rule_dir = _decompose_role_rule_dir(role)` в `_qa_work_block`.
2. В `loop/tests/test_context_loop.py` добавлен юнит-тест `test_qa_and_audit_work_blocks_render_properly` для проверки рендеринга `_qa_work_block` и `_audit_work_block`.

## Проверка исправления

- `bin/pytest loop/tests/test_context_loop.py -q --tb=line` — passed
- `bin/pytest -q --tb=line` — 1772 passed, 3 skipped, 72 warnings

## Delta

- `loop/context_loop.py`
- `loop/tests/test_context_loop.py`
- `memory-bank/back/bugfix/T-HUB-049-workflow-pack-phase-router/bugfix-20260904-fix-qa-work-block-rule-dir.md`

## Acceptance

- [x] AC+: `_qa_work_block` корректно инициализирует `rule_dir` и рендерит канонический блок QA без NameError.
- [x] AC-: Отсутствуют NameError и unhandled exceptions при подготовке сессии фазы QA.
- [x] Полный pytest suite зелёный (1772 passed, 0 failures).

## Следующий шаг

Повторный `BACK QA` эпика T-HUB-049-workflow-pack-phase-router.
