---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-087-epic-layout-v2-fallback-purge
step_id: s01
---

## load_now
1. [back/plan/T-HUB-087-epic-layout-v2-fallback-purge/yaml/steps/s01-contracts-and-seams.yaml](back/plan/T-HUB-087-epic-layout-v2-fallback-purge/yaml/steps/s01-contracts-and-seams.yaml) — текущий work shard (BACK IMPLEMENT s01).
2. [back/plan/T-HUB-087-epic-layout-v2-fallback-purge/yaml/decompose-index.yaml](back/plan/T-HUB-087-epic-layout-v2-fallback-purge/yaml/decompose-index.yaml) — очередь/status (canon=yaml).

## Handoff BACK IMPLEMENT — s01
- **Дальше:** выполнить atomic шаг → FINISH (seed-implement → flush cp → suite → evidence in_progress → validate-step → Handoff → @verify → finalize-step)
- **Эпик:** T-HUB-087-epic-layout-v2-fallback-purge (BACK); armed из `back/plan/T-HUB-087-epic-layout-v2-fallback-purge/yaml/decompose-index.yaml` (прошлый activeContext игнорирован).
- **Текущий шаг:** s01 — Characterize layout v2 contracts, denial diagnostics and negative resolution fixtures (status=pending в index.yaml).
- **Команда:** `BACK IMPLEMENT @s01`
