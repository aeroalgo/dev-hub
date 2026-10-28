# Transactional single-cursor loop

Канонический вход — Python-скрипт `bin/loop.py`. `make` для запуска loop не
используется; он нужен только для подключения проекта через `make hub-link`.

У цикла один владелец текущего состояния: `runtime/<project>/epic/cursor.json`.
Только `loop.kernel.store.CursorStore` пишет cursor, transaction journal,
decompose index и generated `activeContext.md` в рамках одной транзакции.
`cursor.json` содержит `loop-state/v2`; `events.jsonl` содержит prepare/commit
records для recovery и не является вторым state owner. Индекс эпика остаётся
рабочими данными проекта, а `activeContext.md` — проекцией cursor; вручную они
не редактируются для продвижения Loop.

## Команды

```bash
python3 bin/loop.py start --project /path/to/project --epic E1
# Для security-эпика (или при неоднозначности kind) явно передаётся --kind:
python3 bin/loop.py start --project /path/to/project --epic SEC-01 --kind security
python3 bin/loop.py run --project /path/to/project --epic E1 --model <model>
python3 bin/loop.py finish --project /path/to/project --step s01
python3 bin/loop.py halt --project /path/to/project --reason "manual stop"
python3 bin/loop.py status --project /path/to/project --json
python3 bin/loop.py doctor --project /path/to/project --json
python3 bin/loop.py validate-verdict --project /path/to/project --payload '<json-object>'
python3 bin/loop.py board-sync --project /path/to/project [--epic E1]
```

`run` запускает одну сессию за раз. Чистое завершение процесса не двигает
курсор: агент обязан вызвать `finish`. Ошибка, timeout или отсутствие такого
перехода используют один счётчик `attempt`; после лимита курсор получает статус
`HALTED`.

Сессии — журнал диагностики. `events.jsonl` — transaction journal: при сбое
между index, cursor и projection следующий read завершает подготовленную
транзакцию. Ни CLI, ни hook не пишут эти файлы напрямую.

## Граница subagent → loop

Managed gate-субагент завершает ответ ровно одним fenced JSON-блоком
`loop-gate-verdict/v1`. `SubagentStop` проверяет его через Pydantic, сверяет
`session_id`, `epic_id`, `step_id` и `agent_id` с курсором и передаёт запись в
`LoopEngine.accept_verdict`. Только `PASS` под lock меняет очередь и курсор;
`FAIL`/`BLOCKED` обычно записываются как verdict-событие для recovery. Исключение —
`verify-qa: FAIL`: если последний `qa-*.yaml` имеет `verdict: fail|failed|blocked`
и `bugfix-queue.yaml` проходит intake-проверку, boundary атомарно переводит
курсор `QA → BUGFIX`. После завершения BUGFIX следующий валидный gate возвращает
его в QA и требует новый QA artifact. При QA PASS курсор идёт в `CONTEXT_SYNC`
(нужен `context-sync/<epic>/sync-*.md`), затем loop **marks the epic done** in
`memory-bank/<role>/roadmap/queue.yaml` and, if the queue still has a head with
`plan.md`, **arms the next epic** (обычно `DECOMPOSE` по плану в `plan/` или `security/plan/<id>/md/plan.md`). Empty queue / no queue
file → `DONE`. ARCHIVE остаётся операторской командой после финального DONE.
Cadence pause только при `LOOP_RESPECT_CADENCE=1`. Повторный callback идемпотентен, а три
некорректных JSON-ответа переводят курсор в `HALTED`.

Проверка payload до финального ответа агента:

```bash
python3 bin/loop.py validate-verdict --project /path/to/project \
  --payload '{"schema":"loop-gate-verdict/v1", ...}'
```

## Типы эпиков (kind) и SECURITY pipeline

Loop поддерживает типы эпиков `feature`, `refactor` и `security` (`--kind`):

- **Feature (`kind=feature`):** `memory-bank/<role>/plan/<id>/` и `implement/<id>/`. Жизненный цикл: `DECOMPOSE → ANALYZE → IMPLEMENT (sNN) → AUDIT → QA → CONTEXT_SYNC → DONE`.
- **Refactor (`kind=refactor`):** `memory-bank/<role>/refactor/plan/<id>/` и `refactor/implement/<id>/`. Жизненный цикл: `DECOMPOSE → ANALYZE → REFACTOR (rNN) → AUDIT → QA → CONTEXT_SYNC → DONE`.
- **Security (`kind=security`):** `memory-bank/<role>/security/plan/<id>/` и `security/implement/<id>/`. Жизненный цикл: `DECOMPOSE → SECURITY (aNN) → DONE`. Фаза `ANALYZE` пропускается; аудит выполняется по шагам `aNN` с гейтом `verify-security` и артефактами `schema: epic-security/v1` в `security/implement/<id>/aNN-*.yaml`. После завершения всех `aNN` цикл сразу переходит в `DONE` (без прогона feature-фаз `AUDIT`/`QA`/`CONTEXT_SYNC`).

