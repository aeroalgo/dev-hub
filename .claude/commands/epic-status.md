---
description: EPIC STATUS — состояние автоцикла
---
Покажи статус loop (read-only):

```bash
./loop/loop.sh --status
```

Альтернатива (тот же schema `loop-status/v1`):

```bash
python3 .claude/hooks/epic_resolve.py status
```

Выведи кратко: projection (`phase`, `epic`, `next_step`), `stop`, `load_now`, runner/session если есть.

Не запускай `./loop/loop.sh` без `--status` (не стартуй автоцикл из этой команды).

$ARGUMENTS
