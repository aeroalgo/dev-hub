# ANALYZE artifact

ANALYZE — это **STRICTLY READ-ONLY** проверка готового plan/decompose перед первым IMPLEMENT. Отчёт фиксирует покрытие требований, детерминированные findings и рекомендацию следующего шага.

ANALYZE не заменяет AUDIT: ANALYZE ищет пробелы до реализации и не создаёт audit-shards, не сравнивает implement с plan и не изменяет исходные артефакты.

## Когда запускать

- после FINISH `BACK|FRONT|INTEG DECOMPOSE`;
- до первого `* IMPLEMENT`;
- повторно после существенного rewrite plan/decompose.

## Как запускать

Кратко: как запускать ANALYZE — выбрать role-command для эпика; как читать результат — смотреть findings, coverage, metrics и recommendation.

Выберите role-command для эпика:

```text
BACK ANALYZE <epic_id>
FRONT ANALYZE <epic_id>
INTEG ANALYZE <epic_id>
```

Артефакт создаётся по шаблону `epic-analyze.yaml` в `memory-bank/{role}/analyze/<epic_id>/analyze-YYYYMMDD-<slug>.yaml`. Workflow: `@.cursor/rules/back_developer/workflow-analyze.mdc` (BACK) и соответствующие role wrappers.

## Как читать результат

- `findings` — детерминированная таблица находок с category, severity, message и source; показывается не более 50 строк, overflow отражается в metrics.
- `coverage` — требования и decompose-шаги, включая покрытые, отсутствующие и orphan mappings.
- `metrics` — сводные `coverage_pct`, `critical_count`, counts по severity и число overflow findings.
- `recommendation` — следующий безопасный шаг: IMPLEMENT при нулевом CRITICAL либо CLARIFY/PLAN/DECOMPOSE для исправления пробелов.

Результат с `critical_count > 0` не разрешает IMPLEMENT: сначала требуется fix через CLARIFY, PLAN или DECOMPOSE, затем повторный ANALYZE. При отсутствии CRITICAL следующий шаг — IMPLEMENT указанного shard.

## Ссылки

- Workflow: `@.cursor/rules/shared/workflow-analyze-core.mdc` и role-specific `workflow-analyze.mdc`.
- Схема: `.cursor/templates/analyze/epic-analyze.yaml`.
- Reference adaptation: `memory-bank/back/plan/refs/speckit-adapt-011.md`.
- Dry-run fixture: `memory-bank/back/plan/decompose-T-HUB-011-analyze-pre-implement/fixtures/fake-missing-coverage/`.
