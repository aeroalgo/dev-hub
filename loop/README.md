# System loop — автоцикл (вне memory-bank)

Каталог **`loop/`** — автоматизация ролей. `memory-bank/` — артефакты. The source of truth is `activeContext.md` plus the decompose index.

**Канон переходов:** `memory-bank/activeContext.md` + `plan/decompose-*/index.yaml` + implement step.  
**Очередь эпиков (loop canon):** `memory-bank/back/plan/roadmap-epics.queue.yaml` (sibling `.md`; loop не грузит md). Opt-in: `EPIC_CHAIN_ROADMAP=1` → `roadmap-advance`. Default `0` — stop / optional DAG fanout.  
MULTI-EPIC PLAN пишет slug `roadmap-<slug>-epics.queue.yaml`; **`BACK|FRONT|INTEG ROADMAP MERGE`** (CLI `context_loop.py roadmap-merge`) склеивает их в canon. Templates: roadmap-epics.md · roadmap-queue.yaml.  
Для cross-epic journey runner использует runner-owned `loop/dag/*.yaml`: манифест `loop-dag/v2`, dependency-ready узлы выбираются последовательно и стабильно. `GAP_FANOUT` в текущем checkout запускается вручную через `./loop/loop.sh --phase GAP_FANOUT`; он не является автоматическим переходом `loop.sh`.  
Следующий шаг и режим выбираются по activeContext; DAG только переключает эпики. Durable checkpoint cursor не принадлежит `state.json`: `state.json` — телеметрическая проекция checkpoint, а конфликт checkpoint/index останавливается fail-closed.  
Runner владеет сессией, bounded timeout/retry и status evidence; агент владеет содержимым шага, Handoff и state mutation только через канонические артефакты.

DAG-команды:

```bash
./loop/loop.sh --dag-generate portal
./loop/loop.sh --phase GAP_FANOUT
./loop/loop.sh --status
```

Phase C canary (локальная evidence-проверка, без запуска runner):

```bash
timeout 300s .venv/bin/pytest loop/tests/test_dag_canary.py loop/tests/test_finish_integrity.py -q
```

Canary проверяет `canary-finish-integrity`: только последовательную цепочку `validate_finish → check_after → prepare_session`, completion artifact и integrity gate. Для rollback не удаляйте checkpoint evidence; восстановите последний валидированный cursor или `resume_from_step` и используйте помеченный manual fallback.

Манифест — YAML `loop-dag/v2` с `pipeline.id`, `source`, `execution` и `nodes[]`; каждый узел содержит `id`, `decompose`, опциональный `role_dir` и `depends_on`. Совместимый v1-манифест читается только через явный адаптер/диагностику, не как silent fallback.

| | |
|--|--|
| **Курсор/переходы** | `memory-bank/activeContext.md` + decompose index |
| **Гайд** | [`WORKFLOW.md`](WORKFLOW.md) |
| **CLI** | `loop/context_loop.py` |
| **Runner** | `./loop/loop.sh` |
| **Тесты** | `.venv/bin/pytest loop/tests -q` |
| **FINISH** | `.cursor/rules/shared/finish-block.mdc` |

## Production contract

`.claude/project.env` is the checkout canon for runtime and permission values; `.claude/project.env.local` is the only local override. Do not create or synchronize values to a hypothetical example file.

- **Runner bounds:** `EPIC_SESSION_TIMEOUT_SEC` (3600), `EPIC_SESSION_KILL_GRACE_SEC` (30), `EPIC_TRANSIENT_RETRY_MAX` (30), `EPIC_DEGRADED_MAX` (3), `EPIC_SESSION_LOG_LIMIT_BYTES` (10000000), `EPIC_STATUS_HEARTBEAT_SEC` (30; empty = disabled), `EPIC_STREAM_IDLE_TIMEOUT_SEC` (300; empty = disabled; idle = no `tool_use`/`tool_result`, not stream silence), `EPIC_CHAIN_ROADMAP` (0 = stop after EPIC_DONE; 1 = arm next from roadmap Queue). Zero/unlimited mode is not supported; invalid values fail closed with `invalid_runtime_config`.
- **Checkpoint:** durable cursor, `resume_from_step`, lifecycle (`pending` → `active` → `completed`/`BLOCKED`/`NEED_HUMAN`) and the decompose index are the recovery boundary. `state.json` mirrors checkpoint telemetry and must not be edited by an agent. Checkpoint/index conflicts halt fail-closed.
- **Recovery:** after timeout or process death, inspect `HUB_ROOT/runtime/<slug>/epic/last-session.json` (same epic dir as `state.json`); resume only from the validated `resume_from_step`. A transient retry cap is bounded; degraded status is observable and does not silently reset the cursor. Manual fallback must be labelled manual and never masquerade as autonomous projection authority. Do not auto-delete product runtime dirs.
- **Scheduler:** dependency-ready nodes run one at a time in stable order; parallel fanout and distributed-lock claims are out of scope. One checkout is the operational limitation.
- **Gates:** runner owns timeout/session/status evidence; the agent owns the step artifact and Handoff; seed-implement then flush checkpoints during work; verify PASS precedes `mark-index-status`; QA PASS and REFLECT precede `EPIC_DONE`; T-034 policy remains a boundary, not an implicit override.

## Rollout and rollback

- **Phase A — observe:** enable status evidence and compare v1 compatibility diagnostics without changing the durable cursor.
- **Phase B — shadow:** generate v2 manifests and validate dependency/order/checkpoint contracts in read-only mode.
- **Phase C — canary:** run one dependency chain sequentially with bounded timeout, retry and degraded caps.
- **Phase D — expand:** roll out to remaining chains only after restart-after-timeout, process-death and `BLOCKED`/`NEED_HUMAN` resume evidence passes.
- **Phase E — enforce:** reject malformed manifests and checkpoint/index conflicts fail-closed; keep rollback available.
- **Rollback:** stop new scheduling, preserve event/checkpoint evidence, restore the last validated cursor or `resume_from_step`, and use a labelled manual fallback. Never delete `state.json` or reset to the first pending step to hide a conflict.

```bash
./loop/loop.sh gpt
./loop/loop.sh decompose-T-033-concurrent-jobs-outbox gpt implement
./loop/loop.sh -m gpt --max 20
./loop/loop.sh --status
```
