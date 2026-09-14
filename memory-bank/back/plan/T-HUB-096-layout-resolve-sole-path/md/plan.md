# [T-HUB-096 | layout-resolve-sole-path] PLAN

**Дата:** 2026-09-14  
**Режим:** BACK PLAN REFACTOR (multi-epic cut)  
**Уровень:** L3  
**Статус:** active  
**Clarify:** [memory-bank/back/clarify/clarify-20260912-plan-refactor.md](../../../clarify/clarify-20260912-plan-refactor.md)  
**Prompt:** [md/prompt.md](prompt.md)  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `plan-refactor-leftover-20260914` · `kind: refactor`  
**Deps:** — (soft after T-HUB-095)  
**Unlocks:** T-HUB-097 (soft)  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns · python-design-patterns · python-anti-patterns  
**Источник:** BACK PLAN REFACTOR; inventory post T-HUB-087…090

---

## Epic cut (нарезка)

| ID | Ось | Clusters | Deps |
|----|-----|----------|------|
| T-HUB-095 | Epic runtime import sole path | C1 + C2 | — |
| T-HUB-096 | Layout/plan resolve sole path | C4 | — |
| T-HUB-097 | Offline event/DAG adapter + test hygiene | C3 + C5 | — |

---

## Контекст

- **req:** `plan_path` / `resolve_epic_slug` / index load всё ещё имеют параллельные ветки: flat v1 file, `epic_paths.find_plan_md_path`, hardcoded v2, `epic_layout.resolve`, с `except Exception: pass` swallow; `load_steps_for_index` предпочитает sibling `index.md` при наличии yaml; `SCHEMA_*_LEGACY` в `epic_yaml`; stale docstring «falling back to v1»; arm path ещё знает `decompose-` layout flag.
- **gap:** multi-owner resolve для одного meaning (epic plan/index location) после layout v2 denial.
- **refs:** `loop/roadmap_queue.py` L271–326+; `loop/paths/epic_layout.py`; `loop/paths/epic_paths.py`; `harness/hooks/epic_paths.py`; `harness/hooks/epic_yaml.py`; `test_epic_layout_v2_denial.py`.
- **Не:** epic_lib facade (095); offline adapt_* (097); смена layout kinds / новых FS схем.

**CREATIVE need:** нет.

---

## Baseline

См. общий baseline batch в T-HUB-095 §Baseline (тот же scan scope B). Graph limitation: stale — proof = rg + targeted tests.

---

## Delivery closure

| Capability / outcome | Classification | Production entrypoint and caller | Success / failure enforcement | Independent outcome test | Foundation approval / follow-up |
|---|---|---|---|---|---|
| Sole plan/index path resolve | `vertical_slice` | `roadmap_queue.plan_path` / arm / board consumers | swallow branches gone; missing plan → explicit miss/error | layout denial + roadmap_queue tests | `n/a` |
| Yaml-prefer index load | `vertical_slice` | `load_steps_for_index` | md not authoritative when yaml exists | `test_index_fail_closed` | `n/a` |

---

## Technology axiom

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Layout SoT | `loop.paths.epic_layout` (+ thin hooks helpers if still needed) | parallel flat + find_plan_md + resolve without single owner |
| Index machine SoT | `index.yaml` | prefer `index.md` when yaml present |
| Errors | fail-closed | `except Exception: pass` then next resolver |
| Legacy schema | deny or migrated shards only | silent accept `SCHEMA_*_LEGACY` without inventory |

---

## Product probe

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Reframe | Multi-resolve hides v2 denial | One owner + no swallow |
| 2 | Narrowest wedge | `plan_path` sole path + delete swallow | Highest risk row F09 |
| 3 | Pre-mortem | Flat plan files in wild still needed | Inventory before deny; migrate or explicit support window |
| 4 | Adoption | Same roadmap-advance / arm entrypoints | No new CLI |
| 5 | Leverage | Reuse `epic_layout.resolve` | no new adapter |
| 6 | Appetite | 2–3 days | SCHEMA_LEGACY only after shard inventory |

---

## WHAT

Один machine path для поиска plan/index артефактов эпика; legacy parallel resolve и swallow нельзя; поведение для валидных v2 деревьев неизменно.

### User Stories

| # | Story | P | Independent Test |
|---|-------|---|------------------|
| US-001 | Как loop, я резолвлю plan.md одним owner API | P0 | v2 epic resolves; multi-branch/swallow absent |
| US-002 | Как gate, yaml index — SoT при наличии yaml | P0 | md sibling не перебивает yaml |
| US-003 | Как maintainer, Kind I не учит v1 fallback | P0 | docstring/rg stale prose = 0 |

