# [T-HUB-087 | epic-layout-v2-fallback-purge] PLAN

**Дата:** 2026-09-08  
**Режим:** BACK PLAN REFACTOR  
**Уровень:** L4  
**Статус:** draft  
**Clarify:** Phase 0 skipped — taxonomy clear: outcome, canonical layout and deletion boundary are defined by T-HUB-047/T-HUB-050 and the current fallback inventory.  
**Prompt:** [md/prompt.md](prompt.md)  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `legacy-fallback-purge-20260908`  
**Deps:** hard T-HUB-047, T-HUB-050 and T-HUB-084; T-HUB-061 is the completed structured-boundary precedent.  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns · python-design-patterns · python-anti-patterns

## Контекст и цель

В layout v2 каноном являются `memory-bank/<role>/plan/<epic>/md/plan.md`, `yaml/decompose-index.yaml`, `yaml/steps/` и flat `memory-bank/<role>/implement/<epic>/<step>.yaml`. Runtime по-прежнему содержит v1 lookup, Markdown status parsing, `implement-<id>` directories и leftover `yaml/steps` lookup. В рабочем tree обнаружены 8 legacy implement-директорий при 72 v2-директориях.

Цель — сначала перевести оставшиеся живые артефакты и call sites на resolver/layout v2, затем удалить старые path/schema/parser ветки и тесты, которые закрепляют их использование. Архивные артефакты не становятся live input и не удаляются этим эпиком.

## Delivery closure

| Capability / outcome | Classification | Production entrypoint and caller | Success / failure enforcement | Independent outcome test | Foundation approval / follow-up |
|---|---|---|---|---|---|
| Единственный layout v2 для epic plan/decompose/implement | `vertical_slice` | `epic_resolve.py`, `epic.core`, board/mb-load callers → `loop.paths.epic_layout.resolve` | v1 target/path → explicit `layout_v1_removed` / non-zero, без silent fallback | arm/load/reconcile для v2 проходят, v1 fixture получает отказ | `n/a` |

## Product probe

| Реальная проблема | Wedge | Pre-mortem | Appetite |
|---|---|---|---|
| Один и тот же epic определяется несколькими filesystem layouts | v2-only resolver + миграция 8 live legacy implement trees | внешний проект ещё использует v1 и получает непонятный отказ | 4–5 дней; сначала live artifacts и callers, затем purge |

## WHAT

### User stories

| ID | Story | Priority | Independent test |
|---|---|---:|---|
| US-001 | Как loop, я хочу разрешать plan/decompose/implement только через layout v2, чтобы один epic не имел конкурирующих адресов. | P0 | v2 arm/load/reconcile проходит, legacy target получает диагностированный отказ. |
| US-002 | Как оператор миграции, я хочу перенести текущие legacy implement artifacts в v2 без потери step/status/evidence. | P0 | migration dry-run/apply + parity scan дают одинаковый набор step ids и файлов. |
| US-003 | Как разработчик, я хочу, чтобы Markdown и v1 path fixtures больше не маскировали отсутствие YAML SoT. | P1 | missing/invalid v2 YAML завершается fail-closed, без `parse_steps_from_md`. |

### Functional requirements

- **FR-001:** Все live plan/decompose/implement call sites используют `loop.paths.epic_layout` или canonical v2 path API.
- **FR-002:** Все 8 legacy `implement/implement-*` trees проходят explicit migration/parity check до удаления.
- **FR-003:** `epic_paths.py` перестаёт искать `plan-*`, `decompose-*` и v1 indexes после cutover.
- **FR-004:** `epic_yaml.py`, `epic/core.py`, `reconcile.py`, `scan_mb.py`, `mb_load/plan_section.py` не имеют v1/Markdown execution fallback.
- **FR-005:** `parse_steps_from_md`, `sync_yaml_from_md` и связанные status-write compatibility tests либо удалены, либо оставлены только в offline migration tool с отдельным non-runtime contract.
- **FR-006:** Ошибка layout/schema не деградирует в другой layout и имеет стабильный diagnostic.
- **FR-007:** Obsolete path tests, fixtures и assertions удалены или переписаны на v2 behavior tests в том же эпике.

