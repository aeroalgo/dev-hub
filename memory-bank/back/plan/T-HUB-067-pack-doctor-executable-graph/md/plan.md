# [T-HUB-067 | pack-doctor-executable-graph] PLAN

**Дата:** 2026-09-05  
**Режим:** BACK PLAN  
**Уровень:** L3–L4  
**Статус:** active  
**Clarify:** `memory-bank/back/clarify/clarify-20260905-workflow-loop-audit.md`  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `workflow-loop-20260905`  
**Deps:** **hard T-HUB-062** (skill literal checker reusable), **hard T-HUB-064** (route exists + agent declare). Soft T-HUB-044/061 doctor CLI. Не ждать 048–052 IMPLEMENT.  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns  
**Источник:** audit `02` pack resolve false-green · `07` P1.5 doctor + P1.6 strict bundle · `03` load_session ok=true partial

---

## Контекст

- **req:** Pack `ok=true` только если **исполняемый граф** цел: `rules_root`, role indexes, каждый `route_command` path, `_lean` gates, phase registry verify agents, manifest rows, schemas, optional tool-gates. `load_session` `ok=true` только если все **required** `load_now` paths прочитаны. SessionStart не inject-ит partial bundle как normal context.
- **gap:**
  1. `full_resolve()` / pack e2e зелёный при missing workflow files (064 leftover; doctor must fail even if 064 not merged yet via fixture).
  2. Doctor/parity не проверяет skill `@` (062), routes existence, `_lean` gates, undeclared agents.
  3. `load_session`: missing files → `diagnostic_codes` **и** `ok=true` (audit 03 §3).
  4. SessionStart swallows `Exception` as Warning (audit 03 §4) — **required** context must halt.
  5. T-HUB-061 hygiene (CLI kwargs) ≠ executable graph.
- **refs:** `loop/workflow/resolve.py`; `loop/mb_load/session.py`; `harness/hooks/session-start.py`; doctor CLI; audit 02, 03, 07 P1.5–P1.6.
- **Не:** video ffmpeg (051); duplicate hooks (065); transactional finish journal (068); Codex TOML policy (069). Bundle **strictness** живёт здесь, не в 065 (065 = runtime arg + hook dedup).

**CREATIVE need:** нет.

---

## Technology axiom

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Pack usable | every route Path.exists + every verify_agent declared | `ok=true` + missing file |
| Doctor codes | `pack_route_missing` · `pack_gate_missing` · `pack_agent_missing` · `skill_ref_missing` (reuse 062) · `pack_schema_missing` | generic `ok=false` без кода |
| load_session | `ok=true` iff required complete | ok + diagnostic_codes missing_file |
| SessionStart | required_missing → CONTEXT_INCOMPLETE halt/degrade | Warning + inject leftover files as success |
| Optional files | typed `optional=true` in request | implicit skip |

---

## Продуктовая спека (WHAT)

1. Doctor (или named pytest suite вызываемый doctor-ом) по каждому registered pack: inventory routes, gates, agents, schemas.
2. Broken fixture packs fail with **precise** codes (audit 07 P1.5).
3. `load_session` result machine fields: `required_missing`, `optional_missing`, `forbidden_skipped`; `ok` derived.
4. SessionStart: `required_missing` → не masquerade as complete additionalContext.
5. Partial bundle fingerprint marked `status=incomplete`.

### Product probe

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Reframe | Pack/doctor врёт «usable» | Executable graph, не ещё один README |
| 2 | Wedge | fixture missing route → `pack_route_missing`; load missing required → ok=false | P0 |
| 3 | Pre-mortem | Doctor checks yaml keys, not Path.exists | FR exists on every route |
| 4 | Adoption | `bin/runtime-sync` / doctor / pytest named | |
| 5 | Leverage | 062 checker + 064 route_command exists | compose, don't rewrite packs |
| 6 | Appetite | 4 days | cut: template pack authoring UI; MCP-only load rewrite |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как CI, я хочу doctor red на missing workflow route. | P0 | fixture pack → `pack_route_missing` |
| US-002 | Как CI, я хочу doctor red на phase verify_agent not in manifest. | P0 | `pack_agent_missing` |
| US-003 | Как CI, я хочу doctor red на missing `_lean` gate file. | P0 | `pack_gate_missing` |
| US-004 | Как operator, я не хочу SessionStart с ok=true при дырявом load_now. | P0 | unit load_session missing required → ok=false |
| US-005 | Как parent, я хочу явный CONTEXT_INCOMPLETE вместо Warning. | P0 | session_start_payload missing file → halt/degrade code |

