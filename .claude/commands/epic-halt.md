---
description: EPIC HALT — остановить автоцикл decompose
---
Halt the epic loop now:

```bash
python3 .claude/hooks/epic_resolve.py halt --reason "${ARGUMENTS:-manual halt from /epic-halt}"
python3 .claude/hooks/epic_resolve.py status
```

Кратко подтверди status=halted.
$ARGUMENTS
