---
description: EPIC STATUS — состояние автоцикла
---
Покажи статус loop (read-only):
```bash
python3 "$DEV_HUB/bin/loop.py" status --json
```
Выведи `status`, `epic_id`, `phase`, `step_id`, `attempt` и путь к единому
`cursor.json`. Не запускай автоцикл из этой команды.
$ARGUMENTS
