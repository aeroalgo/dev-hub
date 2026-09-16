# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-103-event-schema-sot-unify
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**
**Дата:** 2026-09-16
**Режим:** BACK DECOMPOSE

Нарезка устраняет дублирование контракта событий `loop-event/v2` (Event schema SoT unify): ликвидация параллельной Pydantic-схемы `loop/schemas/event.py:LoopEvent` с устаревшей таблицей `EVENT_KINDS`, удаление публичных экспортов из `loop/schemas/__init__.py`, консолидация/переписывание устаревших тестов `loop/tests/test_schemas_event.py` с опорой на канонический живой слой `harness/hooks/epic_events.py` и freeze oracle `loop/tests/test_event_v2_characterization.py`, актуализация Kind I документации `loop/schemas/README.md` и проведение полного cutover purge. Всего 6 sNN (целевой диапазон 5–8).

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность, plan_contract bake-in |
| `python-testing-patterns` | консолидация тестовых наборов, сохранение freeze-oracle инвариантов |
| `architecture-patterns` | единый канонический Source of Truth (SoT), ликвидация дублирующих схем |

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN\|eNN | Notes |
| :--- | :--- | :--- | :--- |
| US-001 | Как maintainer, я валидирую events только через live epic_events SoT | s01, s04, s06 | Валидация событий строго через единый live SoT `harness/hooks/epic_events.py`. |
| US-002 | Как CI, schema-only suite не держит drift kinds | s02, s06 | Устранение дрейфа kinds и устаревших тестов orphan схемы. |
| FR-001 | Delete `loop/schemas/event.py` after proving zero prod callers. | s01, s04, s06 | Аудит callers и удаление модуля orphan схемы `loop/schemas/event.py`. |
| FR-002 | Remove `LoopEvent`/`EVENT_KINDS`/`EVENT_SCHEMA` from `loop/schemas/__init__.py`. | s03, s06 | Удаление экспортов устаревшей схемы из публичного фасада `loop/schemas/__init__.py`. |
| FR-003 | Delete or rewrite `test_schemas_event.py` to live SoT; consolidate fixtures with characterization where overlapping. | s02, s06 | Переписывание/консолидация тестового сьюта на канонический live SoT. |
| FR-004 | Update `loop/schemas/README.md` to point to epic_events. | s05, s06 | Обновление Kind I документации реестра схем на `epic_events.py`. |
| FR-005 | Do not change live event kind set except to document existing epic_events as sole source (no feature kinds). | s01, s05, s06 | Сохранение неизменности набора видов событий без произвольных добавлений. |
| SC-001 | `rg 'from loop.schemas.event|loop\.schemas\.event' loop harness` → only historical comments if any; no imports. | s01, s03, s04, s06 | Нулевое количество импортов `loop.schemas.event`. |
| SC-002 | Freeze oracle green. | s01, s02, s06 | Зеленый статус `test_event_v2_characterization.py`. |
| SC-003 | net_loc ≤ 0; net public schema symbols ≤ 0. | s03, s04, s06 | Сокращение кодовой базы и количества публичных символов. |
| AC− #1 | Нет dual `EVENT_KINDS`. | s03, s04, s06 | Единственный источник `EVENT_KINDS` в `harness/hooks/epic_events.py`. |
| AC− #2 | Нет silent PASS через orphan model. | s02, s04, s06 | Исключение валидации через устаревшую модель `LoopEvent`. |
| AC− #3 | Нет живых тестов, требующих удалённый `LoopEvent`. | s02, s06 | Отсутствие тестов, завязанных на `LoopEvent`. |
| AC− #4 | Нет «optional schema module» рядом с epic_events. | s04, s06 | Полное удаление `loop/schemas/event.py`. |
| Out of scope | Plan-path classifier + board_sync helper | — | follow_up: T-HUB-104-plan-path-classifier-dedup |
| Out of scope | Roadmap legacy source + orchestrator import | — | follow_up: T-HUB-105-roadmap-legacy-source-purge |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN\|eNN |
| :--- | :--- | :--- |
| Аудит вызовов и фиксация freeze oracle baseline | plan.md §HOW #1 | s01 |
| Переписывание и консолидация тестов схемы | plan.md §HOW #2 | s02 |
| Очистка экспортов публичного фасада схем | plan.md §HOW #3 | s03 |
| Удаление orphan модуля схемы событий | plan.md §HOW #3 | s04 |
| Kind I актуализация документации | plan.md §HOW #3 | s05 |
| Финальный purge scan и регрессионная верификация | plan.md §HOW #4 | s06 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Zero prod callers proof & freeze oracle baseline: доказательство отсутствия prod-зависимостей от LoopEvent | s01, s06 |
| Test suite consolidation: исключение устаревших проверок orphan модели, опора на live validate_event | s02, s06 |
| Public API cleanup: удаление LoopEvent, EVENT_KINDS, EVENT_SCHEMA из loop/schemas/__init__.py | s03, s06 |
| Orphan schema removal: удаление loop/schemas/event.py и fail-closed запрет импортов | s04, s06 |
| Instruction & registry hygiene: актуализация README.md со ссылкой на sole SoT epic_events.py | s05, s06 |
| Deletion budget: net_loc ≤ 0, net_symbols ≤ 0, copies_removed ≥ 1 | s01, s02, s03, s04, s05, s06 |
| Out of scope: Plan-path classifier + board_sync helper | follow_up: T-HUB-104-plan-path-classifier-dedup |
| Out of scope: Roadmap legacy source + orchestrator import | follow_up: T-HUB-105-roadmap-legacy-source-purge |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN\|eNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `loop/schemas/event.py` (module) | A | `harness/hooks/epic_events.py` | s04, s06 | no | Удаление orphan модуля схемы |
| `loop/schemas/__init__.py:LoopEvent` | B | `epic_events.validate_event` | s03, s06 | no | Удаление экспорта модели |
| `loop/schemas/__init__.py:EVENT_KINDS` | B | `epic_events.EVENT_KINDS` | s03, s06 | no | Удаление экспорта таблицы видов событий |
| `loop/schemas/__init__.py:EVENT_SCHEMA` | B | `epic_events.EVENT_SCHEMA` | s03, s06 | no | Удаление экспорта константы схемы |
| `loop/tests/test_schemas_event.py` | C | `loop/tests/test_event_v2_characterization.py` | s02, s06 | no | Удаление/переписывание obsolete тестов |
| `loop/schemas/README.md` (row `LoopEvent`) | I | `harness/hooks/epic_events.py` reference | s05, s06 | no | Kind I актуализация реестра схем |

