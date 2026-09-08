# [T-HUB-090 | boundary-compatibility-shim-purge] PLAN

**Дата:** 2026-09-08  
**Режим:** BACK PLAN REFACTOR  
**Уровень:** L3  
**Статус:** draft  
**Clarify:** Phase 0 skipped — candidate shims have explicit symbols, current callers and later canonical owners.  
**Prompt:** [md/prompt.md](prompt.md)  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `legacy-fallback-purge-20260908`  
**Deps:** hard T-HUB-087, T-HUB-058, T-HUB-059, T-HUB-065 and T-HUB-069.  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns · python-design-patterns · python-anti-patterns

## Контекст и цель

После перехода на canonical agent metadata, runtime registry и board command routing в коде остаются compatibility shims: hardcoded `_LEGACY_OVERLAYS`, old board CLI handlers, runtime alias/module scan, session API aliases, DSH tool-name aliases и несколько dead public helper aliases. Часть из них — настоящие old implementation paths, часть — operational compatibility и не должна удаляться без proof.

Цель — удалить только подтверждённо устаревшие boundary shims и связанные obsolete tests, а operational reliability fallbacks оставить с явной классификацией. Эпик не меняет пользовательскую семантику команд, только делает canonical owner обязательным.

## Delivery closure

| Capability / outcome | Classification | Production entrypoint and caller | Success / failure enforcement | Independent outcome test | Foundation approval / follow-up |
|---|---|---|---|---|---|
| Canonical boundary APIs без dead compatibility aliases | `vertical_slice` | agent registry/materializer, board CLI, runtime adapter factory | old alias/import → explicit failure; operational fallback remains outside scope | canonical command/materialization smoke + old symbol scan | `n/a` |

## Product probe

| Реальная проблема | Wedge | Pre-mortem | Appetite |
|---|---|---|---|
| Старые имена и hardcoded defaults скрывают отсутствие нового metadata/registry contract | remove dead aliases and enforce canonical metadata for managed agents | external users import old helper or old DSH tool name | 3 дня; dynamic/external risk requires deny inventory |

## WHAT

### User stories

| ID | Story | Priority | Independent test |
|---|---|---:|---|
| US-001 | Как runtime, я хочу получать agent overlay из canonical metadata, а не из hardcoded legacy map. | P0 | materialization with metadata succeeds; missing required metadata fails. |
| US-002 | Как оператор, я хочу canonical board commands, а legacy handlers не должны жить скрытым вторым route. | P1 | canonical CLI invoke passes; old dispatch path is absent/denied. |
| US-003 | Как maintainer, я хочу удалить dead API aliases без удаления operational PATH/LLM/DSH resilience. | P1 | static import inventory is clean and reliability fallback tests remain green. |

### Functional requirements

- **FR-001:** `_LEGACY_OVERLAYS` is removed from managed agent resolution after metadata coverage is proven.
- **FR-002:** `loop/board_sync/cli.py` has one canonical dispatch route; unused `_print_result_legacy` is deleted and legacy command handlers are removed or explicitly denied.
- **FR-003:** Runtime adapter alias/module scan is removed only where registry/config coverage proves no dynamic implementation dependency; runtime failure remains explicit.
- **FR-004:** Dead aliases `ABORT_PATTERNS`, `_handoff_mode_from_legacy_markdown`, `checkpoint_prompt_lines` and `validate_shard_yaml` are removed after external-import scan.
- **FR-005:** Session resilience parameters retained for active callers are not falsely classified as dead; only zero-caller compatibility surface is deleted.
- **FR-006:** DSH lowercase canonical tools remain; compatibility aliases are deleted only after client/reference scan proves no supported caller.
- **FR-007:** Tests for deleted symbols/legacy handlers are removed or rewritten to canonical behavior; operational fallback tests remain.

### Success criteria

| ID | Результат | Проверка | Type |
|---|---|---|---|
| SC-001 | no hardcoded managed-agent fallback for covered agents | registry/materializer scan | outcome |
| SC-002 | no internal callers of deleted aliases | import/call graph + rg | outcome |
| SC-003 | canonical board/runtime paths green | targeted pytest | outcome |
| SC-004 | operational fallbacks still bounded and explicit | reliability regression tests | outcome |

## Acceptance criteria

1. Every managed agent has canonical overlay metadata before `_LEGACY_OVERLAYS` is removed.
2. Board CLI canonical commands no longer route through an unused legacy printer/dispatcher.
3. Deleted aliases have zero production, test-support and configuration references, or are explicitly retained with owner and reason in the plan.
4. PATH/npx, LLM secondary model, runtime configuration failure and DSH alias behavior are not accidentally removed.
5. Canonical runtime/agent/board tests replace old alias tests.

### AC−

1. Нет hardcoded legacy agent defaults for agents with metadata SOT.
2. Нет dead public alias definitions without caller proof.
3. Нет legacy CLI handler silently reachable from canonical commands.
4. Operational fallback is not converted into silent success or removed without replacement.
5. Нет obsolete tests importing deleted symbols.

