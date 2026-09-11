---
description: PROGRAM RUN — alias → /loop-run (./bin/loop / ./loop/loop.sh --phase GAP_FANOUT)
---
**Alias → `/loop-run`.** Тот же runner: `./bin/loop` (shim: `./loop/loop.sh`) · `loop/WORKFLOW.md` · `.claude/instructions/program-loop.md`.
Не запускай runner из этой сессии. Пользователю — отдельный терминал:
```bash
./bin/loop --dag-generate portal
./bin/loop --phase GAP_FANOUT
./bin/loop gpt
./bin/loop --status
```
FORBIDDEN: `--track`, `--id`, `--gap`, `--resume-implement`, `./loop/program-loop.sh`.
$ARGUMENTS
