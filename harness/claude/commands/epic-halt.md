---
description: EPIC HALT — остановить автоцикл decompose
---
Останови epic loop через единственный владелец состояния:

```bash
python3 "$DEV_HUB/bin/loop.py" halt --reason "${ARGUMENTS:-manual halt from /epic-halt}" --json
```

Кратко подтверди `status=halted`.
$ARGUMENTS