#### Acceptance Scenarios — US-001

- **Given:** epic tree layout v2 under `plan/<slug>/md/plan.md`
- **When:** `plan_path` / arm resolves
- **Then:** same path as today via sole owner; no silent fallthrough after exception

#### Acceptance Scenarios — US-002

- **Given:** `index.yaml` and sibling `index.md`
- **When:** `load_steps_for_index`
- **Then:** steps from yaml SoT (md non-authoritative)

### Functional Requirements

- **FR-001:** Collapse `plan_path` to one resolver owner (`epic_layout` and/or single `epic_paths` wrapper); remove bare `except: pass` swallow.
- **FR-002:** Align `resolve_epic_slug` with the same owner (no divergent multi-try).
- **FR-003:** `load_steps_for_index`: when `index.yaml` exists, do not load via md-prefer path as authoritative.
- **FR-004:** Role-map `loop.paths.epic_layout` vs `loop.paths.epic_paths` vs `harness/hooks/epic_paths`: document keep-split **or** merge hooks helpers into layout; `move` without deleting sibling copy = FAIL.
- **FR-005:** `SCHEMA_*_LEGACY`: inventory live shards; deny unused legacy schema ids **or** keep-split with explicit migrate epic already in queue (none → deny after inventory).
- **FR-006:** Fix stale `harness/hooks/epic_paths.py` docstring claiming v1 fallback.
- **FR-007:** `context_loop` / arm `decompose-` deprecated branch: deny after migrate CLI proven; keep CLI migrate tool if separate.
- **FR-008:** Thin-forward `validate_decompose_yaml` → callers use full validator; delete alias if safe.
- **FR-009:** Rewrite obsolete tests asserting multi-path success; keep `test_epic_layout_v2_denial` strengthened.
- **FR-010:** Kind I rewrite for layout fallback prose.

### Success Criteria / AC−

| SC | Check |
|----|-------|
| SC-001 | `plan_path` body: ≤1 resolve owner; no swallow-pass |
| SC-002 | yaml-prefer index load |
| SC-003 | stale «falling back to v1» prose = 0 in scoped hooks |
| AC− | no dual machine resolve; no silent PASS via flat-after-exception; no obsolete multi-path tests |

---

## Consolidation clusters

| cluster_id | members | canonical_owner | action | why |
|------------|---------|-----------------|--------|-----|
| C4 | `plan_path` multi-resolve; `load_steps_for_index` md-prefer; `SCHEMA_*_LEGACY`; `epic_paths`×2 + `epic_layout`; arm `decompose-`; stale docstring; `validate_decompose_yaml` thin alias | `loop.paths.epic_layout` (+ minimal hooks facade only if required) | **merge** | one meaning — epic artifact location / schema accept |

---

## Refactor inventory

| ID | Path / symbol | Evidence | Action | cluster | copies_removed | net_loc | net_sym | freeze_oracle | proof |
|----|---------------|----------|--------|---------|----------------:|--------:|--------:|---------------|-------|
| F09 | `roadmap_queue.plan_path` | flat→find_plan_md→v2→layout; except pass | merge | C4 | ≥2 branches | ≤ −30 | ≤ 0 | `test_roadmap_queue`, `test_epic_layout_v2_denial` | read L293–326 |
| F10 | `load_steps_for_index` | yaml+md → md path first | merge | C4 | 1 | ≤ −15 | 0 | `test_index_fail_closed` | read L271–290 |
| F11 | `SCHEMA_*_LEGACY` | still accepted | deny/merge | C4 | ≤2 | ≤ 0 | ≤ −2 | `test_epic_yaml` | rg + shard inventory |
| F13 | three path APIs | layout/paths/hooks | merge or keep-split roles | C4 | ≥1 if merge | ≤ 0 | ≤ 0 | `test_epic_paths` | fan-in+rg |
| F15 | `validate_decompose_yaml` | errors-only view; 1 caller | merge | C4 | 1 | ≤ −20 | −1 | `test_validate_decompose` | rg |
| F17 | epic_paths docstring | claims v1 fallback | rewrite | C4 | 0 code | 0 | 0 | hooks tests | docstring vs tests |
| F18 | arm `decompose-` | deprecated still arms | deny after migrate proof | C4 | 1 | ≤ 0 | 0 | transition/layout tests | rg |

---

## Deletion budget

| Scope | Expected net |
|-------|--------------|
| resolve branches / swallow | LOC ≤ 0 (prefer −) |
| legacy schema constants | symbols ≤ 0 |
| thin validate alias | −1 symbol |
| obsolete multi-path tests | consolidate, not grow |

## Concept budget

