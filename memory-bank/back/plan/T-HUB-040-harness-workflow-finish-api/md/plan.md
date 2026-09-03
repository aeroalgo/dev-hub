# [T-HUB-040 | harness-workflow-finish-api] PLAN

**Дата:** 2026-09-01  
**Режим:** BACK PLAN  
**Уровень:** L3–L4  
**Статус:** active  
**Roadmap:** [roadmap-harness-maturity-borrowings-epics.md](roadmap-harness-maturity-borrowings-epics.md)  
**Queue:** [roadmap-harness-maturity-borrowings-epics.queue.yaml](roadmap-harness-maturity-borrowings-epics.queue.yaml)  
**Deps:** **hard** T-HUB-029 (Transition Engine / `arm_phase` stable), T-HUB-033 (`finalize_step` + session boundary). **Soft:** T-HUB-039 (verify sidecar contract), T-HUB-022 (done — `loop-handoff/v1`).

**Skills:** writing-plans · architecture-patterns · python-testing-patterns · fastapi-templates (MCP transport only)

→ [T-HUB-040-harness-workflow-finish-api/md/decompose-index.md](T-HUB-040-harness-workflow-finish-api/md/decompose-index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** Сократить ошибки LLM при FINISH workflow: агент сейчас вручную пишет `activeContext.md`, статусы index/implement, `tasks.md`, `tasks/log` — prose в произвольном формате → shape drift (`multiple_handoff`, `completed_in_load_now`, sandwich), рассинхрон yaml↔index, ложные PASS до `finalize-step`.
- **gap (as-built):**
  - `finalize-step` атомарно закрывает implement+index, но **до** него 4–6 ручных шагов, включая полный Write `activeContext`.
  - `loop-handoff/v1` frontmatter и `validate_active_context_shape` есть (T-HUB-022), но **рендер** всё ещё на усмотрение модели.
  - Phase-specific FINISH описан prose-блоками в `context_loop.py` (`_implement_finish_block`, `_qa_finish_block`, …) — исполняется LLM, не runtime.
  - CLI-атомы разрознены: `validate-step`, `finalize-step`, `mark-index-status`, `arm`, `seed-implement`, `flush-checkpoint` — нет единого «finish IMPLEMENT» API.
  - Incident repair (`active_context_shape_invalid`) чинит форму постфактум, не предотвращает.
- **refs:** чат 2026-09-01 (идея MCP-style typed finish tools); `loop/schemas/handoff.py`; `.claude/hooks/epic/core.py` (`finalize_step`, `arm_active_context_from_decompose`); `loop/context_loop.py` FINISH blocks; `memory-bank/back/reflection/reflection-T-HUB-022-runtime-pydantic-schemas.md` §lessons.

**CREATIVE need:** нет.

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Finish tool request | Pydantic model → JSON CLI stdin/args | LLM Write `activeContext` body на FINISH |
| Finish tool response | JSON `{ok, diagnostic_codes[], …}` | prose «готово» без machine `ok: true` |
| Handoff meta | `loop-handoff/v1` via `render_with_frontmatter` | free-text `## Handoff` без frontmatter при `PROJECT_LOOP_HANDOFF_STRICT=1` |
| Status transitions | tool = единственный writer `completed` | ручной `status: completed` в implement/index |
| MCP (optional) | thin wrapper над те же pydantic models | второй code path с иной семантикой |

DECOMPOSE → purge-step: прямые инструкции «перепиши activeContext» в workflow rules заменить на «вызови `mb-finish …`».

---

## Продуктовая спека (WHAT)

### Product probe (Phase 0 skipped — taxonomy clear)

| # | Question | Answer / Probe | Decision / Impact |
|---|----------|----------------|-------------------|
| 1 | **Reframe:** Какую проблему решаем? | Harness ломается не на коде, а на **prose FINISH** — 40%+ инцидентов shape/handoff drift | Фокус = mutation API, не новый UI |
| 2 | **Narrowest wedge:** Минимальный slice? | `finish_implement_step` один tool закрывает 70% pain (IMPLEMENT hot path) | Phase 1 ship до остальных фаз |
| 3 | **Pre-mortem:** Провал через месяц? | Слишком общий mega-tool или MCP-only без CLI | Один модуль + CLI first, MCP thin |
| 4 | **Distribution:** Кто вызывает? | Parent agent / loop runner через `epic_resolve.py` subcommand | Не отдельный daemon |
| 5 | **Technical leverage:** Что выкинуть? | Дублирующие prose FINISH blocks в prompts — заменить на «call tool X» | Rules shrink, не grow |
| 6 | **Appetite:** Стоит ли? | Да — прямое снижение NEED_HUMAN / doctor repairs | L3–L4, ~8–10 sNN |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как parent IMPLEMENT, я хочу один CLI вызов после verify PASS, чтобы закрыть sNN без ручного activeContext. | P0 | `mb-finish implement --step sNN` → JSON `ok:true`, index+implement completed, shape valid |
| US-002 | Как operator, я хочу fail-closed если verify sidecar отсутствует, чтобы не было ложного completed. | P0 | вызов без PASS sidecar → exit ≠0, implement остаётся `in_progress` |
| US-003 | Как platform, я хочу typed render activeContext (frontmatter+body), чтобы shape errors = 0 на FINISH. | P0 | `validate_active_context_shape` пустой после tool |
| US-004 | Как parent QA, я хочу `finish_qa` записать qa yaml + Handoff REFLECT одним вызовом. | P1 | qa artifact on disk + activeContext mode=REFLECT |
| US-005 | Как parent DECOMPOSE/PLAN/ANALYZE/AUDIT, я хочу phase finish tools с тем же JSON контрактом. | P1 | matrix pytest phase×tool |
| US-006 | Как Cursor user, я хочу опциональный MCP server с теми же tools (schema descriptors). | P2 | MCP `finish_implement_step` = CLI parity test |
| US-007 | Как doctor/incident, я хочу reuse render API для tier0 repair activeContext. | P1 | repair uses `render_active_context` not ad-hoc string |
| US-008 | Как auditor, я хочу stop-gate блокировать FINISH без `last_finish_tool` fingerprint в epic state. | P1 | stop-gate без tool call → block |

#### Acceptance Scenarios — US-001

- **Given:** implement shard s05 in_progress, all cp done, verify sidecar PASS, decompose index pending s05
- **When:** `python3 .claude/hooks/epic_resolve.py mb-finish implement --cwd $PROJECT_ROOT --step s05 --done-summary "wire stop-gate"`
- **Then:** JSON `ok:true`, implement+index s05 completed, activeContext rewritten with next s06 in load_now, single Handoff, `tasks/log` row appended

#### Acceptance Scenarios — US-002

- **Given:** verify sidecar missing or FAIL
- **When:** same command
- **Then:** JSON `ok:false`, diagnostic `verify_pass_required`, no status change

### Functional Requirements (FR-###)

- **FR-001:** Модуль `loop/mb_finish/` — pydantic request/response models (`mb-finish-request/v1`, `mb-finish-result/v1`).
- **FR-002:** `render_active_context(meta: LoopHandoffFrontmatter, load_now: list[LoadNowItem], done: list[str], handoff_body: HandoffBody)` — единственный writer тела activeContext на FINISH.
- **FR-003:** CLI `epic_resolve.py mb-finish <subcmd>` с subcommands: `implement`, `creative`, `decompose`, `plan`, `analyze`, `audit`, `qa`, `bugfix`, `reflect`, `handoff` (low-level escape hatch).
- **FR-004:** `finish_implement` = validate-step + verify PASS check + render activeContext + `finalize_step` (atomic); rollback activeContext on finalize failure.
- **FR-005:** `finish_qa` = validate qa yaml schema + render activeContext + `sync_tasks_index` on phase change + append tasks/log when applicable.
- **FR-006:** `finish_decompose` / `finish_plan` / `finish_analyze` / `finish_audit` — phase-specific validators + arm via Transition Engine (`arm_phase` / `promote_if_ready`), не дублировать legacy arm paths.
- **FR-007:** Epic state поле `last_finish_tool: {name, at, fingerprint}` — stop-gate читает на FINISH (IMPLEMENT minimum).
- **FR-008:** Workflow rules + `context_loop.py` FINISH blocks: заменить prose steps на «вызови mb-finish …»; cheatsheets обновить.
- **FR-009:** Doctor tier0 `active_context_shape_invalid` repair → delegate to `render_active_context` when epic projection known.
- **FR-010:** (P2) MCP server `dev-hub-mb-finish` — register same functions; zero duplicate business logic.
- **FR-011:** Все tools: `extra=forbid` pydantic, JSON stdout, stderr human-readable, exit 0 только при `ok:true`.
- **FR-012:** Hub self-test: product `PROJECT_ROOT` vs hub `dev-hub` cwd guard (как IMPLEMENT FINISH block).

### Success Criteria

| ID | Измеримый результат | Проверка | Type |
|----|---------------------|----------|------|
| SC-001 | IMPLEMENT FINISH без ручного Write activeContext в rules | rg "Write.*activeContext" workflow-implement → only mb-finish | outcome |
| SC-002 | 0 shape errors в test matrix 20 FINISH scenarios | pytest `test_mb_finish_*` | outcome |
| SC-003 | stop-gate blocks IMPLEMENT stop без finish tool fingerprint | pytest stop-gate | outcome |
| SC-004 | Doctor repair uses shared render | pytest incident doctor | outcome |

### Assumptions

- Content shards (implement evidence, plan prose, creative text) агент пишет сам; tools только **закрывают** machine state.
- MCP — optional P2; CLI достаточен для loop + Cursor shell.
- `PROJECT_LOOP_HANDOFF_STRICT` default остаётся `0` в hub; tool всегда пишет frontmatter (ready for strict).

### Clarifications

- Session: n/a (идея из чата 2026-09-01, taxonomy clear).
- T-HUB-033 atomic commit hook остаётся внутри `finalize_step` — mb-finish не дублирует.

---

## AC

1. `loop/mb_finish/` с pydantic models + `render_active_context` + phase finish functions.
2. CLI `mb-finish` subcommands (minimum: `implement`, `handoff`, `qa`; full matrix per FR-006).
3. `finish_implement` интегрирован в IMPLEMENT FINISH rules + stop-gate fingerprint.
4. Doctor repair reuse render API.
5. pytest matrix: shape validation, verify gate, rollback, phase transitions.
6. (P2) MCP thin wrapper + descriptor parity test.
7. Sunset: workflow rules не инструктируют LLM писать `status: completed` / полный activeContext на FINISH.

### AC− (brownfield replace)

1. Нет второго writer `implement/index completed` кроме `finalize_step` (mb-finish вызывает его, не дублирует).
2. Нет prose-only Handoff path при strict=1 без frontmatter.
3. Misconfig (bad cwd, missing decompose) → JSON error, не partial write.
4. Нет dual path «mb-finish OR ручной Write» в rules после эпика — только tool (+ documented repair CLI).
5. Нет regex extract Handoff mode из prose как machine input — `loop-handoff/v1` или structured `HandoffBody` fields.

---

## Техника / HOW

### Модули

| Path | Role |
|------|------|
| `loop/mb_finish/schemas.py` | Request/response pydantic (`FinishImplementRequest`, `FinishQaRequest`, `MbFinishResult`, `LoadNowItem`, `HandoffBody`) |
| `loop/mb_finish/render.py` | `render_active_context`, templates per phase, `validate_before_write` |
| `loop/mb_finish/implement.py` | `finish_implement_step` orchestration |
| `loop/mb_finish/phases.py` | `finish_qa`, `finish_decompose`, `finish_plan`, `finish_analyze`, `finish_audit`, `finish_bugfix`, `finish_reflect`, `finish_creative` |
| `loop/mb_finish/state.py` | `record_finish_tool`, fingerprint |
| `.claude/hooks/epic_resolve.py` | `mb-finish` subparser → dispatch |
| `.claude/hooks/stop-gate.py` | require `last_finish_tool` for IMPLEMENT FINISH |
| `loop/incidents/doctor.py` | tier0 repair delegate |
| `loop/mcp/mb_finish_server.py` | (P2) MCP tool registration |
| `.cursor/rules/**/workflow-*.mdc` | FINISH steps → mb-finish calls |
| `loop/context_loop.py` | FINISH blocks shortened |

### Data flow (ASCII)

```text
[Parent LLM]
    |  (evidence in implement yaml — manual)
    v
[mb-finish CLI] --stdin JSON or flags
    | pydantic validate request
    v
[phase handler] --> read verify sidecar / validate-step / schema checks
    | pass
    v
[render_active_context] --> loop-handoff/v1 frontmatter + load_now + handoff body + done
    | atomic_write_text(activeContext)
    v
[finalize_step | arm_phase | sync_tasks] --> index/implement/events/log/portfolio
    | ok
    v
[record_finish_tool] --> epic state.json
    |
    v
JSON stdout {ok:true, next_step, diagnostic_codes:[]}
    |
    v
[stop-gate] reads last_finish_tool + shape validate --> allow stop
```

### Failure matrix

| Component / link | Failure | Detection | User/system response | Test ID |
|------------------|---------|-----------|----------------------|---------|
| mb-finish request | invalid pydantic | ValidationError | JSON `ok:false`, exit 2 | TM-001 |
| verify sidecar | missing/FAIL | `_verify_pass_ready_for_step` | no mutation, exit 1 | TM-002 |
| activeContext render | shape invalid pre-write | `validate_active_context_shape` | abort before write | TM-003 |
| finalize_step | index write fail | marked `ok:false` rollback | implement rolled back, activeContext restored from backup | TM-004 |
| wrong cwd (hub vs product) | path guard | `PROJECT_ROOT` check | fail-closed JSON error | TM-005 |
| stop-gate | no finish fingerprint | epic state | block FINISH, prompt mb-finish | TM-006 |
| arm_phase delegate | transition engine error | `promote_if_ready` dict | propagate diagnostic_codes | TM-007 |
| MCP wrapper (P2) | schema drift vs CLI | parity test | CI fail | TM-008 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | 5 | — |
| Failure coverage | 4 | rollback path needs explicit backup spec in s03 |
| Testability | 5 | matrix per phase |

---

## Replacement / sunset (brownfield)

### A. Code / modules

| Устаревает | Замена | Policy |
|------------|--------|--------|
| `_try_advance_active_context` ad-hoc strings в epic/core (partial) | `mb_finish.render` | delete in-epic where duplicated |
| Prose-only FINISH blocks (full duplicate logic) | mb-finish call instructions | delete prose steps, keep 1-line CLI |
| LLM regex Handoff mode extract as primary | `loop-handoff/v1` | delete in-epic as primary path |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
|------------|--------|--------|
| Ручной `Write activeContext` на FINISH | `epic_resolve.py mb-finish` | delete in-epic (rules) |
| n/a | — | greenfield for new phases |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
|------------|--------|--------|
| «напиши Handoff своими словами» | typed `done_summary` + template | delete in-epic |
| silent skip verify before completed | fail-closed tool | delete in-epic |
| doctor ad-hoc activeContext patch strings | `render_active_context` | delete in-epic |

---

<a id="qa-consumes"></a>
## QA consumes (test plan)

### Scope under test

- Epic: T-HUB-040 — `loop/mb_finish/*`, CLI, stop-gate wire, doctor delegate.
- Out of scope: MCP server live Cursor integration (P2 smoke only).

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|----|----------|----------|-------------------|----------|------------|
| TM-001 | P0 | finish_implement happy path | pytest tmp_path epic s01 | ok:true, completed, shape valid | FR-004, AC-1 |
| TM-002 | P0 | verify missing → no mutation | pytest | ok:false, in_progress | FR-002, US-002 |
| TM-003 | P0 | shape validator rejects bad load_now | pytest | abort pre-write | FR-003 |
| TM-004 | P0 | finalize rollback restores activeContext | pytest mock index fail | no half state | Failure matrix |
| TM-005 | P0 | stop-gate without fingerprint | pytest stop-gate | block | FR-007 |
| TM-006 | P1 | finish_qa → REFLECT handoff | pytest | qa file + handoff mode | FR-005 |
| TM-007 | P1 | finish_decompose arms ANALYZE gate | pytest transition | armed_step ANALYZE | FR-006 |
| TM-008 | P1 | doctor repair uses render | pytest doctor | shared code path | FR-009 |
| TM-009 | P2 | MCP descriptor parity CLI | pytest | same JSON | FR-010 |

### Regression notes

- Order: verify PASS must precede mb-finish implement (mirror current FINISH order).
- Concurrent finalize: existing epic state lock behavior preserved.

---

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3: one of done | skip+reason | §Product probe table (6 rows) |
| Eng review spine | L2+ | done | §Техника / HOW + failure matrix |
| §0.11 counterparts (draft) | if external refs | done | epic_resolve, stop-gate, handoff.py, finalize_step — all in-repo |
| CREATIVE | if flagged | n/a | — |
| qa_consumes draft | L2+ | done | §QA consumes ≥9 TM |
| Plan review batch | L2+ | done | §Plan review batch log |

---

## Plan review batch log

| Phase | Auto-resolved | Deferred (owner/next) | Taste / CRITICAL surfaced |
|-------|---------------|-------------------------|---------------------------|
| Product | Wedge = implement tool first; MCP P2 | — | — |
| Eng | Single module `loop/mb_finish`; CLI before MCP; reuse finalize_step not fork | MCP UX in product repos — post hub pilot | — |

---

## Где ещё применимо (beyond FINISH)

| Surface | Сейчас | С tool API |
|---------|--------|------------|
| **Board arm / `arm_epic`** | `arm_active_context_from_decompose` legacy strings | `mb-finish handoff` + Transition Engine delegate |
| **Doctor tier0** | ad-hoc reformat activeContext | `render_active_context` from projection |
| **Incident fingerprint stall** | manual Handoff touch | idempotent `handoff` refresh tool |
| **Janitor GC (T-HUB-034)** | read-only scan; apply could need safe metadata patch | `mb-finish patch_index` (future, out of scope v1) |
| **Episode packages (T-HUB-031)** | snapshot reads files | record `last_finish_tool` in bundle manifest |
| **analyze-convergence (T-HUB-032)** | reports drift | detect «FINISH without mb-finish» as finding class |
| **RECONCILE (T-HUB-026)** | read-only | no write; but can recommend mb-finish for remediation |
| **REFLECT / ARCHIVE** | partial scripts | `finish_reflect` + existing `mb-archive-epic.py` chain in s09 |
| **CREATIVE gate close** | manual index + shard fields | `finish_creative` |
| **Checkpoint flush** | already CLI | stays separate mid-step; mb-finish only at boundary |

---

## До DECOMPOSE (черновик нарезки)

| sNN | Slice |
|-----|-------|
| s01 | `loop/mb_finish/schemas.py` + `render.py` + shape tests |
| s02 | `finish_implement_step` + CLI `mb-finish implement` + rollback |
| s03 | stop-gate `last_finish_tool` + epic state wire |
| s04 | `finish_handoff` low-level + doctor delegate |
| s05 | `finish_qa` + `finish_bugfix` |
| s06 | `finish_decompose` + `finish_plan` + transition engine delegate |
| s07 | `finish_analyze` + `finish_audit` |
| s08 | `finish_creative` + `finish_reflect` |
| s09 | workflow rules + context_loop FINISH blocks + cheatsheets purge prose |
| s10 | (P2) MCP server thin wrapper + parity tests |
| s11 | legacy purge: prose FINISH instructions, dual handoff write paths |

**Advisory floor:** 11 steps · **timebox_days:** 5 · **cut_list:** `['MCP server', 'finish_reflect polish', 'janitor patch_index']`

---

## Appetite

| Поле | Значение |
|------|----------|
| `timebox_days` | 5 |
| `cut_list` | MCP P2, janitor patch_index, extra phases if 029 unstable |

---

## Следующий режим

→ **BACK DECOMPOSE** T-HUB-040 (после T-HUB-033 + T-HUB-039 в canon queue)
