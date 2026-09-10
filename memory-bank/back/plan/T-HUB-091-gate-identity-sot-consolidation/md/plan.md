# [T-HUB-091 | gate-identity-sot-consolidation] PLAN

**Дата:** 2026-09-10  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Clarify:** Phase 0 skipped — taxonomy clear (чат: Claude+Codex only, без DSH; один SoT; атомарные write; убрать поштучный coerce)  
**Prompt:** [md/prompt.md](prompt.md) — outcome SoT  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `gate-identity-sot-20260910`  
**Deps:** soft **T-HUB-066** (ownership compare / semantic_ownership_mismatch уже есть); soft **T-HUB-071** (SessionStart COMMAND/PromptScope — другой слой, не смешивать); soft **T-HUB-080** (freeze `session_start_identity` / ownership overlay уже частично в коде).  
**Skills:** writing-plans · architecture-patterns · python-testing-patterns  
**Источник:** чат NEED_HUMAN `step_id mismatch (got s05, expected BUGFIX)`; inventory writers epic state / spawn-gate / coerce; `loop/session_finalize.py`; `harness/hooks/subagent-{start,stop}.py`; `loop/runtime_adapters/subagent_lifecycle.py`

---

## Контекст

- **req:** Один SoT gate identity для Claude + Codex. Доставка identity в child до работы (Claude: SubagentStart; Codex: rewrite spawn prompt). Stop сравнивает/биндит fence к SoT без поштучного coerce. Сократить число writers, конфликтующих по `armed_step` / freeze / projection / spawn-gate / LLM fence. Атомарные операции там, где сейчас race (freeze+mirror, spawn mark+identity).
- **gap:**
  1. Claude имеет pre-child `GATE_IDENTITY`; Codex lifecycle вызывает `subagent-start` **после** wait → inject бесполезен.
  2. Codex stop: coerce `session_id`, затем `step_id`/`epic_id` кусками — симптоматический dual-policy.
  3. Writers: `session_start_identity`, `armed_step`, `projection.step`, spawn-gate `gate_identity`, LLM fence — разные правды.
  4. `sync_gate_identity` отложен до stop/prompt; spawn mark без atomic identity bind.
- **refs:** `loop/session_finalize.py` (`SessionStartIdentity`, `ownership_expected_*`, `apply_ownership_identity`); `harness/hooks/_lib.py` `current_gate_identity` / `set_gate_identity`; `subagent-start.py:173–190`; `subagent-stop.py` Codex coerce; `subagent_lifecycle.py:355–422`; `epic_codex_stream_filter.py`; tests `test_codex_session_ownership_coerce.py`.
- **Не:** DSH adapter / DSH parity (явный out of scope); полный SessionContextService / Event projector (071 cut); mega-hook dispatcher (085); Python supervisor cutover (086); PromptScope COMMAND drift как primary (071).

**CREATIVE need:** нет.

---

## Delivery closure

