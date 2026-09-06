---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-070-phase-policy-overlay-sole-sot
step_id: s01
---

## load_now
1. [back/plan/T-HUB-070-phase-policy-overlay-sole-sot/yaml/steps/s01-overlay-red-tests.yaml](back/plan/T-HUB-070-phase-policy-overlay-sole-sot/yaml/steps/s01-overlay-red-tests.yaml) — текущий work shard (BACK IMPLEMENT s01).
2. [back/plan/T-HUB-070-phase-policy-overlay-sole-sot/yaml/decompose-index.yaml](back/plan/T-HUB-070-phase-policy-overlay-sole-sot/yaml/decompose-index.yaml) — очередь/status (canon=yaml).

## Handoff BACK IMPLEMENT — s01
- **Дальше:** выполнить atomic шаг → FINISH (seed-implement → flush cp → suite → evidence in_progress → validate-step → Handoff → @verify → finalize-step)
- **Эпик:** T-HUB-070-phase-policy-overlay-sole-sot (BACK); armed из `back/plan/T-HUB-070-phase-policy-overlay-sole-sot/yaml/decompose-index.yaml` (прошлый activeContext игнорирован).
- **Текущий шаг:** s01 — Red tests — armed DECOMPOSE need_verify true; QA FINISH without REFLECT (status=pending в index.yaml).
- **Команда:** `BACK IMPLEMENT @s01`
