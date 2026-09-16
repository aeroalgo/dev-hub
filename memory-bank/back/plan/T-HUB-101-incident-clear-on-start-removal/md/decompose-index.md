# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-101-incident-clear-on-start-removal
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**
**Дата:** 2026-09-15
**Режим:** BACK DECOMPOSE

Декомпозиция реализует полное удаление автоматической очистки инцидентов при старте оркестратора (removal of automatic open incidents clear on loop/orchestrator start): исключение вызова `clear_open_on_start` из `Orchestrator.run()`, удаление метода `IncidentTracker.clear_open_on_start`, закрепление CLI `incident-clear-open` как единственного opt-in bulk-clear пути с сохранением forensic visibility инцидентов через перезапуски процесса, обновление тестов оркестратора и хранилища инцидентов, очистка Kind I инструкций и docstrings, и финальный sunset purge scan. Всего 6 шагов s01–s06 (в целевом диапазоне 5–8).

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность, plan_contract bake-in |
| `python-testing-patterns` | регрессионные тесты персистентности, обновление mock fixtures |
| `architecture-patterns` | fail-closed visibility, изоляция startup от побочных эффектов |

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN\|eNN | Notes |
| :--- | :--- | :--- | :--- |
| US-I2-001 | Как оператор loop, я хочу видеть open incidents после рестарта процесса, чтобы forensic typed failure surface не исчезала до явного решения. | s01, s03, s06 | Открытые инциденты сохраняются после перезапуска оркестратора. |
| US-I2-002 | Как оператор loop, я хочу явную CLI-команду incident-clear-open как единственный поддержанный способ массового снятия инцидентов. | s02, s04, s06 | CLI `incident-clear-open` является единственным opt-in bulk-clear путем. |
| FR-I2-001 | Orchestrator.run() MUST NOT вызывать bulk resolve open incidents на startup; блок ~285–294 с clear_open_on_start удаляется или заменяется no-op без side-effect на incidents.jsonl. | s01, s06 | Удаление вызова clear_open_on_start из `run()`. |
| FR-I2-002 | IncidentTracker.clear_open_on_start MUST быть удалён или превращён в deprecated stub, который fail-closed raise/логирует при вызове; единственный machine path bulk-clear — operator CLI. | s02, s06 | Удаление метода `clear_open_on_start` из класса `IncidentTracker`. |
| FR-I2-003 | Open incidents MUST оставаться visible (status: open) across process restart до explicit incident-clear-open или per-incident resolve API; forensic diagnostic codes не теряются. | s01, s03, s06 | Сохранение инцидентов в `incidents.jsonl` при перезапусках. |
| FR-I2-004 | CLI incident-clear-open MUST оставаться единственным opt-in audited bulk recovery; resolution_action и resolution_tier фиксируются в resolved record (не silent delete). | s02, s04, s06 | Фиксация аудита полей резолюции и JSON payload в CLI. |
| FR-I2-005 | Тесты loop/tests/test_runner_orchestrator.py MUST быть обновлены: убрать expectations на clear_open_on_start.assert_called_once; добавить regression — restart не clears incidents. | s03, s06 | Обновление тестов оркестратора и добавление regression persistence теста. |
| FR-I2-006 | Тесты incidents CLI/store MUST подтверждать, что auto-start path отсутствует; существующий test_resolve_all_open_incidents остаётся valid для operator CLI path only. | s04, s06 | Верификация изоляции CLI и store тестов от старта оркестратора. |
| FR-I2-007 | Kind I surfaces MUST NOT instruct agent/loop to auto-clear incidents or markers on restart; если такие фразы есть — rewrite на operator-only recovery. | s05, s06 | Очистка docstrings, CLI help и комментариев. |
| NFR-I2-001 | Изменение не добавляет новый persistence layer и не требует migration существующих resolved records. | s01, s02, s06 | Используется существующий JSONL persistence layer без миграции. |
| NFR-I2-002 | Startup orchestrator не выполняет write I/O на `incidents.jsonl` кроме уже существующих trace/telemetry paths вне scope этого gap. | s01, s02, s06 | Startup не мутирует хранилище инцидентов. |
| NFR-I2-003 | Operator CLI contract (`incident-clear-open`, JSON output) остаётся backward-compatible; breaking change запрещён без documented migration. | s02, s04, s06 | Операторский CLI и JSON-контракт сохраняются. |
| NFR-I2-004 | I2 не меняет idempotency keys, reducer transitions, receipt provenance (077) или capability evidence paths. | s01, s02, s03, s04, s05, s06 | Изменения ограничены удалением startup incident clearing. |
| AC-1 | Orchestrator run() на startup не вызывает bulk resolve open incidents; pre-seeded open incident остаётся open после restart. | s01, s03, s06 | Проверка поведения startup. |
| AC-2 | IncidentTracker.clear_open_on_start удалён или unreachable; grep по repo не находит live call path from orchestrator start. | s02, s06 | Проверка отсутствия символа. |
| AC-3 | incident-clear-open CLI остаётся рабочим opt-in bulk recovery с JSON output и audited resolution fields. | s04, s06 | Проверка работы CLI. |
| AC-4 | Regression tests orchestrator не expect clear_open_on_start; новый test подтверждает forensic persistence. | s03, s06 | Проверка тестов оркестратора. |
| AC-5 | Prompt Forbidden after «Marker clearing» не нарушается автоматическим wipe на start. | s01, s05, s06 | Исключение автоматического маркера/очистки. |
| AC− #1 | Нет автоматического resolve open incidents при loop/process start. | s01, s06 | Исключение auto-resolve на старте. |
| AC− #2 | Нет dual path: auto-clear + operator CLI как равноправные bulk recovery. | s02, s04, s06 | Единственный bulk-path — operator CLI. |
| AC− #3 | Нет silent swallow ошибок incident store на startup через auto-clear try/except. | s01, s02, s06 | Устранение блока try/except swallow. |
| AC− #4 | Нет расширения scope на durable reducer rewrite, dashboard, 077/078/080/076. | s01, s02, s03, s04, s05, s06 | Строгое соблюдение границ скоупа. |
| AC− #5 | Нет instruction surface, обучающей agent auto-clear incidents/markers on restart. | s05, s06 | Очистка Kind I поверхностей. |
| Out of scope | LifecycleReducer durable _by_key rewrite | — | follow_up: T-HUB-078-context-budget-enforcement |
| Out of scope | Provider dashboard / UI | — | follow_up: T-HUB-077-gate-evidence-integrity |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN\|eNN |
| :--- | :--- | :--- |
| Remove auto-clear from Orchestrator.run() | plan.md §Outcome summary & §Target layout | s01 |
| Purge IncidentTracker.clear_open_on_start & store defaults | plan.md §Technology axiom & §Sunset A | s02 |
| Update orchestrator unit tests & add restart regression | plan.md §FR-I2-005 & §QA consumes | s03 |
| Enforce operator CLI as sole bulk recovery path | plan.md §FR-I2-004, FR-I2-006 & §Sunset B | s04 |
| Kind I instructions & docstring hygiene | plan.md §FR-I2-007 & §Sunset I | s05 |
| Final sunset scan & full regression verification | plan.md §Sunset A/B/C/I & §QA consumes | s06 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Fail-closed incident visibility on restart | s01, s03, s06 |
| IncidentTracker.clear_open_on_start removed | s02, s06 |
| Operator-only bulk incident recovery via incident-clear-open | s02, s04, s06 |
| Orchestrator tests updated without auto-clear expectations | s03, s06 |
| Kind I instructions and docstrings aligned | s05, s06 |
| Sunset inventory verified (zero legacy calls / swallow blocks) | s06 |
| Out of scope: LifecycleReducer durable _by_key rewrite | follow_up: T-HUB-078-context-budget-enforcement |
| Out of scope: Provider dashboard / UI | follow_up: T-HUB-077-gate-evidence-integrity |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN\|eNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `IncidentTracker.clear_open_on_start` | A | operator CLI `incident-clear-open` | s02, s06 | no | Удаление метода из `IncidentTracker` |
| `Orchestrator.run()` auto-clear block | A | no startup incident mutation | s01, s06 | no | Удаление вызова из `run()` |
| `resolution_action: clear_open_on_loop_start` | A | explicit operator action | s02, s06 | no | Замена дефолта на явное действие оператора |
| `mock_tracker.clear_open_on_start` test mocks | A | `test_orchestrator_preserves_open_incidents_on_start` | s03, s06 | no | Удаление моков и добавление теста персистентности |
| Implicit loop restart clears incidents | B | `incident-clear-open` CLI | s04, s06 | no | Явный вызов через CLI |
| `except Exception: return ok/cleared_count 0` swallow | C | fail-closed error handling | s01, s02, s06 | no | Исключение подавления ошибок |
| Kind I auto-clear instructions / docstrings | I | operator-only recovery docs | s05, s06 | no | Очистка docstrings и текстов справок |

