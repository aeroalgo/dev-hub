# [T-HUB-104 | plan-path-classifier-dedup] PLAN

**Дата:** 2026-09-16  
**Режим:** BACK PLAN REFACTOR (multi-epic cut)  
**Уровень:** L2  
**Статус:** active  
**Clarify:** Phase 0 skipped — taxonomy clear; user forced PLAN REFACTOR (scan scope B)  
**Prompt:** [md/prompt.md](prompt.md)  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `plan-refactor-leftover-20260916` · `kind: refactor`  
**Deps:** —  
**Unlocks:** T-HUB-105 (soft)  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns · python-design-patterns · python-anti-patterns  
**Источник:** BACK PLAN REFACTOR inventory 2026-09-16

---

## Epic cut (нарезка)

| ID | Ось | Clusters | Deps |
|----|-----|----------|------|
| T-HUB-103 | Event schema SoT unify | C1 | — |
| T-HUB-104 | Plan-path classifier + board_sync helper | C2 + C3 | — |
| T-HUB-105 | Roadmap legacy source + orchestrator import | C7 | — |

**MULTI-EPIC PLAN — 3 эпика.**

---

## Контекст

- **req:** Два classifier meaning для «markdown plan-like path» живут в `loop/mb_load/plan_section.py:is_whole_plan_path` и `loop/mb_load/session.py:is_markdown_plan_path` (перекрытие на `md/plan.md` / `plan-*.md`; session шире: gap/analyze/decompose-index). Параллельно identical `_plan_path` (sys.path → `find_plan_md_path`) в `loop/board_sync/epic_resolver.py` и `loop/board_sync/scan_gates.py`.
- **gap:** два owner на classifier surface + две копии одного board_sync helper.
- **refs:** inventory; callers `context_scope`, `context_ledger_adapters`, `mb_load/resolver`, tests `test_mb_load_session`, `test_plan_jump_context_policy`.
- **Не:** event schema; roadmap discover; смена deny semantics.

**CREATIVE need:** нет.

---

## Baseline (scan scope B)

См. T-HUB-103 plan §Baseline (тот же scan). Graph unavailable — rg only.

---

## Consolidation clusters

| cluster_id | members | meaning | canonical_owner | action | why |
|---|---|---|---|---|---|
| C2 | `plan_section.is_whole_plan_path`; `session.is_markdown_plan_path` | classify restricted markdown plan/gap paths for load deny/strip | `loop/mb_load/plan_section.py` (unified owner; broader classifier + keep/alias narrow API if needed) | **merge** | one module owns both; session body deleted; behavior freeze on existing match tables |
| C3 | `board_sync/epic_resolver._plan_path`; `board_sync/scan_gates._plan_path` | resolve plan.md via epic_paths | `loop/board_sync/_epic_paths.py` (new thin helper) **only if** deletes both copies | **extract** | copies_removed_count = 2; fail if extract leaves either body |

---

## Refactor inventory

| ID | path/symbol | evidence | category | action | cluster_id | canonical_owner | copies_removed_count | net_loc_delta | net_symbol_delta | behavior_freeze_oracle | proof |
|---|---|---|---|---|---|---|---:|---:|---:|---|---|
| F-104-01 | `session.is_markdown_plan_path` body | callers: session load loop; tests unit | twin | **move** to `plan_section`; session re-export or call-through; **delete** session body | C2 | `plan_section` | 1 | −20 | 0 (symbol may re-export) | `bin/pytest loop/tests/test_mb_load_session.py -k markdown_plan -q` + plan_jump/context_scope targeted | rg one definition |
| F-104-02 | overlapping plan.md regex | both classifiers | twin | **share** helper used by `is_whole_plan_path` and markdown classifier | C2 | `plan_section` | 1 | −10 | 0 | same True/False matrix as tests | parametrize matrix |
| F-104-03 | `epic_resolver._plan_path` | identical 14-line block | twin | **delete** after extract | C3 | `board_sync/_epic_paths.plan_path` | 1 | −14 | −1 | board_sync resolver tests / smoke import | identity |
| F-104-04 | `scan_gates._plan_path` | identical block | twin | **delete** after extract | C3 | same | 1 | −14 | −1 | scan_gates tests | identity |
| F-104-05 | optional `_epic_id_from_plan_path` twin pattern in epic_resolver | same sys.path hack | twin | **merge** into same helper module if duplicate exists in scan_gates | C3 | `_epic_paths` | ≥1 if dup | ≤0 | ≤0 | existing board_sync tests | rg |

**FAIL if:** new `_epic_paths.py` without deleting ≥2 caller-local copies; move classifier without deleting session body.

---

## Delivery closure

