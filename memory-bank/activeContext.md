---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-047-harness-mb-scaffold-epic-layout
step_id: s10
---

## load_now
1. [back/plan/T-HUB-047-harness-mb-scaffold-epic-layout/yaml/steps/s10-migrate-apply-dev-hub.yaml](back/plan/T-HUB-047-harness-mb-scaffold-epic-layout/yaml/steps/s10-migrate-apply-dev-hub.yaml) — текущий work shard (BACK IMPLEMENT s10).
2. [back/plan/T-HUB-047-harness-mb-scaffold-epic-layout/yaml/decompose-index.yaml](back/plan/T-HUB-047-harness-mb-scaffold-epic-layout/yaml/decompose-index.yaml) — очередь/status (canon=yaml).

## Handoff BACK IMPLEMENT — s10
- **Дальше:** выполнить atomic шаг → FINISH (seed-implement → flush cp → suite → evidence in_progress → validate-step → Handoff → @verify → finalize-step)
- **Эпик:** T-HUB-047-harness-mb-scaffold-epic-layout (BACK); armed из `back/plan/T-HUB-047-harness-mb-scaffold-epic-layout/yaml/decompose-index.yaml` (прошлый activeContext игнорирован).
- **Текущий шаг:** s10 — Migrate apply на dev-hub memory-bank + validate-decompose-tree green (status=pending в index.yaml).
- **Команда:** `BACK IMPLEMENT @s10`

## done
- s01–s09 completed в `back/plan/T-HUB-047-harness-mb-scaffold-epic-layout/yaml/decompose-index.yaml` (9 шагов)
