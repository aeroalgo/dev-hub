# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-104-plan-path-classifier-dedup
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**
**Дата:** 2026-09-16
**Режим:** BACK DECOMPOSE

Нарезка устраняет дублирование классификаторов путей планов и хелперов board_sync (Plan-path classifier + board_sync helper): объединение классификаторов путей `is_whole_plan_path` и `is_markdown_plan_path` в едином каноническом модуле `loop/mb_load/plan_section.py`, удаление дублирующего тела функции из `loop/mb_load/session.py`, выделение общего хелпера `loop/board_sync/_epic_paths.py` с удалением локальных копий `_plan_path` и `_find_decompose` из `epic_resolver.py` и `scan_gates.py`, консолидация тестов и полный cutover purge. Всего 7 sNN (целевой диапазон 5–8).

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность, plan_contract bake-in |
| `python-testing-patterns` | freeze oracle baseline, параметризованная матрица тестов путей |
| `architecture-patterns` | единый канонический Source of Truth (SoT), ликвидация дублирующих реализаций |
| `python-design-patterns` | выделение изолированных чистых хелперов без sys.path хаков |
| `python-anti-patterns` | устранение дублирования кода (DRY) и двойного владения логикой |

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN\|eNN | Notes |
| :--- | :--- | :--- | :--- |
| US-001 | Maintainer меняет classifier в одном модуле | s01, s02, s03, s06, s07 | Единая точка определения классификаторов путей планов в `plan_section.py`. |
| US-002 | board_sync resolve plan без copy-paste | s01, s04, s05, s06, s07 | Разрешение путей планов в board_sync через общий хелпер без дубликатов. |
| FR-001 | Move `is_markdown_plan_path` into `plan_section` (or unify under one name with aliases); delete session implementation body. | s01, s02, s03, s07 | Перенос классификатора в `plan_section` и удаление реализации из `session.py`. |
| FR-002 | Share overlapping plan.md detection between whole-plan and markdown classifiers without dual regex maintenance. | s01, s02, s07 | Переиспользование общего regex `_PLAN_PATTERN` в `plan_section.py`. |
| FR-003 | Extract `board_sync` plan path helper; delete both `_plan_path` copies. | s01, s04, s05, s07 | Выделение `loop/board_sync/_epic_paths.py` и удаление локальных копий. |
| FR-004 | Consolidate tests into one parametrized matrix where duplicated. | s01, s06, s07 | Консолидация тестового покрытия и параметризация матрицы путей. |
| SC-001 | `rg 'def is_markdown_plan_path' loop` → one definition (plan_section). | s02, s03, s07 | Ровно одно определение функции в `loop/mb_load/plan_section.py`. |
| SC-002 | `rg 'def _plan_path' loop/board_sync` → zero (or only in helper if named differently once). | s01, s04, s05, s06, s07 | Отсутствие локальных `_plan_path` в модулях `board_sync`. |
| SC-003 | net_loc ≤ 0; owners ≤ 0 growth. | s03, s05, s07 | Сокращение дублирующегося кода и сохранение бюджета концепций. |
| AC− #1 | Нет двух полных classifier bodies. | s02, s03, s07 | Исключение дублирования логики классификатора в `session.py`. |
| AC− #2 | Нет двух sys.path hacks for `find_plan_md_path` in board_sync. | s04, s05, s07 | Устранение дублирующихся sys.path вставок в `board_sync`. |
| AC− #3 | Нет extract без delete siblings. | s05, s07 | Гарантированное удаление копий при вынесении в общий хелпер. |
| AC− #4 | Нет изменения deny matrix без явного behavior epic. | s01, s02, s03, s06, s07 | Сохранение неизменности булевой матрицы результатов проверок. |
| Out of scope | Event schema SoT unify | — | follow_up: T-HUB-103-event-schema-sot-unify |
| Out of scope | Roadmap legacy source + orchestrator import | — | follow_up: T-HUB-105-roadmap-legacy-source-purge |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN\|eNN |
| :--- | :--- | :--- |
| Capture classifier matrix tests & freeze oracles | plan.md §HOW #1 | s01 |
| Move/merge C2 in plan_section; share regex | plan.md §HOW #2 | s02 |
| Cutover session loader; delete duplicate body | plan.md §HOW #2 | s03 |
| Extract C3 board_sync helper | plan.md §HOW #3 | s04 |
| Cutover callers & delete twin helpers | plan.md §HOW #3 | s05 |
| Consolidate unit tests & matrix | plan.md §Test refactor | s06 |
| Targeted pytest freeze oracles & sunset purge | plan.md §HOW #4 | s07 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Freeze oracle baseline: фиксация эталонного поведения классификаторов и хелперов путей | s01, s07 |
| Unified plan-path classifier: перенос и объединение логики в loop/mb_load/plan_section.py | s02, s07 |
| Single classifier definition: удаление дублирующего тела из loop/mb_load/session.py | s03, s07 |
| Shared board_sync paths helper: выделение loop/board_sync/_epic_paths.py | s04, s07 |
| Twin helpers deletion: удаление _plan_path / _find_decompose из epic_resolver и scan_gates | s05, s07 |
| Test consolidation: объединение модульных проверок и устранение дублирования ассертов | s06, s07 |
| Deletion budget: net_loc ≤ 0, net_symbols ≤ 0, copies_removed >= 2 | s01, s02, s03, s04, s05, s06, s07 |
| Out of scope: Event schema SoT unify | follow_up: T-HUB-103-event-schema-sot-unify |
| Out of scope: Roadmap legacy source + orchestrator import | follow_up: T-HUB-105-roadmap-legacy-source-purge |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN\|eNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `loop/mb_load/session.py::is_markdown_plan_path` (body) | A | `loop/mb_load/plan_section.py::is_markdown_plan_path` | s03, s07 | no | Удаление дублирующей реализации классификатора |
| `loop/board_sync/epic_resolver.py::_plan_path` | B | `loop/board_sync/_epic_paths.py::plan_path` | s05, s07 | no | Удаление локального хелпера разрешения планов |
| `loop/board_sync/scan_gates.py::_plan_path` | B | `loop/board_sync/_epic_paths.py::plan_path` | s05, s07 | no | Удаление локального хелпера разрешения планов |
| `loop/tests/test_mb_load_session.py` (duplicate asserts) | C | `loop/tests/test_plan_path_classifier_characterization.py` | s06, s07 | no | Консолидация проверок классификатора |
| `loop/board_sync/` sys.path hooks insertions | I | `loop/board_sync/_epic_paths.py` clean imports | s05, s07 | no | Устранение sys.path хаков в кодовой базе |

