---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-095-epic-runtime-import-sole-path
step_id: s01
---

## load_now
1. [back/plan/T-HUB-095-epic-runtime-import-sole-path/yaml/steps/s01-dead-alias-purge-c2.yaml](back/plan/T-HUB-095-epic-runtime-import-sole-path/yaml/steps/s01-dead-alias-purge-c2.yaml) — текущий work shard (BACK IMPLEMENT s01).
2. [back/plan/T-HUB-095-epic-runtime-import-sole-path/yaml/decompose-index.yaml](back/plan/T-HUB-095-epic-runtime-import-sole-path/yaml/decompose-index.yaml) — очередь/status (canon=yaml).

## Handoff BACK IMPLEMENT — s01
- **Дальше:** выполнить atomic шаг → FINISH (seed-implement → flush cp → suite → evidence in_progress → validate-step → Handoff → @verify → finalize-step)
- **Эпик:** T-HUB-095-epic-runtime-import-sole-path (BACK); armed из `back/plan/T-HUB-095-epic-runtime-import-sole-path/yaml/decompose-index.yaml` (прошлый activeContext игнорирован).
- **Текущий шаг:** s01 — s01 — dead-alias-purge-c2 — remove auto_finish_after_gate and DEFAULT_ROADMAP (status=pending в index.yaml).
- **Команда:** `BACK IMPLEMENT @s01`