| Capability / outcome | Classification | Production entrypoint and caller | Success / failure enforcement | Independent outcome test | Foundation approval / follow-up |
|---|---|---|---|---|---|
| GateIdentity SoT (freeze/read/bind/assert) | `vertical_slice` | `prepare_session` + `SubagentStart`/`SubagentStop` + Codex spawn observe → SoT API | freeze missing → fail-closed ownership; Claude mismatch → `semantic_ownership_mismatch`; Codex fence IDs overwritten from SoT (не LLM) | Given frozen BUGFIX; When Codex fence `step_id=s05`; Then recorded/compared identity = BUGFIX without NEED_HUMAN ownership; Claude same fence → NEED_HUMAN | n/a |
| Claude inject from SoT | `vertical_slice` | `harness/hooks/subagent-start.py` → `inject_text(SoT)` | child получает exact IDs; mismatch на stop → NEED_HUMAN | SubagentStart additionalContext содержит `GATE_IDENTITY` = SoT | n/a |
| Codex spawn-time delivery | `vertical_slice` | `epic_codex_stream_filter` / lifecycle на `spawn_agent` → prepend `GATE_IDENTITY` + bind spawn-gate | spawn без bind → fail-closed / не silent coerce-only path | spawn_agent prompt содержит SoT block до child; pending thread tied to frozen identity | n/a |
| Stop ownership policy (strict vs bind) | `vertical_slice` | `subagent-stop.py` через SoT `assert_fence`/`bind_fence` | Claude strict; Codex bind-from-SoT; agent_id mismatch всё ещё NEED_HUMAN | pytest matrix Claude strict / Codex bind; no per-field if-ladder as product | n/a |

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| GateIdentity SoT | typed blob / pydantic model из epic `session_start_identity` (+ armed только если freeze отсутствует) | LLM fence IDs как SoT; live `projection.step` как ownership step без freeze |
| Delivery | Claude `additionalContext`; Codex rewritten `spawn_agent.prompt` | post-wait SubagentStart как «inject для Codex» |
| Stop policy | `policy=strict` (Claude) \| `policy=transport_bind` (Codex) в SoT API | поштучный `if runtime==codex: coerce session` / отдельно step / отдельно epic в хуке |
| Spawn-gate mirror | derived cache из SoT, sync атомарно с freeze/spawn | независимый writer «правды» в spawn-gate |
| Atomic ops | prepare: freeze+mirror; spawn: mark_in_flight+bind identity | mark_in_flight без identity; mid-session `armed_step` меняет ownership без нового freeze |

---

## Продуктовая спека (WHAT)

1. Для любой in-flight gate-сессии Claude/Codex существует ровно один ownership identity blob: `session_id`, `epic_id`, `step_id`, `role` (и hashes при наличии) — **GateIdentity SoT**.
2. SoT замораживается на `prepare_session` и не следует mid-session `armed_step`/`projection` после mb-finish внутри той же parent-сессии.
3. Claude child **до** работы видит тот же SoT в inject-блоке; чужой fence step/epic/session → `semantic_ownership_mismatch` (без schema-retry).
4. Codex child получает SoT через rewrite spawn prompt (до выполнения child); на stop fence identity **:= SoT** (транспортный bind), ownership дальше про verdict/agent, не про угадайку LLM.
5. Поштучный coerce в stop как продуктовая «фича» удалён; один API `bind_fence` / `assert_fence`.
6. Число конфликтующих writers сокращено: ownership readers не читают сырой `projection.step` в обход SoT; spawn-gate не претендует на независимую правду.
7. Где возможно — атомарно: freeze+spawn-gate mirror; Claude PreToolUse mark_in_flight+sync SoT; Codex spawn observe bind SoT+pending thread.

### Product probe

| # | Question | Answer / Probe | Decision / Impact on PLAN |
|---|----------|----------------|---------------------------|
| 1 | **Reframe:** Какую реальную проблему решаем? | Конфликтующие источники identity → NEED_HUMAN / ложный halt / пластырный coerce | Один SoT + delivery adapters, не ещё один coerce |
| 2 | **Narrowest wedge:** | SoT API + Claude strict + Codex spawn prepend + stop bind; один regression pytest файл | P0 vertical slice |
| 3 | **Pre-mortem:** | Оставить coerce «на всякий» рядом с bind → dual path | AC−: coerce ladder delete in-epic |
| 4 | **Distribution:** | Loop/hooks автоматически; агент не выбирает | Kind I: prompts говорят «IDs from GATE_IDENTITY / SoT» |
| 5 | **Technical leverage:** | Уже есть `SessionStartIdentity` + `apply_ownership_identity` | Расширить в сервис, не второй freeze |
| 6 | **Appetite:** | ~3–4 дня; cut DSH, PromptScope, mega SessionContextService | Out of scope явный |

