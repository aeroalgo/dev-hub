# [T-HUB-097 | event-dag-offline-adapter-hygiene] PLAN

**Дата:** 2026-09-14  
**Режим:** BACK PLAN REFACTOR (multi-epic cut)  
**Уровень:** L2–L3  
**Статус:** active  
**Clarify:** [memory-bank/back/clarify/clarify-20260912-plan-refactor.md](../../../clarify/clarify-20260912-plan-refactor.md)  
**Prompt:** [md/prompt.md](prompt.md)  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `plan-refactor-leftover-20260914` · `kind: refactor`  
**Deps:** — (soft after T-HUB-095/096)  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns · python-anti-patterns  
**Источник:** BACK PLAN REFACTOR; post T-HUB-089 live purge leftover offline surface

---

## Epic cut (нарезка)

| ID | Ось | Clusters | Deps |
|----|-----|----------|------|
| T-HUB-095 | Epic runtime import sole path | C1 + C2 | — |
| T-HUB-096 | Layout/plan resolve sole path | C4 | — |
| T-HUB-097 | Offline event/DAG adapter + test hygiene | C3 + C5 | — |

---

## Контекст

- **req:** Live arm уже не вызывает `adapt_manifest` / `adapt_v1_event` (089 + rg). Остаются offline tools (`migrate_manifest`, `migrate_event_log`, `adapt_*`) и **пересекающиеся** characterization/legacy tests (`test_dag_*`, `test_event_legacy_adapter`, `test_migration_compatibility`, `test_t035_invariants`, …), которые могут читаться как «runtime success».
- **gap:** semantic twin = «legacy adapt as live SoT» в test/docs meaning; code copies of offline adapters may stay if extracted/labeled.
- **refs:** `loop/dag.py` adapt/migrate; `harness/hooks/epic_events.py` adapt_v1_event; `queue_rel_from_roadmap` md map; audit T-HUB-089.
- **Не:** возврат v1 в live arm; epic_lib; layout multi-resolve; behavior change migrate algorithms.

### CREATIVE need
**нет**

---

## Baseline

Общий baseline batch — см. T-HUB-095. Live proof: `adapt_manifest` not called from `_arm_dag_next` / context_loop (rg=0).

---

## Delivery closure

| Capability / outcome | Classification | Production entrypoint and caller | Success / failure enforcement | Independent outcome test | Foundation approval / follow-up |
|---|---|---|---|---|---|
| Offline-only migrate tools | `vertical_slice` | CLI/migrate entrypoints only | live readers never call adapt_* | characterization asserts not-called + live validate path | `n/a` |
| Consolidated legacy test suite | `vertical_slice` | pytest offline module | no duplicate success-as-runtime | one suite; deleted dup cases | `n/a` |

---

## Technology axiom

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Live events/DAG | v2 validate-only | adapt_* in live read/arm |
| Offline migrate | explicit migrate entrypoint | silent dual path from arm |
| Tests | behavior/deny oracle | adapt_* green as runtime SoT |

---

## Product probe

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Reframe | Leftover offline tools + dup tests blur 089 success | Label/extract + consolidate tests |
| 2 | Wedge | Prove live ≠ adapt; merge overlapping tests | C5 first measurable −copies |
| 3 | Pre-mortem | Delete adapt_* entirely breaks migrate CLI users | keep-split offline, not delete-blind |
| 4 | Adoption | Same migrate CLI if retained | docs Kind I |
| 5 | Leverage | No new adapter (extract only if ≥2 live translators — N/A); for tests extract shared fixtures with copies_removed ≥ 1 | |
| 6 | Appetite | 1–2 days | queue_rel md map only if callers allow |

---

## WHAT

Offline migrate остаётся явным offline; live path fail-closed на v2; дублирующие characterization assertions слиты — нельзя принять adapt_* за runtime SoT.

### User Stories

| # | Story | P | Independent Test |
|---|-------|---|------------------|
| US-001 | Как runtime, live event/DAG не вызывает adapt_* | P0 | rg + not-called tests |
| US-002 | Как maintainer, одна offline characterization suite | P0 | dup cases removed; coverage retained |
| US-003 | Как оператор, migrate CLI (если retained) явно offline | P1 | entrypoint docs + import path |

### Functional Requirements

- **FR-001:** Re-assert live `read_event_log` / DAG arm never call `adapt_*` (control tests remain).
- **FR-002:** Classify `adapt_manifest` / `migrate_manifest` / `adapt_v1_event` / `migrate_event_log` as offline-only; extract to `loop/migrate/` **only if** that removes ≥1 duplicate ownership surface (copies_removed ≥ 1) — else keep-split in place with hard comments + Kind I (no new module without deletion).
- **FR-003:** Consolidate overlapping characterization tests into one offline suite; delete redundant cases (`copies_removed_count ≥ 1` of same assertion meaning).
- **FR-004:** `queue_rel_from_roadmap` md→queue map: delete if no CLI/docs callers; else keep-split with explicit legacy CLI contract.
- **FR-005:** Kind I: instructions must not present adapt_* as live success path.
- **FR-006:** No restoration of live v1 fallbacks.

### AC−

1. Нет live call sites to adapt_*.
2. Нет N files asserting identical «adapt succeeds as runtime» without offline label.
3. Нет нового migrate package без удаления старого owner surface.
4. Behavior of migrate algorithms unchanged (freeze oracle offline tests).

---

