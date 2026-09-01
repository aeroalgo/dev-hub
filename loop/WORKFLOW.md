# Автоцикл — context-first + transitions canon

Каталог **`loop/`** — автоматизация ролей; **не** часть `memory-bank/`.

> **Переходы (канон):** `memory-bank/activeContext.md` + decompose index; открытый `needs_creative: yes (CR-…)` или CREATIVE tip армирует CREATIVE, а closed/completed creative step возвращает тот же/следующий tip в IMPLEMENT; **pre-IMPLEMENT ANALYZE gate** (zero completed sNN + analyze missing/stale/critical) → ANALYZE до IMPLEMENT; IMPLEMENT→QA→REFLECT→complete через context-first gates.
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
| **Runtime bounds** | `EPIC_SESSION_TIMEOUT_SEC`, `EPIC_SESSION_KILL_GRACE_SEC`, `EPIC_TRANSIENT_RETRY_MAX`, `EPIC_DEGRADED_MAX`, `EPIC_STATUS_HEARTBEAT_SEC`, `EPIC_CHAIN_ROADMAP`, `EPIC_RUNTIME` |
| **Checkpoint** | durable cursor + `resume_from_step`; `state.json` — telemetry projection only |
| **Scheduler** | `loop-dag/v2`, dependency-ready nodes sequentially, one checkout |

## Epic-level board (Task Board)

При синхронизации с task-board (`dsh` / `mb-bridge`):
- **Единая карточка эпика (`card_kind: epic`):** На доске создаётся одна карточка на уровень эпика, вместо множества атомарных карточек отдельных шагов `sNN`.
- **Arm epic & Run:** Армирование контекста выполняется через `arm_epic` (`python3 loop/context_loop.py arm-epic <epic_id>`). Запуск выполнения эпика с таскборда выполняется по кнопке **Run** на карточке эпика или через CLI `./loop/loop.sh --epic-id <epic_id>`.
- **Column logic (Статусы колонок):**
  - `running`: эпик в очереди на позициях активной работы (rank 0 / active) и в процессе выполнения (phase PLAN, DECOMPOSE, IMPLEMENT, QA, etc.).
  - `backlog`: эпик находится в очереди roadmap (`roadmap-*.queue.yaml`), но ждёт своей очереди (rank > 0).
  - `todo`: эпик завершил фазу выполнения (`phase` = `DONE` или `NEXT_EPIC`) или готов к повторному запуску/принятию.
- **Sunset step cards:** Ранее созданные карточки шагов (`card_kind: step`) автоматически архивируются при запуске sync, уступая место единой карточке эпика.

## Production semantics

- **Runtime engine:** `EPIC_RUNTIME` selects execution engine: `claude` (default) | `dsh` (developer preview, opt-in; not production default). See [`docs/runbooks/dsh-loop-pilot.md`](../docs/runbooks/dsh-loop-pilot.md) for runbook details.
- `.claude/project.env` is the checkout canon for runtime and permission values; `.claude/project.env.local` is the only local override. Do not create or synchronize values to a hypothetical example file.

- `activeContext.md`, the decompose index and the implement step are the source of truth for the current agent transition. The runner owns session timeout, process kill grace, bounded retry, degraded status and machine-readable diagnostics.
- A checkpoint records the durable cursor and lifecycle. `state.json` mirrors checkpoint telemetry; it is not an agent-owned cursor. A checkpoint/index conflict, malformed selected source or missing manifest is fail-closed.
- Recovery after timeout/process death reads `<hub>/runtime/<slug>/epic/last-session.json` (canon: `HUB_ROOT/runtime/<slug>/epic/` next to `state.json`) and accepts only an explicitly validated `resume_from_step`. `BLOCKED` and `NEED_HUMAN` preserve the cursor; resume must validate the checkpoint and index before scheduling. Do not auto-delete product runtime dirs.
- The v2 scheduler executes one dependency-ready node at a time in stable order. `GAP_FANOUT` is a manual-only operational command in this checkout; parallel fanout and distributed locks are not implied.
- FINISH order is **seed-implement → flush checkpoints during work → suite → evidence (`status` stays `in_progress`) → validate-step → Handoff → verify PASS → `finalize-step` (atomic implement+index `completed`, `ok: true`)**. `EPIC_DONE` requires QA PASS and REFLECT. T-034 policy is a boundary and never an implicit permission to mutate agent state. `mark-index-status` updates index state on step completion.
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