Min: 6/6 заполнены (L3).

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как loop, я читаю ownership только из GateIdentity SoT. | P0 | unit: expected(state) == freeze; live armed≠freeze не меняет expected |
| US-002 | Как Claude verify child, я вижу GATE_IDENTITY = SoT до работы. | P0 | SubagentStart additionalContext содержит exact SoT fields |
| US-003 | Как Claude stop, чужой step_id → NEED_HUMAN ownership. | P0 | fence s05 vs SoT BUGFIX → semantic_ownership_mismatch, no schema retry |
| US-004 | Как Codex parent, spawn_agent prompt получает GATE_IDENTITY до child. | P0 | stream/lifecycle test: prompt rewritten / contains SoT block on spawn observe |
| US-005 | Как Codex stop, fence с s05/foreign epic не даёт ownership NEED_HUMAN; identity := SoT. | P0 | pytest: returncode 0 path; recorded/compared IDs = SoT |
| US-006 | Как инженер, я не вижу поштучный coerce в stop. | P0 | rg: no per-field coerce ladder; SoT API only |
| US-007 | Как runner, freeze+mirror spawn-gate атомарны на prepare. | P1 | после prepare spawn-gate gate_identity == SoT без отдельного stop sync |

#### Acceptance Scenarios — US-001

- **Given:** `session_start_identity.step_id=BUGFIX`, mid-session `armed_step=QA`
- **When:** `GateIdentity.expected(state)` / ownership compare
- **Then:** step = `BUGFIX`, не `QA`

#### Acceptance Scenarios — US-003

- **Given:** Claude runtime, SoT step=BUGFIX, fence step=s05, same session/epic/agent
- **When:** SubagentStop
- **Then:** exit 2, `semantic_ownership_mismatch`, schema_retry_count unchanged

#### Acceptance Scenarios — US-004 / US-005

- **Given:** Codex spawn_agent for verify-bugfix, SoT BUGFIX
- **When:** spawn observe + later wait with fence step_id=s05
- **Then:** spawn prompt содержал GATE_IDENTITY BUGFIX; stop не NEED_HUMAN по step; compared identity = BUGFIX

### Functional Requirements (FR-###)

- **FR-001:** Ввести единый API GateIdentity SoT (расширение/`loop` module на базе `session_finalize`): `freeze`, `expected`, `inject_text`, `bind_spawn_gate`, `assert_fence(policy=strict|transport_bind)`.
- **FR-002:** `prepare_session` атомарно: bind `session_id` + freeze `session_start_identity` + `bind_spawn_gate` (mirror).
- **FR-003:** Все ownership readers (start/stop/posttool/stop-gate/lifecycle dedupe) используют только SoT `expected` / `current_gate_identity` через SoT — запрет сырого `gate_identity` без overlay на ownership path.
- **FR-004:** Claude SubagentStart: `inject_text(SoT)` в additionalContext (сохранить контракт + HARD_RULE).
- **FR-005:** Claude PreToolUse: `mark_in_flight` + `bind_spawn_gate(SoT)` атомарно (или один helper).
- **FR-006:** Codex на `spawn_agent` observe: prepend/rewrite prompt с `inject_text(SoT)`; записать pending thread + SoT bind **до** wait.
- **FR-007:** Codex SubagentStop: `transport_bind` — fence session/epic/step := SoT целиком через API (не if-ladder полей); agent_id mismatch остаётся ownership fail.
- **FR-008:** Claude SubagentStop: `strict` — любое расхождение session/epic/step → `semantic_ownership_mismatch`.
- **FR-009:** Удалить продуктовый поштучный coerce block в `subagent-stop.py`; переписать тесты coerce на SoT policies.
- **FR-010:** Post-wait вызов SubagentStart для Codex не считается delivery inject (либо skip inject side-effect, либо document-only mark_in_flight) — запрет ложной симметрии.
- **FR-011:** Kind I: agent/verify prompts — IDs из GATE_IDENTITY / литералы фазы (`BUGFIX`/`QA`) согласованы с SoT; не учить «угадай sNN с эпика».
- **FR-012:** DSH не расширять; существующие thin passthrough не ломать без явного touch (no new DSH requirements).
- **FR-013:** `session_start_payload` / PromptScope не становятся вторым GateIdentity SoT в этом эпике (071 soft); не учить fence ownership через projection overwrite.
- **FR-014:** Wire-complete: dual path coerce+bind запрещён после эпика.

### Success Criteria (SC-###)

