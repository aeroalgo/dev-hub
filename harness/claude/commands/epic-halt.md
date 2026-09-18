---
description: EPIC HALT — остановить автоцикл decompose
---
Останови epic loop через единственный владелец состояния:

```bash
./bin/loop halt --reason "${ARGUMENTS:-manual halt from /epic-halt}" --json
```

Кратко подтверди `status=halted`.
$ARGUMENTS