### Success criteria

| ID | Измеримый результат | Проверка | Type |
|---|---|---|---|
| SC-001 | 0 active v1 layout branches в перечисленных runtime-модулях | executable `rg` inventory | outcome |
| SC-002 | 0 live `implement/implement-*` directories в BACK tree | filesystem migration scan | outcome |
| SC-003 | v2 arm/load/reconcile/index smoke green | targeted pytest через `bin/pytest` | outcome |
| SC-004 | legacy path invocation завершается ошибкой, а не v2 lookup | negative integration fixtures | outcome |

## Acceptance criteria

1. Вызов canonical v2 для каждого role/epic разрешает plan, decompose index и implement shard без wrapper-ветки.
2. Legacy `plan-*`, `decompose-*`, `implement-*` и `yaml/steps` runtime paths не вызываются и отсутствуют в active production scope.
3. Текущие 8 legacy implement trees мигрированы с сохранением step ids, статусов и ссылок.
4. Markdown index остаётся human-readable documentation, но не является источником runtime step/status.
5. v1 path/schema input выдаёт explicit failure/diagnostic; silent fallback запрещён.
6. Тесты проверяют canonical behavior и denial старого layout, а не наличие старого файла.

### AC−

1. Нет dual v1/v2 resolver path.
2. Нет `try new except legacy` для path resolution.
3. Нет production caller у `parse_steps_from_md`/`sync_yaml_from_md`.
4. Нет live `implement/implement-*` artifacts после migration gate.
5. Нет теста, который требует legacy layout для зелёного runtime.

## Technology axiom

| Выбор | Machine input | Запрещено после эпика |
|---|---|---|
| Layout v2 resolver | typed `EpicLayoutKind` + canonical v2 paths | glob-based v1 discovery |
| Decompose status | `decompose-index.yaml` + `yaml/steps/*.yaml` | Markdown parsing as runtime SoT |
| Implement artifacts | `implement/<epic>/<step>.yaml` | `implement-<epic>/` and leftover `yaml/steps` |
| Migration | explicit migration command before purge | implicit read-time migration |

## Refactor inventory

| ID | Path / symbol | Evidence and callers | Action | Replacement owner | Tests |
|---|---|---|---|---|---|
| L87-01 | `harness/hooks/epic_paths.py:find_decompose_index_path` | v2 resolver followed by `decompose-*/index.*` glob; used by reconcile, arm and gates | delete v1 branch | `loop.paths.epic_layout.resolve` | `test_epic_layout_resolver*.py`, `test_epic_paths.py` |
| L87-02 | `harness/hooks/epic_paths.py:find_plan_md_path`, `epic_id_from_plan_path` | accepts `plan-*.md` after v2 lookup | delete legacy parsing | v2 `plan/<epic>/md/plan.md` | `test_epic_paths.py`, v2 regressions |
| L87-03 | `harness/hooks/epic_yaml.py:resolve_implement_path` | v2 flat → leftover `yaml/steps` → v1 `implement-*` | delete leftover/v1 branches after migration | `EpicLayoutKind.IMPLEMENT_STEP` | epic YAML tests, implement hub alias tests |
| L87-04 | `harness/hooks/epic_yaml.py:_resolve_decompose_dir` | `base/raw`, `decompose-raw`, root fallback | delete v1 path alternatives | canonical resolver | path resolver tests |
| L87-05 | `harness/hooks/epic/core.py:_load_decompose_steps`, `load_decompose_steps_fail_closed` | YAML absence calls `parse_steps_from_md` | delete Markdown execution path | YAML-only index loader | `test_index_yaml_only.py`, `test_index_fail_closed.py` |
| L87-06 | `harness/hooks/epic/reconcile.py:resolve_epic_bundle` | v2 implement dir else `implement-{plan_id}` | delete v1 branch | v2 implement dir | reconcile tests |
| L87-07 | `harness/hooks/epic_resolve.py` legacy decompose/implement resolution | explicit v1 directory checks remain in CLI | delete after migration | canonical layout resolver | CLI/reconcile tests |
| L87-08 | `loop/board_sync/scan_mb.py:_index_paths` | scans `decompose-*/index.yaml` after v2 | delete v1 scan | v2 glob/resolver | `test_board_sync_scan_mb.py` |
| L87-09 | `loop/mb_load/plan_section.py` scoped legacy filename candidates | live load path accepts `plan-<id>[-slug].md` | delete legacy candidates | v2 plan path | `test_mb_load_plan_section.py` |
| L87-10 | `harness/hooks/epic_index.py:parse_steps_from_md`, `sync_yaml_from_md` | parser and migration helper are runtime-visible; no new runtime caller allowed | delete runtime parser; retain only if migration command needs isolated copy | v2 YAML loader / explicit migration tool | index and migration tests |
| L87-11 | `loop/migrate/epic_layout_v1_to_v2.py` | required for 8 current legacy implement trees | use once, then narrow/remove old discovery after apply | v2 artifact tree | `test_epic_layout_migrate.py` |
| L87-12 | legacy path fixtures/assertions | `loop/tests/fixtures/board_sync/.../decompose-*`, resolver v1 cases | delete or rewrite to denial tests | v2 fixtures | path/board/traceability tests |

