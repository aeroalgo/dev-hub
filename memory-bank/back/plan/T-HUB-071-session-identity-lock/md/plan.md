# [T-HUB-071 | session-identity-lock] PLAN

**Дата:** 2026-09-06  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Clarify:** `memory-bank/back/clarify/clarify-20260906-loop-session-architecture.md`  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `loop-session-architecture-20260906`  
**Deps:** **hard T-HUB-070** (overlay больше не врёт gates; иначе identity lock бессмыслен — три COMMAND всё равно). Soft T-HUB-065 (runtime entrypoint inject — complementary, не identity). Soft T-HUB-057 (JSON session contract).  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns  
**Источник:** architecture §1.3 identity lock P0.3; session audit §5 `94cea2d3` BUGFIX vs QA; `loop/prompt_builder.py` step unknown

→ decompose: [decompose-index.md](decompose-index.md) · [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml)

---

## Контекст

- **req:** Одна сессия = одна identity `(role, phase, epic_id, step_id, session_id)`. SessionStart `COMMAND` **обязан** совпасть с `state.armed_step` / `projection.phase`. Handoff frontmatter `loop-handoff/v1` обязан совпасть с identity. Mismatch → сессия **не** стартует работу (`CONTEXT_IDENTITY_DRIFT` / halt). `step` в PromptScope **никогда** не литерал `unknown`, если armed_step задан.
- **gap:**
  1. Session `94cea2d3`: loop user COMMAND = `BACK BUGFIX`, SessionStart additionalContext COMMAND = `BACK QA`, overlay PROJECTION phase=QA. Три команды в одном ходе.
  2. `prompt_builder.PromptScope.step` берётся из `projection.step | next_step`, иначе **`unknown`**. QA/BUGFIX/AUDIT в пятнашке = unknown.
  3. `session_start_payload` / `build_prompt_scope` не сверяют expected identity с AC frontmatter.
  4. T-HUB-065 чинит duplicate hooks + `EPIC_RUNTIME` entrypoint, **не** COMMAND lock.
- **refs:** `loop/prompt_builder.py`; `harness/hooks/session-start.py`; `harness/hooks/epic/core.py` `session_start_payload`; `loop/schemas/handoff.py`; architecture §1.3; session audit §5.
- **Не:** overlay REFLECT/verify OFF (070); md inline (072); abort 401 (073); finish_qa (074); dual SessionStart process (065).

**CREATIVE need:** нет.

---

## Technology axiom

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Identity | Pydantic `EpicState` + `LoopHandoffFrontmatter` | regex `## Handoff BACK QA` как COMMAND |
| COMMAND | `f"{role} {armed_phase}"` from state | SessionStart COMMAND ≠ loop COMMAND |
| step | `armed_step` / shard id (sNN) or phase name | literal `unknown` when armed |
| mismatch | halt / `CONTEXT_IDENTITY_DRIFT` | warning + continue work |
| PromptScope | built from identity, runtime from EPIC_RUNTIME (065) | default phase from AC heading |

---

## Продуктовая спека (WHAT)

1. `build_prompt_scope` / `session_start_payload`: COMMAND = `{ROLE} {PHASE}` где PHASE = armed_step/projection.phase (normalized).
2. Если loop/env expected phase передана и ≠ state → **не** inject conflicting COMMAND; halt payload `ok=false` diagnostic `CONTEXT_IDENTITY_DRIFT`.
3. AC frontmatter `mode` vs state.phase mismatch → same halt (fail-closed).
4. `PromptScope.step`: if IMPLEMENT → sNN from state/index; if QA/BUGFIX/AUDIT/DECOMPOSE/ANALYZE → phase token (e.g. `QA`, `BUGFIX`), **never** `unknown` when armed.
5. Tests reproduce `94cea2d3`: state BUGFIX + stale projection QA → drift, not dual COMMAND.

### Product probe

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Reframe | Harness врёт фазу агенту | Identity lock halt |
| 2 | Wedge | COMMAND from armed_step; step≠unknown; mismatch fail | P0 |
| 3 | Pre-mortem | Inject both COMMANDs «для совместимости» | FR: one COMMAND only |
| 4 | Adoption | SessionStart additionalContext | |
| 5 | Leverage | PromptScope dataclass already has command/role/phase/step | |
| 6 | Appetite | 3 days | cut: full SessionContextService class tree; Event projector |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как BUGFIX loop session, я вижу COMMAND BACK BUGFIX, не QA. | P0 | unit payload COMMAND contains BUGFIX not QA when armed BUGFIX |
| US-002 | Как агент, я не получаю step=unknown на QA. | P0 | PromptScope.step == `QA` (or artifact id), not `unknown` |
| US-003 | Как runner, mismatch state vs AC mode halt. | P0 | session_start_payload ok false / diagnostic CONTEXT_IDENTITY_DRIFT |
| US-004 | Как IMPLEMENT, step=sNN from armed. | P0 | armed s05 → step s05 |
| US-005 | Как Codex/Claude, runtime entrypoint orthogonal (065). | P1 | this epic does not regress EPIC_RUNTIME if 065 landed; skip if not |