| Capability | Classification | Entrypoint | Enforcement | Independent test | Follow-up |
|---|---|---|---|---|---|
| Sole plan-path classifier owner | vertical_slice | mb_load / context_scope → plan_section | session has no duplicate body | classifier matrix tests | n/a |
| Sole board_sync plan resolve helper | vertical_slice | epic_resolver/scan_gates → `_epic_paths` | no local `_plan_path` bodies | board_sync targeted | n/a |

---

## Technology axiom

| Выбор | Machine input | FORBIDDEN |
|-------|---------------|-----------|
| Classifier SoT | functions in `plan_section` | second full body in `session` |
| board_sync path SoT | one helper module | copy-paste sys.path+import blocks |
| Behavior | existing True/False / Path|None results | broaden/narrow deny without test matrix update = behavior change → stop |

---

## Product probe

| # | Q | A | Impact |
|---|---|---|---|
| 1 | Reframe | Twin helpers hide canonical owner | One module each cluster |
| 2 | Wedge | Move markdown classifier; extract `_plan_path` | C2 then C3 |
| 3 | Pre-mortem | Subtle matrix drift on gap/analyze | Freeze matrix in tests before merge |
| 4 | Adoption | Same call sites | re-export OK short-term if body gone |
| 5 | Leverage | Delete two identical blocks | copies_removed ≥ 2 for C3 |
| 6 | Appetite | ≤1–2 days | out: event/roadmap |

---

## WHAT

Один owner для markdown-plan classification и один shared board_sync plan-path helper; duplicate bodies нельзя; deny/load behavior неизменно.

### User Stories

| # | Story | P | Independent Test |
|---|-------|---|------------------|
| US-001 | Maintainer меняет classifier в одном модуле | P0 | single definition; matrix PASS |
| US-002 | board_sync resolve plan без copy-paste | P0 | no `_plan_path` in epic_resolver/scan_gates; helper used |

#### Acceptance Scenarios — US-001

- **Given:** paths from existing unit matrix (plan.md, gap, analyze, yaml)
- **When:** classifiers run via plan_section owner
- **Then:** same booleans as pre-merge

#### Acceptance Scenarios — US-002

- **Given:** epic with plan.md
- **When:** epic_resolver/scan_gates resolve plan path
- **Then:** same Path|None; local duplicate functions absent

### Functional Requirements

- **FR-001:** Move `is_markdown_plan_path` into `plan_section` (or unify under one name with aliases); delete session implementation body.
- **FR-002:** Share overlapping plan.md detection between whole-plan and markdown classifiers without dual regex maintenance.
- **FR-003:** Extract `board_sync` plan path helper; delete both `_plan_path` copies.
- **FR-004:** Consolidate tests into one parametrized matrix where duplicated.

### Success Criteria

- **SC-001:** `rg 'def is_markdown_plan_path' loop` → one definition (plan_section).
- **SC-002:** `rg 'def _plan_path' loop/board_sync` → zero (or only in helper if named differently once).
- **SC-003:** net_loc ≤ 0; owners ≤ 0 growth.

### AC−

1. Нет двух полных classifier bodies.
2. Нет двух sys.path hacks for `find_plan_md_path` in board_sync.
3. Нет extract без delete siblings.
4. Нет изменения deny matrix без явного behavior epic.

---

## HOW (outline)

1. Capture classifier matrix tests (red if drift).
2. Move/merge C2; update imports.
3. Extract C3 helper; delete twins.
4. Targeted pytest freeze oracles.

---

## Deletion budget

| Item | Expectation |
|------|-------------|
| Code LOC | ≈ −40…−60 |
| Test LOC | ≤0 (merge duplicate asserts; may add matrix once) |
| Net | **≤ 0** |

---

## Concept budget

| Concept | Before | After | Δ |
|---------|-------:|------:|--:|
| Classifier module owners | 2 | 1 | −1 |
| board_sync `_plan_path` copies | 2 | 1 | −1 |
| New public APIs | 0 preferred | ≤1 helper module | 0 net owners if replaces 2 |

---

## Test refactor

| Action | Target | Replacement |
|--------|--------|-------------|
| merge | `test_mb_load_session` classifier units + `test_plan_jump_context_policy` whole-plan | one parametrized module or shared fixture |
| update | board_sync tests | import helper |

---

## Replacement / sunset

| Sunset | Policy |
|--------|--------|
| A | delete session classifier body |
| B | delete duplicate `_plan_path` |
| C | obsolete duplicate asserts |
| I | none beyond code |

---

## QA consumes draft

1. **TM-01:** classifier matrix identical.
2. **TM-02:** board_sync plan resolve unchanged; no local twins.
3. **TM-03:** full suite in BACK QA.

---

## Review readiness

| Required | Status |
|----------|--------|
| C2+C3 table | done |
| copies_removed ≥1 / C3 ≥2 | done |
| budgets ≤0 | done |

---

## Independent Tests (behavior)

- Given load_now plan.md / gap path, when mb_load/session classifies, then strip/deny same as before.
- Given epic id, when board_sync resolves plan, then same path.
