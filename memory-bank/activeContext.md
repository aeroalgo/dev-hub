## load_now
1. [s04-board-launch-registry-runtime.yaml](back/plan/decompose-T-HUB-044-runtime-sync-doctor-docs/s04-board-launch-registry-runtime.yaml) — текущий work shard (BACK IMPLEMENT s04).
2. [index.yaml](back/plan/decompose-T-HUB-044-runtime-sync-doctor-docs/index.yaml) — очередь/status (canon=yaml).

## Handoff BACK IMPLEMENT — s04
- **Эпик:** T-HUB-044-runtime-sync-doctor-docs (BACK); armed из `back/plan/decompose-T-HUB-044-runtime-sync-doctor-docs/index.yaml` (прошлый activeContext игнорирован).
- **Текущий шаг:** s04 — Board launch --runtime choices from registry (add codex) (status=pending в index.yaml).
- **Команда:** `BACK IMPLEMENT @s04`
- **Дальше:** выполнить atomic шаг → FINISH (seed-implement → flush cp → suite → evidence in_progress → validate-step → Handoff → @verify → finalize-step).

## done — do NOT load
- s01–s03 completed в `back/plan/decompose-T-HUB-044-runtime-sync-doctor-docs/index.yaml` (3 шагов).