## Очередь шагов (BACK / FRONT)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-characterization-and-freeze-oracle-baseline.yaml](../yaml/steps/s01-characterization-and-freeze-oracle-baseline.yaml) | [s01…](../../implement/T-HUB-104-plan-path-classifier-dedup/s01-characterization-and-freeze-oracle-baseline.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-move-classifier-and-share-plan-pattern.yaml](../yaml/steps/s02-move-classifier-and-share-plan-pattern.yaml) | [s02…](../../implement/T-HUB-104-plan-path-classifier-dedup/s02-move-classifier-and-share-plan-pattern.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-cutover-session-and-delete-duplicate-classifier-body.yaml](../yaml/steps/s03-cutover-session-and-delete-duplicate-classifier-body.yaml) | [s03…](../../implement/T-HUB-104-plan-path-classifier-dedup/s03-cutover-session-and-delete-duplicate-classifier-body.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-extract-board-sync-epic-paths-helper.yaml](../yaml/steps/s04-extract-board-sync-epic-paths-helper.yaml) | [s04…](../../implement/T-HUB-104-plan-path-classifier-dedup/s04-extract-board-sync-epic-paths-helper.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-cutover-board-sync-callers-and-delete-twin-helpers.yaml](../yaml/steps/s05-cutover-board-sync-callers-and-delete-twin-helpers.yaml) | [s05…](../../implement/T-HUB-104-plan-path-classifier-dedup/s05-cutover-board-sync-callers-and-delete-twin-helpers.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-consolidate-unit-tests-and-matrix.yaml](../yaml/steps/s06-consolidate-unit-tests-and-matrix.yaml) | [s06…](../../implement/T-HUB-104-plan-path-classifier-dedup/s06-consolidate-unit-tests-and-matrix.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s07** | [s07-legacy-fallback-purge.yaml](../yaml/steps/s07-legacy-fallback-purge.yaml) | [s07…](../../implement/T-HUB-104-plan-path-classifier-dedup/s07-legacy-fallback-purge.yaml) | no | no | BACK IMPLEMENT | completed |