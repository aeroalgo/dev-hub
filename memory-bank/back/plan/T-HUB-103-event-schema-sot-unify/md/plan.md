# [T-HUB-103 | event-schema-sot-unify] PLAN

**Дата:** 2026-09-16  
**Режим:** BACK PLAN REFACTOR (multi-epic cut)  
**Уровень:** L2  
**Статус:** active  
**Clarify:** Phase 0 skipped — taxonomy clear; user forced PLAN REFACTOR (scan scope B)  
**Prompt:** [md/prompt.md](prompt.md)  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `plan-refactor-leftover-20260916` · `kind: refactor`  
**Deps:** —  
**Unlocks:** T-HUB-104 (soft order), T-HUB-105  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns · python-design-patterns · python-anti-patterns  
**Источник:** BACK PLAN REFACTOR inventory 2026-09-16; post T-HUB-095…102 leftover

---

## Epic cut (нарезка)

| ID | Ось | Clusters | Deps |
|----|-----|----------|------|
| T-HUB-103 | Event schema SoT unify | C1 | — |
| T-HUB-104 | Plan-path classifier + board_sync helper | C2 + C3 | — |
| T-HUB-105 | Roadmap legacy source + orchestrator import | C7 + dead import | — |

**MULTI-EPIC PLAN — 3 эпика.** Cut по независимому meaning / дереву / риску.

---

## Контекст

- **req:** Live event validate живёт в `harness/hooks/epic_events.py`; параллельно существует orphan `loop/schemas/event.py:LoopEvent` с отдельной `EVENT_KINDS` (drift: нет `operator_repair` и др. kinds live-слоя), prod callers `LoopEvent` = 0 (только `loop/tests/test_schemas_event.py` + re-export в `loop/schemas/__init__.py`).
- **gap:** два schema owners одного meaning `loop-event/v2`.
- **refs:** inventory 2026-09-16; `loop/schemas/event.py`; `harness/hooks/epic_events.py`; `loop/tests/test_schemas_event.py`; `loop/tests/test_event_v2_characterization.py`.
- **Не:** offline `adapt_v1_event` (097/ось 105 вне); plan-path; roadmap merge.

**CREATIVE need:** нет.

---

## Baseline (scan scope B)

| Metric | Value | Command / note |
|--------|------:|----------------|
| `loop/`+`harness/` `*.py` files | 638 | rglob excl `__pycache__` |
| Combined LOC | ~156 783 | `wc -l` |
| Prod (excl tests) files / LOC | 268 / ~78 266 | excl `*/tests/*` |
| `loop/tests` LOC | ~64 403 | |
| Graph | **unavailable** | no `memory-bank/**/graph.json`; evidence = rg/import |
| Exclusions | memory-bank artifacts, `.venv`, `__pycache__`, vendor | declared |
| Prior purge | 095–097, 101 | не re-plan done work |

---

## Consolidation clusters

| cluster_id | members | meaning | canonical_owner | action | why |
|---|---|---|---|---|---|
| C1 | `loop/schemas/event.py:LoopEvent` + `EVENT_KINDS`; `harness/hooks/epic_events.py:validate_event` + kinds/constants | loop-event/v2 validate/schema | `harness/hooks/epic_events.py:validate_event` | **merge** (delete orphan schema; tests → live owner / thin re-export only if public API must keep name) | prod LoopEvent callers = 0; kind tables already drift |

`no keep-split` for C1 — split would preserve dual SoT.

---

## Refactor inventory

| ID | path/symbol | evidence / callers | category | action | cluster_id | canonical_owner | copies_removed_count | net_loc_delta | net_symbol_delta | behavior_freeze_oracle | proof |
|---|---|---|---|---|---|---|---:|---:|---:|---|---|
| F-103-01 | `loop/schemas/event.py` (module) | prod `LoopEvent` import: tests only; `__init__` re-export | dead/twin | **delete** module after export cleanup | C1 | `epic_events.validate_event` | 1 | −90 | −3 (`LoopEvent`, `EVENT_KINDS`, `EVENT_SCHEMA` schema-local) | `bin/pytest loop/tests/test_event_v2_characterization.py -q` + rewritten schema suite or delete | rg prod imports = 0 before delete |
| F-103-02 | `loop/schemas/__init__.py` exports | exports `LoopEvent` | shim | **delete** exports; update README kinds table | C1 | epic_events | 1 | −5 | −1 | import `from loop.schemas import LoopEvent` must fail | rg |
| F-103-03 | `loop/tests/test_schemas_event.py` | asserts orphan model | test twin | **delete or rewrite** against live validate API / shared fixtures with characterization | C1 | characterization suite | 1 | −80 | 0 | characterization + any remaining public validate tests green | suite |
| F-103-04 | `loop/schemas/README.md` row `LoopEvent` | docs dual SoT | Kind I | **rewrite** row → epic_events sole path | C1 | epic_events | 0 (docs) | 0 | 0 | n/a docs | manual |

**Deletion/consolidation test:** each step removes a copy of event-schema meaning; no new adapter without retiring ≥1 copy.

---

## Delivery closure

| Capability / outcome | Classification | Production entrypoint and caller | Success / failure enforcement | Independent outcome test | Foundation approval / follow-up |
|---|---|---|---|---|---|
| Sole event schema/validate owner | `vertical_slice` | writers/readers → `epic_events.validate_event` | orphan `loop.schemas.event` absent; import fails | characterization + rg zero orphan | `n/a` |

