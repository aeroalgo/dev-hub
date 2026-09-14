# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-096-layout-resolve-sole-path
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**
**Дата:** 2026-09-14
**Режим:** BACK DECOMPOSE

Нарезка реализует консолидацию резолва путей артефактов эпиков (layout resolve sole path): разграничение ответственности между модулями путей `epic_layout`, `epic_paths` и `harness.hooks.epic_paths`, схлопывание `plan_path` и `resolve_epic_slug` в `loop/roadmap_queue.py` до единственного владельца резолва с удалением параллельных веток и swallow pass (`except Exception: pass`), обеспечение строгого приоритета `index.yaml` в `load_steps_for_index` и схлопывание алиаса `validate_decompose_yaml`, отказ от устаревших констант схем `SCHEMA_*_LEGACY` и префикса `decompose-` в arm-путях, удаление устаревших docstrings «falling back to v1» с актуализацией инструкций Kind I и усилением тестов denial, и финальный sunset-аудит. Всего 6 sNN (целевой диапазон 5–8).

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность, plan_contract bake-in |
| `python-testing-patterns` | изоляция тестов, проверка fail-closed поведения и denial |
| `architecture-patterns` | единый владелец путей (sole owner) без скрытых fallback-цепочек |

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN\|eNN | Notes |
| :--- | :--- | :--- | :--- |
| US-001 | Как loop, я резолвлю plan.md одним owner API | s02, s06 | Схлопывание `plan_path` и `resolve_epic_slug` до одного вызова без swallow. |
| US-002 | Как gate, yaml index — SoT при наличии yaml | s03, s06 | `load_steps_for_index` использует `index.yaml` как единственный SoT шагов. |
| US-003 | Как maintainer, Kind I не учит v1 fallback | s05, s06 | Очистка docstrings в `epic_paths.py` и инструкций от упоминаний fallback на v1. |
| FR-001 | Collapse `plan_path` to one resolver owner (`epic_layout` and/or single `epic_paths` wrapper); remove bare `except: pass` swallow. | s02, s06 | Единый вызов `resolve` в `plan_path`, удаление `except Exception: pass`. |
| FR-002 | Align `resolve_epic_slug` with the same owner (no divergent multi-try). | s02, s06 | Единообразное определение имени эпика через канонический резолвер. |
| FR-003 | `load_steps_for_index`: when `index.yaml` exists, do not load via md-prefer path as authoritative. | s03, s06 | Загрузка шагов из `index.yaml` напрямую без предпочтения md sibling. |
| FR-004 | Role-map `loop.paths.epic_layout` vs `loop.paths.epic_paths` vs `harness/hooks/epic_paths`: document keep-split **or** merge hooks helpers into layout; `move` without deleting sibling copy = FAIL. | s01, s06 | Разграничение ответственности и документация контракта модулей путей. |
| FR-005 | `SCHEMA_*_LEGACY`: inventory live shards; deny unused legacy schema ids **or** keep-split with explicit migrate epic already in queue (none → deny after inventory). | s01, s04, s06 | Инвентаризация шардов (0 живых) и удаление констант legacy-схем. |
| FR-006 | Fix stale `harness/hooks/epic_paths.py` docstring claiming v1 fallback. | s05, s06 | Удаление устаревшего docstring о fallback на v1 из `epic_paths.py`. |
| FR-007 | `context_loop` / arm `decompose-` deprecated branch: deny after migrate CLI proven; keep CLI migrate tool if separate. | s04, s06 | Запрет устаревшего `decompose-` формата в arm-логике. |
| FR-008 | Thin-forward `validate_decompose_yaml` → callers use full validator; delete alias if safe. | s01, s03, s06 | Перевод вызовов на `validate_decompose_full` и удаление алиаса. |
| FR-009 | Rewrite obsolete tests asserting multi-path success; keep `test_epic_layout_v2_denial` strengthened. | s05, s06 | Переписывание тестов на строгий отказ (v2 denial). |
| FR-010 | Kind I rewrite for layout fallback prose. | s05, s06 | Актуализация инструкций и комментариев в кодовой базе. |
| SC-001 | `plan_path` body: ≤1 resolve owner; no swallow-pass | s02, s06 | Тело `plan_path` использует одного владельца и не подавляет исключения. |
| SC-002 | yaml-prefer index load | s03, s06 | Загрузка индекса отдает приоритет YAML при его наличии. |
| SC-003 | stale «falling back to v1» prose = 0 in scoped hooks | s05, s06 | Ноль упоминаний fallback на v1 в хуках. |
| AC− | no dual machine resolve; no silent PASS via flat-after-exception; no obsolete multi-path tests | s02, s03, s04, s05, s06 | Отсутствие параллельного резолва и замалчивания ошибок. |
| Out of scope | epic runtime import sole path | — | follow_up: T-HUB-095-epic-runtime-import-sole-path |
| Out of scope | offline event/DAG adapter + test hygiene | — | follow_up: T-HUB-097-event-dag-offline-adapter-hygiene |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN\|eNN |
| :--- | :--- | :--- |
| Characterize path APIs + inventory flat/legacy shards | plan.md §До DECOMPOSE #1 | s01 |
| Sole `plan_path` / `resolve_epic_slug`; remove swallow | plan.md §До DECOMPOSE #2 | s02 |
| Yaml-prefer `load_steps_for_index` + validate alias decision | plan.md §До DECOMPOSE #3 | s03 |
| SCHEMA_LEGACY deny + arm `decompose-` policy | plan.md §До DECOMPOSE #4 | s04 |
| Docstring/Kind I + test denial rewrite | plan.md §До DECOMPOSE #5 | s05 |
| Final purge scan + denial tests (sunset inventory) | plan.md §До DECOMPOSE #6 | s06 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Sole plan/index path resolve: roadmap_queue.plan_path и resolve_epic_slug имеют одного владельца | s02, s06 |
| Yaml-prefer index load: index.yaml — канонический SoT шагов декомпозиции | s03, s06 |
| Fail-closed error handling: удалены silent `except Exception: pass` swallow-блоки | s02, s06 |
| Legacy schema deny: SCHEMA_*_LEGACY удалены из epic_yaml | s04, s06 |
| Documentation hygiene: docstrings и Kind I не содержат упоминаний устаревшего v1 fallback | s05, s06 |
| Deletion budget: net_loc_delta ≤ 0, net_symbol_delta ≤ 0, copies_removed ≥ 1 | s01, s02, s03, s04, s05, s06 |
| Out of scope: epic runtime import sole path | follow_up: T-HUB-095-epic-runtime-import-sole-path |
| Out of scope: offline event/DAG adapters | follow_up: T-HUB-097-event-dag-offline-adapter-hygiene |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN\|eNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| multi-branch `plan_path` | A | `loop.paths.epic_layout.resolve` | s02, s06 | no | Удаляются параллельные ветки поиска |
| `load_steps_for_index` md-prefer | A | yaml SoT | s03, s06 | no | Шаги читаются из `index.yaml` |
| `SCHEMA_*_LEGACY` | A | `SCHEMA_EPIC_*` | s04, s06 | no | Константы удаляются после инвентаря |
| `validate_decompose_yaml` alias | A | `validate_decompose_full` | s03, s06 | no | Вызовы переводятся на полный валидатор |
| arm `decompose-` prefix | B | layout v2 path | s04, s06 | no | Отказ от устаревшего формата префикса |
| `except Exception: pass` swallow | C | explicit miss / error | s02, s06 | no | Исключение замалчивания ошибок |
| stale «falling back to v1» docstrings | I | layout v2 canon | s05, s06 | no | Обновление комментариев в `epic_paths.py` |

