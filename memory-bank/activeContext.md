---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-079-orchestrator-lifecycle-reliability
step_id: s04
---

## load_now
1. [back/plan/T-HUB-079-orchestrator-lifecycle-reliability/yaml/steps/s04-typed-parent-api-todowrite-policy.yaml](back/plan/T-HUB-079-orchestrator-lifecycle-reliability/yaml/steps/s04-typed-parent-api-todowrite-policy.yaml) — текущий work shard (BACK IMPLEMENT s04).
2. [back/plan/T-HUB-079-orchestrator-lifecycle-reliability/yaml/decompose-index.yaml](back/plan/T-HUB-079-orchestrator-lifecycle-reliability/yaml/decompose-index.yaml) — очередь/status (canon=yaml).

## Handoff BACK IMPLEMENT — s04
- **Эпик:** T-HUB-079-orchestrator-lifecycle-reliability
- **Режим/шаг:** BACK IMPLEMENT s04
- **Сделано:** выполнен bootstrap шага s04, создан implement shard s04-typed-parent-api-todowrite-policy.yaml, начата реализация typed parent API await_gate и TodoWrite lifecycle policy.
- **Осталось:** завершить cp1 (await_gate/get_invocation_status в loop/lifecycle.py + test_await_gate_api.py), cp2 (TodoWrite policy в loop/context_loop.py + test_todowrite_policy.py), cp3 (проверка/очистка harness/instructions/epic-loop.md), запустить тесты и пройти gate verify.
