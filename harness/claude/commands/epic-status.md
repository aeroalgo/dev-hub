---
description: EPIC STATUS — состояние автоцикла
---
Покажи статус loop (read-only):
```bash
./bin/loop --status
```
(или через compatibility shim `./loop/loop.sh --status`)

Альтернатива (тот же schema `loop-status/v1`):
```bash
python3 .claude/hooks/epic_resolve.py status
```
Выведи кратко: projection (`phase`, `epic`, `next_step`), `stop`, `load_now`, runner/session если есть.
Не запускай `./bin/loop` без `--status` (не стартуй автоцикл из этой команды).
$ARGUMENTS
