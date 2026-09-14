# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-097-event-dag-offline-adapter-hygiene
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**
**Дата:** 2026-09-14
**Режим:** BACK DECOMPOSE

Нарезка реализует гигиену офлайн-адаптеров событий и DAG (offline event/DAG adapter + test hygiene): закрепление строгого отсутствия вызовов `adapt_*` из live runtime артефактов (live `read_event_log`, DAG next arm execution), консолидация дублирующих legacy characterization тестов DAG и событий в канонические тестовые модули с удалением избыточных assertion twins (`copies_removed ≥ 1`), явная классификация адаптеров как offline-only (keep-split без разрастания модулей), формализация контракта `queue_rel` и актуализация Kind I инструкций и docstrings. Всего 6 sNN (целевой диапазон 5–8).

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность, plan_contract bake-in |
| `python-testing-patterns` | консолидация тестовых наборов, сохранение freeze-oracle инвариантов |
| `architecture-patterns` | изоляция live vs offline подсистем, исключение скрытых fallback |

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN\|eNN | Notes |
| :--- | :--- | :--- | :--- |
| US-001 | Как runtime, live event/DAG не вызывает adapt_* | s01, s05, s06 | Верификация и закрепление изоляции live arm от вызовов `adapt_*`. |
| US-002 | Как maintainer, одна offline characterization suite | s02, s03, s06 | Слияние дублирующих наборов тестов DAG и событий в канонические сьюты. |
| US-003 | Как оператор, migrate CLI (если retained) явно offline | s04, s05, s06 | Чёткая offline-only классификация CLI и адаптеров миграций. |
| FR-001 | Re-assert live `read_event_log` / DAG arm never call `adapt_*` (control tests remain). | s01, s06 | Закрепление control tests: live пути никогда не вызывают adapt_*. |
| FR-002 | Classify `adapt_manifest` / `migrate_manifest` / `adapt_v1_event` / `migrate_event_log` as offline-only; extract to `loop/migrate/` **only if** that removes ≥1 duplicate ownership surface (copies_removed ≥ 1) — else keep-split in place with hard comments + Kind I (no new module without deletion). | s04, s06 | Явная offline-only классификация адаптеров, keep-split по месту без разрастания модулей. |
| FR-003 | Consolidate overlapping characterization tests into one offline suite; delete redundant cases (`copies_removed_count ≥ 1` of same assertion meaning). | s02, s03, s06 | Слияние разрозненных тестов DAG и event migration, удаление избыточных копий проверок. |
| FR-004 | `queue_rel_from_roadmap` md→queue map: delete if no CLI/docs callers; else keep-split with explicit legacy CLI contract. | s04, s06 | Аудит callers и фиксация контракта `queue_rel_from_roadmap`. |
| FR-005 | Kind I: instructions must not present adapt_* as live success path. | s05, s06 | Очистка docstrings, инструкций и промптов от трактовки adapt_* как live runtime SoT. |
| FR-006 | No restoration of live v1 fallbacks. | s05, s06 | Блокировка любых попыток добавления v1 fallback логики в live path. |
| AC− #1 | Нет live call sites to adapt_*. | s01, s05, s06 | Нулевое количество live call sites к `adapt_*`. |
| AC− #2 | Нет N files asserting identical «adapt succeeds as runtime» without offline label. | s02, s03, s06 | Устранение дублирующих тестов, проверяющих adapt как runtime SoT. |
| AC− #3 | Нет нового migrate package без удаления старого owner surface. | s04, s06 | Keep-split существующих инструментов без создания лишних пакетов. |
| AC− #4 | Behavior of migrate algorithms unchanged (freeze oracle offline tests). | s02, s03, s06 | Сохранение инвариантов и freeze oracle для алгоритмов миграции. |
| Out of scope | epic runtime import sole path | — | follow_up: T-HUB-095-epic-runtime-import-sole-path |
| Out of scope | layout resolve sole path | — | follow_up: T-HUB-096-layout-resolve-sole-path |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN\|eNN |
| :--- | :--- | :--- |
| Control: live adapt call sites = 0 + list test twins | plan.md §До DECOMPOSE #1 | s01 |
| Merge DAG characterization suite; delete dups | plan.md §До DECOMPOSE #2 | s02 |
| Merge event migration suite; delete dups | plan.md §До DECOMPOSE #2 | s03 |
| Adapter placement decision + queue_rel policy | plan.md §До DECOMPOSE #3, #4 | s04 |
| Kind I + final scan | plan.md §До DECOMPOSE #5 | s05 |
| Final purge scan + verification (sunset inventory) | plan.md §До DECOMPOSE #6 | s06 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Live arm isolation: live `read_event_log` и `arm_dag_next` никогда не обращаются к `adapt_*` | s01, s06 |
| Consolidated DAG tests: единый канонический сьют `test_dag_v2_characterization.py` | s02, s06 |
| Consolidated event tests: единый канонический сьют для миграции событий | s03, s06 |
| Offline classification: явный offline-only контракт для инструментов миграции | s04, s06 |
| Instruction hygiene: Kind I и docstrings не допускают трактовки adapt_* как live SoT | s05, s06 |
| Deletion budget: net_loc_delta ≤ 0, net_symbol_delta ≤ 0, copies_removed ≥ 1 | s01, s02, s03, s04, s05, s06 |
| Out of scope: epic runtime import sole path | follow_up: T-HUB-095-epic-runtime-import-sole-path |
| Out of scope: layout resolve sole path | follow_up: T-HUB-096-layout-resolve-sole-path |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN\|eNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| duplicate DAG test assertions | A | `test_dag_v2_characterization.py` | s02, s06 | no | Удаляются избыточные дублирующие проверки |
| duplicate event migration test assertions | A | `test_event_v2_characterization.py` / `test_event_legacy_adapter.py` | s03, s06 | no | Схлопываются повторные кейсы |
| ambiguous live-adjacent adapt exports | A | offline entrypoint only | s04, s06 | no | Keep-split с явными offline-only маркерами |
| unused `queue_rel` md map | A | `DEFAULT_QUEUE` paths only | s04, s06 | no | Аудит callers и фиксация контракта |
| adapt if validate fails in live | C | fail-closed error | s01, s05, s06 | no | Исключение fallback на адаптеры при сбое валидации |
| docs/instructions implying adapt in arm | I | validate-only live / offline migrate only | s05, s06 | no | Обновление комментариев и docstrings |

