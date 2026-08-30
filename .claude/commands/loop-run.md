---
description: LOOP RUN — запуск ./loop/loop.sh снаружи сессии (не из Bash агента)
---
Единая точка: `./loop/loop.sh`. Гайд: `loop/WORKFLOW.md`. Pointer: `.claude/instructions/loop-state.md`.

## HARD

1. **Не** вызывай `./loop/loop.sh` из Bash/Agent внутри текущей Claude-сессии.
2. Скажи пользователю **выйти** из сессии (или открыть отдельный терминал) и запустить команду там.
3. **FORBIDDEN** флаги (их нет в runner): `--track`, `--id`, `--gap`, `--resume-implement`.
4. Один EPIC-спек за запуск. Два `decompose-*` → `multiple epic specs`.

## Канон (терминал)

```bash
# продолжить текущий activeContext
./loop/loop.sh gpt

# switch эпика (overwrite activeContext из index)
./loop/loop.sh decompose-T-034-loop-agent-scopes gpt
./loop/loop.sh decompose-T-034-loop-agent-scopes gpt implement

# options
./loop/loop.sh -m gpt
./loop/loop.sh --status
./loop/loop.sh --dag-generate portal
./loop/loop.sh --phase GAP_FANOUT
```

`$ARGUMENTS` — только подсказка пользователю (epic id / model). Не собирай из них `--track` / `--id`.

$ARGUMENTS