| ID | Измеримый результат | Проверка / источник | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | Ownership step при freeze≠armed всегда freeze | pytest SoT | outcome |
| SC-002 | Claude stale step → ownership NEED_HUMAN | pytest stop | outcome |
| SC-003 | Codex wrong fence IDs → no ownership NEED_HUMAN; IDs=SoT | pytest stop/lifecycle | outcome |
| SC-004 | Codex spawn prompt contains GATE_IDENTITY before child | unit/filter/lifecycle | outcome |
| SC-005 | Нет per-field coerce ladder в stop | rg + test | outcome |
| SC-006 | prepare leaves spawn-gate mirror == SoT | pytest | outcome |

### Assumptions

- Claude SubagentStart по-прежнему способен доставить `additionalContext` в child.
- Codex stream filter / lifecycle видит `spawn_agent` item с мутабельным `prompt` до исполнения child (или эквивалентный rewrite point в pipeline); если rewrite невозможен на transport — fail-closed design в HOW с bind-on-stop как **единственный** Codex delivery+ownership path, но тогда spawn-time prepend всё равно required на уровне lifecycle contract / parent packing где возможно.
- DSH остаётся out of scope; не блокирует Claude/Codex.
- T-HUB-066 semantics ownership mismatch сохраняются для Claude.

### Clarifications

- Session: 2026-09-10, Phase 0 skipped — taxonomy clear.
- Решения чата: без DSH; сократить источники правды; атомарность; SoT + adapters; убрать кусковой coerce.

### [НУЖНО УТОЧНИТЬ]

- нет CRITICAL (defer non-blocking): точный hook point rewrite Codex prompt (stream filter vs tool interceptor) — выбрать в IMPLEMENT spike ≤1h внутри sNN Codex delivery; fail-closed если point отсутствует.

---

## AC

1. GateIdentity SoT API — единственный ownership reader для Claude/Codex gate fences.
2. Claude: inject pre-child + strict ownership.
3. Codex: spawn-time SoT delivery + transport_bind на stop.
4. Per-field coerce удалён; тесты переписаны.
5. prepare атомарно freeze+mirror; Claude spawn mark+bind.
6. Kind I prompts согласованы.
7. DSH не в scope и не «случайно» расширен требованиями.

### AC−

1. Нет dual path coerce+SoT bind.
2. Нет ownership от сырого `projection.step` в обход freeze.
3. Нет schema-retry на ownership.
4. Нет «Codex post-wait SubagentStart = inject».
5. Нет нового DSH adapter scope.
6. Нет второго SoT в PromptScope/`resolve_session_identity` как fence ownership.

---

## Техника / архитектура (HOW)

- **Стек:** Python hub; pydantic/dataclasses для GateIdentity blob; существующие hooks Claude/Codex; pytest через `bin/pytest`.
- **Модуль SoT:** расширить `loop/session_finalize.py` **или** тонкий `loop/gate_identity.py` re-exporting freeze/expected + новые bind/assert/inject — один import surface. Adapters Claude/Codex thin.
- **Claude:** `subagent-start` / `agent-pretool` / `subagent-stop` → SoT.
- **Codex:** `SubagentLifecycle.process_item(spawn_agent)` + `epic_codex_stream_filter` rewrite prompt; stop `transport_bind`.
- **Stores:** epic `state.json` держит freeze (SoT); spawn-gate — mirror only.
- **Наблюдаемость:** stderr ownership diagnostics без schema-retry; optional log `gate_identity_bound` на spawn.
- **Ограничения:** не трогать DSH policy files; не merge с 085 dispatcher; не переписывать PromptScope (071).

### Target layout (advisory)

```text
loop/gate_identity.py          # SoT API (или session_finalize expansion)
harness/hooks/subagent-start.py  # inject_text(SoT)
harness/hooks/subagent-stop.py   # assert_fence / bind_fence — no coerce ladder
harness/hooks/agent-pretool.py   # atomic mark+bind
loop/runtime_adapters/subagent_lifecycle.py  # Codex spawn bind+prompt
harness/hooks/epic_codex_stream_filter.py    # ensure rewrite path
```

