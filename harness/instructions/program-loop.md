# Program loop

Тот же runner, что epic: `./bin/loop` (Python supervisor: `python3 -m loop.runner`; compatibility shim: `./loop/loop.sh`).  
Канон переходов: `memory-bank/activeContext.md` + decompose index.

```bash
./bin/loop --dag-generate portal
./bin/loop --phase GAP_FANOUT
./bin/loop gpt
./bin/loop --status
```

FORBIDDEN: `--track`, `--id`, `--gap`, `--resume-implement`, `program-loop.sh`.
Запуск — снаружи сессии (см. `/loop-run`).
