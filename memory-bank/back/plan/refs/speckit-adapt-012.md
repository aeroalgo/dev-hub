# Spec Kit adaptation — T-HUB-012

## Что взяли из converge.md

- **Gap types** `missing`, `partial`, `contradicts`, `unrequested` как каноническую классификацию remediation findings.
- **Severity** `CRITICAL / HIGH / MEDIUM / LOW`; `CRITICAL` означает, что IMPLEMENT нельзя начинать без исправления или явного defer.
- **Source references** для каждой находки: `FR-###`, `SC-###`, `US#/AC#`, `plan:<section>` или `step:sNN`; ссылка переносится в `goal` и `plan_refs` нового audit shard.
- **Append-only remediation**: completed implement shards не переписываются; actionable finding получает новый `sNN-audit-*` shard.
- **Constitution MUST** получает `CRITICAL`, если нарушение действительно применимо.
- **Intent Inventory** до оценки реализации: каждый FR/SC/US/AC/NFR связывается со step/eNN или явно отмечается out-of-scope.
- **No git**: AUDIT работает по bounded plan/decompose/implement evidence и не использует `git-diff` как источник оценки.
- **Converged report**: `converged: true` разрешён только без actionable findings, с пустыми leftover-массивами и выполненным purge/sunset.

## Что отвергли / адаптировали

- **Phase N Convergence** в `tasks.md` не портируется: convergence — поле audit artifact и условие маршрутизации, а не отдельная фаза delivery.
- `__SPECKIT_*` markers не портируются: состояние хранится в `epic-audit/v2`, decompose index и implement shards.
- Extension hooks не портируются: AUDIT не выполняет before/after callbacks и не читает runtime-конфигурацию расширений.
- Отдельная команда **CONVERGE** не добавляется: нет нового slash command и нет нового MODE CONVERGE.
- `FEATURE_DIR` не портируется: epic-scoped paths остаются в `memory-bank/{role}/`.

## Граница ANALYZE vs AUDIT

| BACK ANALYZE | BACK AUDIT |
|---|---|
| Pre-IMPLEMENT, read-only plan/decompose coverage, без implement YAML | Post-IMPLEMENT intent↔code/evidence assessment и remediation loop |
| Ищет coverage, ambiguity и constitution gaps | Классифицирует `findings[]`, пишет evidence и создаёт append-only `sNN-audit-*` |
| Не оценивает фактический код и не создаёт audit shards | Проверяет implement headers/evidence и legacy leftovers |
| Не определяет QA по convergence | `converged: true` → QA; иначе IMPLEMENT новых audit shards → AUDIT |

## FORBIDDEN

- Устанавливать внешний CLI, выполнять `specify-cli` или init-команды только ради AUDIT.
- Создавать служебный каталог `.specify/` или заменять `memory-bank/` на отдельный каталог спецификаций.
- Вводить **MODE CONVERGE**, отдельный slash command или Phase N Convergence.
- Выполнять extension hooks, command macros или mutating scripts из reference.
- Изменять исходные plan/decompose-файлы во время ANALYZE.
- Автоматически удалять unrequested код или артефакты; такой случай остаётся finding с решением в `remaining_work`.
- Запускать suite в AUDIT: pytest/vitest/Playwright выполняются в IMPLEMENT/QA.

## Refs

- `spec-kit/templates/commands/converge.md` — reference для convergence semantics и append-only remediation.
- `.cursor/templates/audit/epic-audit.yaml` — локальная схема `epic-audit/v2`.
- `.cursor/rules/back_developer/workflow-audit.mdc` — BACK contract.
- `.cursor/rules/front_developer/workflow-audit.mdc` — FRONT parity contract.
- `.cursor/rules/integration_developer/workflow-audit.mdc` — INTEG parity contract.
- `.cursor/rules/shared/finish-doc-router.mdc` — converged-aware handoff routing.

Связь: FR-4/FR-6/FR-7/FR-8/FR-9/FR-10, AC+ #4/#6. Документ фиксирует адаптацию и границы, а не подключает runtime-зависимости Spec Kit.