## Deletion budget

| Scope | Expected deletion | Migration/rewire delta | Net concept target |
|---|---:|---:|---:|
| Runtime v1 path branches | 150–300 LOC | v2 resolver call sites | −6 path concepts |
| Markdown runtime parser/status path | 100–180 LOC | YAML-only loader | −2 SoT concepts |
| Legacy resolver tests/fixtures | 20–40 tests/fixtures | 8–12 v2 denial/parity tests | −1 test family |
| Legacy live implement trees | 8 directories | migrate to v2 | 0 lost artifacts |

## Test refactor

- Delete tests whose only assertion is successful `plan-*`, `decompose-*`, `implement-*` lookup.
- Rewrite path tests to assert v2 result and a negative `layout_v1_removed` diagnostic.
- Keep migration tests only for explicit migration command and current 8-tree parity.
- Remove Markdown status mutation tests from runtime suite; add one test that runtime refuses an index without YAML.
- Preserve board/mb-load behavior tests with v2 fixtures, not by keeping legacy fixture paths.
- Run targeted commands from repository root through `bin/pytest`.

## HOW / data flow

```text
operator/loop entrypoint
  -> canonical epic resolver
  -> v2 plan/decompose/implement paths
  -> typed YAML loader
  -> runtime gate/reconcile/board consumer
```

No runtime node may branch from a missing v2 artifact to a legacy path. Migration is a separate explicit command and is not imported by hot paths.

## Failure matrix

| Link | Failure | Detection | Response | Test |
|---|---|---|---|---|
| v2 plan lookup | missing plan | resolver diagnostic | fail-closed | TM-087-01 |
| v2 index lookup | missing/invalid YAML | schema validation | deny arm/load | TM-087-02 |
| implement migration | missing step/status | parity manifest | stop migration, no delete | TM-087-03 |
| old target | `plan-*`/`decompose-*` input | path classifier | `layout_v1_removed` | TM-087-04 |
| board scan | legacy index present | canonical scan | ignore/diagnose, never execute | TM-087-05 |
| mb-load | legacy plan filename | canonical candidate list | plan_missing | TM-087-06 |

## Replacement / sunset

### A. Code / modules

| Устаревает | Замена | Policy |
|---|---|---|
| v1 branches in `epic_paths.py` | `loop.paths.epic_layout` v2 | delete in-epic |
| `implement-*` and leftover `yaml/steps` resolver branches | flat v2 implement resolver | delete in-epic |
| Markdown runtime parsing | `decompose-index.yaml` loader | delete in-epic |
| legacy board/mb-load path candidates | v2 path API | delete in-epic |
| runtime use of migration module | explicit migration CLI only | delete in-epic |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
|---|---|---|
| `--decompose`/path-only arm input | `--epic-id` + canonical resolver | delete in-epic |
| implicit v1 migration during load | explicit migration command | delete in-epic |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
|---|---|---|
| v2 missing → v1 path | explicit missing/invalid diagnostic | delete in-epic |
| YAML missing → Markdown parse | fail-closed YAML-only load | delete in-epic |
| v2 implement missing → `implement-*` | v2 missing diagnostic | delete in-epic |

