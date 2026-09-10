---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-091-gate-identity-sot-consolidation
step_id: s07
---

## load_now
1. [back/plan/T-HUB-091-gate-identity-sot-consolidation/yaml/steps/s07-legacy-fallback-purge.yaml](back/plan/T-HUB-091-gate-identity-sot-consolidation/yaml/steps/s07-legacy-fallback-purge.yaml) — текущий work shard (BACK IMPLEMENT s07).
2. [back/plan/T-HUB-091-gate-identity-sot-consolidation/yaml/decompose-index.yaml](back/plan/T-HUB-091-gate-identity-sot-consolidation/yaml/decompose-index.yaml) — очередь/status (canon=yaml).

## Handoff BACK IMPLEMENT — s07
- **Дальше:** выполнить atomic шаг → FINISH (seed-implement → flush cp → suite → evidence in_progress → validate-step → Handoff → @verify → finalize-step)
- **Эпик:** T-HUB-091-gate-identity-sot-consolidation (BACK); armed из `back/plan/T-HUB-091-gate-identity-sot-consolidation/yaml/decompose-index.yaml` (прошлый activeContext игнорирован).
- **Текущий шаг:** s07 — s07 — legacy-fallback-purge — full sunset inventory scan + deletes (status=pending в index.yaml).
- **Команда:** `BACK IMPLEMENT @s07`

## done
- s01–s06 completed в `back/plan/T-HUB-091-gate-identity-sot-consolidation/yaml/decompose-index.yaml` (6 шагов)
