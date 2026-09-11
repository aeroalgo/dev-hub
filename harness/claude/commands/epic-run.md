---
description: EPIC RUN — alias → /loop-run (./bin/loop / ./loop/loop.sh, без --track)
---
**Alias → `/loop-run`.** Канон: `./bin/loop` (shim: `./loop/loop.sh`) · `loop/WORKFLOW.md`.
Не запускай runner из этой сессии. Пользователю — отдельный терминал:
```bash
./bin/loop gpt
./bin/loop decompose-<epic_id> gpt
./bin/loop --status
```
FORBIDDEN: `--track`, `--id`, `--gap`, `--resume-implement`, `./loop/epic-loop.sh`.
$ARGUMENTS
