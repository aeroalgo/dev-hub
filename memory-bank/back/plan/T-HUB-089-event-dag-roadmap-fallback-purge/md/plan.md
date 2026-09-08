# [T-HUB-089 | event-dag-roadmap-fallback-purge] PLAN

**Дата:** 2026-09-08  
**Режим:** BACK PLAN REFACTOR  
**Уровень:** L4  
**Статус:** draft  
**Clarify:** Phase 0 skipped — event, DAG and roadmap canonical formats are already defined; this plan only removes their historical adapters after inventory.  
**Prompt:** [md/prompt.md](prompt.md)  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `legacy-fallback-purge-20260908`  
**Deps:** hard T-HUB-087, T-HUB-072 and T-HUB-084; T-HUB-060 is a historical reference, not a queue dependency because it is not in the current merge set.  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns · python-design-patterns · python-anti-patterns

## Контекст и цель

После эпиков T-HUB-060/T-HUB-072 canonical contracts — `loop-event/v2`, `loop-dag/v2` и `roadmap-queue/v2`. Runtime всё ещё умеет адаптировать v1 event logs, v1 DAG manifests, legacy roadmap queues и deprecated Markdown roadmap mirror. Эти ветки смешивают историческое восстановление и live execution.

Цель — отделить одноразовую/архивную миграцию от live runtime, перевести call sites на v2, enforce отказ старых форматов и удалить obsolete adapters/tests. Архивные event logs могут читаться отдельным offline migration tool, но не должны быть fallback live reducer.

## Delivery closure

| Capability / outcome | Classification | Production entrypoint and caller | Success / failure enforcement | Independent outcome test | Foundation approval / follow-up |
|---|---|---|---|---|---|
| Единственные v2 event/DAG/roadmap runtime contracts | `vertical_slice` | event reducer, `_arm_dag_next`, roadmap queue/merge | v1 input → explicit incompatible diagnostic | valid v2 flow + v1 denial | `n/a` |

## Product probe

| Реальная проблема | Wedge | Pre-mortem | Appetite |
|---|---|---|---|
| Исторический формат может незаметно стать live execution input | v2-only live readers with explicit offline migration | старые archive logs потеряются при purge | 4 дня; preserve archive tool, remove live fallback |

## WHAT

### User stories

| ID | Story | Priority | Independent test |
|---|---|---:|---|
| US-001 | Как lifecycle reducer, я хочу читать только canonical event v2 и игнорировать dead history без adapter branch. | P0 | v2 replay passes, v1 live file is rejected, archived dead event remains harmless. |
| US-002 | Как DAG runner, я хочу выполнять только v2 manifest с explicit autonomous contract. | P0 | v2 arm succeeds; v1 manifest fails before execution. |
| US-003 | Как roadmap runner, я хочу одну v2 queue и YAML-only merge. | P0 | v2 queue advance/merge passes; legacy queue/md mirror is not read/written by default. |

### Functional requirements

- **FR-001:** `read_event_log_result` consumes canonical v2 live logs; v1 conversion is removed from live read path.
- **FR-002:** `migrate_event_log` is isolated as explicit offline migration or deleted if no supported consumer remains.
- **FR-003:** `reflection_done` remains a dead historical kind only where required for archive replay; it cannot affect phase or trigger fallback.
- **FR-004:** `loop/context_loop._arm_dag_next` rejects v1 manifests instead of calling `adapt_manifest` implicitly.
- **FR-005:** `QUEUE_VERSION_V1`, `LEGACY_DEFAULT_QUEUE`, legacy plan lookup and Markdown mirror are removed from normal roadmap runtime.
- **FR-006:** `roadmap_merge` writes only `roadmap/queue.yaml`; `canon_md_rel` and `_render_merged_roadmap_md` are removed when no dry-run/API caller remains.
- **FR-007:** v2 behavior, explicit denial and historical archive semantics are covered by tests; adapter-only tests are deleted.

### Success criteria

| ID | Результат | Проверка | Type |
|---|---|---|---|
| SC-001 | no live v1 event/DAG/queue adapters | call-site and branch rg | outcome |
| SC-002 | v2 event/DAG/roadmap flows green | targeted pytest | outcome |
| SC-003 | legacy inputs fail closed | negative fixtures | outcome |
| SC-004 | archive preservation decision is executable | migration/retention tests | outcome |

## Acceptance criteria

1. Live reducer never calls `adapt_v1_event`.
2. Live DAG arm never calls `adapt_manifest` for v1.
3. Default roadmap parser never probes `plan/roadmap-epics.queue.yaml`.
4. No runtime code builds or writes a Markdown roadmap mirror.
5. Archived `reflection_done` remains non-semantic and does not alter lifecycle.
6. Tests retain valid v2 and historical ignore behavior, but delete adapter success tests when adapter is removed.

