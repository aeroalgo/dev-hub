# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-084-workflow-reference-graph-hygiene
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml)
**Дата:** 2026-09-08
**Режим:** BACK DECOMPOSE

Нарезка сохраняет четыре outcome плана: bounded graph validator, единственный owner edge, сохранение mode semantics и доказанный purge `back-audit.mdc`. Всего 6 sNN: core validator, два кластера owner rewrite, topology rewrite, corpus gate и финальный purge. Полный suite TM-084-06 передаётся BACK QA после IMPLEMENT.

## Requirements coverage

| Req ID | Plan FR text | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | each active W declares a shared dependency once. | s02, s03, s04, s05 | В каждом кластере остаётся ровно одна owner declaration; повторные inline `@` ссылки проверяются corpus gate. |
| FR-002 | A→B plus W→B has one owner selected by lazy timing and semantic responsibility. | s01, s02, s03, s04 | s01 фиксирует обнаружение; s02–s04 применяют owner map по mode-кластерам. |
| FR-003 | graph validator reports direct duplicate, transitive ambiguity and dangling dead reference. | s01, s05, s06 | Fixture-level red tests, active-corpus scan и purge evidence дают три класса отчётов. |
| FR-004 | priority mode semantics remain; dead audit cheatsheet has no active caller. | s05, s06 | Marker regression остаётся отдельной проверкой; audit cheatsheet и loader удаляются только после scan. |
| AC+ #1 | Duplicate edge fixture fails with both lines. | s01 | Ошибка содержит обе исходные строки synthetic fixture. |
| AC+ #2 | Removing sole owner fails; removing redundant edge passes. | s01, s05 | Проверяется fail-closed owner rule и positive redundant-edge removal. |
| AC+ #3 | PLAN/DECOMPOSE/ANALYZE markers remain. | s05 | Проверка идёт по canonical workflow owners после rewrite. |
| AC− #1 | No inlining large shared policy, archive rewrite, blind `rg` deletion, or compatibility alias. | s02, s03, s04, s05, s06 | Изменяются только owner edges, caller block и доказанно мёртвый audit artifact; shared policy body не переносится. |

## Stages coverage

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| edge inventory и red fixtures | plan §HOW / Eng spine, TM-084-01, TM-084-02 | s01 |
| ownership rewrite для behavior-first и DECOMPOSE | plan §WHAT, priority mode semantics | s02 |
| ownership rewrite для ANALYZE, PLAN и CLARIFY | plan §WHAT, TM-084-02 | s03 |
| ownership rewrite для VAN и REFACTOR | plan §WHAT, TM-084-02 | s04 |
| validator, mode markers и archive exclusion | TM-084-03, TM-084-05 | s05 |
| proven dead cleanup и complete sunset scan | TM-084-04, plan §Replacement / sunset | s06 |
| full suite | TM-084-06 | BACK QA после IMPLEMENT; не входит в decompose verify |

## Outcome map

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Один owner edge с явным lazy timing для активного workflow | s01, s02, s03, s04, s05 |
| behavior-first в DECOMPOSE не имеет прямой/transitive duplicate edge | s01, s02, s05 |
| ANALYZE core и PLAN/CLARIFY orchestration сохраняют свои mode semantics | s03, s05 |
| DECOMPOSE/VAN/CLARIFY/REFACTOR transitive pairs классифицированы и переподключены | s03, s04, s05 |
| Validator сообщает direct duplicate, transitive ambiguity и dangling dead reference | s01, s05 |
| PLAN/DECOMPOSE/ANALYZE markers не исчезают | s05 |
| `back-audit.mdc` не имеет активного caller после доказанного scan | s06 |
| Полный suite TM-084-06 | BACK QA handoff после s06 |
| Out of scope: archive/history rewrite и compatibility alias | — | запрещены AC−; archive/history только исключаются из active corpus |

## Replacement cleanup

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN\|eNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| repeated/transitive active `@` edges | A | one owner edge + validator report | s02, s03, s04, s05, s06 | no | Удалять только edge, сохраняя semantic owner и порядок загрузки. |
| `harness/cursor/rules/shared/cheatsheets/back-audit.mdc` и его active loader block | A | canonical `workflow-audit.mdc` path без cheatsheet | s06 | no | Сначала проверить caller scan; другие zero-reference файлы только классифицировать. |
| duplicate link as safety fallback | C | fail-closed owner validation | s01, s05, s06 | yes | Нет alias/shim; лишняя ссылка не служит fallback. |
| stale active `@` mentions | I | canonical dependency declaration with explicit timing | s02, s03, s04, s05, s06 | no | Archive/history mentions не переписываются и не считаются active callers. |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-reference-graph-fixtures.yaml](../yaml/steps/s01-reference-graph-fixtures.yaml) | [s01-reference-graph-fixtures.yaml](../../implement/T-HUB-084-workflow-reference-graph-hygiene/s01-reference-graph-fixtures.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s02** | [s02-behavior-first-owner.yaml](../yaml/steps/s02-behavior-first-owner.yaml) | [s02-behavior-first-owner.yaml](../../implement/T-HUB-084-workflow-reference-graph-hygiene/s02-behavior-first-owner.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s03** | [s03-analyze-plan-clarify-owners.yaml](../yaml/steps/s03-analyze-plan-clarify-owners.yaml) | [s03-analyze-plan-clarify-owners.yaml](../../implement/T-HUB-084-workflow-reference-graph-hygiene/s03-analyze-plan-clarify-owners.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s04** | [s04-van-refactor-owners.yaml](../yaml/steps/s04-van-refactor-owners.yaml) | [s04-van-refactor-owners.yaml](../../implement/T-HUB-084-workflow-reference-graph-hygiene/s04-van-refactor-owners.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s05** | [s05-active-corpus-gate.yaml](../yaml/steps/s05-active-corpus-gate.yaml) | [s05-active-corpus-gate.yaml](../../implement/T-HUB-084-workflow-reference-graph-hygiene/s05-active-corpus-gate.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s06** | [s06-legacy-fallback-purge.yaml](../yaml/steps/s06-legacy-fallback-purge.yaml) | [s06-legacy-fallback-purge.yaml](../../implement/T-HUB-084-workflow-reference-graph-hygiene/s06-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | pending |

**Следующий режим после завершения дерева:** BACK ANALYZE. `ANALYZE deferred` не используется.