#### Acceptance Scenarios — US-001

- **Given:** tmp pack whose `route_command("SCRIPT PLAN")` (or software analog) path does not exist
- **When:** doctor / `check_pack_graph(pack_id)`
- **Then:** `ok=false`, code `pack_route_missing`, path listed; production `dev-hub-software` pack green **only if** all routes exist

#### Acceptance Scenarios — US-004

- **Given:** activeContext `load_now` lists required path that is absent
- **When:** `load_session(...)`
- **Then:** `ok is False`; `required_missing` contains path; `diagnostic_codes` keep `missing_file:`; MCP wrapper cannot override to ok for partial required

### Functional Requirements

- **FR-001:** `check_pack_graph(pack)` walks: registry entry, `rules_root` exists, each role index, each intent→route Path.exists, each `_lean` gate referenced by workflow Gates, each phase `verify_agent` in manifest **or** `no_gate_reason`, each schema_id in BOUNDARY_REGISTRY if pack declares schemas.
- **FR-002:** Precise fail codes (axiom table). Multiple codes allowed (list), not first-only hide.
- **FR-003:** Consume 062 skill checker on pack/workflow corpora (or call same function). Missing skill → `skill_ref_missing` counts as pack unusable if referenced from pack rules.
- **FR-004:** Consume 064 route exists helper; do not duplicate divergent exists logic.
- **FR-005:** Doctor CLI exit ≠0 when any registered pack unusable; `--pack` filter.
- **FR-006:** `load_session`: never set `ok=True` after required miss/read error. Derive `ok = not required_missing and not read_errors_on_required`.
- **FR-007:** Request model: entries marked required vs optional. Unmarked = required (fail-closed).
- **FR-008:** Result schema fields: `required_missing`, `optional_missing`, `forbidden_skipped`, `fingerprint`, `status=complete|incomplete`.
- **FR-009:** SessionStart: if `status=incomplete` or `ok=false` → inject `CONTEXT_INCOMPLETE` + codes; **forbid** presenting leftover files as sufficient for main work. Halt vs degrade: halt when **any required** missing; degrade documented only for optional.
- **FR-010:** Split diagnostic-only exceptions vs required-context exceptions (audit 03 §4). Required → typed code, not `Warning: load_session exception`.
- **FR-011:** pytest fixtures: (a) missing route (b) missing gate (c) missing agent (d) missing required load path (e) optional missing still ok=true.
- **FR-012:** Kind I: pack README / CLAUDE pack table cannot say «fully wired» while doctor red.
- **FR-013:** Software pack regression: doctor green on `dev-hub-software` after 064 video leftover — video pack may stay red until 064; doctor must still **report** video red, not skip pack.
- **FR-014:** Do not swallow doctor IO errors as skip pack.
- **FR-015:** External tool gates (ffmpeg) = `pack_tool_gate_missing` **advisory vs fail**: Appetite cut = fail only if pack `tool_gates.required=true`; video ffmpeg remains 051 — this epic documents field, default not fail hub software pack.

### Success Criteria

| ID | Result | Check | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | broken route fixture code exact | pytest | outcome |
| SC-002 | load required miss → ok false | unit | outcome |
| SC-003 | SessionStart incomplete not success inject | hook/unit | outcome |
| SC-004 | software pack doctor uses exists not keys-only | pytest | outcome |
| SC-005 | optional miss → ok true + optional_missing | unit | outcome |

### Assumptions

- Video pack may be red until 064 lands; 067 tests use **fixtures**, production assertion: software pack green; video asserted only if 064 done (feature flag / xfail documented — prefer order queue 064 before 067).
- MCP wrapper partial-empty fix remains; extend to partial-nonempty.

## AC

1. Doctor fail-closed on unusable pack with precise codes.
2. load_session ok iff required complete.
3. SessionStart does not treat partial required as success.
4. Optional typed and does not flip ok.
5. Skill/route checkers composed, not forked.

### AC−

1. Нет `ok=true` + `missing_file` on required.
2. Нет doctor green on yaml-only keys.
3. Нет Warning-only on required context exception.
4. Нет skip video pack in doctor because red.
5. Нет second exists-implementation diverging from 064.

## HOW

- New `loop/workflow/pack_graph.py` (or extend resolve) + `loop/mb_load/session.py` ok derivation + session-start branch + doctor command + tests `loop/tests/test_pack_graph_doctor.py`, `test_mb_load_session.py`.
- Reuse 062 `skill_refs` and 064 exists check.