### AC−

1. Нет v1 adapter invocation from live event/DAG/roadmap call sites.
2. Нет legacy queue fallback when v2 queue is missing.
3. Нет `canon_md_rel`/Markdown mirror production dependency.
4. Нет тестов, которые требуют v1 migration as runtime success.
5. Archive compatibility is explicit, bounded and not a hidden fallback.

## Technology axiom

| Выбор | Machine input | Запрещено после эпика |
|---|---|---|
| Event | `loop-event/v2` | implicit v1 adapter in reducer |
| DAG | `loop-dag/v2` | inferred autonomous execution from v1 |
| Roadmap | `roadmap-queue/v2` YAML | v1 queue and Markdown mirror |
| Archive | explicit offline migration/read tool | archive data as live fallback |

## Refactor inventory

| ID | Path / symbol | Evidence and callers | Action | Replacement owner | Tests |
|---|---|---|---|---|---|
| L89-01 | `harness/hooks/epic_events.py:adapt_v1_event` | called by event reader/migration/replay | remove from live reader; isolate only explicit archive command | v2 event validator | `test_event_legacy_adapter.py`, event stream tests |
| L89-02 | `read_event_log_result` non-v2 branch | raw non-v2 invokes adapter | reject live non-v2 with diagnostic | `validate_event` | event replay tests |
| L89-03 | `migrate_event_log` | physical rewrite of legacy files | keep only if explicit offline CLI is supported; otherwise delete | migration tool boundary | migration compatibility tests |
| L89-04 | `LEGACY_DEAD_EVENT_KINDS`/`reflection_done` | T-HUB-060 requires archive ignore | keep narrow historical classifier, remove live semantic paths | dead-event ignore | `test_event_schema.py`, reducer QA tests |
| L89-05 | `loop/dag.py:migrate_manifest`, `adapt_manifest` | `_arm_dag_next` calls adapter after validation failure | move to explicit migration or delete live call | v2 `validate_manifest` | DAG manifest/transition tests |
| L89-06 | `loop/context_loop.py:_arm_dag_next` | invalid v2/v1 can enter adaptation branch | enforce v2 validation before arm | DAG scheduler | `test_dag_transition.py`, journey tests |
| L89-07 | `loop/roadmap_queue.py:QUEUE_VERSION_V1` and parser fallback | supports v1 and legacy default path | delete v1 runtime support | v2 parser | `test_roadmap_queue.py` |
| L89-08 | `resolve_epic_slug` legacy plan/decompose probes | searches old plan and decompose paths | use canonical v2 identity only | epic resolver | roadmap/identity tests |
| L89-09 | `canon_md_rel`, `_render_merged_roadmap_md` | deprecated mirror still built in merge result | remove API/preview if no callers | YAML queue output | roadmap tests |
| L89-10 | legacy source queue scan/archive path | `discover_source_queues` and merge migration | isolate explicit import command | v2 queue/batches | roadmap merge tests |
| L89-11 | adapter success tests/fixtures | old formats are treated as runtime green | delete/rewrite to v2/deny/archive-only assertions | v2 behavior tests | event/DAG/roadmap suites |

## Deletion budget

| Scope | Expected deletion | Rewire delta | Net concept target |
|---|---:|---:|---:|
| event v1 live adapter | 80–150 LOC | v2 reader/explicit archive boundary | −1 live schema |
| DAG adapter branch | 50–100 LOC | v2 validation before arm | −1 execution mode |
| roadmap v1/md mirror | 150–280 LOC | v2 queue only | −3 source formats |
| adapter tests/fixtures | 15–30 tests/fixtures | v2/deny/archive tests | −2 test families |

## Test refactor

- Keep v2 schema/replay tests and the narrow `reflection_done` ignore test.
- Rewrite `test_event_legacy_adapter.py` into explicit offline migration tests or delete it with the migration command.
- Rewrite DAG tests from “v1 is adapted” to “v1 is rejected before arm”; retain v2 journey/scheduler behavior.
- Remove tests asserting `LEGACY_DEFAULT_QUEUE` discovery or Markdown mirror output.
- Add roadmap v2 merge/advance tests proving missing v2 queue is an error, not a v1 probe.
- Keep one archive retention test if the offline migration contract remains supported.

## HOW / data flow

```text
v2 event/DAG/queue artifact
  -> typed validator
  -> reducer/scheduler/roadmap consumer
  -> state transition or explicit diagnostic

legacy archive input -> explicit offline migration only
```

## Failure matrix

