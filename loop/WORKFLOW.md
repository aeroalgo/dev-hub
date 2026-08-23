# Автоцикл — context-first + transitions canon

Каталог **`loop/`** — автоматизация ролей; **не** часть `memory-bank/`.

> **Переходы (канон):** `memory-bank/activeContext.md` + decompose index; открытый `needs_creative: yes (CR-…)` или CREATIVE tip армирует CREATIVE, а closed/completed creative step возвращает тот же/следующий tip в IMPLEMENT; IMPLEMENT→QA→REFLECT→complete через context-first gates.
>
> **Очередь эпиков (канон):** `memory-bank/back/plan/roadmap-epics.queue.yaml`. Slug `roadmap-<slug>-epics.queue.yaml` — источники; слияние: `* ROADMAP MERGE` / `context_loop.py roadmap-merge`. При `EPIC_CHAIN_ROADMAP=1` после `EPIC_DONE` → `roadmap-advance`. Без флага — stop.
>
> **Тесты (канон):** [`.cursor/rules/shared/test-timeout.mdc`](../.cursor/rules/shared/test-timeout.mdc) — каждая test-команда запускается с внешним таймаутом 300 секунд.
> **HARD:** эпик **не** DONE / `EPIC_DONE`, пока нет **QA pass** + **REFLECT**  
> **Курсор сессии:** `memory-bank/activeContext.md` (проекция)  
> **Runner:** [`context_loop.py`](context_loop.py) · [`./loop.sh`](loop.sh)

| Канон | Путь |
|-------|------|
| Где стоим / next | `memory-bank/activeContext.md` + decompose `index.md` |
| Очередь эпиков | `roadmap-*.queue.yaml` (machine); md = human map |
| Переходы | `activeContext.md` + `context_loop.py`/`epic` gates |
| Gate DONE | `epic.epic_complete_allowed` (QA + reflection) |
| Chain next epic | `EPIC_CHAIN_ROADMAP=1` → `roadmap-advance` |
| Runner | `./loop/loop.sh` → `context_loop.py` |
| **Runtime bounds** | `EPIC_SESSION_TIMEOUT_SEC`, `EPIC_SESSION_KILL_GRACE_SEC`, `EPIC_TRANSIENT_RETRY_MAX`, `EPIC_DEGRADED_MAX`, `EPIC_STATUS_HEARTBEAT_SEC`, `EPIC_CHAIN_ROADMAP` |
| **Checkpoint** | durable cursor + `resume_from_step`; `state.json` — telemetry projection only |
| **Scheduler** | `loop-dag/v2`, dependency-ready nodes sequentially, one checkout |

## Production semantics

`.claude/project.env` is the checkout canon for runtime and permission values; `.claude/project.env.local` is the only local override. Do not create or synchronize values to a hypothetical example file.

- `activeContext.md`, the decompose index and the implement step are the source of truth for the current agent transition. The runner owns session timeout, process kill grace, bounded retry, degraded status and machine-readable diagnostics.
- A checkpoint records the durable cursor and lifecycle. `state.json` mirrors checkpoint telemetry; it is not an agent-owned cursor. A checkpoint/index conflict, malformed selected source or missing manifest is fail-closed.
- Recovery after timeout/process death reads `<hub>/runtime/<slug>/epic/last-session.json` (canon: `HUB_ROOT/runtime/<slug>/epic/` next to `state.json`) and accepts only an explicitly validated `resume_from_step`. `BLOCKED` and `NEED_HUMAN` preserve the cursor; resume must validate the checkpoint and index before scheduling. Do not auto-delete product runtime dirs.
- The v2 scheduler executes one dependency-ready node at a time in stable order. `GAP_FANOUT` is a manual-only operational command in this checkout; parallel fanout and distributed locks are not implied.
- FINISH order is **seed-implement → flush checkpoints during work → suite → evidence (`status` stays `in_progress`) → validate-step → Handoff → verify PASS → `finalize-step` (atomic implement+index `completed`, `ok: true`)**. `EPIC_DONE` requires QA PASS and REFLECT. T-034 policy is a boundary and never an implicit permission to mutate agent state.
- `prepare` on `mark_index_missing`: auto-rollback implement `completed`→`in_progress` (never auto-mark index), then continue; remaining integrity conflicts stay fail-closed/`NEED_HUMAN`.

## Rollout / rollback checklist

- **Phase A — observe:** collect bounded status and v1 compatibility diagnostics.
- **Phase B — shadow:** validate v2 manifest dependencies and checkpoint transitions without scheduling.
- **Phase C — canary:** execute one sequential dependency chain with timeout/retry/degraded caps.
- **Phase D — expand:** add chains only after restart-after-timeout, process-death and blocked-resume evidence.
- **Phase E — enforce:** fail-closed on malformed sources and checkpoint/index conflicts.
- **Rollback:** stop new scheduling, preserve event evidence, restore the last validated cursor or `resume_from_step`, then use a labelled manual fallback; never reset to first pending or delete telemetry.

### Phase C canary runbook

Локально подтвердите canary evidence до расширения rollout:

```bash
timeout 300s .venv/bin/pytest loop/tests/test_dag_canary.py loop/tests/test_finish_integrity.py -q
```

Тест закрепляет `validate_finish → check_after → prepare_session`: следующий узел остаётся закрытым до completion artifact предшественника, а финальный artifact требует `status: completed` и `integration_gate: pass`. Таймаут, retry и degraded caps берутся из runtime bounds выше; при ошибке сохраните evidence и выполните rollback boundary, не запускайте новый scheduling.

