---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-091-gate-identity-sot-consolidation
step_id: s01
---

## load_now
1. [back/plan/T-HUB-091-gate-identity-sot-consolidation/yaml/steps/s01-gate-identity-sot-api.yaml](back/plan/T-HUB-091-gate-identity-sot-consolidation/yaml/steps/s01-gate-identity-sot-api.yaml) — текущий work shard (BACK IMPLEMENT s01).
2. [back/plan/T-HUB-091-gate-identity-sot-consolidation/yaml/decompose-index.yaml](back/plan/T-HUB-091-gate-identity-sot-consolidation/yaml/decompose-index.yaml) — очередь/status (canon=yaml).

## Handoff BACK IMPLEMENT — s01
- **Дальше:** выполнить atomic шаг → FINISH (seed-implement → flush cp → suite → evidence in_progress → validate-step → Handoff → @verify → finalize-step)
- **Эпик:** T-HUB-091-gate-identity-sot-consolidation (BACK); armed из `back/plan/T-HUB-091-gate-identity-sot-consolidation/yaml/decompose-index.yaml` (прошлый activeContext игнорирован).
- **Текущий шаг:** s01 — s01 — GateIdentity SoT API core (freeze, expected, inject_text, assert_fence, bind_fence) (status=pending в index.yaml).
- **Команда:** `BACK IMPLEMENT @s01`
