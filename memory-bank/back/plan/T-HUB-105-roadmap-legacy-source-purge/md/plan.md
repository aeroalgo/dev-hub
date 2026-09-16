# [T-HUB-105 | roadmap-legacy-source-purge] PLAN

**Дата:** 2026-09-16  
**Режим:** BACK PLAN REFACTOR (multi-epic cut)  
**Уровень:** L2  
**Статус:** active  
**Clarify:** Phase 0 skipped — taxonomy clear; user forced PLAN REFACTOR (scan scope B)  
**Prompt:** [md/prompt.md](prompt.md)  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `plan-refactor-leftover-20260916` · `kind: refactor`  
**Deps:** —  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns · python-design-patterns · python-anti-patterns  
**Источник:** BACK PLAN REFACTOR inventory 2026-09-16

---

## Epic cut (нарезка)

| ID | Ось | Clusters | Deps |
|----|-----|----------|------|
| T-HUB-103 | Event schema SoT unify | C1 | — |
| T-HUB-104 | Plan-path classifier + board_sync helper | C2 + C3 | — |
| T-HUB-105 | Roadmap legacy source + orchestrator import | C7 + D1 | — |

**MULTI-EPIC PLAN — 3 эпика.**

---

## Контекст

- **req:** `discover_source_queues` всё ещё сканирует live `memory-bank/<role>/plan/roadmap-*-epics.queue.yaml`, хотя live файлов = **0** (остались только `roadmap/archive/`). `queue_rel_from_roadmap` мапит legacy `.md` → `.queue.yaml`. `loop/runner/orchestrator.py` делает `from loop.epic_paths import epic_dir` внутри `try/except Exception: pass` — модуль `loop.epic_paths` для `epic_dir` не является live SoT (silent no-op trace/tier1 path).
- **gap:** legacy discovery/map + silent broken import как dual/dead paths.
- **refs:** `loop/roadmap_queue.py:43`, `:1126`, `:1280`; `loop/runner/orchestrator.py:67,87`; tests `test_queue_rel_from_roadmap`, `test_dag_v2_characterization` path asserts.
- **Не:** event schema; plan classifiers; удаление `roadmap/batches/*.yaml` discovery если ещё используется.

**CREATIVE need:** нет.

---

## Baseline (scan scope B)

См. T-HUB-103 §Baseline. Proof live slug queues: `Glob plan/roadmap-*-epics.queue.yaml` → 0; archive only.

---

## Consolidation clusters

| cluster_id | members | meaning | canonical_owner | action | why |
|---|---|---|---|---|---|
| C7 | `discover_source_queues` plan-dir branch; archive-only slug queues | discover optional merge sources | `discover_source_queues` batches-only (canon `queue.yaml` never source) | **merge/simplify** — delete plan-dir scan arm | live plan-dir sources = 0; archive is provenance not merge input |
| C7b | `queue_rel_from_roadmap` `.md` → `.queue.yaml` | map roadmap path to machine queue | canon `…/roadmap/queue.yaml` only for live | **delete or fail-closed** on `.md` input | legacy map keeps dual SoT illusion |
| D1 | `orchestrator` `loop.epic_paths.epic_dir` + bare except | resolve epic dir for trace/tier1 | `harness.hooks.epic_paths.epic_dir` (or documented loop paths API that exists) | **delete** broken import path; **wire** canonical | silent pass hides missing owner |

---

## Refactor inventory

| ID | path/symbol | evidence | category | action | cluster_id | canonical_owner | copies_removed_count | net_loc_delta | net_symbol_delta | behavior_freeze_oracle | proof |
|---|---|---|---|---|---|---|---:|---:|---:|---|---|
| F-105-01 | `discover_source_queues` plan_dir loop | live glob 0 files; only archive copies | dead | **delete** plan-dir scan block | C7 | batches dir scan only | 1 | −25 | 0 | `bin/pytest loop/tests/test_roadmap_queue.py -k discover -q` / merge tests | Glob + rg |
| F-105-02 | `queue_rel_from_roadmap` `.md` branch | tests assert md→queue.yaml | shim | **fail-closed** ValueError/typed error on `.md` **or** delete helper if only legacy callers | C7b | `canon_queue_rel` / explicit queue.yaml | 1 | −5…−40 | ≤0 | update tests: md input errors; bare roadmap & queue.yaml still map | callers rg |
| F-105-03 | characterization asserts on md map | `test_dag_v2_characterization.py:306+` | obsolete test | **rewrite** to deny expectation | C7b | — | 1 | ≤0 | 0 | characterization | suite |
| F-105-04 | `orchestrator` import `loop.epic_paths.epic_dir` | ImportError swallowed | dead/shim | **replace** with canonical `epic_dir`; **remove** bare `except Exception: pass` on that path (fail-closed or scoped log+reraise policy consistent with neighbors — **no silent success**) | D1 | `harness.hooks.epic_paths.epic_dir` | 1 | ≤0 (may +few for correct import) | 0 | `bin/pytest loop/tests/test_runner_orchestrator.py -q` | importlib |

**Note on net_loc for F-105-04:** fixing broken import may add LOC; must be offset by F-105-01/02 deletions so epic net ≤ 0. If fix alone would grow net, fold extra dead branch deletion in same epic (plan-dir scan) — already listed.

---

## Delivery closure

| Capability | Classification | Entrypoint | Enforcement | Independent test | Follow-up |
|---|---|---|---|---|---|
| Roadmap source discovery sole live path | vertical_slice | merge_queues → discover_source_queues | plan-dir scan absent; md map denied | roadmap_queue targeted | n/a |
| Orchestrator epic_dir sole import | vertical_slice | orchestrator trace/tier1 | no `loop.epic_paths.epic_dir`; no silent swallow | orchestrator targeted | n/a |

