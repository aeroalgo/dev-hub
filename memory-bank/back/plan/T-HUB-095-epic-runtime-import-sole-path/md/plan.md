# [T-HUB-095 | epic-runtime-import-sole-path] PLAN

**Дата:** 2026-09-14  
**Режим:** BACK PLAN REFACTOR (multi-epic cut)  
**Уровень:** L3  
**Статус:** active  
**Clarify:** [memory-bank/back/clarify/clarify-20260912-plan-refactor.md](../../../clarify/clarify-20260912-plan-refactor.md)  
**Prompt:** [md/prompt.md](prompt.md)  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `plan-refactor-leftover-20260914` · `kind: refactor`  
**Deps:** —  
**Unlocks:** T-HUB-096 (soft order), T-HUB-097  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns · python-design-patterns · python-anti-patterns  
**Источник:** BACK PLAN REFACTOR Phase 0 Clarify Q1=B; inventory post T-HUB-087…090

---

## Epic cut (нарезка)

| ID | Ось | Clusters | Deps |
|----|-----|----------|------|
| T-HUB-095 | Epic runtime import sole path | C1 + C2 | — |
| T-HUB-096 | Layout/plan resolve sole path | C4 | — |
| T-HUB-097 | Offline event/DAG adapter + test hygiene | C3 + C5 | — |

**MULTI-EPIC PLAN — 3 эпика.** Cut по независимому meaning / дереву / риску, не по слоям внутри одной фичи.

---

## Контекст

- **req:** После 087–090 live v1 event/DAG/roadmap fallbacks сняты, но остаётся twin import surface: `epic_lib` facade (~18 prod/test import sites) рядом с `epic` / `harness.hooks.epic.core`, triple-try в `pretool_policy._load_epic_state`, mock-intercept под несколько module names, plus zero-caller aliases `auto_finish_after_gate` и `DEFAULT_ROADMAP`.
- **gap:** dual SoT для одного meaning (epic runtime helpers) + dead compat names.
- **refs:** inventory session 2026-09-14; `harness/hooks/epic_lib.py`; `harness/hooks/pretool_policy.py`; `loop/runtime_adapters/subagent_lifecycle.py`; `loop/roadmap_queue.py`; graphify-out (stale 2026-09-10 — не sole proof).
- **Не:** layout multi-resolve (096); offline adapt_* (097); смена finish/lifecycle семантики; LLM env-parse twins (out of theme).

**CREATIVE need:** нет.

---

## Baseline (scan scope B)

| Metric | Value | Command / note |
|--------|------:|----------------|
| `loop/` prod files / LOC | 193 / 39 237 | rglob `*.py` excl tests |
| `harness/hooks/` prod | 47 / 27 586 | same |
| Combined prod | 240 / 66 823 | scope B trees |
| Combined tests | 369 / 76 475 | `loop/tests` + `harness/hooks/tests` |
| Graph | usable w/ limits | `graphify-out/graph.json` mtime 2026-09-10; stale fan-in — verify with rg |
| Exclusions | memory-bank artifacts, `.venv`, `__pycache__`, vendor, graphify-out | declared |

---

## Delivery closure

| Capability / outcome | Classification | Production entrypoint and caller | Success / failure enforcement | Independent outcome test | Foundation approval / follow-up |
|---|---|---|---|---|---|
| Sole epic-runtime import owner | `vertical_slice` | hooks/loop callers → `epic` / `harness.hooks.epic.core` | `epic_lib` import fail or module gone; triple-try removed | import scan + finish/state targeted tests | `n/a` |
| Dead alias purge | `vertical_slice` | `gate_atomic_finish`, `DEFAULT_QUEUE` | deleted symbols absent | rg zero + alias-owner tests | `n/a` |

---

## Technology axiom

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Epic helpers SoT | package `epic` / `harness.hooks.epic.core` | `epic_lib` as live facade |
| State load | single import path | try/except chain across 3 module names |
| Compat delete | static caller proof | restore alias «на всякий» |
| Behavior | existing function contracts | rename-only without deleting twin |

As-built = sunset inventory only.

---

## Product probe

| # | Question | Answer / Probe | Decision / Impact |
|---|----------|----------------|-------------------|
| 1 | Reframe | Twin import surface hides canonical owner after package extract | Sole path = done signal |
| 2 | Narrowest wedge | Delete zero-caller aliases + rewire `epic_lib` callers | C2 first inside epic, then C1 |
| 3 | Pre-mortem | Monkeypatch tests still patch `epic_lib` → false green | Test consolidate mandatory |
| 4 | Distribution | Same hooks/loop entrypoints; no new CLI | Kind I rewrite only |
| 5 | Technical leverage | Drop facade module entirely after rewire | copies_removed ≥ 1 |
| 6 | Appetite | 2–3 days; no layout/offline in this epic | cut_list = 096/097 |