| Link | Failure | Detection | Response | Test |
|---|---|---|---|---|
| event reader | non-v2 live record | schema check | reject/diagnose | TM-089-01 |
| archive migration | malformed old record | migration validator | preserve source, report failure | TM-089-02 |
| DAG arm | v1 schema | v2 validator | no arm | TM-089-03 |
| DAG execution | missing autonomous field | schema validation | fail-closed | TM-089-04 |
| roadmap parser | v2 queue missing | canonical path check | queue_missing error | TM-089-05 |
| roadmap merge | legacy source supplied | explicit import boundary | no implicit merge | TM-089-06 |

## Replacement / sunset

### A. Code / modules

| Устаревает | Замена | Policy |
|---|---|---|
| live `adapt_v1_event` branch | v2 event validator | delete in-epic |
| implicit `adapt_manifest` in DAG arm | v2 validation | delete in-epic |
| `QUEUE_VERSION_V1` runtime support | v2 queue | delete in-epic |
| Markdown roadmap mirror helpers | YAML queue result | delete in-epic |
| legacy slug/path probes | canonical epic identity | delete in-epic |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
|---|---|---|
| implicit event/DAG/roadmap migration during runtime | explicit offline migration CLI or no migration | delete in-epic |
| `write_md`/mirror preview if exposed as runtime contract | YAML-only merge output | delete in-epic |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
|---|---|---|
| non-v2 event → adapter | schema error | delete in-epic |
| invalid DAG → inferred v2/autonomous false | validation failure | delete in-epic |
| missing v2 queue → legacy queue | queue_missing | delete in-epic |

### I. Instruction surfaces

| Устаревает | Замена | Policy |
|---|---|---|
| roadmap docs naming Markdown mirror as SoT | v2 queue YAML | delete/rewrite in-epic |
| runbook suggesting v1 DAG/event input | v2 schemas + explicit migration | delete/rewrite in-epic |

## До DECOMPOSE (черновик нарезки)

1. Characterize v2 event/DAG/roadmap flows and archive requirements.
2. Split live readers from explicit migration/retention tools.
3. Wire all consumers to v2 validators and queue.
4. Enforce denial of v1 inputs and missing v2 queue.
5. Delete mirror/adapter tests and rewrite v2/deny coverage.
6. Run final purge inventory and full regression.

## QA consumes

| ID | Priority | Scenario | Command / fixture | Expected | Maps |
|---|---:|---|---|---|---|
| TM-089-01 | P0 | live event v2 read / v1 deny | `bin/pytest loop/tests/test_event_stream.py loop/tests/test_event_schema.py -q` | PASS/fail-closed | FR-001 |
| TM-089-02 | P1 | archive migration boundary | `bin/pytest loop/tests/test_event_legacy_adapter.py loop/tests/test_migration_compatibility.py -q` | explicit only | FR-002/003 |
| TM-089-03 | P0 | DAG v1 denied | `bin/pytest loop/tests/test_dag_manifest.py loop/tests/test_dag_transition.py -q` | no arm | FR-004 |
| TM-089-04 | P0 | DAG v2 scheduler parity | `bin/pytest loop/tests/test_dag_scheduler.py loop/tests/test_dag_journey.py -q` | PASS | FR-004 |
| TM-089-05 | P0 | v2 queue required | `bin/pytest loop/tests/test_roadmap_queue.py -q` | no legacy probe | FR-005 |
| TM-089-06 | P1 | merge YAML-only | targeted roadmap merge tests | no md output/implicit source | FR-006 |
| TM-089-07 | P0 | purge symbols and references | plan `rg` controls | zero live adapters | AC− |
| TM-089-08 | P1 | full hub regression | `bin/pytest -q --tb=line` | PASS | SC-002 |

## Review readiness

| Gate | Required | Status | Evidence |
|---|---|---|---|
| Product probe | L3+ | done | §Product probe |
| Structural inventory | required | done | event/DAG/roadmap callers |
| Refactor inventory | required | done | §Refactor inventory |
| Deletion budget | required | done | §Deletion budget |
| Test refactor | required | done | §Test refactor |
| Replacement/sunset A+B+C+I | required | done | §Replacement / sunset |
| QA consumes | required | done | TM-089-01…08 |
| Open CRITICAL | required | none | archive decision is explicit |

## Plan review batch log

| Phase | Auto-resolved | Deferred | Decision |
|---|---|---|---|
| Product | archive compatibility is separate from live execution | retention period policy | no implicit live fallback regardless of retention |
| Engineering | keep only narrow historical dead-event behavior | migration CLI removal if no consumer | audit caller evidence before deletion |

## Appetite

| Поле | Значение |
|---|---|
| `timebox_days` | 4 |
| `cut_list` | redesign of v2 schemas, archive rewrite beyond current migration contract, new roadmap features |

## Следующий режим

→ **BACK DECOMPOSE T-HUB-089-event-dag-roadmap-fallback-purge** after T-HUB-087 and queue reconcile.
