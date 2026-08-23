# Program loop

Тот же runner, что epic: `./loop/loop.sh` (context-first).  
Канон переходов: `memory-bank/activeContext.md` + decompose index.

```bash
./loop/loop.sh --dag-generate portal
./loop/loop.sh --phase GAP_FANOUT
./loop/loop.sh gpt
./loop/loop.sh --status
```

FORBIDDEN: `--track`, `--id`, `--gap`, `--resume-implement`, `program-loop.sh`.
Запуск — снаружи сессии (см. `/loop-run`).