## Очередь шагов (BACK / FRONT)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-characterize-and-role-map-path-apis.yaml](../yaml/steps/s01-characterize-and-role-map-path-apis.yaml) | [s01…](../../implement/T-HUB-096-layout-resolve-sole-path/s01-characterize-and-role-map-path-apis.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-collapse-plan-path-and-resolve-epic-slug.yaml](../yaml/steps/s02-collapse-plan-path-and-resolve-epic-slug.yaml) | [s02…](../../implement/T-HUB-096-layout-resolve-sole-path/s02-collapse-plan-path-and-resolve-epic-slug.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-yaml-prefer-index-load-and-validate-alias.yaml](../yaml/steps/s03-yaml-prefer-index-load-and-validate-alias.yaml) | [s03…](../../implement/T-HUB-096-layout-resolve-sole-path/s03-yaml-prefer-index-load-and-validate-alias.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-deny-legacy-schemas-and-arm-decompose.yaml](../yaml/steps/s04-deny-legacy-schemas-and-arm-decompose.yaml) | [s04…](../../implement/T-HUB-096-layout-resolve-sole-path/s04-deny-legacy-schemas-and-arm-decompose.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-docstring-kind-i-and-test-denial-rewrite.yaml](../yaml/steps/s05-docstring-kind-i-and-test-denial-rewrite.yaml) | [s05…](../../implement/T-HUB-096-layout-resolve-sole-path/s05-docstring-kind-i-and-test-denial-rewrite.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-legacy-fallback-purge.yaml](../yaml/steps/s06-legacy-fallback-purge.yaml) | [s06…](../../implement/T-HUB-096-layout-resolve-sole-path/s06-legacy-fallback-purge.yaml) | no | no | BACK IMPLEMENT | completed |