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
python3 bin/loop.py run --project /path/to/project --epic E1 --model <model>
python3 bin/loop.py finish --project /path/to/project --step s01
python3 bin/loop.py halt --project /path/to/project --reason "manual stop"
python3 bin/loop.py status --project /path/to/project --json
python3 bin/loop.py doctor --project /path/to/project --json
python3 bin/loop.py validate-verdict --project /path/to/project --payload '<json-object>'
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
`FAIL`/`BLOCKED` записываются как verdict-событие. Повторный callback
идемпотентен, а три некорректных JSON-ответа переводят курсор в `HALTED`.

Проверка payload до финального ответа агента:

```bash
python3 bin/loop.py validate-verdict --project /path/to/project \
  --payload '{"schema":"loop-gate-verdict/v1", ...}'
```

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
| `LOOP_COLLABORATION_WAIT_TIMEOUT` | `180` сек | предел ожидания native Codex subagent |
| `LOOP_SESSION_KILL_GRACE` | `30` сек | время на graceful stop перед `SIGKILL` |

Heartbeat виден в обычном выводе и сохраняется в `session-*.log`. При idle или
общем timeout процесс завершается, результат получает отдельный диагностический
код, а `SessionSupervisor` выполняет обычный bounded retry; это не маскируется
под пользовательский interrupt. Пустое значение отключает соответствующий
необязательный watchdog.

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