---

## WHAT

Один канонический owner для epic-runtime helpers; facade и мёртвые aliases нельзя использовать без ошибки; поведение функций неизменно.

### User Stories

| # | Story | P | Independent Test |
|---|-------|---|------------------|
| US-001 | Как maintainer, я импортирую helpers только из canonical epic package | P0 | rg: no live `epic_lib` prod imports; state load works via one path |
| US-002 | Как runtime, я не маскирую ImportError цепочкой facade | P0 | `_load_epic_state` single import; missing module → explicit fail |
| US-003 | Как maintainer, zero-caller aliases удалены | P0 | `auto_finish_after_gate` / `DEFAULT_ROADMAP` absent; owners remain |

#### Acceptance Scenarios — US-001

- **Given:** hooks/loop production code that previously imported `epic_lib`
- **When:** module loads / finish integrity path runs
- **Then:** symbols resolve from `epic`/`epic.core` only; behavior unchanged vs freeze oracle

#### Acceptance Scenarios — US-002

- **Given:** `pretool_policy` needs epic state
- **When:** canonical module missing or present
- **Then:** no silent fallback to second/third module name

#### Acceptance Scenarios — US-003

- **Given:** inventory proved zero prod callers
- **When:** purge step completes
- **Then:** aliases gone; `gate_atomic_finish` / `DEFAULT_QUEUE` still work

### Functional Requirements

- **FR-001:** Rewire all production `epic_lib` imports to canonical `epic` / `harness.hooks.epic.core`.
- **FR-002:** Delete `harness/hooks/epic_lib.py` after rewire **or** reduce to fail-closed stub that raises (prefer delete).
- **FR-003:** Collapse `pretool_policy._load_epic_state` to one import; remove silent `except` chain.
- **FR-004:** Remove or justify `_legacy_mock_intercept` only if tests patch canonical owner; rewrite tests first.
- **FR-005:** Delete `auto_finish_after_gate`; keep `gate_atomic_finish`.
- **FR-006:** Delete `DEFAULT_ROADMAP`; keep `DEFAULT_QUEUE`.
- **FR-007:** Collapse `find_qa_pass_artifact` alias to one public name (or keep one name, delete the other) after caller rewire.
- **FR-008:** Simplify `epic/__init__.py` discover/mark facades so one definition lives in `core` (copies_removed ≥ 1).
- **FR-009:** Rewrite/delete obsolete tests that require `epic_lib` or multi-module monkeypatch; freeze behavior via targeted suite.
- **FR-010:** Kind I: prompts/rules/memory-bank implement shards that teach `from epic_lib import` → rewrite in-epic (only paths in shard `files:` at IMPLEMENT).

### Success Criteria

| ID | Результат | Проверка |
|----|-----------|----------|
| SC-001 | 0 prod `epic_lib` imports | `rg 'from epic_lib\|import epic_lib' loop harness/hooks --glob '*.py'` (tests may fail-closed assert absence) |
| SC-002 | single state-load import | read `pretool_policy._load_epic_state` |
| SC-003 | dead aliases gone | rg symbol = 0 |
| SC-004 | freeze oracle green | targeted pytest listed in QA consumes |

### AC−

1. Нет dual live import surface (`epic_lib` + `epic`) для одних helpers.
2. Нет silent try/except module fallback.
3. Нет zero-caller public aliases из inventory.
4. Нет obsolete tests, требующих удалённый facade.
5. Нет роста public symbols/owners (concept budget ≤ 0).

---

## Clarifications

- Session: clarify-20260912-plan-refactor · Q1 → **B**
- Queue на момент PLAN: `queue: []` (092–094 в done)

---

## Consolidation clusters

| cluster_id | members | canonical_owner | action | why |
|------------|---------|-----------------|--------|-----|
| C1 | `epic_lib` facade; `epic/__init__` discover/mark wrappers; dual `epic.core` vs `harness.hooks.epic.core` imports; `pretool_policy` triple-try; `_legacy_mock_intercept`; `find_qa_pass_artifact` alias | `harness/hooks/epic/core.py` (package `epic`) | **merge** | one meaning — epic runtime helpers |
| C2 | `auto_finish_after_gate`; `DEFAULT_ROADMAP` | `gate_atomic_finish`; `DEFAULT_QUEUE` | **delete** | zero external callers (rg) |