#### Acceptance Scenarios — US-001

- **Given:** epic state `phase=BUGFIX`, `armed_step=BUGFIX`, AC frontmatter mode=BUGFIX
- **When:** `session_start_payload` / `render_prompt_scope`
- **Then:** rendered COMMAND line is `BACK BUGFIX` (role from state); no second COMMAND QA

#### Acceptance Scenarios — US-003

- **Given:** state phase=BUGFIX, AC mode=QA (stale fingerprint)
- **When:** SessionStart adapter
- **Then:** does not emit work COMMAND for QA; diagnostic `CONTEXT_IDENTITY_DRIFT`; agent additionalContext is halt card not dual commands

### Functional Requirements

- **FR-001:** Single function `resolve_session_identity(state, ac_meta) -> Identity | Drift`. Drift codes: `phase_mismatch`, `epic_mismatch`, `step_unknown_while_armed`.
- **FR-002:** `build_prompt_scope` uses Identity; `step` fallback chain: `projection.step` → `state.armed_step` → `state.phase` → **empty + diagnostic**, never the string `unknown` if any of the three is set. If **nothing** armed, step may be `unarmed` (explicit) not `unknown` (ambiguous). Prefer: unarmed IDE → step=`-` documented.
- **FR-003:** Literal `unknown` purged from prompt_builder as default when armed exists. Tests grep `unknown` in PromptScope for armed fixtures = 0.
- **FR-004:** SessionStart: if Drift → additionalContext warning **and** `ok=false` in load result if composed; do not start «work» inject of load_now bodies (072 will path-only; this epic at least doesn't lie COMMAND).
- **FR-005:** `expected_identity` from loop env (`EPIC_PHASE` / runner) if present must match state; else halt.
- **FR-006:** Kind I: comments «step unknown OK for QA» — delete.
- **FR-007:** Do not parse `## Handoff` heading for phase when frontmatter valid (`loop-handoff/v1`). If frontmatter missing — diagnostic, migrational regex with drift counter (existing active_context parsers) **not** as COMMAND source if state armed.
- **FR-008:** Tests: matrix phases PLAN/DECOMPOSE/ANALYZE/IMPLEMENT/AUDIT/QA/BUGFIX each has non-unknown step when armed.
- **FR-009:** `render_prompt_scope` HARD READ still says read entrypoint then chain — **do not** expand to inline workflow (072).
- **FR-010:** Identity fields required in halt diagnostic JSON (typed), not prose-only.
- **FR-011:** Concurrent dual SessionStart (065) — identity function must be pure/idempotent.
- **FR-012:** BUGFIX `bugfix_finish_required` already in finish_handoff — keep; identity lock is **start** side.
- **FR-013:** Phase token table (locked for PromptScope.step when not IMPLEMENT sNN):

  | armed_step / phase | step token | COMMAND |
  |--------------------|------------|---------|
  | PLAN | PLAN | `{ROLE} PLAN` |
  | DECOMPOSE | DECOMPOSE | `{ROLE} DECOMPOSE` |
  | ANALYZE | ANALYZE | `{ROLE} ANALYZE` |
  | CREATIVE | CREATIVE | `{ROLE} CREATIVE` |
  | CLARIFY | CLARIFY | `{ROLE} CLARIFY` |
  | IMPLEMENT + sNN | sNN (e.g. `s03`) | `{ROLE} IMPLEMENT` |
  | AUDIT | AUDIT | `{ROLE} AUDIT` |
  | QA | QA | `{ROLE} QA` |
  | BUGFIX | BUGFIX | `{ROLE} BUGFIX` |
  | DONE | DONE (should not spawn work session) | halt or no COMMAND work |

- **FR-014:** Reproduction fixture `94cea2d3`:
  - env/loop intended COMMAND = `BACK BUGFIX`
  - `state.phase` / `armed_step` = `BUGFIX`
  - stale AC frontmatter `mode: QA` **or** overlay leftover projection QA
  - **Then:** Drift halt, **not** SessionStart `COMMAND: BACK QA` plus user `BACK BUGFIX`.
- **FR-015:** ROLE comes from state/frontmatter `role` (BACK/FRONT/INTEG), not guessed from prompt regex when armed.
- **FR-016:** `session_id` if present in state/last-session must be echoed in halt diagnostic; mismatch session_id is **not** this epic (068/journal) unless cheap.
- **FR-017:** Wire-complete: **Add** `resolve_session_identity` → **Wire** `session_start_payload` + `build_prompt_scope` → **Enforce** pytest 94cea2d3 + matrix → **Purge** default `"unknown"` and heading-as-COMMAND.
- **FR-018:** Out vs T-HUB-065: 065 deletes duplicate realpath SessionStart + injects `EPIC_RUNTIME` entrypoint. This epic **must not** reopen duplicate-hook WHAT. If 065 not landed, identity tests mock a **single** payload function.
- **FR-019:** `PromptScope.command` field (or rendered line) is the only COMMAND in additionalContext. Grep fixture output: count of lines matching `COMMAND:` or `^BACK (QA|BUGFIX|IMPLEMENT)` ≤ 1.
- **FR-020:** If projection.phase and state.armed_step disagree (both set, different) → Drift `phase_mismatch` even if AC frontmatter matches one of them. State vs projection: **armed_step wins for COMMAND** only if they match; if they disagree → halt (do not pick a winner silently).

#### Acceptance Scenarios — US-002

- **Given:** armed_step=`QA`, projection.step missing
- **When:** `build_prompt_scope`
- **Then:** `scope.step == "QA"`; `scope.step != "unknown"`

#### Acceptance Scenarios — US-004

- **Given:** armed IMPLEMENT, `armed_step` or index cursor `s03`
- **When:** `build_prompt_scope`
- **Then:** `scope.step == "s03"`; COMMAND `{ROLE} IMPLEMENT`

### Success Criteria

| ID | Result | Check | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | armed BUGFIX COMMAND not QA | pytest | outcome |
| SC-002 | no step unknown when armed | pytest matrix | outcome |
| SC-003 | mismatch halt | pytest diagnostic | outcome |
| SC-004 | IMPLEMENT step sNN | pytest | outcome |
| SC-005 | no heading regex as COMMAND if frontmatter ok | unit | outcome |

### Assumptions

- Runner already knows intended COMMAND (loop prompt). SessionStart must not invent another.
- 070 merged first so overlay won't still print QA FINISH REFLECT during BUGFIX (complementary).

### Clarifications

- Session clarify-20260906; identity ≠ duplicate hooks.

## AC

1. One COMMAND per SessionStart, equals armed phase.
2. step never `unknown` when armed.
3. Drift halt, not warning-continue.
4. Tests for 94cea2d3 reproduction.

### AC−

1. Нет двух COMMAND строк.
2. Нет silent continue on mismatch.
3. Нет `unknown` default masking missing projection.
4. Нет regex heading SoT when frontmatter valid.
5. Нет dual-path «prefer AC heading if richer».

---

## Техника / архитектура (HOW)

- **Паттерн:** Facade SessionStart → `resolve_session_identity` (Specification).
- **Модули:** `loop/prompt_builder.py`; `harness/hooks/epic/core.py` `session_start_payload`; possibly `loop/schemas/state.py`.
- **Не** новый сервисный пакет `SessionContextService/` дерево (cut_list); one module function + tests.

Sunset: default `"unknown"`; any code that sets COMMAND from `extract_handoff_heading`.

### As-built inventory (delete / lock, not copy)

| Path | As-built behavior | After epic |
|------|-------------------|------------|
| `loop/prompt_builder.py` `PromptScope.step` | `projection.step \| next_step` else **`unknown`** | armed → phase or sNN; never unknown |
| `harness/hooks/epic/core.py` `session_start_payload` | injects COMMAND from AC/projection without lock | `resolve_session_identity` first |
| `harness/hooks/session-start.py` | additionalContext may include stale COMMAND | halt card on Drift |
| AC `## Handoff BACK QA` heading | tempting regex SoT | ignored when `loop-handoff/v1` valid |
| Session `94cea2d3` | BUGFIX loop + QA SessionStart + QA overlay | halt CONTEXT_IDENTITY_DRIFT |

### Halt diagnostic shape (machine)

```text
{
  "code": "CONTEXT_IDENTITY_DRIFT",
  "armed_step": "BUGFIX",
  "ac_mode": "QA",
  "projection_phase": "QA",
  "epic_id": "...",
  "role": "BACK"
}
```

extra=forbid on existing result models → put these in `diagnostic_codes` + `shape_errors` / existing halt fields; **do not** invent a second JSON file. If current payload is markdown additionalContext only, halt card MUST include the same fields as labeled lines.

---

## Eng review spine

### Data flow (ASCII)

```text
[loop spawn / SessionStart]
    -> [load_epic_state]                    sync
    -> [parse AC frontmatter loop-handoff/v1]
    -> [resolve_session_identity]           fail-closed mismatch
    -> [PromptScope COMMAND/role/phase/step]
    -> [render_prompt_scope additionalContext]
```

### Failure matrix

| Component | Failure | Detection | Response | Test ID |
|-----------|---------|-----------|----------|---------|
| BUGFIX vs QA inject | dual COMMAND | pytest US-001 | halt/lock | TM-001 |
| step unknown | agent lost shard | pytest | never unknown | TM-002 |
| AC stale mode | drift | diagnostic | halt | TM-003 |
| missing frontmatter | regex temptation | drift counter | state wins if armed | TM-004 |
| unarmed IDE | no state | documented step token | not crash | TM-005 |
| epic_id mismatch | wrong plan | halt | TM-006 |
| 065 dual hook | double payload | idempotent | TM-007 |
| IMPLEMENT missing sNN | armed implement no step | diagnostic not unknown | TM-008 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | 5 | |
| Failure coverage | 5 | |
| Testability | 5 | |

---

## Replacement / sunset

### A. Code / modules

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| PromptScope step default `unknown` when armed | armed_step / phase | delete in-epic |
| COMMAND from stale AC heading | identity resolver | delete in-epic |

### B. Entrypoints

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| n/a | SessionStart same | n/a |

### C. Fallbacks

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| warning + continue on mismatch | halt CONTEXT_IDENTITY_DRIFT | delete in-epic |

### I. Instruction surfaces

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| docs «step unknown OK» | armed always has step | delete in-epic |

---

## NFR

| ID | Requirement |
|----|-------------|
| NFR-1 | Halt faster than agent tool-use (SessionStart) |
| NFR-2 | Diagnostic machine-readable |
| NFR-3 | Idempotent under dual hooks |

---

## QA consumes

<a id="qa-consumes"></a>

### Scope under test

- session_start_payload, prompt_builder, identity drift.
- Out: overlay strings (070), mb-load ok flag (072).

### Test matrix

| ID | Priority | Scenario | Command | Expected | Maps |
|----|----------|----------|---------|----------|------|
| TM-001 | P0 | BUGFIX armed COMMAND | pytest | BACK BUGFIX only | US-001 |
| TM-002 | P0 | QA step not unknown | pytest | step QA | US-002 |
| TM-003 | P0 | mismatch halt | pytest | CONTEXT_IDENTITY_DRIFT | US-003 |
| TM-004 | P0 | IMPLEMENT sNN | pytest | s05 | US-004 |
| TM-005 | P1 | unarmed IDE | pytest | no crash | FR-002 |
| TM-006 | P1 | epic mismatch | pytest | halt | FR-001 |
| TM-007 | P1 | no heading COMMAND | unit | state wins | FR-007 |
| TM-008 | P1 | matrix all phases | pytest | no unknown | FR-008 |

### Regression notes

- 065 may change SessionStart count; identity tests mock payload function not jsonl.

---

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3 | done | clarify + probe |
| Eng review spine | L2+ | done | |
| §0.11 | | done | COMMAND ↔ armed_step ↔ AC mode |
| CREATIVE | | n/a | |
| qa_consumes | L2+ | done | |
| Plan review batch | L2+ | done | |

## Plan review batch log

| Phase | Auto-resolved | Deferred | Taste |
|-------|---------------|----------|-------|
| Product | Halt not warn | SessionContextService class | |
| Eng | Identity Specification | Event sourcing B | |

---

## До DECOMPOSE

1. s01 — red tests 94cea2d3 + unknown step matrix.
2. s02 — resolve_session_identity + PromptScope step chain.
3. s03 — session_start_payload halt on drift.
4. s04 — Kind I + purge unknown default.
5. s05 — phase matrix tests.
6. s06 — purge leftover.

---

## Appetite

| Поле | Значение | Описание |
| :--- | :--- | :--- |
| `timebox_days` | `3` | |
| `cut_list` | `['SessionContextService package', 'Variant B projector']` | |

## Independent Test

- PASS: armed BUGFIX injects BUGFIX; QA step≠unknown; mismatch diagnostic.
- FAIL: «projection usually matches» without halt fixture.

## Следующий режим

→ BACK DECOMPOSE T-HUB-071 after 070.

**CREATIVE need:** нет.
