# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-105-roadmap-legacy-source-purge
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**
**Дата:** 2026-09-16
**Режим:** BACK DECOMPOSE

Нарезка выполняет полное удаление устаревших источников roadmap и исправление импорта оркестратора (Roadmap legacy source + orchestrator import): удаление сканирования legacy slug-очередей `plan/roadmap-*-epics.queue.yaml` из `discover_source_queues`, перевод маппинга `.md` путей в `queue_rel_from_roadmap` в режим fail-closed (запрет фиктивных `.queue.yaml`), переписывание устаревших тестов, исправление импорта `epic_dir` в `loop/runner/orchestrator.py` с удалением `except Exception: pass`, актуализация документации и полный cutover purge. Всего 7 sNN (целевой диапазон 5–8).

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность, plan_contract bake-in |
| `python-testing-patterns` | freeze oracle baseline, тестирование fail-closed сценариев и mock-изоляция |
| `architecture-patterns` | канонический Source of Truth для очередей и модульных импортов |
| `python-design-patterns` | явная обработка ошибок вместо скрытия исключений (fail-closed) |
| `python-anti-patterns` | устранение мертвого кода, shims и silent exception swallowing |

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN\|eNN | Notes |
| :--- | :--- | :--- | :--- |
| US-001 | Merge не подхватывает plan-dir slug queues | s01, s02, s06, s07 | Merge и discovery работают исключительно с canon queue и batches. |
| US-002 | `.md` roadmap path не silently maps | s01, s03, s04, s06, s07 | Передача `.md` пути вызывает явную ошибку (fail-closed). |
| US-003 | Orchestrator epic_dir работает через canonical import | s01, s05, s07 | Импорт канонического `epic_dir` без silent swallow. |
| FR-001 | Remove plan-dir `roadmap-*-epics.queue.yaml` discovery from live `discover_source_queues`. | s01, s02, s06, s07 | Удаление ветки сканирования директорий планов. |
| FR-002 | Remove or fail-closed `.md` branch of `queue_rel_from_roadmap`; rewrite tests. | s01, s03, s04, s07 | Перевод `.md` ветки в fail-closed и обновление тестов. |
| FR-003 | Wire orchestrator to canonical `epic_dir`; delete silent `except Exception: pass` around that import. | s01, s05, s07 | Канонический импорт `epic_dir` и удаление `except Exception: pass`. |
| FR-004 | Keep `roadmap/batches/*.yaml` discovery if still part of supported merge ops (prove with tests); do not delete without caller proof. | s01, s02, s07 | Сохранение поддержки `batches/*.yaml` с тестовым доказательством. |
| SC-001 | rg plan-dir scan loop absent. | s02, s07 | Отсутствие цикла сканирования plan_dir в коде. |
| SC-002 | md map tests expect deny. | s03, s04, s07 | Все тесты маппинга `.md` ожидают ValueError/исключение. |
| SC-003 | no `from loop.epic_paths import epic_dir` in orchestrator. | s05, s07 | Отсутствие некорректного импорта в orchestrator. |
| SC-004 | net_loc ≤ 0; net owners ≤ 0. | s02, s03, s05, s07 | Сокращение кодовой базы и отсутствие новых сущностей. |
| AC− #1 | Нет live plan-dir slug-queue merge source. | s02, s06, s07 | Исключение slug-очередей из источников слияния. |
| AC− #2 | Нет silent PASS на broken epic_dir import. | s05, s07 | Исключение скрытого проглатывания ошибок импорта. |
| AC− #3 | Нет dual machine map `.md` ↔ queue без ошибки. | s03, s04, s07 | Исключение неявного преобразования `.md` в очередь. |
| AC− #4 | Нет зелёных тестов, требующих legacy md map success. | s03, s04, s07 | Удаление/переписывание всех устаревших ассертов. |
| Out of scope | Event schema SoT unify | — | follow_up: T-HUB-103-event-schema-sot-unify |
| Out of scope | Plan-path classifier + board_sync helper | — | follow_up: T-HUB-104-plan-path-classifier-dedup |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN\|eNN |
| :--- | :--- | :--- |
| Prove Glob 0 live plan-dir queues; adjust discover tests | plan.md §HOW #1 | s01, s02 |
| Fail-closed md map; rewrite characterization/unit asserts | plan.md §HOW #2 | s03, s04 |
| Fix orchestrator import; remove swallow; targeted tests | plan.md §HOW #3 | s05 |
| Docstrings and instruction Kind I hygiene | plan.md §Replacement / sunset | s06 |
| Freeze oracles & full sunset purge | plan.md §HOW #4 | s01, s07 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Freeze oracle baseline: фиксация эталонного поведения discovery, queue_rel и orchestrator | s01, s07 |
| Purge plan-dir discovery: удаление сканирования slug-очередей из discover_source_queues | s02, s07 |
| Fail-closed md mapping: запрет неявного маппинга .md файлов в queue_rel_from_roadmap | s03, s07 |
| Characterization update: переписывание устаревших тестов на ожидание deny | s04, s07 |
| Canonical orchestrator import: корректный импорт epic_dir и устранение silent swallow | s05, s07 |
| Docs & instructions hygiene: очистка комментариев и докстрингов от устаревших форматов | s06, s07 |
| Deletion budget: net_loc ≤ 0, net owners ≤ 0 | s01, s02, s03, s04, s05, s06, s07 |
| Out of scope: Event schema SoT unify | follow_up: T-HUB-103-event-schema-sot-unify |
| Out of scope: Plan-path classifier + board_sync helper | follow_up: T-HUB-104-plan-path-classifier-dedup |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN\|eNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `loop/roadmap_queue.py::discover_source_queues` plan_dir loop | A | batches dir scan only | s02, s07 | no | Удаление сканирования plan_dir |
| `loop/roadmap_queue.py::ROLE_PLAN_DIRS` | A | `ROLE_ROADMAP_DIRS` only | s02, s07 | no | Удаление словаря директорий планов |
| `loop/roadmap_queue.py::queue_rel_from_roadmap` `.md` branch | B | fail-closed ValueError on `.md` | s03, s07 | no | Запрет маппинга `.md` путей |
| `loop/runner/orchestrator.py` broken `loop.epic_paths.epic_dir` + bare except | A | `from epic_paths import epic_dir` + explicit error handling | s05, s07 | no | Исправление импорта и удаление silent swallow |
| `loop/tests/test_dag_v2_characterization.py:307` md success assert | C | assert pytest.raises(ValueError) | s04, s07 | no | Переписывание ассерта на отказ |
| `loop/tests/test_roadmap_queue.py:476` md success assert | C | assert pytest.raises(ValueError) | s03, s07 | no | Переписывание ассерта на отказ |
| `loop/roadmap_queue.py` docstrings mentioning plan-dir slug queues | I | updated docstrings (batches only) | s06, s07 | no | Очистка устаревших упоминаний |