## Очередь шагов (BACK / FRONT)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-control-live-adapt-isolation-and-test-inventory.yaml](../yaml/steps/s01-control-live-adapt-isolation-and-test-inventory.yaml) | [s01…](../../implement/T-HUB-097-event-dag-offline-adapter-hygiene/s01-control-live-adapt-isolation-and-test-inventory.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-consolidate-legacy-dag-adapter-tests.yaml](../yaml/steps/s02-consolidate-legacy-dag-adapter-tests.yaml) | [s02…](../../implement/T-HUB-097-event-dag-offline-adapter-hygiene/s02-consolidate-legacy-dag-adapter-tests.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-consolidate-legacy-event-adapter-tests.yaml](../yaml/steps/s03-consolidate-legacy-event-adapter-tests.yaml) | [s03…](../../implement/T-HUB-097-event-dag-offline-adapter-hygiene/s03-consolidate-legacy-event-adapter-tests.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-offline-adapter-classification-and-queue-rel-policy.yaml](../yaml/steps/s04-offline-adapter-classification-and-queue-rel-policy.yaml) | [s04…](../../implement/T-HUB-097-event-dag-offline-adapter-hygiene/s04-offline-adapter-classification-and-queue-rel-policy.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-instruction-kind-i-and-runtime-denial-rewrite.yaml](../yaml/steps/s05-instruction-kind-i-and-runtime-denial-rewrite.yaml) | [s05…](../../implement/T-HUB-097-event-dag-offline-adapter-hygiene/s05-instruction-kind-i-and-runtime-denial-rewrite.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-legacy-fallback-purge.yaml](../yaml/steps/s06-legacy-fallback-purge.yaml) | [s06…](../../implement/T-HUB-097-event-dag-offline-adapter-hygiene/s06-legacy-fallback-purge.yaml) | no | no | BACK IMPLEMENT | completed |