Стоп автоцикла: `EPIC_DONE` **только** после QA pass + reflection; иначе runner сбрасывает на QA/REFLECT.  
При `EPIC_CHAIN_ROADMAP=1`: после валидного `EPIC_DONE` (из `check-after` **или** `prepare`, если projection.phase уже DONE) → `roadmap-advance` (следующий из Queue YAML) → outer loop continue; очередь исчерпана → `ROADMAP_DONE`.  
`BLOCKED:` | `NEED_HUMAN:` — halt **только** для внешнего/человеческого стопа.
Incomplete AC текущего эпика (pending cp, `gaps.blocked`, parity FAIL) → не `BLOCKED:`;
hooks demote ложный `@verify` PASS → FAIL; prepare injects `## FIX INCOMPLETE` и loop чинит в том же эпике.
`GAPS:` / `**GAPS:**` — **не** stop (часто deferred sNN/eNN notes; путают с INTEG GAP). ARCHIVE — вручную вне loop (не в DONE/REFLECT loop-сессии; finish = EPIC_DONE → chain).

**Lifecycle reducer (post-implement):** `bugfix_done` / `qa_fail` **после** `reflection_done` снова открывают QA. Evidence-rehash bugfix **между** `qa_pass` и reflection **не** блокирует `DONE`. Default `_load_dag()` **не** автовыбирает `canary-*` / `*-demo` (только явный `--pipeline`).

## Managed-agent gate bypass и policy

`PROJECT_AGENT_<NAME>_MODEL` — модель. `PROJECT_AGENT_<NAME>_MODEL_CHAT` и `PROJECT_AGENT_<NAME>_MODEL_LOOP` — только boolean selectors (0/1), не model id. Отсутствующий selector → default `loop=1`, `chat=0`.

### Loop phase models (main session `--model`)

На каждой итерации `prepare` выбирает модель по `armed_step` / projection phase:

| Phase | Env |
|-------|-----|
| DECOMPOSE | `PROJECT_LOOP_DECOMPOSE_MODEL` |
| PLAN | `PROJECT_LOOP_PLAN_MODEL` |
| CREATIVE | `PROJECT_LOOP_CREATIVE_MODEL` |
| IMPLEMENT | `PROJECT_LOOP_IMPLEMENT_MODEL` |
| AUDIT | `PROJECT_LOOP_AUDIT_MODEL` |
| QA | `PROJECT_LOOP_QA_MODEL` |
| BUGFIX | `PROJECT_LOOP_BUGFIX_MODEL` |
| REFLECT | `PROJECT_LOOP_REFLECT_MODEL` |

Если override задан в `.claude/project.env` (или `.local`) — он **важнее** CLI `MODEL` (`make loop ARGS=gpt`). Если нет — используется CLI model. Пример: `PROJECT_LOOP_DECOMPOSE_MODEL=agy/claude-sonnet-4-6` при `make loop ARGS=gpt` → DECOMPOSE на sonnet, IMPLEMENT на gpt.

**Fail-closed model swap:** только при явном сообщении Claude/org `is restricted… Using X instead` — session wrapper убивает процесс (`exit 125`), `record-session` → `permanent_failure` / `model_substitution`, loop **HALT**. Разница CLI id vs init alias (например `agy/gemini-3.5-flash-medium` → `gemini-default`) — **не** halt. Fix при настоящем restrict: разрешить модель в org/OmniRoute или убрать недоступный `PROJECT_LOOP_<PHASE>_MODEL`.

Disabled managed agent — это `scope_disabled`/gate bypass, а не ошибка workflow: optional overlay не блокирует переход или completion. Для обязательного gate (`mode: gate`) невалидная конфигурация (`model_invalid` и аналогичные ошибки) остаётся fail-closed и блокирует Stop; корректно выключенный gate только фиксируется в bypass telemetry. Scope policy не даёт агенту implicit permission менять agent state.

Добавленный `.claude/agents/<name>.md` с `overlay:` автоматически попадает в registry; не требуется менять `settings.json`. После изменения каталога agents перезапустите Claude Code.

---

## 2. Запуск

```bash
./loop/loop.sh gpt
./loop/loop.sh decompose-v1-portal gpt
./loop/loop.sh --status
```

`decompose-<id>` → `arm`: overwrite `activeContext` из index (первый pending/active/blocked). Без EPIC — текущий курсор.

---

## 3. Агенту в сессии

Порядок IMPLEMENT FINISH (HARD):

1. `seed-implement` (YAML `in_progress`, cp=pending) **сразу**  
2. по ходу: `flush-checkpoint` после каждого зелёного cp  
3. suite parent → evidence (`done`/`files`/`tests`, cp=done) — **status остаётся `in_progress`** → `validate-step`  
4. Handoff (`activeContext`) → `@verify` packed (если code)  
5. `VERDICT: PASS` → `finalize-step` (атомарно implement+index `completed` через `mark-index-status`) → JSON `ok: true` → stop  

**FORBIDDEN:** писать `status: completed` руками · `finalize-step` до `VERDICT: PASS` · stop без `ok: true` · игнорировать fail-closed integrity без repair · runner CLI (`epic_resolve after|resolve|arm|…`)  
Канон detail: `.claude/instructions/spawn-hard.md` · prompt из `loop/context_loop.py`.