### Anti-dilution Notes

- «Модуль GateIdentity существует» ≠ done без wire в start/stop/spawn.
- «Coerce оставлен как fallback» ≠ done.
- Foundation-only SoT без Codex spawn delivery ≠ vertical_slice этого эпика.

---

## Eng review spine

### Data flow (ASCII)

```text
prepare_session
  -> GateIdentity.freeze(state) + bind_spawn_gate     [atomic]
  -> epic state.json (SoT) + spawn-gate mirror

Claude spawn:
  PreToolUse mark_in_flight + bind_spawn_gate(SoT)    [atomic]
  -> SubagentStart inject_text(SoT) -> child
  -> SubagentStop assert_fence(strict) -> PASS/FAIL|NEED_HUMAN

Codex spawn:
  spawn_agent observe -> rewrite prompt(inject_text) + bind + pending  [atomic-ish]
  -> child runs with SoT in prompt
  -> wait -> SubagentStop bind_fence(transport) + assert agent
  -> (optional) late start hook = mark only, NOT inject-as-delivery
```

### Failure matrix

| Component / link | Failure | Detection | User/system response | Test ID |
|------------------|---------|-----------|----------------------|---------|
| freeze missing | ownership expected empty / wrong | prepare/test | fail-closed prepare or ownership HALT | TM-001 |
| Claude fence wrong step | mismatch | SubagentStop | NEED_HUMAN semantic_ownership_mismatch | TM-002 |
| Codex fence wrong step | would-be mismatch | bind_fence | IDs:=SoT; continue verdict path | TM-003 |
| Codex spawn without rewrite | child без GATE_IDENTITY | lifecycle/filter assert | fail-closed or forced bind-only path documented + test | TM-004 |
| agent_id mismatch | wrong agent fence | stop | NEED_HUMAN (оба runtime) | TM-005 |
| mid-session armed drift | armed≠freeze | expected() | ownership ignores armed | TM-001 |
| coerce ladder leftover | dual policy | rg/sot_enforce | QA FAIL | TM-006 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | 5 | Claude+Codex paths explicit; DSH cut |
| Failure coverage | 5 | ownership / bind / spawn rewrite / agent |
| Testability | 5 | pytest hooks + lifecycle; no live Codex required for P0 |

---

## Replacement / sunset (brownfield)

### A. Code / modules

| Устаревает (path / symbol) | Замена | Policy |
| :--- | :--- | :--- |
| `harness/hooks/subagent-stop.py` per-field Codex coerce (`session_id`/`step_id`/`epic_id` if-ladder) | `GateIdentity.bind_fence` / `assert_fence(policy=transport_bind)` | delete in-epic |
| Ownership reads via raw `gate_identity(...)` without overlay on stop/start paths | `GateIdentity.expected` / `current_gate_identity`→SoT only | delete in-epic |
| `subagent-start._gate_session_id` duplicate of `_lib.gate_session_id` (если ещё дубль) | один helper через SoT/session | delete in-epic |
| `loop/tests/test_codex_session_ownership_coerce.py` cases locking per-field coerce as product | rewrite: spawn delivery + transport_bind API | delete/rewrite in-epic |
| Codex post-wait SubagentStart treated as child inject delivery | mark-only / non-delivery | delete in-epic (behavior) |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| n/a — те же hooks/CLI | — | greenfield n/a for deploy |

### C. Fallbacks / soft-fail

| Устаревает | Замена (fail-closed) | Policy |
| :--- | :--- | :--- |
| «если rewrite недоступен → оставить coerce ladder forever» | один documented Codex policy path (bind) + test; dual forbid | delete in-epic |
| silent accept LLM fence IDs when SoT present (Claude) | strict mismatch | delete in-epic |
| ownership from live projection after finish without freeze | freeze-only expected | delete in-epic |

### I. Instruction surfaces

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| Agent prompts «подставь любой step_id / sNN с эпика» для verify-bugfix/qa | GATE_IDENTITY / литерал фазы BUGFIX\|QA | delete in-epic (уже частично; добить Kind I) |
| Docs/comments «Codex coerce session only» | transport_bind SoT policy | rewrite in-epic |
| Collaboration text implying post-wait start = inject | spawn-time rewrite | rewrite in-epic |