### I. Instruction surfaces

| Устаревает | Замена | Policy |
|---|---|---|
| instructions naming `decompose-*`, `plan-*.md`, `implement-*` as live paths | v2 resolver paths | delete/rewrite in-epic |
| migration wording that implies transparent fallback | explicit one-time migration then fail-closed runtime | delete/rewrite in-epic |

## До DECOMPOSE (черновик нарезки)

1. Characterize v2 behavior and enumerate the 8 live legacy implement trees.
2. Migrate artifacts and verify step/status/evidence parity.
3. Wire all runtime callers to the canonical v2 resolver.
4. Enforce denial of old layout and YAML-only runtime loading.
5. Rewrite/remove path, Markdown and legacy fixture tests.
6. Run the complete `*-legacy-fallback-purge` inventory and regression suite.

## QA consumes

| ID | Priority | Scenario | Command / fixture | Expected | Maps |
|---|---:|---|---|---|---|
| TM-087-01 | P0 | v2 plan/decompose/implement resolve | `bin/pytest loop/tests/test_v2_path_resolution_regressions.py harness/hooks/tests/test_epic_layout_resolver.py -q` | PASS | FR-001 |
| TM-087-02 | P0 | YAML-only fail-closed load | `bin/pytest loop/tests/test_index_yaml_only.py loop/tests/test_index_fail_closed.py -q` | no Markdown fallback | FR-004 |
| TM-087-03 | P0 | 8 legacy tree migration parity | `bin/pytest harness/hooks/tests/test_epic_layout_migrate.py -q` | parity + no data loss | FR-002 |
| TM-087-04 | P0 | old path denial | targeted resolver negative tests | explicit diagnostic/non-zero | FR-003/006 |
| TM-087-05 | P1 | board scan v2 only | `bin/pytest loop/tests/test_board_sync_scan_mb.py -q` | no v1 execution | FR-004 |
| TM-087-06 | P1 | mb-load v2 only | `bin/pytest loop/tests/test_mb_load_plan_section.py loop/tests/test_mb_load_session.py -q` | v2 behavior | FR-004 |
| TM-087-07 | P0 | full legacy purge scan | plan `rg` controls | zero active v1 symbols | AC− |
| TM-087-08 | P1 | full hub regression | `bin/pytest -q --tb=line` | PASS | SC-003 |

## Review readiness

| Gate | Required | Status | Evidence |
|---|---|---|---|
| Product probe | L3+ | done | §Product probe |
| Structural inventory | required | done | bounded rg/import inventory; graphify stale-path limitation recorded |
| Refactor inventory | required | done | §Refactor inventory |
| Deletion budget | required | done | §Deletion budget |
| Test refactor | required | done | §Test refactor |
| Replacement/sunset A+B+C+I | required | done | §Replacement / sunset |
| QA consumes | required | done | TM-087-01…08 |
| Open CRITICAL | required | none | no unresolved blocker |

## Plan review batch log

| Phase | Auto-resolved | Deferred | Decision |
|---|---|---|---|
| Product | One canonical layout and explicit migration | External downstream projects not in repo | support window must close before purge |
| Engineering | Migration and purge stay in one vertical slice | no separate migration-only epic | no data-loss deletion before parity |

## Appetite

| Поле | Значение |
|---|---|
| `timebox_days` | 5 |
| `cut_list` | historical archive cleanup, new resolver redesign, operational fallback changes |

## Следующий режим

→ **BACK DECOMPOSE T-HUB-087-epic-layout-v2-fallback-purge** after queue reconcile.