---

## Technology axiom

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Event validate SoT | `epic_events` kinds + validate | parallel `EVENT_KINDS` in `loop/schemas/event.py` |
| Public schema | optional thin re-export **without** second table | pydantic model that diverges from live kinds |
| Behavior | existing event write/read contracts | change kind set «заодно» без evidence |

As-built = sunset inventory only.

---

## Product probe

| # | Question | Answer / Probe | Decision / Impact |
|---|----------|----------------|-------------------|
| 1 | Reframe | Orphan schema hides drift from live events | Delete orphan = sole SoT |
| 2 | Narrowest wedge | Delete module + exports + obsolete tests | F-103-01…03 |
| 3 | Pre-mortem | External import of `LoopEvent` breaks | rg + fail-closed; no silent restore |
| 4 | Distribution | Same event files on disk | Kind I README only |
| 5 | Technical leverage | One kinds table | copies_removed ≥ 1 |
| 6 | Appetite | ≤1 day | cut_list = 104/105 |

Phase 0 skipped — user forced PLAN REFACTOR; scan scope B declared.

---

## WHAT

Один канонический owner для loop-event/v2 schema/validate; orphan Pydantic-копия и obsolete schema-only tests нельзя использовать; поведение live event path неизменно.

### User Stories

| # | Story | P | Independent Test |
|---|-------|---|------------------|
| US-001 | Как maintainer, я валидирую events только через live epic_events SoT | P0 | rg: no `loop.schemas.event`; characterization PASS |
| US-002 | Как CI, schema-only suite не держит drift kinds | P0 | `test_schemas_event` gone or rewritten; no second EVENT_KINDS |

#### Acceptance Scenarios — US-001

- **Given:** production/hooks event path
- **When:** validate/write/read event
- **Then:** sole kinds/validate owner; behavior unchanged vs freeze oracle

#### Acceptance Scenarios — US-002

- **Given:** orphan schema deleted
- **When:** suite runs
- **Then:** no test requires divergent LoopEvent kinds

### Functional Requirements

- **FR-001:** Delete `loop/schemas/event.py` after proving zero prod callers.
- **FR-002:** Remove `LoopEvent`/`EVENT_KINDS`/`EVENT_SCHEMA` from `loop/schemas/__init__.py`.
- **FR-003:** Delete or rewrite `test_schemas_event.py` to live SoT; consolidate fixtures with characterization where overlapping.
- **FR-004:** Update `loop/schemas/README.md` to point to epic_events.
- **FR-005:** Do not change live event kind set except to document existing epic_events as sole source (no feature kinds).

### Success Criteria

- **SC-001:** `rg 'from loop.schemas.event|loop\.schemas\.event' loop harness` → only historical comments if any; no imports.
- **SC-002:** Freeze oracle green.
- **SC-003:** net_loc ≤ 0; net public schema symbols ≤ 0.

### AC−

1. Нет dual `EVENT_KINDS`.
2. Нет silent PASS через orphan model.
3. Нет живых тестов, требующих удалённый `LoopEvent`.
4. Нет «optional schema module» рядом с epic_events.

---

## HOW (outline)

1. rg proof zero prod LoopEvent.
2. Rewrite/delete schema tests first (TDD red on import removal).
3. Purge exports + module + README.
4. Run freeze oracle; full suite → BACK QA.

---

## Deletion budget

| Item | Expectation |
|------|-------------|
| Code LOC | ≈ −90…−120 |
| Test LOC | ≈ −50…−100 (delete or shrink twin suite) |
| Public symbols | −`LoopEvent` − schema-local `EVENT_KINDS`/`EVENT_SCHEMA` |
| Net | **≤ 0** |

---

## Concept budget

| Concept | Before | After | Δ |
|---------|-------:|------:|--:|
| Event schema/validate owners | 2 | 1 | −1 |
| Adapter types (new) | 0 | 0 | 0 |
| Test helper modules for event schema | 2 overlapping | ≤1 | ≤0 |

---

## Test refactor

| Action | Target | Replacement coverage |
|--------|--------|----------------------|
| delete/rewrite | `loop/tests/test_schemas_event.py` | `test_event_v2_characterization.py` (+ thin validate tests on epic_events if public API needed) |
| keep | characterization / legacy adapter isolation tests | unchanged offline meaning (out of epic) |

---

## Replacement / sunset

| Sunset | Policy |
|--------|--------|
| A — module | delete `loop/schemas/event.py` |
| B — exports | remove from `__init__.py` |
| C — tests | delete/rewrite obsolete |
| I — docs | README row |

---

## QA consumes draft

1. **TM-01:** orphan schema import fails; characterization PASS.
2. **TM-02:** no dual EVENT_KINDS in loop/schemas.
3. **TM-03:** full `bin/pytest -q --tb=line` (QA only).

---

## Review readiness

| Required | Status |
|----------|--------|
| Inventory + C1 cluster | done |
| Deletion + concept budget ≤0 | done |
| Behavior freeze named | done |
| No new abstraction without copies_removed ≥1 | done |

---

## Independent Tests (behavior)

- Given event log v2 on disk, when validate via epic_events, then same accept/reject as before; orphan import path dead.
