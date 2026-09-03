---
description: PROGRAM RUN — alias → /loop-run (./loop/loop.sh --phase GAP_FANOUT)
---
**Alias → `/loop-run`.** Тот же runner: `./loop/loop.sh` · `loop/WORKFLOW.md` · `.claude/instructions/program-loop.md`.

Не запускай runner из этой сессии. Пользователю — отдельный терминал:

```bash
./loop/loop.sh --dag-generate portal
./loop/loop.sh --phase GAP_FANOUT
./loop/loop.sh gpt
./loop/loop.sh --status
```

FORBIDDEN: `--track`, `--id`, `--gap`, `--resume-implement`, `./loop/program-loop.sh`.

$ARGUMENTS
