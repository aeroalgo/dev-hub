---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-086-python-loop-supervisor-cutover
step_id: s04
---

## load_now
1. [back/plan/T-HUB-086-python-loop-supervisor-cutover/yaml/steps/s04-outer-orchestrator-and-lifecycle.yaml](back/plan/T-HUB-086-python-loop-supervisor-cutover/yaml/steps/s04-outer-orchestrator-and-lifecycle.yaml) — текущий work shard (BACK IMPLEMENT s04).
2. [back/plan/T-HUB-086-python-loop-supervisor-cutover/yaml/decompose-index.yaml](back/plan/T-HUB-086-python-loop-supervisor-cutover/yaml/decompose-index.yaml) — очередь/status (canon=yaml).

## Handoff BACK IMPLEMENT — s04
- **Дальше:** выполнить atomic шаг → FINISH (seed-implement → flush cp → suite → evidence in_progress → validate-step → Handoff → @verify → finalize-step)
- **Эпик:** T-HUB-086-python-loop-supervisor-cutover (BACK); armed из `back/plan/T-HUB-086-python-loop-supervisor-cutover/yaml/decompose-index.yaml` (прошлый activeContext игнорирован).
- **Текущий шаг:** s04 — LoopRunner outer orchestrator, retry policy and action decision machine (status=pending в index.yaml).
- **Команда:** `BACK IMPLEMENT @s04`

## done
- s01–s03 completed в `back/plan/T-HUB-086-python-loop-supervisor-cutover/yaml/decompose-index.yaml` (3 шагов)
