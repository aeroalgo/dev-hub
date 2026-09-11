---
description: LOOP RUN — запуск ./bin/loop снаружи сессии (не из Bash агента)
---

Единая точка: `./bin/loop` (или `python3 -m loop.runner`; compatibility shim: `./loop/loop.sh`). Гайд: `loop/WORKFLOW.md`. Pointer: `.claude/instructions/loop-state.md`.

## HARD
1. **Не** вызывай `./bin/loop` из Bash/Agent внутри текущей Claude-сессии.
2. Скажи пользователю **выйти** из сессии (или открыть отдельный терминал) и запустить команду там.
3. **FORBIDDEN** флаги (их нет в runner): `--track`, `--id`, `--gap`, `--resume-implement`.
4. Один EPIC-спек за запуск. Два `decompose-*` → `multiple epic specs`.

## Канон (терминал)
```bash
# продолжить текущий activeContext
./bin/loop gpt

# switch эпика (overwrite activeContext из index)
./bin/loop decompose-T-034-loop-agent-scopes gpt
./bin/loop decompose-T-034-loop-agent-scopes gpt implement

# options
./bin/loop -m gpt
./bin/loop --status
./bin/loop --dag-generate portal
./bin/loop --phase GAP_FANOUT
```

`$ARGUMENTS` — только подсказка пользователю (epic id / model). Не собирай из них `--track` / `--id`.

$ARGUMENTS
