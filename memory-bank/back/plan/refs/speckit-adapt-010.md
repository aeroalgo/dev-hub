# Spec Kit adaptation — T-HUB-010

## Что взяли из Spec Kit

- Последовательные уточнения: не более пяти целевых вопросов, по одному за ход.
- Для каждого варианта ответа показываем Recommended/Suggested.
- Ответ сразу инкрементально записывается в черновик.
- Используем taxonomy покрытия из восьми категорий.
- Для каждой User Story сохраняем Independent Test.
- Success Criteria оформляем как измеримые `SC-###` и отделяем outcome от buildable.
- Завершаем коротким Completion Report: вопросы, затронутые секции, coverage, deferred/outstanding и next command.
- Из шаблона спецификации сохраняем независимые P1/P2/P3 scenarios, Edge Cases, Requirements и measurable outcomes.

## Что отвергли / адаптировали

- `FEATURE_DIR/specs/###-feature/` заменён на `memory-bank/{role}/clarify/`.
- `{SCRIPT}` / `check-prerequisites` не переносим: shell gates живут в rules.
- Extension hooks YAML не переносим.
- `__SPECKIT_COMMAND_*` placeholders не переносим в рабочий workflow.
- Constitution Articles I–IX вынесены в T-HUB-013.
- ANALYZE/AUDIT converge вынесены в T-HUB-011/T-HUB-012.
- `spec-kit/extensions/assess/` учитывается частично в T-HUB-013.
- Handoff к `speckit.plan` заменён переходом к локальному BACK/FRONT/INTEG PLAN.
- Локальный `spec-kit/templates/commands/clarify.md` используется только как read-only reference.

## FORBIDDEN

**FORBIDDEN: install specify-cli / specify init / создавать `.specify/` / заменять `memory-bank/` на `specs/`.**

## Refs

- `spec-kit/templates/commands/clarify.md` — локальный reference для вопросов, записи Clarifications и Completion Report.
- `spec-kit/templates/spec-template.md` — локальный reference для scenarios, requirements и `SC-###`.