---

## Refactor inventory

| ID | Path / symbol | Evidence | Action | cluster_id | canonical_owner | copies_removed_count | net_loc_delta | net_symbol_delta | behavior_freeze_oracle | proof |
|----|---------------|----------|--------|------------|-----------------|---------------------:|--------------:|-----------------:|------------------------|-------|
| F01 | `harness/hooks/epic_lib.py` | ~18 import sites; docstring «Backward-compatible facade» | merge/delete module | C1 | `epic.core` | ≥1 module + import sites | ≤ −20 | ≤ −1 module | `loop/tests/test_finish_integrity.py`, `test_epic_lib.py`→rewrite | rg imports |
| F02 | `epic/__init__.py` discover/mark facades | triple definitions with `core` | simplify | C1 | `epic.core` | ≥2 wrappers | ≤ 0 | ≤ −2 | `test_epic_lib*.py` | rg `^def discover_epic` |
| F03 | `find_qa_pass_artifact` | alias of `latest_qa_pass_artifact_for_reference` | merge name | C1 | one public name | 1 | ≤ 0 | ≤ −1 | `test_epic_lib.py` | rg |
| F04 | `auto_finish_after_gate` | def only in prod | **delete** | C2 | `gate_atomic_finish` | 1 | ≤ −15 | −1 | `test_subagent_lifecycle.py` | rg callers=0 |
| F05 | `DEFAULT_ROADMAP` | identical to `DEFAULT_QUEUE`; def only | **delete** | C2 | `DEFAULT_QUEUE` | 1 | ≤ −3 | −1 | `test_roadmap_queue.py` | rg callers=0 |
| F08 | `pretool_policy._load_epic_state` | try core → epic.core → epic_lib | simplify | C1 | one import | 2 branches | ≤ −10 | 0 | pretool / finish-boundary | read L117–138 |
| F12 | `_legacy_mock_intercept` | arm path honors multi-module mocks | delete after test rewrite | C1 | patch `epic.core` only | 1 | ≤ −20 | −1 | `test_epic_transition.py` | rg |

Uncertain (not commit): dynamic PYTHONPATH packaging that still requires `epic_lib` name for external plugins — if found at IMPLEMENT inventory → FAIL-closed keep with follow-up ID (none found in hub scan).

---

## Deletion budget

| Scope | Expected | Net |
|-------|----------|-----|
| `epic_lib` module + rewire | −23 LOC module + churn imports | net LOC ≤ 0 |
| dead aliases C2 | −2 symbols | −2 |
| mock intercept + triple-try | −1 fn, −2 branches | ≤ 0 |
| obsolete tests rewrite | merge/delete facade-only cases | suite not grow concepts |

**Target:** `net_loc_delta ≤ 0`, `net_symbol_delta ≤ 0`, `copies_removed_count ≥ 1` per extract/merge row.

---

## Concept budget

| Concept | Before (approx) | After target |
|---------|-----------------|--------------|
| Import surfaces for epic helpers | 3 (`epic_lib`, `epic`, `harness.hooks.epic.core`) | 1–2 max (`epic` package; dotted harness path = same package if wired) |
| Public aliases (C2) | 2 | 0 |
| State-load fallback branches | 3 | 1 |
| New helpers/adapters | 0 allowed without copies_removed ≥ 1 | 0 |

---

## Test refactor

- Rewrite `loop/tests/test_epic_lib.py` / `test_finish_integrity.py` imports to canonical package; delete cases that only assert facade re-export.
- Monkeypatch suites (`test_epic_transition`, creative/episode) patch `epic.core` / `epic` only.
- Add negative test: `epic_lib` absent or import raises (if module deleted).
- Keep behavior assertions on `gate_atomic_finish`, `load_epic_state`, finish integrity — freeze oracle.
- Production merge + test consolidate **same epic** (no standalone test-cleanup epic).

---

## Replacement / sunset

### A. Code / modules

| Устаревает | Замена | Policy |
|------------|--------|--------|
| `epic_lib.py` | `epic` / `epic.core` | delete in-epic |
| `auto_finish_after_gate` | `gate_atomic_finish` | delete in-epic |
| `DEFAULT_ROADMAP` | `DEFAULT_QUEUE` | delete in-epic |
| triple-try `_load_epic_state` | single import | delete branches in-epic |
| `_legacy_mock_intercept` | patch canonical | delete in-epic after tests |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
|------------|--------|--------|
| PYTHONPATH docs teaching `epic_lib` | `epic` package | Kind I rewrite |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
|------------|--------|--------|
| ImportError → next module name | fail-closed | delete in-epic |

