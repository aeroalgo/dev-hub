# Single-cursor loop

`bin/loop` запускает `python3 -m loop.kernel`.

У цикла один владелец текущего состояния: `runtime/<project>/epic/cursor.json`.
Только `loop.kernel.store.CursorStore` пишет этот файл. Индекс эпика остаётся
рабочими данными проекта и меняется только командой `finish`; сгенерированный
`activeContext.md` является представлением курсора и не редактируется вручную.

## Команды

```bash
bin/loop start --project /path/to/project --epic E1
bin/loop run --project /path/to/project --epic E1 --model <model>
bin/loop finish --project /path/to/project --step s01
bin/loop halt --project /path/to/project --reason "manual stop"
bin/loop status --project /path/to/project --json
bin/loop doctor --project /path/to/project --json
```

`run` запускает одну сессию за раз. Чистое завершение процесса не двигает
курсор: агент обязан вызвать `finish`. Ошибка, timeout или отсутствие такого
перехода используют один счётчик `attempt`; после лимита курсор получает статус
`HALTED`.

Сессии и `events.jsonl` — журнал диагностики. Они не являются источником
состояния и не участвуют в выборе следующего шага.