---

## Technology axiom

| Выбор | Machine input | FORBIDDEN |
|-------|---------------|-----------|
| Queue SoT | `memory-bank/<role>/roadmap/queue.yaml` | live merge from `plan/roadmap-*-epics.queue.yaml` |
| Path map | queue.yaml / bare roadmap dir | `.md` roadmap as machine input |
| epic_dir | real module symbol | `except: pass` around missing import |

---

## Product probe

| # | Q | A | Impact |
|---|---|---|---|
| 1 | Reframe | Legacy scan/map + silent import fake health | Purge + fail-closed |
| 2 | Wedge | Delete plan-dir arm (0 live files) | F-105-01 first |
| 3 | Pre-mortem | Someone drops slug queue in plan/ expecting merge | fail-closed; docs Kind I |
| 4 | Adoption | Canon queue already SoT | batches/*.yaml kept if present |
| 5 | Leverage | Remove dead arms | copies_removed ≥1 |
| 6 | Appetite | ≤1 day | out: 103/104 |

---

## WHAT

Live roadmap merge/discovery не читает legacy plan-dir slug queues и не принимает `.md` roadmap как machine map; orchestrator epic_dir импортирует существующий owner без silent swallow; поведение canon queue merge неизменно для batches + queue.yaml.

### User Stories

| # | Story | P | Independent Test |
|---|-------|---|------------------|
| US-001 | Merge не подхватывает plan-dir slug queues | P0 | discover returns no plan-dir paths; merge tests PASS |
| US-002 | `.md` roadmap path не silently maps | P0 | call errors or helper gone; tests updated |
| US-003 | Orchestrator epic_dir работает через canonical import | P0 | import path exists; no bare except success |

#### Acceptance Scenarios — US-001

- **Given:** only archive slug queues exist
- **When:** discover_source_queues runs
- **Then:** plan-dir patterns not scanned / not returned

#### Acceptance Scenarios — US-002

- **Given:** caller passes `…/plan/roadmap-foo-epics.md`
- **When:** queue_rel_from_roadmap (or replacement)
- **Then:** explicit error (or API absent); no `.queue.yaml` fiction for live path

#### Acceptance Scenarios — US-003

- **Given:** orchestrator records trace / tier1
- **When:** needs epic_dir
- **Then:** canonical import resolves; failure is visible if misconfigured

### Functional Requirements

- **FR-001:** Remove plan-dir `roadmap-*-epics.queue.yaml` discovery from live `discover_source_queues`.
- **FR-002:** Remove or fail-closed `.md` branch of `queue_rel_from_roadmap`; rewrite tests.
- **FR-003:** Wire orchestrator to canonical `epic_dir`; delete silent `except Exception: pass` around that import.
- **FR-004:** Keep `roadmap/batches/*.yaml` discovery if still part of supported merge ops (prove with tests); do not delete without caller proof.

### Success Criteria

- **SC-001:** rg plan-dir scan loop absent.
- **SC-002:** md map tests expect deny.
- **SC-003:** no `from loop.epic_paths import epic_dir` in orchestrator.
- **SC-004:** net_loc ≤ 0; net owners ≤ 0.

### AC−

1. Нет live plan-dir slug-queue merge source.
2. Нет silent PASS на broken epic_dir import.
3. Нет dual machine map `.md` ↔ queue без ошибки.
4. Нет зелёных тестов, требующих legacy md map success.

---

## HOW (outline)

1. Prove Glob 0 live plan-dir queues; adjust discover tests.
2. Fail-closed md map; rewrite characterization/unit asserts.
3. Fix orchestrator import; remove swallow; targeted tests.
4. Freeze oracles.

---

## Deletion budget

| Item | Expectation |
|------|-------------|
| Code LOC | ≈ −30…−80 (plan-dir + md branch) + small import fix |
| Test LOC | rewrite ≤0 net preferred |
| Net | **≤ 0** |

---

## Concept budget

| Concept | Before | After | Δ |
|---------|-------:|------:|--:|
| Live queue source roots | canon + batches + plan-dir | canon + batches | −1 |
| Roadmap path map modes | queue/bare/md | queue/bare (md denied) | −1 |
| epic_dir import owners in orchestrator | broken+swallowed | 1 real | −0 broken |

---

## Test refactor

| Action | Target | Replacement |
|--------|--------|-------------|
| rewrite | `test_queue_rel_from_roadmap` md success | expect error |
| rewrite | characterization md assert | deny |
| update | discover/merge tests | no plan-dir expectation |
| update | `test_runner_orchestrator` | canonical epic_dir |

---

## Replacement / sunset

| Sunset | Policy |
|--------|--------|
| A | plan-dir discover arm |
| B | md map success path |
| C | tests requiring md success |
| I | merge docs if mention plan/roadmap-*-epics.queue.yaml as live |

---

## QA consumes draft

1. **TM-01:** discover/merge without plan-dir.
2. **TM-02:** md roadmap input fail-closed.
3. **TM-03:** orchestrator epic_dir canonical; full suite in QA.

---

## Review readiness

| Required | Status |
|----------|--------|
| C7/D1 evidence | done |
| budgets ≤0 | done |
| behavior freeze | done |

---

## Independent Tests (behavior)

- Given canon queue + optional batches, when merge runs, then same membership without plan-dir inputs.
- Given orchestrator audit path, when epic_dir needed, then canonical module used.
