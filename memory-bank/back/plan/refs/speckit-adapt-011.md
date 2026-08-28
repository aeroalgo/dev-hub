# Spec Kit adaptation — T-HUB-011

## Что взяли из Spec Kit

- **detection passes** как фиксированную taxonomy: Duplication, Ambiguity, Underspecification, Coverage Gaps, Inconsistency и Constitution.
- Severity heuristic `CRITICAL / HIGH / MEDIUM / LOW`; `CRITICAL` означает, что IMPLEMENT нельзя начинать без исправления или явного defer.
- **50-cap** для findings: в таблицу попадают первые 50 детерминированных находок, overflow сводится в summary и metrics.
- Constitution authority: нарушение обязательного MUST-требования конституции получает `CRITICAL`, если constitution-файл существует.
- **STRICTLY READ-ONLY**: ANALYZE не меняет plan, decompose или исходные shards; выдаёт только report и optional remediation plan после approval пользователя.
- Progressive disclosure: сначала загружаются заголовки и sample shards, а не полный dump всех артефактов.
- Детерминированные IDs, counts и recommendation, чтобы повторный запуск без изменений давал сопоставимый результат.

## Что отвергли / адаптировали

- Feature-directory/spec layout `###-feature` заменён на `memory-bank/{role}/analyze/<epic_id>/`.
- `{SCRIPT}/check-prerequisites.sh` не портируется: prerequisites проверяются в workflow и lean-gate (наличие plan и decompose index).
- extension hooks не портируются: ANALYZE не выполняет before/after callbacks и не читает runtime-конфигурацию расширений.
- Command placeholders не портируются: команда выбирается role-command router, а не macro substitution.
- `spec-kit analyze` адаптирован в `ANALYZE`; канонический отчёт — YAML по шаблону `epic-analyze.yaml`, а не markdown по умолчанию.
- Pre-hook execution не портируется: ANALYZE только читает входные артефакты и формирует findings.
- Отсутствие `constitution.md` не блокирует dry-run: проверка Constitution pass пропускается с явной отметкой `n/a`.

## FORBIDDEN

- Устанавливать внешний CLI или выполнять init-команды только ради ANALYZE.
- Создавать служебный каталог `.specify/` или заменять `memory-bank/` на отдельный каталог спецификаций.
- Выполнять extension hooks before/after analysis.
- Выполнять command macros, shell prerequisites или любые mutating scripts из reference.
- Изменять исходные plan/decompose-файлы во время ANALYZE.

## Refs

- `spec-kit/templates/commands/analyze.md` — локальный read-only reference для detection principles, severity, cap и read-only boundary.
- `spec-kit/templates/spec-template.md` — reference для Independent Test и Success Criteria при cross-reference.
- `.cursor/rules/shared/workflow-analyze-core.mdc` — локальный canonical workflow и detection passes.
- `.cursor/templates/analyze/epic-analyze.yaml` — схема findings, coverage, metrics и recommendation.

Связь: FR-11, AC+ #6. Этот документ фиксирует адаптацию, а не подключает runtime зависимости Spec Kit.
