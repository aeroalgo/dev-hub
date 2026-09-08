---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-083-role-core-shared-contract
step_id: s05
---

## load_now
1. [back/plan/T-HUB-083-role-core-shared-contract/yaml/steps/s05-role-core-semantic-regression.yaml](back/plan/T-HUB-083-role-core-shared-contract/yaml/steps/s05-role-core-semantic-regression.yaml) — текущий work shard (BACK IMPLEMENT s05).
2. [back/plan/T-HUB-083-role-core-shared-contract/yaml/decompose-index.yaml](back/plan/T-HUB-083-role-core-shared-contract/yaml/decompose-index.yaml) — очередь/status (canon=yaml).

## Handoff BACK IMPLEMENT — s05
- **Дальше:** выполнить atomic шаг → FINISH (seed-implement → flush cp → suite → evidence in_progress → validate-step → Handoff → @verify → finalize-step)
- **Эпик:** T-HUB-083-role-core-shared-contract (BACK); armed из `back/plan/T-HUB-083-role-core-shared-contract/yaml/decompose-index.yaml` (прошлый activeContext игнорирован).
- **Текущий шаг:** s05 — Mode-W matrix и полный hub suite подтверждают отсутствие компенсационных изменений (status=pending в index.yaml).
- **Команда:** `BACK IMPLEMENT @s05`

## done
- s01–s04 completed в `back/plan/T-HUB-083-role-core-shared-contract/yaml/decompose-index.yaml` (4 шагов)