## Technology axiom

| Выбор | Machine input | Запрещено после эпика |
|---|---|---|
| Agent policy | metadata/registry SOT | hardcoded legacy overlay for managed agent |
| Board CLI | canonical parser/dispatch | hidden second command route |
| Runtime adapter | registry/config contract | blind module scan as normal resolution |
| Compatibility deletion | static/import/config proof | delete based only on no local test caller |

## Refactor inventory

| ID | Path / symbol | Evidence and callers | Action | Replacement owner | Tests |
|---|---|---|---|---|---|
| L90-01 | `harness/hooks/agent_registry.py:_LEGACY_OVERLAYS` | hardcoded fallback used by `_legacy_or_default`; T-HUB-058/059 canonical agent SOT is newer | migrate metadata, delete map | agent frontmatter/registry | `test_agent_registry.py`, materializer tests |
| L90-02 | `_legacy_or_default` default field merge | fills absent overlay fields from legacy map | require canonical metadata for managed agents; keep optional defaults only if contract says so | typed agent metadata | registry/policy tests |
| L90-03 | `loop/board_sync/cli.py:_print_result_legacy` | no internal callers found | delete | `_print_result` / `_print_operations` | `test_board_sync_cli.py` |
| L90-04 | `loop/board_sync/cli.py:_dispatch_legacy` | `main` routes `sync/status` through it | migrate command parser to canonical dispatch, then delete if no external import contract | canonical CLI dispatcher | board CLI tests |
| L90-05 | `loop/runtime_adapters/common.py:_RUNTIME_ALIASES` | old Claude identifiers normalize to canonical runtime | keep only aliases with supported config references; delete unreferenced names | runtime registry | runtime adapter tests |
| L90-06 | module attribute fallback scan | registry object without expected attr scans all `*Adapter` | remove after registry returns typed implementation; unknown runtime raises | `get_runtime_adapter` | runtime registry/dispatch tests |
| L90-07 | `harness/hooks/session_resilience.py:ABORT_PATTERNS` | definition only in production | delete alias; preserve private pattern tuples | `_FATAL_ABORT_PATTERNS`/classifier | session resilience tests |
| L90-08 | `active_context._handoff_mode_from_legacy_markdown` | definition-only alias | delete | `handoff_mode_from_text` | handoff tests |
| L90-09 | `epic_yaml.checkpoint_prompt_lines` | definition-only legacy prompt helper | delete | `step_context_prompt_lines` | prompt tests |
| L90-10 | `epic_yaml.validate_shard_yaml` | no production callers; full validator is canonical | delete or keep only external API if import audit finds support | `validate_shard_yaml_full` | validator tests |
| L90-11 | DSH `tool-name-compat` aliases | active Claude compatibility aliases | retain until supported client scan is zero; then delete plugin registrations/tests | lowercase DSH tools | plugin/runtime tests |
| L90-12 | `which-dsh` npx, `which-codex` PATH, LLM fallback | operational resilience, not old implementation | keep; add classification tests, no purge | binary/model resolver | runtime/LLM tests |
| L90-13 | `loop/board_status.py` unranked fallback, incident/metrics/runbook fallback | safe recovery, not canonical boundary replacement | keep with explicit scope | operational recovery | status/incident tests |

## Deletion budget

| Scope | Expected deletion | Rewire delta | Net concept target |
|---|---:|---:|---:|
| agent hardcoded fallback | 40–90 LOC | metadata coverage | −1 policy source |
| dead aliases/printer | 30–80 LOC | canonical helpers | −4 API aliases |
| runtime/CLI legacy route | 30–90 LOC | registry/parser calls | −1 route |
| obsolete tests | 10–25 tests/assertions | canonical/negative tests | −1 compatibility family |

## Test refactor

- Add a metadata completeness test before deleting `_LEGACY_OVERLAYS`.
- Delete tests that import or assert `ABORT_PATTERNS`, `_handoff_mode_from_legacy_markdown`, `checkpoint_prompt_lines` or `validate_shard_yaml` if no supported external import exists.
- Rewrite board CLI tests around canonical parser/dispatch and explicit unsupported-command errors.
- Rewrite runtime adapter tests to assert registry-owned implementation and explicit unknown-runtime failure; do not test blind module discovery.
- Retain DSH tool alias tests and operational fallback tests until their separate support windows close.
- Add a control test that classifies retained operational fallbacks so the purge does not remove them accidentally.

## HOW / data flow

```text
canonical metadata/config
  -> registry/materializer/parser
  -> runtime/agent/board production entrypoint
  -> explicit result or failure

operational environment fallback -> bounded resolver only, never legacy workflow implementation
```

## Failure matrix