## Конфигурация

Настройки цикла находятся в корневом `.env` и загружаются через
`loop.config.LoopSettings`. Файл `.claude/project.env` больше не читается.

Модель разрешается на каждой итерации: `--model` → `LOOP_STEP_MODELS` →
phase-переменная (`LOOP_MODEL_IMPLEMENT`, `LOOP_MODEL_QA`, …) → `LOOP_MODEL`.
Это позволяет менять модель при переходе на следующий step без перезапуска
supervisor. Если ни один источник не задан, запуск завершается с
`model_required`.

Границы runtime также задаются в `.env` (старые имена `EPIC_*` поддерживаются):

| Настройка | По умолчанию | Назначение |
|---|---:|---|
| `LOOP_SESSION_TIMEOUT` | `3600` сек | общий предел одной сессии |
| `LOOP_STATUS_HEARTBEAT` | `30` сек | период `SESSION_HEARTBEAT` с `elapsed` и `idle_for` |
| `LOOP_STREAM_IDLE_TIMEOUT` | `300` сек | таймаут отсутствия реального tool/command прогресса |
| `LOOP_COLLABORATION_WAIT_TIMEOUT` | выключен | необязательный предел ожидания native Codex subagent |
| `LOOP_SESSION_KILL_GRACE` | `30` сек | время на graceful stop перед `SIGKILL` |

Heartbeat виден в обычном выводе и сохраняется в `session-*.log`. При idle или
общем timeout процесс завершается, результат получает отдельный диагностический
код, а `SessionSupervisor` выполняет обычный bounded retry; это не маскируется
под пользовательский interrupt. Пустое значение отключает соответствующий
необязательный watchdog. По умолчанию ожидание native Codex subagent ограничено
только общим `LOOP_SESSION_TIMEOUT`.

Hooks активны только когда процесс запущен через `bin/loop.py`: он выставляет
`LOOP_ACTIVE=1` и `EPIC_LOOP=1`. Hook entrypoints без этих маркеров ничего не
делают.

## Контекстная граница и scope

`PreToolUse`/`PostToolUse` используют один атомарный policy ledger в runtime:

- `boundary-state.json` хранит actor-scoped версии и интервалы чтения,
  фактические изменения текущего шага, invalidation и метрики в одной модели.
  Он не хранит копию cursor: текущий scope вычисляется из cursor, прочитанного
  через `CursorStore`.
  Полностью покрытый hash/range возвращает `duplicate` и блокируется;
  пересечение возвращает `partial` только с непокрытыми интервалами.
  Неизвестный hash или границы — fail-closed.
- После `PostToolUse` ranges файла инвалидируются у всех actors текущей
  root-session. Поэтому retry видит прежний результат шага, а после изменения
  обязан прочитать новую версию. `git status` и незакоммиченные чужие файлы в
  scope не участвуют.

Проверка scope выполняется новым ядром:

```bash
python3 bin/loop.py scope --project /path/to/project --json
```


## Проекция состояния на внешние доски (Board Projection)

Loop поддерживает одностороннюю проекцию переходов эпиков на канбан-доски внешних таск-трекеров (Bitrix24, Plane). Доска является зеркалом (read-only mirror), единственным источником правды (SoT) остаётся локальный CursorStore цикла. Прямые вызовы REST API трекеров выполняются через унифицированный `BoardProjectionAdapter` Protocol без использования MCP как первичного транспорта.

### Конфигурация (.loop/board-projection.yaml)

Настройки проекции хранятся в `.loop/board-projection.yaml` проекта. Шаблон с описанием параметров доступен в `.loop/board-projection.yaml.example`.

- YAML (`.loop/board-projection.yaml`) — **общая структура**: `phase_alias`, `role_allowlist`, `project_docs.files`. Без id чужой доски.
- **Per-project board** (у каждого репо/доски своё) — только `.env` (env побеждает yaml):
  - `LOOP_BOARD_PROVIDER=bitrix24|plane|none`
  - Bitrix: `BITRIX_WEBHOOK_URL`, `BITRIX_GROUP_ID`, `BITRIX_RESPONSIBLE_ID`, `BITRIX_STAGE_*` или `BITRIX_STAGE_MAP` (JSON)
  - Plane: `PLANE_API_KEY`, `PLANE_BASE_URL`, `PLANE_WORKSPACE_SLUG`, `PLANE_PROJECT_ID`, `PLANE_STATE_*` / `PLANE_STATE_MAP`
  - Docs folder: `PROJECT_DOCS_FOLDER`