---

<a id="qa-consumes"></a>
## QA consumes (test plan)

### Scope under test

- Epic surfaces: GateIdentity SoT, Claude start/stop, Codex spawn rewrite + stop bind, atomic prepare/spawn bind, sunset coerce.
- Out of scope for QA: DSH; PromptScope COMMAND (071); full suite flake unrelated; supervisor (086).

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|----|----------|----------|-------------------|----------|------------|
| TM-001 | P0 | freeze≠armed → expected=freeze | `bin/pytest` SoT unit | step=freeze | FR-001/002, US-001, SC-001 |
| TM-002 | P0 | Claude stale step ownership | `bin/pytest` stop hook | NEED_HUMAN ownership | FR-008, US-003, SC-002 |
| TM-003 | P0 | Codex wrong fence IDs bind | `bin/pytest` stop/lifecycle | no ownership NEED_HUMAN; IDs=SoT | FR-007, US-005, SC-003 |
| TM-004 | P0 | Codex spawn prompt has GATE_IDENTITY | lifecycle/filter unit | prompt contains SoT | FR-006, US-004, SC-004 |
| TM-005 | P0 | agent_id mismatch both runtimes | stop hook | NEED_HUMAN | FR-007/008 |
| TM-006 | P0 | no coerce ladder leftover | rg + pytest | absent dual path | FR-009/014, SC-005 |
| TM-007 | P1 | prepare mirror spawn-gate | pytest | mirror==SoT | FR-002, US-007, SC-006 |

### Regression notes

- Не ломать T-HUB-066 stale-step Claude tests.
- Переписать coerce tests, не зелёнить старый контракт.
- Ordering: spawn observe before wait в lifecycle fixtures.

---

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3: one of done | skip+reason | Phase 0 skipped — taxonomy clear; §Product probe 6/6 |
| Eng review spine | L2+ | done | §Eng review spine |
| §0.11 counterparts (draft) | if external refs | done | SoT ↔ start/stop/lifecycle/filter counterparts listed in HOW |
| Delivery closure | P0/P1 | done | §Delivery closure vertical_slice |
| CREATIVE | if flagged | n/a | нет |
| qa_consumes draft | L2+ | done | ≥3 TM (7) |
| Plan review batch | L2+ | done | §Plan review batch log |

**FINISH PLAN allowed:** no pending Required.

## Plan review batch log

| Phase | Auto-resolved | Deferred (owner/next) | Taste / CRITICAL surfaced |
|-------|---------------|-------------------------|---------------------------|
| Product | DSH out; single epic; SoT not PromptScope | Codex exact rewrite hook point → IMPLEMENT spike | none CRITICAL |
| Eng | Expand session_finalize vs new module — prefer one API surface; spawn-gate=mirror | — | avoid second freeze store |

---

## До DECOMPOSE (черновик нарезки)

Advisory band 5–8 sNN (не cap):

1. **s01** — GateIdentity SoT API + freeze/expected + tests (armed drift).
2. **s02** — Atomic prepare freeze+mirror; Claude pretool mark+bind.
3. **s03** — Claude start inject + stop strict wire to SoT (preserve mismatch).
4. **s04** — Codex spawn-time rewrite + pending bind.
5. **s05** — Codex stop transport_bind via API; delete coerce ladder; rewrite coerce tests.
6. **s06** — Kind I prompts/comments + leftover rg enforce.
7. **s07** — legacy-fallback-purge (A/C/I leftovers + obsolete tests).

---

## Appetite

| Поле | Значение | Описание |
| :--- | :--- | :--- |
| `timebox_days` | `3–4` | Claude+Codex SoT vertical slice |
| `cut_list` | `['DSH adapter','PromptScope/SessionContextService','signed envelopes','full event projector']` | Вырезать первым при overrun |

## Следующий режим

→ **BACK DECOMPOSE** `T-HUB-091-gate-identity-sot-consolidation`