## Очередь шагов (BACK / FRONT)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-remove-startup-incident-mutation.yaml](../yaml/steps/s01-remove-startup-incident-mutation.yaml) | [s01…](../../implement/T-HUB-101-incident-clear-on-start-removal/s01-remove-startup-incident-mutation.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-purge-incident-tracker-clear-open-on-start.yaml](../yaml/steps/s02-purge-incident-tracker-clear-open-on-start.yaml) | [s02…](../../implement/T-HUB-101-incident-clear-on-start-removal/s02-purge-incident-tracker-clear-open-on-start.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-update-orchestrator-tests-and-forensic-persistence.yaml](../yaml/steps/s03-update-orchestrator-tests-and-forensic-persistence.yaml) | [s03…](../../implement/T-HUB-101-incident-clear-on-start-removal/s03-update-orchestrator-tests-and-forensic-persistence.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-enforce-operator-cli-sole-bulk-recovery.yaml](../yaml/steps/s04-enforce-operator-cli-sole-bulk-recovery.yaml) | [s04…](../../implement/T-HUB-101-incident-clear-on-start-removal/s04-enforce-operator-cli-sole-bulk-recovery.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-instruction-kind-i-and-docstring-hygiene.yaml](../yaml/steps/s05-instruction-kind-i-and-docstring-hygiene.yaml) | [s05…](../../implement/T-HUB-101-incident-clear-on-start-removal/s05-instruction-kind-i-and-docstring-hygiene.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-legacy-fallback-purge.yaml](../yaml/steps/s06-legacy-fallback-purge.yaml) | [s06…](../../implement/T-HUB-101-incident-clear-on-start-removal/s06-legacy-fallback-purge.yaml) | no | no | BACK IMPLEMENT | completed |