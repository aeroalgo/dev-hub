---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-047-harness-mb-scaffold-epic-layout
step_id: s01
---

## load_now
1. [back/plan/decompose-T-HUB-047-harness-mb-scaffold-epic-layout/s01-plan-spec-schema.yaml](back/plan/decompose-T-HUB-047-harness-mb-scaffold-epic-layout/s01-plan-spec-schema.yaml) — текущий work shard (BACK IMPLEMENT s01).
2. [back/plan/decompose-T-HUB-047-harness-mb-scaffold-epic-layout/index.yaml](back/plan/decompose-T-HUB-047-harness-mb-scaffold-epic-layout/index.yaml) — очередь/status (canon=yaml).

## Handoff BACK IMPLEMENT — s01
- **Дальше:** выполнить atomic шаг → FINISH (seed-implement → flush cp → suite → evidence in_progress → validate-step → Handoff → @verify → finalize-step)
- **Эпик:** T-HUB-047-harness-mb-scaffold-epic-layout (BACK); armed из `back/plan/decompose-T-HUB-047-harness-mb-scaffold-epic-layout/index.yaml` (прошлый activeContext игнорирован).
- **Текущий шаг:** s01 — epic-plan/v1 schema + epic-layout/v2 schema (loop/schemas/) (status=pending в index.yaml).
- **Команда:** `BACK IMPLEMENT @s01`