## Очередь шагов (BACK / FRONT)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-verify-callers-and-characterization-baseline.yaml](../yaml/steps/s01-verify-callers-and-characterization-baseline.yaml) | [s01…](../../implement/T-HUB-103-event-schema-sot-unify/s01-verify-callers-and-characterization-baseline.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-rewrite-and-consolidate-schema-tests.yaml](../yaml/steps/s02-rewrite-and-consolidate-schema-tests.yaml) | [s02…](../../implement/T-HUB-103-event-schema-sot-unify/s02-rewrite-and-consolidate-schema-tests.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-remove-schema-exports-and-shim.yaml](../yaml/steps/s03-remove-schema-exports-and-shim.yaml) | [s03…](../../implement/T-HUB-103-event-schema-sot-unify/s03-remove-schema-exports-and-shim.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-delete-orphan-event-schema-module.yaml](../yaml/steps/s04-delete-orphan-event-schema-module.yaml) | [s04…](../../implement/T-HUB-103-event-schema-sot-unify/s04-delete-orphan-event-schema-module.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-instruction-kind-i-and-docs-hygiene.yaml](../yaml/steps/s05-instruction-kind-i-and-docs-hygiene.yaml) | [s05…](../../implement/T-HUB-103-event-schema-sot-unify/s05-instruction-kind-i-and-docs-hygiene.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-legacy-fallback-purge.yaml](../yaml/steps/s06-legacy-fallback-purge.yaml) | [s06…](../../implement/T-HUB-103-event-schema-sot-unify/s06-legacy-fallback-purge.yaml) | no | no | BACK IMPLEMENT | completed |