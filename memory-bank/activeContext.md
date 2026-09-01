## load_now
1. [s03-stop-gate-fingerprint.yaml](back/plan/decompose-T-HUB-040-harness-workflow-finish-api/s03-stop-gate-fingerprint.yaml) — текущий work shard (BACK IMPLEMENT s03).
2. [index.yaml](back/plan/decompose-T-HUB-040-harness-workflow-finish-api/index.yaml) — очередь/status (canon=yaml).

## Handoff BACK IMPLEMENT — s03
- **Эпик:** T-HUB-040-harness-workflow-finish-api (BACK); armed из `back/plan/decompose-T-HUB-040-harness-workflow-finish-api/s03-stop-gate-fingerprint.yaml`.
- **Текущий шаг:** s03 — stop-gate last_finish_tool fingerprint + epic state wire.
- **Команда:** `BACK IMPLEMENT @s03`
- **Состояние:** Код и тесты s03 реализованы, checkpoints cp1-cp4 выполнены, pytest harness/hooks/tests/test_stop_gate_fingerprint.py зелёный. Готово к @verify и finalize-step.

## done — do NOT load
- s01–s02 completed в `back/plan/decompose-T-HUB-040-harness-workflow-finish-api/index.yaml` (2 шагов).
