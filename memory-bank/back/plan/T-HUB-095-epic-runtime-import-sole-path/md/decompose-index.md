# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-095-epic-runtime-import-sole-path
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**
**Дата:** 2026-09-14
**Режим:** BACK DECOMPOSE

Нарезка реализует консолидацию импортов рантайма эпиков (epic runtime import sole path): удаление мёртвых алиасов нулевого вызова C2 (`auto_finish_after_gate`, `DEFAULT_ROADMAP`), переключение всех рабочих вызовов `epic_lib` на канонический пакет `epic` / `harness.hooks.epic.core` и схлопывание `_load_epic_state` в `pretool_policy` до одного импорта, объединение алиаса поиска QA-артефакта `find_qa_pass_artifact` и упрощение обёрток в `epic/__init__.py`, переписывание monkeypatch-тестов на канонического владельца и удаление `_legacy_mock_intercept`, удаление модуля-фасада `harness/hooks/epic_lib.py` с обновлением инструкций Kind I, и финальный sunset purge с полным сканированием инвентаря A+B+C+I. Всего 6 sNN (целевой диапазон 5–8).

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность, plan_contract bake-in |
| `python-testing-patterns` | freeze oracle, изоляция monkeypatch на каноническом модуле |
| `architecture-patterns` | единая точка входа (sole path) без дублирующих фасадов |

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN\|eNN | Notes |
| :--- | :--- | :--- | :--- |
| US-001 | Как maintainer, я импортирую helpers только из canonical epic package | s02, s03, s04, s05, s06 | Переключение импортов на `epic`/`epic.core`, удаление фасада `epic_lib`. |
| US-002 | Как runtime, я не маскирую ImportError цепочкой facade | s02, s06 | Схлопывание `_load_epic_state` в `pretool_policy` до единого импорта. |
| US-003 | Как maintainer, zero-caller aliases удалены | s01, s06 | Удаление `auto_finish_after_gate` и `DEFAULT_ROADMAP`. |
| FR-001 | Rewire all production `epic_lib` imports to canonical `epic` / `harness.hooks.epic.core`. | s02, s06 | Переключение всех prod-файлов в `loop/` и `harness/hooks/`. |
| FR-002 | Delete `harness/hooks/epic_lib.py` after rewire or reduce to fail-closed stub that raises (prefer delete). | s05, s06 | Удаление файла `harness/hooks/epic_lib.py`. |
| FR-003 | Collapse `pretool_policy._load_epic_state` to one import; remove silent `except` chain. | s02, s06 | Один импорт `load_epic_state` без цепочки fallback across 3 module names. |
| FR-004 | Remove or justify `_legacy_mock_intercept` only if tests patch canonical owner; rewrite tests first. | s04, s06 | Переписывание monkeypatch в тестах и удаление `_legacy_mock_intercept`. |
| FR-005 | Delete `auto_finish_after_gate`; keep `gate_atomic_finish`. | s01, s06 | Удаление функции из `loop/runtime_adapters/subagent_lifecycle.py`. |
| FR-006 | Delete `DEFAULT_ROADMAP`; keep `DEFAULT_QUEUE`. | s01, s06 | Удаление константы из `loop/roadmap_queue.py`. |
| FR-007 | Collapse `find_qa_pass_artifact` alias to one public name (or keep one name, delete the other) after caller rewire. | s03, s06 | Переключение вызовов на `latest_qa_pass_artifact_for_reference` и удаление алиаса. |
| FR-008 | Simplify `epic/__init__.py` discover/mark facades so one definition lives in `core` (copies_removed ≥ 1). | s03, s06 | Удаление дублирующих обёрток discover/mark в `epic/__init__.py`. |
| FR-009 | Rewrite/delete obsolete tests that require `epic_lib` or multi-module monkeypatch; freeze behavior via targeted suite. | s04, s05, s06 | Обновление тестов, удаление проверок фасада `epic_lib`. |
| FR-010 | Kind I: prompts/rules/memory-bank implement shards that teach `from epic_lib import` → rewrite in-epic (only paths in shard `files:` at IMPLEMENT). | s05, s06 | Актуализация инструкций агентов (напр. `verify-implement.md`). |
| SC-001 | 0 prod `epic_lib` imports | s02, s05, s06 | Ноль импортов `epic_lib` в prod-коде. |
| SC-002 | single state-load import | s02, s06 | Единый импорт в `pretool_policy._load_epic_state`. |
| SC-003 | dead aliases gone | s01, s06 | `auto_finish_after_gate` и `DEFAULT_ROADMAP` отсутствуют. |
| SC-004 | freeze oracle green | s04, s05, s06 | Таргетированные тесты и freeze oracle проходят успешно. |
| AC+ #1 | Symbols resolve from `epic`/`epic.core` only; behavior unchanged vs freeze oracle. | s02, s03, s04, s05, s06 | Единая точка разрешения символов через пакет `epic`. |
| AC+ #2 | No silent fallback to second/third module name in `pretool_policy`. | s02, s06 | Fail-closed импорт без fallback. |
| AC+ #3 | Aliases gone; `gate_atomic_finish` / `DEFAULT_QUEUE` still work. | s01, s06 | Канонические функции и константы работают без алиасов. |
| AC− #1 | Нет dual live import surface (`epic_lib` + `epic`) для одних helpers. | s02, s05, s06 | Полное удаление фасада `epic_lib`. |
| AC− #2 | Нет silent try/except module fallback. | s02, s06 | Удалены fallback-ветки в `_load_epic_state`. |
| AC− #3 | Нет zero-caller public aliases из inventory. | s01, s06 | Алиасы C2 удалены. |
| AC− #4 | Нет obsolete tests, требующих удалённый facade. | s04, s05, s06 | Тесты переведены на канонические модули. |
| AC− #5 | Нет роста public symbols/owners (concept budget ≤ 0). | s01, s02, s03, s04, s05, s06 | Чистое сокращение LOC и символов. |
| Out of scope | layout resolve sole path | — | follow_up: T-HUB-096-layout-resolve-sole-path |
| Out of scope | offline event/DAG adapter + test hygiene | — | follow_up: T-HUB-097-event-dag-offline-adapter-hygiene |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN\|eNN |
| :--- | :--- | :--- |
| Characterize import graph + freeze oracle baseline | plan.md §До DECOMPOSE #1 | s01, s02 |
| Purge C2 dead aliases + tests | plan.md §До DECOMPOSE #2 | s01 |
| Rewire prod `epic_lib` → `epic`; collapse `_load_epic_state` | plan.md §До DECOMPOSE #3 | s02 |
| Collapse QA alias / `__init__` facades | plan.md §Refactor inventory F02/F03 | s03 |
| Rewrite monkeypatch / delete intercept | plan.md §До DECOMPOSE #4 | s04 |
| Delete `epic_lib.py`; Kind I rewrite; final rg enforce | plan.md §До DECOMPOSE #5 | s05 |
| Legacy-fallback purge scan (AC−) | plan.md §До DECOMPOSE #6 | s06 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Sole epic-runtime import owner: hooks/loop callers resolve from `epic` / `harness.hooks.epic.core` | s02, s03, s05, s06 |
| Dead alias purge: `auto_finish_after_gate`, `DEFAULT_ROADMAP` removed, owners preserved | s01, s06 |
| State-load single import: `pretool_policy` fails closed on missing module without silent fallback | s02, s06 |
| Mock intercept elimination: test suites patch canonical owner directly | s04, s06 |
| Deletion budget: net_loc_delta ≤ 0, net_symbol_delta ≤ 0, copies_removed ≥ 1 | s01, s02, s03, s04, s05, s06 |
| Out of scope: layout multi-resolve | follow_up: T-HUB-096-layout-resolve-sole-path |
| Out of scope: offline event/DAG adapters | follow_up: T-HUB-097-event-dag-offline-adapter-hygiene |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN\|eNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `harness/hooks/epic_lib.py` | A | `harness/hooks/epic/core.py` (package `epic`) | s05, s06 | no | Фасадный модуль удаляется целиком |
| `auto_finish_after_gate` | A | `gate_atomic_finish` | s01, s06 | no | Zero-caller dead alias в `subagent_lifecycle.py` |
| `DEFAULT_ROADMAP` | A | `DEFAULT_QUEUE` | s01, s06 | no | Zero-caller dead alias в `roadmap_queue.py` |
| `find_qa_pass_artifact` | A | `latest_qa_pass_artifact_for_reference` | s03, s06 | no | Алиас схлопывается до канонического имени |
| `epic/__init__.py` duplicate wrappers | A | `epic.core` definitions | s03, s06 | no | Упрощение фасада пакета |
| `_legacy_mock_intercept` | A | monkeypatch на `epic.core` | s04, s06 | no | Удаление механизма перехвата моков |
| triple-try fallback in `_load_epic_state` | C | single direct import | s02, s06 | yes | Удаление fallback try-except цепочки |
| instructions teaching `from epic_lib import` | I | `from epic import` / `from harness.hooks.epic.core import` | s05, s06 | no | Обновление `verify-implement.md` и документации |

