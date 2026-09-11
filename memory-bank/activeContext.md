---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-086-python-loop-supervisor-cutover
step_id: s01
---

## load_now
1. [back/plan/T-HUB-086-python-loop-supervisor-cutover/yaml/steps/s01-contracts-and-seams.yaml](back/plan/T-HUB-086-python-loop-supervisor-cutover/yaml/steps/s01-contracts-and-seams.yaml) — текущий work shard (BACK IMPLEMENT s01).
2. [back/plan/T-HUB-086-python-loop-supervisor-cutover/yaml/decompose-index.yaml](back/plan/T-HUB-086-python-loop-supervisor-cutover/yaml/decompose-index.yaml) — очередь/status (canon=yaml).

## Handoff BACK IMPLEMENT — s01
- **Дальше:** выполнить atomic шаг → FINISH (seed-implement → flush cp → suite → evidence in_progress → validate-step → Handoff → @verify → finalize-step)
- **Эпик:** T-HUB-086-python-loop-supervisor-cutover (BACK); armed из `back/plan/T-HUB-086-python-loop-supervisor-cutover/yaml/decompose-index.yaml` (прошлый activeContext игнорирован).
- **Текущий шаг:** s01 — Typed runner contracts, seams and CLI characterization tests (status=pending в index.yaml).
- **Команда:** `BACK IMPLEMENT @s01`