| Link | Failure | Detection | Response | Test |
|---|---|---|---|---|
| agent registry | missing overlay metadata | completeness validator | fail managed agent load | TM-090-01 |
| board CLI | old command route | parser/reference scan | explicit unsupported/error | TM-090-02 |
| runtime adapter | registry missing implementation | typed registry error | non-zero/diagnostic | TM-090-03 |
| alias deletion | hidden import/config caller | rg/import scan | block purge | TM-090-04 |
| DSH compatibility | supported client still uses alias | client/reference scan | retain with owner | TM-090-05 |
| operational fallback | binary/model unavailable | resolver tests | bounded fallback or explicit failure | TM-090-06 |

## Replacement / sunset

### A. Code / modules

| Устаревает | Замена | Policy |
|---|---|---|
| `_LEGACY_OVERLAYS` for covered agents | canonical metadata | delete in-epic |
| `_print_result_legacy` | canonical result printers | delete in-epic |
| unused compatibility aliases | canonical helper names | delete in-epic |
| module attribute adapter scan | registry-owned adapter | delete in-epic if coverage proven |
| legacy board dispatcher | canonical command parser | delete in-epic |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
|---|---|---|
| old board command forms with no supported caller | canonical CLI | delete in-epic |
| old DSH tool names | lowercase canonical tools | shim+follow-up only while supported clients exist |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
|---|---|---|
| missing agent metadata → hardcoded legacy overlay | metadata validation error | delete in-epic |
| registry miss → blind module scan | typed registry error | delete in-epic |
| dead API alias | canonical function | delete in-epic |
| PATH/npx/LLM operational recovery | bounded operational resolver | keep with explicit non-legacy classification |

### I. Instruction surfaces

| Устаревает | Замена | Policy |
|---|---|---|
| docs/instructions naming old board route or agent default map | metadata/registry canonical route | delete/rewrite in-epic |
| instructions requiring DSH alias names | lowercase canonical tool names | rewrite; delete alias only after support scan |

## До DECOMPOSE (черновик нарезки)

1. Inventory metadata, CLI, registry and external/dynamic references.
2. Enforce metadata completeness and canonical board/runtime ownership.
3. Remove proven dead aliases and old printer/route.
4. Decide DSH alias and runtime scan rows from reference evidence; retain only bounded operational fallbacks.
5. Rewrite/delete obsolete tests and instructions.
6. Run final purge scan and reliability regression.

## QA consumes

| ID | Priority | Scenario | Command / fixture | Expected | Maps |
|---|---:|---|---|---|---|
| TM-090-01 | P0 | agent metadata completeness | `bin/pytest loop/tests/test_agent_registry.py loop/tests/test_agent_materializer.py -q` | no legacy map needed | FR-001 |
| TM-090-02 | P0 | canonical board CLI | `bin/pytest loop/tests/test_board_sync_cli.py loop/tests/test_board_launch_cli.py -q` | canonical route only | FR-002 |
| TM-090-03 | P0 | registry-owned runtime adapter | `bin/pytest loop/tests/test_runtime_registry.py loop/tests/test_runtime_dispatch.py -q` | explicit unknown failure | FR-003 |
| TM-090-04 | P0 | dead alias/import scan | plan `rg`/import controls | zero deleted-symbol hits | FR-004 |
| TM-090-05 | P1 | supported DSH aliases | `bin/pytest loop/tests/test_dsh_runtime_adapter.py loop/tests/test_dsh_epic_gate_gaps.py -q` | retained aliases behave | FR-006 |
| TM-090-06 | P1 | operational fallback preservation | `bin/pytest loop/tests/test_hooks_llm_fallback.py loop/tests/test_incidents_doctor.py loop/tests/test_incidents_metrics.py -q` | bounded fallback unchanged | FR-007 |
| TM-090-07 | P0 | sunset instructions and tests | plan `rg` controls | no old contract references | AC− |
| TM-090-08 | P1 | full hub regression | `bin/pytest -q --tb=line` | PASS | SC-003/004 |

## Review readiness

| Gate | Required | Status | Evidence |
|---|---|---|---|
| Product probe | L3 | done | §Product probe |
| Structural inventory | required | done | alias/caller/reference inventory |
| Refactor inventory | required | done | §Refactor inventory |
| Deletion budget | required | done | §Deletion budget |
| Test refactor | required | done | §Test refactor |
| Replacement/sunset A+B+C+I | required | done | §Replacement / sunset |
| QA consumes | required | done | TM-090-01…08 |
| Open CRITICAL | required | none | DSH/runtime dynamic risk is explicit gate, not hidden assumption |

## Plan review batch log

| Phase | Auto-resolved | Deferred | Decision |
|---|---|---|---|
| Product | operational fallbacks are not legacy implementation | external DSH alias clients | retain until reference scan is zero |
| Engineering | delete only zero-caller aliases; no broad facade rewrite | public external imports | import audit decides policy per symbol |

## Appetite

| Поле | Значение |
|---|---|
| `timebox_days` | 3 |
| `cut_list` | DSH alias removal, new runtime registry design, operational fallback redesign |

## Следующий режим

→ **BACK DECOMPOSE T-HUB-090-boundary-compatibility-shim-purge** after T-HUB-087 and queue reconcile.