| Concept | Before | After |
|---------|--------|-------|
| Plan resolve strategies in `plan_path` | 3–4 | 1 |
| Index authoritative formats when both exist | md-prefer | yaml |
| Path helper modules | 3 overlapping | 1 owner + optional thin re-export (copies_removed if re-export deleted) |
| New resolvers | forbidden without copies_removed ≥ 1 | 0 |

---

## Test refactor

- Strengthen denial: exception in intermediate resolver must not silently succeed via flat/v2 hardcoded.
- Rewrite tests that assert md-over-yaml authority.
- SCHEMA_LEGACY: replace accept tests with deny/migrate cases after inventory.
- Keep migrate CLI tests if CLI retained; separate from live arm.
- Same-epic production + test consolidate.

---

## Replacement / sunset

### A. Code
| Устаревает | Замена | Policy |
|------------|--------|--------|
| multi-branch `plan_path` | sole `epic_layout`(/paths) | delete branches in-epic |
| md-prefer when yaml exists | yaml SoT | delete branch |
| unused `SCHEMA_*_LEGACY` | deny | delete after inventory |
| `validate_decompose_yaml` alias | full validator | delete if safe |

### B. Entrypoints
| Устаревает | Замена | Policy |
|------------|--------|--------|
| arm `decompose-` without migrate | v2 only / migrate CLI | deny in-epic after proof |

### C. Fallbacks
| Устаревает | Замена | Policy |
|------------|--------|--------|
| except pass → next resolver | propagate / explicit miss | delete in-epic |

### I. Instructions
| Устаревает | Замена | Policy |
|------------|--------|--------|
| «falling back to legacy v1» | v2-only / deny | rewrite in-epic |

---

## HOW spine

```text
role-map path modules
  → sole plan_path/resolve_epic_slug
  → yaml-prefer index load
  → SCHEMA inventory → deny/keep-split
  → docstring + Kind I
  → arm decompose- deny if migrate proven
  → rg AC−
```

---

## Failure matrix

| Link | Failure | Detection | Response | Test |
|------|---------|-----------|----------|------|
| flat epic still in wild | resolve miss | inventory | migrate tool / explicit error | TM-096-01 |
| swallow left | silent wrong path | code review + test | block | TM-096-02 |
| SCHEMA deny early | shards fail validate | inventory | keep-split + queue follow-up | TM-096-03 |

---

## До DECOMPOSE (черновик)

1. Characterize path APIs + inventory flat/legacy shards.
2. Sole `plan_path` / `resolve_epic_slug`; remove swallow.
3. Yaml-prefer `load_steps_for_index`.
4. SCHEMA_LEGACY + validate alias decision.
5. Docstring/Kind I + arm `decompose-` policy.
6. Final purge scan + denial tests.

---

## QA consumes draft

| ID | P | Scenario | Command | Expected |
|----|---|----------|---------|----------|
| TM-096-01 | P0 | plan resolve v2 | `bin/pytest loop/tests/test_roadmap_queue.py loop/tests/test_epic_layout_v2_denial.py -q` | PASS |
| TM-096-02 | P0 | index yaml SoT | `bin/pytest loop/tests/test_index_fail_closed.py -q` | PASS |
| TM-096-03 | P0 | epic_paths denial | `bin/pytest harness/hooks/tests/test_epic_paths.py loop/tests/test_epic_paths.py -q` | PASS; no v1-fallback prose |
| TM-096-04 | P1 | epic_yaml schemas | `bin/pytest harness/hooks/tests/test_epic_yaml.py -q` | deny/migrate as planned |
| TM-096-05 | P0 | validate decompose | `bin/pytest loop/tests/test_validate_decompose.py -q` | PASS |
| TM-096-06 | P0 | AC− rg multi-resolve/swallow | plan controls | 0 swallow-pass; sole owner |
| TM-096-07 | P1 | full suite QA | `bin/pytest -q --tb=line` | PASS |

---

## Review readiness

| Gate | Status |
|------|--------|
| Clusters C4 | done |
| Inventory F09–F18 | done |
| Budgets | done |
| Test refactor | done |
| Sunset A+B+C+I | done |
| QA consumes | done |
| CRITICAL open | none (SCHEMA inventory is IMPLEMENT gate, not open CRITICAL) |

## Appetite

| Поле | Значение |
|------|----------|
| `timebox_days` | 2–3 |
| `cut_list` | new layout kinds; epic_lib; offline adapt live restore |

## Следующий режим

→ после 095 DECOMPOSE/IMPLEMENT order per queue; this epic **BACK DECOMPOSE T-HUB-096-layout-resolve-sole-path**.
