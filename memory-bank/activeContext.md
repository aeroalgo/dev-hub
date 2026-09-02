## load_now
1. [s06-lib-resolve-runtime-registry.yaml](back/plan/decompose-T-HUB-042-runtime-adapter-framework/s06-lib-resolve-runtime-registry.yaml) — текущий work shard (BACK IMPLEMENT s06).
2. [index.yaml](back/plan/decompose-T-HUB-042-runtime-adapter-framework/index.yaml) — очередь/status (canon=yaml).

## Handoff BACK IMPLEMENT — s06
- **Эпик:** T-HUB-042-runtime-adapter-framework (BACK); armed из `back/plan/decompose-T-HUB-042-runtime-adapter-framework/index.yaml` (прошлый activeContext игнорирован).
- **Текущий шаг:** s06 — _lib.resolve_runtime_config registry-driven; purge _RUNTIME_MODES frozenset (status=pending в index.yaml).
- **Команда:** `BACK IMPLEMENT @s06`
- **Дальше:** выполнить atomic шаг → FINISH (seed-implement → flush cp → suite → evidence in_progress → validate-step → Handoff → @verify → finalize-step).

## done — do NOT load
- s01–s05 completed в `back/plan/decompose-T-HUB-042-runtime-adapter-framework/index.yaml` (5 шагов).