## Очередь шагов (BACK / FRONT)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-dead-alias-purge-c2.yaml](../yaml/steps/s01-dead-alias-purge-c2.yaml) | [s01…](../../implement/T-HUB-095-epic-runtime-import-sole-path/s01-dead-alias-purge-c2.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-rewire-prod-epic-lib-and-state-load.yaml](../yaml/steps/s02-rewire-prod-epic-lib-and-state-load.yaml) | [s02…](../../implement/T-HUB-095-epic-runtime-import-sole-path/s02-rewire-prod-epic-lib-and-state-load.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-collapse-qa-artifact-alias-and-epic-facades.yaml](../yaml/steps/s03-collapse-qa-artifact-alias-and-epic-facades.yaml) | [s03…](../../implement/T-HUB-095-epic-runtime-import-sole-path/s03-collapse-qa-artifact-alias-and-epic-facades.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-rewrite-tests-and-delete-mock-intercept.yaml](../yaml/steps/s04-rewrite-tests-and-delete-mock-intercept.yaml) | [s04…](../../implement/T-HUB-095-epic-runtime-import-sole-path/s04-rewrite-tests-and-delete-mock-intercept.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-delete-epic-lib-facade-and-kind-i.yaml](../yaml/steps/s05-delete-epic-lib-facade-and-kind-i.yaml) | [s05…](../../implement/T-HUB-095-epic-runtime-import-sole-path/s05-delete-epic-lib-facade-and-kind-i.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-legacy-fallback-purge.yaml](../yaml/steps/s06-legacy-fallback-purge.yaml) | [s06…](../../implement/T-HUB-095-epic-runtime-import-sole-path/s06-legacy-fallback-purge.yaml) | no | no | BACK IMPLEMENT | completed |