**Lifecycle reducer (post-implement):** `bugfix_done` / `qa_fail` **после** `reflection_done` снова открывают QA **только пока нет более нового `qa_pass`**. Следующий `qa_pass` закрывает окно reopen → `REFLECT` (если reflection stale vs QA) или `DONE`. Иначе исторический `bugfix_done` после `reflection_done` навсегда пинит `phase=QA` при каждом rewrite `qa-*.yaml` (симптом: endless BACK QA при Handoff→REFLECT). Evidence-rehash bugfix **между** `qa_pass` и reflection **не** блокирует `DONE`. Default `_load_dag()` **не** автовыбирает `canary-*` / `*-demo` (только явный `--pipeline`).

## Managed-agent gate bypass и policy

`PROJECT_AGENT_<NAME>_MODEL` — модель. `PROJECT_AGENT_<NAME>_MODEL_CHAT` и `PROJECT_AGENT_<NAME>_MODEL_LOOP` — только boolean selectors (0/1), не model id. Отсутствующий selector → default `loop=1`, `chat=0`.

## Transition Engine

Unified phase transition contract (`loop/epic_transition.py`) orchestrates phase resolution, state arming, and readiness promotion across the loop subsystem. Driven by `loop/phase_registry.yaml`.

```
resolve_next(cwd, epic_id, role)
       │
       ▼
  arm_phase(cwd, epic_id, phase, role, **kwargs)
       │
       ▼
promote_if_ready(cwd, epic_id, role)
```

### Entry Points Table

| Function | Description |
|----------|-------------|
| `resolve_next(cwd, epic_id, role)` | Resolves next action and target phase based on current epic state and decompose index. |
| `arm_phase(cwd, epic_id, phase, role, **kwargs)` | Arms activeContext and epic state for a specified phase. |
| `promote_if_ready(cwd, epic_id, role)` | Evaluates readiness and gates (e.g. `analyze_gate`), promoting pre-implement phases (DECOMPOSE/ANALYZE) to IMPLEMENT. |
| `load_phase_registry(path)` | Loads phase definitions, verify agents, and DSH presets from `loop/phase_registry.yaml`. |

### Legacy Deprecations

Functions `promote_decompose_phase_if_ready`, `arm_active_context_from_decompose`, and `arm_pre_implement_context` are deprecated shims delegating to `epic_transition`.


### Loop phase models (main session `--model`)

На каждой итерации `prepare` выбирает модель по `armed_step` / projection phase:

| Phase | Env |
|-------|-----|
| DECOMPOSE | `PROJECT_LOOP_DECOMPOSE_MODEL` |
| PLAN | `PROJECT_LOOP_PLAN_MODEL` |
| ANALYZE | `PROJECT_LOOP_ANALYZE_MODEL` |
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

## Phase verify agents

Автоцикл использует специализированные гейт-агенты для валидации результатов на разных фазах:

| Phase | Dedicated Agent | Verdict Contract | Alias / Notes |
|-------|-----------------|------------------|---------------|
| IMPLEMENT | `verify-implement` | `loop-gate-verdict/v1` (`PASS`/`FAIL`) | Pre-FINISH code verification gate. Alias `@verify` → `verify-implement` |
| BUGFIX | `verify-bugfix` | `loop-gate-verdict/v1` (`PASS`/`FAIL`) | Pre-FINISH bugfix verification gate |
| QA | `verify-qa` | `loop-gate-verdict/v1` (`PASS`/`FAIL`) | Post-suite QA review gate. Alias `@reviewer` → `verify-qa` |
| DECOMPOSE | `verify-decompose` | `loop-gate-verdict/v1` (`PASS`/`FAIL`) | Decompose coverage & traceability verify gate |
| ANALYZE | `analyze-verify` | Read-only re-check | Post-analyze fixes verification before re-ANALYZE/IMPLEMENT |

### Migration Note
Исторические алиасы `@verify` и `@reviewer` поддерживаются через автоматическую нормализацию алиасов на фазовые типы `verify-implement` и `verify-qa`.

---

## Incident Autopilot

Автопилот инцидентов обеспечивает автоматическую диагностику и восстановление при ошибках оркестрации.

### Flow (Tier-0 → Tier-1 → Escalation)
