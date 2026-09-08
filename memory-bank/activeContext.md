---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-084-workflow-reference-graph-hygiene
step_id: s01
---

## load_now
1. [back/plan/T-HUB-084-workflow-reference-graph-hygiene/yaml/steps/s01-reference-graph-fixtures.yaml](back/plan/T-HUB-084-workflow-reference-graph-hygiene/yaml/steps/s01-reference-graph-fixtures.yaml) — текущий work shard (BACK IMPLEMENT s01).
2. [back/plan/T-HUB-084-workflow-reference-graph-hygiene/yaml/decompose-index.yaml](back/plan/T-HUB-084-workflow-reference-graph-hygiene/yaml/decompose-index.yaml) — очередь/status (canon=yaml).

## Handoff BACK IMPLEMENT — s01
- **Дальше:** выполнить atomic шаг → FINISH (seed-implement → flush cp → suite → evidence in_progress → validate-step → Handoff → @verify → finalize-step)
- **Эпик:** T-HUB-084-workflow-reference-graph-hygiene (BACK); armed из `back/plan/T-HUB-084-workflow-reference-graph-hygiene/yaml/decompose-index.yaml` (прошлый activeContext игнорирован).
- **Текущий шаг:** s01 — Build a fail-closed reference graph validator with direct, transitive, and dangling fixtures (status=pending в index.yaml).
- **Команда:** `BACK IMPLEMENT @s01`