## Eng review spine

### Data flow

```text
[pack registry] -> [check_pack_graph]
                      -> rules_root / routes exists / gates / agents / schemas / skills
                      -> codes[]  ok=len(codes)==0
[SessionStart] -> [load_session]
                      -> required vs optional
                      -> ok? complete inject : CONTEXT_INCOMPLETE (halt)
```

### Failure matrix

| Component | Failure | Detection | Response | Test ID |
|-----------|---------|-----------|----------|---------|
| missing route | false pack ok | exists | pack_route_missing | TM-001 |
| missing gate | lean 404 | exists | pack_gate_missing | TM-002 |
| undeclared verify agent | spawn fail later | manifest set | pack_agent_missing | TM-003 |
| missing skill @ | Read 404 | 062 checker | skill_ref_missing | TM-004 |
| required load miss | ok true today | derive ok | ok false | TM-005 |
| optional miss | false fail | optional flag | ok true | TM-006 |
| exception swallow | Warning success | classify | halt required | TM-007 |
| doctor skips red pack | hide video | all packs | report | TM-008 |
| keys-only doctor | false green | fixture missing file yaml present | fail exists | TM-009 |

### Eng spine self-check

| Dimension | Score | Gap |
|-----------|-------|-----|
| Data flow complete | 5 | |
| Failure coverage | 5 | 9 rows |
| Testability | 5 | fixtures no LLM |

## Replacement / sunset

### A

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| `ok=true` after required miss | derived ok | delete in-epic |
| pack resolve without exists | graph checker | delete in-epic |
| doctor keys-only | exists+declare | delete in-epic |

### B

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| doctor exit 0 on unusable pack | exit ≠0 | delete in-epic |

### C

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| SessionStart Warning on Exception as success | typed halt | delete in-epic for required |
| MCP ok override partial required | same derive | delete in-epic |

### I

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| docs «pack wired» | doctor green | delete in-epic |
| «partial load ok» comments | required complete | delete in-epic |

## QA consumes

<a id="qa-consumes"></a>

| ID | Priority | Scenario | Command | Expected | Maps |
|----|----------|----------|---------|----------|------|
| TM-001 | P0 | missing route fixture | pytest pack graph | pack_route_missing | US-001 |
| TM-002 | P0 | missing gate fixture | pytest | pack_gate_missing | US-003 |
| TM-003 | P0 | missing agent fixture | pytest | pack_agent_missing | US-002 |
| TM-004 | P0 | required load miss | pytest mb_load | ok false | US-004 |
| TM-005 | P0 | SessionStart incomplete | unit hook | CONTEXT_INCOMPLETE | US-005 |
| TM-006 | P1 | optional miss | pytest | ok true + optional_missing | FR-007 |
| TM-007 | P1 | software pack exists-based | doctor --pack dev-hub-software | matches FS | FR-013 |

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3 | done | |
| Eng review spine | L2+ | done | |
| §0.11 | n/a | n/a | |
| CREATIVE | n/a | n/a | |
| qa_consumes | L2+ | done | |
| Plan review batch | L2+ | done | |

## Plan review batch log

| Phase | Auto-resolved | Deferred |
|-------|---------------|----------|
| Product | Compose 062/064 checkers | template pack UI |
| Eng | Derive ok; halt required | full ContextBoundaryService (068 cut) |

## До DECOMPOSE

1. s01 — red tests: route/gate/agent fixtures + load ok false.
2. s02 — `check_pack_graph` exists+codes; doctor CLI.
3. s03 — compose skill_refs (062).
4. s04 — load_session derive ok + result fields.
5. s05 — SessionStart CONTEXT_INCOMPLETE + exception split.
6. s06 — Kind I docs; software pack assertion.
7. s07 — purge ok=true leftover + Warning-as-success.

## Appetite

| Поле | Значение | Описание |
| :--- | :--- | :--- |
| `timebox_days` | `4` | |
| `cut_list` | `['template pack authoring', 'MCP load rewrite', 'full ContextBoundaryService class', 'ffmpeg required gate']` | 068 owns transaction service |

## Independent Test

- PASS: fixture missing route → exact code; required miss → ok false; optional miss → ok true.
- FAIL: «doctor prints yaml keys» without Path.exists; «diagnostic_codes nonempty but ok true» as accepted.

## Следующий режим

→ BACK DECOMPOSE T-HUB-067 after 064 and 062.

**CREATIVE need:** нет.