- Если файл yaml отсутствует или итоговый `provider=none` — проекция disabled (AC-5, SC-002).
- При обычном `loop.py run/start/finish` board-переменные из project `.env` подхватываются автоматически; уже заданные переменные процесса имеют приоритет.
- Рабочий yaml + sidecar `.loop/board-epic-map.yaml` gitignored; в репо — `.loop/board-projection.yaml.example` + `.env.example`.

### Жизненный цикл и sidecar-маппинг (.loop/board-epic-map.yaml)

Связка между `epic_id` и внешним идентификатором задачи фиксируется в sidecar-файле `.loop/board-epic-map.yaml`:

- **Lazy create:** При первом `start`/`run` после появления PLAN (или при ручном `board-sync`) создаётся карточка в `design`, а её `external_id` атомарно сохраняется в sidecar.
- **Move / transition:** Каждый подтверждённый переход cursor (`run`, `finish`, `rewind`, `halt`) перемещает карточку в колонку согласно `phase_alias` и карте стадий провайдера. Поиск карточки ведётся строго по `external_id` (поиск по заголовку запрещён во избежание коллизий).
- **Halt:** При ручной или автоматической остановке цикла (`halt`) карточка переводится в колонку `blocked` (алиас фазы `HALT`).

### Политика soft-fail

Ошибки взаимодействия с внешней доской (сетевые таймауты, 5xx ошибки REST API, временная недоступность сервиса) **никогда не откатывают** транзакцию перехода фазы и не прерывают выполнение команд `finish` и `halt` (FR-004, FR-009). При ошибке:
1. Сообщение об ошибке выводится в `sys.stderr`.
2. В файле `.loop/board-epic-map.yaml` для данного эпика выставляется поле `sync_error`.
3. Команда CLI возвращает успешный код завершения локального перехода.

### Защита от смены провайдера (provider_mismatch)

Если в sidecar-маппинге `.loop/board-epic-map.yaml` уже записаны карточки от одного провайдера (например, `bitrix24`), а в конфигурации активирован другой (например, `plane`), система завершается ошибкой `ProviderMismatchError` fail-closed **до** любых HTTP-запросов, предотвращая передачу чужих ID в несоответствующее API.

### Текст карточки (`prompt.md` → `## Board`)

При **первом** create (обычно `start`/`run` после `PLAN`, либо ручной `board-sync`) loop читает `memory-bank/<role>/plan/<epic>/md/prompt.md`:

- секция `## Board` с полями `title:` и `summary:` (без ID эпика — ID префиксует adapter);
- если `## Board` нет — fallback на `## Epic` → `### Outcome`;
- в описание добавляются `Epic:` и путь к `plan.md`.

Дальнейшие переходы **двигают** карточку по `phase_alias` → `stage_map` / `state_map`. Отдельной фазы «создать карточку» нет.

### Ручная публикация документации проекта (`project-docs`)

Это **не** эпик. Общие правила работы (workflow / gitflow / runbooks) публикуются в хранилище **проекта**:

- Bitrix24: Диск группы (`group_id`) → папка `project_docs.folder_name` (нужен scope `disk`)
- Plane: Pages проекта

Список файлов — в `.loop/board-projection.yaml` → `project_docs.files`. Только явная команда (не finish/halt):

```bash
python3 bin/loop.py project-docs --project . --json
python3 bin/loop.py project-docs --project . --file docs/runbooks/workflow-pack-operator.md --json
```

Workflow: `.cursor/rules/shared/workflow-board-docs.mdc` (`PROJECT DOCS`).

Опционально `board-docs` — аттач **только** `prompt.md` + `plan.md` к карточке эпика (без сгенерированного brief):

```bash
python3 bin/loop.py board-docs --project . --epic E1 --json
```

### Ручной догон синхронизации (CLI board-sync)

Для устранения накопленных `sync_error` после восстановления связи с внешним трекером предназначена подкоманда `board-sync`:

```bash
# Синхронизация текущего активного эпика:
python3 bin/loop.py board-sync --project /path/to/project

# Синхронизация конкретного эпика:
python3 bin/loop.py board-sync --project /path/to/project --epic E1
```

При успешном выполнении команда создаёт карточку (если ещё нет) или перемещает в актуальную стадию и очищает поле `sync_error`.