## Очередь шагов (BACK / FRONT)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-characterization-and-freeze-oracle-baseline.yaml](../yaml/steps/s01-characterization-and-freeze-oracle-baseline.yaml) | [s01…](../../implement/T-HUB-105-roadmap-legacy-source-purge/s01-characterization-and-freeze-oracle-baseline.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-purge-plan-dir-discovery-from-roadmap-queue.yaml](../yaml/steps/s02-purge-plan-dir-discovery-from-roadmap-queue.yaml) | [s02…](../../implement/T-HUB-105-roadmap-legacy-source-purge/s02-purge-plan-dir-discovery-from-roadmap-queue.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-fail-closed-md-roadmap-path-mapping.yaml](../yaml/steps/s03-fail-closed-md-roadmap-path-mapping.yaml) | [s03…](../../implement/T-HUB-105-roadmap-legacy-source-purge/s03-fail-closed-md-roadmap-path-mapping.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-rewrite-characterization-and-caller-tests.yaml](../yaml/steps/s04-rewrite-characterization-and-caller-tests.yaml) | [s04…](../../implement/T-HUB-105-roadmap-legacy-source-purge/s04-rewrite-characterization-and-caller-tests.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-canonical-orchestrator-epic-dir-import.yaml](../yaml/steps/s05-canonical-orchestrator-epic-dir-import.yaml) | [s05…](../../implement/T-HUB-105-roadmap-legacy-source-purge/s05-canonical-orchestrator-epic-dir-import.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-docs-and-instruction-kind-i-hygiene.yaml](../yaml/steps/s06-docs-and-instruction-kind-i-hygiene.yaml) | [s06…](../../implement/T-HUB-105-roadmap-legacy-source-purge/s06-docs-and-instruction-kind-i-hygiene.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s07** | [s07-legacy-fallback-purge.yaml](../yaml/steps/s07-legacy-fallback-purge.yaml) | [s07…](../../implement/T-HUB-105-roadmap-legacy-source-purge/s07-legacy-fallback-purge.yaml) | no | no | BACK IMPLEMENT | completed |