### I. Instruction surfaces

| Устаревает | Замена | Policy |
|------------|--------|--------|
| implement/plan shards `from epic_lib import … OK` | canonical import | rewrite/delete in-epic |
| workflow examples naming facade | `epic` | rewrite |

---

## HOW (spine — не код)

```text
inventory callers (rg)
  → rewrite prod imports to epic.core
  → rewrite tests/monkeypatch
  → delete epic_lib + dead aliases
  → enforce: import epic_lib fails / absent
  → Kind I purge
```

Function merge ladder: delete dead (C2) → merge twins (C1) → extract only if ≥2 callers remain after merge → move N/A → simplify signatures N/A.

---

## Failure matrix

| Link | Failure | Detection | Response | Test |
|------|---------|-----------|----------|------|
| rewire miss | leftover `epic_lib` import | rg gate | block FINISH | TM-095-01 |
| behavior drift | finish/state mismatch | freeze oracle | revert step | TM-095-02 |
| mock intercept remove early | transition tests red | pytest | rewrite patches first | TM-095-03 |
| alias restore | symbol reappears | rg AC− | fail | TM-095-04 |

---

## До DECOMPOSE (черновик sNN)

1. Characterize import graph + freeze oracle baseline (red/green).
2. Purge C2 dead aliases + tests.
3. Rewire prod `epic_lib` → `epic`; collapse `_load_epic_state`.
4. Rewrite monkeypatch / delete intercept; collapse QA alias / `__init__` facades.
5. Delete `epic_lib.py`; Kind I rewrite; final rg enforce.
6. Legacy-fallback purge scan (AC−).

Advisory band 5–8 steps — DECOMPOSE владеет финальной нарезкой.

---

## QA consumes draft

| ID | P | Scenario | Command / fixture | Expected | Maps |
|----|---|----------|-------------------|----------|------|
| TM-095-01 | P0 | no prod epic_lib | `rg -n 'from epic_lib\|import epic_lib' loop harness/hooks --glob '*.py'` | 0 (or tests asserting denial only) | FR-001/002 |
| TM-095-02 | P0 | finish integrity | `bin/pytest loop/tests/test_finish_integrity.py -q` | PASS | FR-001 |
| TM-095-03 | P0 | subagent lifecycle alias gone | `bin/pytest loop/tests/test_subagent_lifecycle.py -q` | PASS; no `auto_finish_after_gate` | FR-005 |
| TM-095-04 | P0 | roadmap queue const | `bin/pytest loop/tests/test_roadmap_queue.py -q` | PASS; no `DEFAULT_ROADMAP` | FR-006 |
| TM-095-05 | P0 | epic transition patches | `bin/pytest loop/tests/test_epic_transition.py -q` | PASS | FR-004 |
| TM-095-06 | P1 | pretool single import | read + targeted pretool/hooks tests | one import path | FR-003 |
| TM-095-07 | P0 | AC− symbol scan | plan rg controls | zero deleted symbols | AC− |
| TM-095-08 | P1 | full suite (QA only) | `bin/pytest -q --tb=line` | PASS | SC-004 |

---

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| Product probe | L3 | done | §Product probe |
| Baseline | required | done | §Baseline |
| Consolidation clusters | required | done | C1+C2 |
| Refactor inventory | required | done | F01–F12 |
| Deletion / concept budget | required | done | sections |
| Test refactor | required | done | §Test refactor |
| Sunset A+B+C+I | required | done | §Replacement |
| QA consumes ≥3 | required | done | TM-095-01…08 |
| Open CRITICAL | none | — | — |

## Plan review batch log

| Phase | Auto-resolved | Deferred | Decision |
|-------|---------------|----------|----------|
| Product | facade is leftover twin, not feature | external plugin needing `epic_lib` name | hub scan zero; IMPLEMENT re-scan before delete |
| Eng | C2 fold into this epic (not separate) | layout/offline | 096/097 |

## Appetite

| Поле | Значение |
|------|----------|
| `timebox_days` | 2–3 |
| `cut_list` | layout resolve; offline adapters; LLM env dedupe |

## Следующий режим

→ **BACK DECOMPOSE T-HUB-095-epic-runtime-import-sole-path** после queue reconcile.
