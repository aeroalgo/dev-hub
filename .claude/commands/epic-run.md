---
description: EPIC RUN — alias → /loop-run (./loop/loop.sh, без --track)
---
**Alias → `/loop-run`.** Канон: `./loop/loop.sh` · `loop/WORKFLOW.md`.

Не запускай runner из этой сессии. Пользователю — отдельный терминал:

```bash
./loop/loop.sh gpt
./loop/loop.sh decompose-<epic_id> gpt
./loop/loop.sh --status
```

FORBIDDEN: `--track`, `--id`, `--gap`, `--resume-implement`, `./loop/epic-loop.sh`.

$ARGUMENTS