## Consolidation clusters

| cluster_id | members | canonical_owner | action | why |
|------------|---------|-----------------|--------|-----|
| C3 | adapt_manifest, migrate_manifest, adapt_v1_event+migrate_event_log, queue_rel md map | offline migrate owner + live v2 validators | **extract** or **keep-split** | live already sole; leftover offline |
| C5 | overlapping DAG/event legacy tests | one offline characterization module | **merge** | same assertion meaning × N |

---

## Refactor inventory

| ID | Path / symbol | Evidence | Action | cluster | copies_removed | net_loc | net_sym | freeze_oracle | proof |
|----|---------------|----------|--------|---------|----------------:|--------:|--------:|---------------|-------|
| F06 | `loop/dag.py:adapt_manifest/migrate_manifest` | live arm not called | extract or keep-split | C3 | ≥1 if extract deletes live-adjacent owner confusion | ≤ 0 | ≤ 0 | `test_dag_scheduler` not-called; migrate tests | rg context_loop=0 |
| F07 | `epic_events.adapt_v1_event` | only `migrate_event_log` | keep-split or extract | C3 | ≥1 if module split removes dual reading | ≤ 0 | ≤ 0 | `test_event_legacy_adapter` | body scan |
| F16 | characterization overlap | multiple test files | merge | C5 | ≥3 redundant cases | ≤ 0 | ≤ 0 | retained offline suite | rg -c adapt_manifest |
| F19 | `queue_rel_from_roadmap` | md map | delete or keep | C3 | 1 if delete | ≤ 0 | ≤ 0 | `test_roadmap_queue` | rg callers |

---

## Deletion budget / Concept budget

| Scope | Target |
|-------|--------|
| Redundant test cases | −copies ≥ 3 assertions/cases |
| Live adapt call sites | stay 0 (no growth) |
| New modules | only with copies_removed ≥ 1 of ownership surface |
| Public live symbols | ≤ 0 delta (prefer − if delete queue_rel dead) |

---

## Test refactor

- Keep single offline suite proving migrate behavior + live not-called.
- Delete duplicate cases across `test_dag_manifest`, `test_dag_generate`, `test_t035_invariants`, `test_dag_v2_characterization`, `test_migration_compatibility`, `test_event_legacy_adapter` where assertion meaning identical.
- Forbidden: delete coverage without naming replacement oracle.
- Same-epic consolidate.

---

## Replacement / sunset

### A. Code
| Устаревает | Замена | Policy |
|------------|--------|--------|
| Dup test cases | one offline suite | delete in-epic |
| Ambiguous live-adjacent adapt exports | offline entrypoint only | extract **or** keep-split + Kind I |
| Unused `queue_rel` md map | DEFAULT_QUEUE paths only | delete if callers=0 |

### B/C
| Устаревает | Замена | Policy |
|------------|--------|--------|
| Docs implying adapt in arm | validate-only live | Kind I |
| Soft «adapt if validate fails» | never | already purged — keep purged |

### I
| Устаревает | Замена | Policy |
|------------|--------|--------|
| Instructions teaching adapt as normal path | offline migrate only | rewrite |

---

## HOW spine

```text
rg live adapt call sites (=0 control)
  → inventory test assertion twins
  → consolidate offline suite (delete dups)
  → decide extract vs keep-split adapters (budget)
  → queue_rel caller proof
  → Kind I
  → AC− scan
```

---

## Failure matrix

| Link | Failure | Detection | Response | Test |
|------|---------|-----------|----------|------|
| extract without delete | concept growth | concept budget | forbid extract | TM-097-01 |
| over-delete migrate | CLI break | migrate tests | keep-split | TM-097-02 |
| live regress | adapt called | rg + not-called | halt | TM-097-03 |

---

## До DECOMPOSE (черновик)

1. Control: live adapt call sites = 0 + list test twins.
2. Merge characterization suite; delete dups.
3. Adapter placement decision (extract only with copies_removed).
4. queue_rel policy.
5. Kind I + final scan.

---

## QA consumes draft

| ID | P | Scenario | Command | Expected |
|----|---|----------|---------|----------|
| TM-097-01 | P0 | live not-called | `bin/pytest loop/tests/test_dag_scheduler.py loop/tests/test_event_v2_characterization.py -q` | PASS; adapt not in live path |
| TM-097-02 | P0 | offline migrate retained behavior | `bin/pytest loop/tests/test_event_legacy_adapter.py loop/tests/test_migration_compatibility.py -q` (post-consolidate paths) | PASS |
| TM-097-03 | P0 | rg live adapt | `rg -n 'adapt_manifest\|adapt_v1_event' loop harness/hooks --glob '*.py'` filtered to live callers | 0 live |
| TM-097-04 | P1 | dup assertion count ↓ | test inventory receipt | copies_removed ≥ 1 |
| TM-097-05 | P1 | full suite QA | `bin/pytest -q --tb=line` | PASS |

---

## Review readiness

| Gate | Status |
|------|--------|
| Clusters C3+C5 | done |
| Inventory | done |
| Budgets | done |
| Test refactor | done |
| Sunset | done |
| QA consumes | done |
| CRITICAL | none |

## Appetite

| Поле | Значение |
|------|----------|
| `timebox_days` | 1–2 |
| `cut_list` | delete all migrate tools; reopen live v1 |

## Следующий режим

→ **BACK DECOMPOSE** per queue order (095 first).
