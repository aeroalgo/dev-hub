# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-042-runtime-adapter-framework  
**План:** [plan-T-HUB-042-runtime-adapter-framework.md](../plan-T-HUB-042-runtime-adapter-framework.md)  
**Machine index:** [index.yaml](index.yaml) — **канон status**  
**Дата:** 2026-09-02  
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml`.

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность |
| `python-testing-patterns` | TDD, fixtures, pytest |
| `python-error-handling` | fail-closed patterns |

## Requirements coverage (plan → steps)

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | runtime_registry.yaml schema runtime-registry/v1 | s01 | TM-001 |
| FR-002 | RuntimeAdapter Protocol + dataclasses base.py | s02 | |
| FR-003 | ClaudeAdapter — extract claude argv builder | s03 | TM-003, TM-004-partial |
| FR-004 | DshAdapter — implement Protocol wrapping dsh.py | s04 | TM-004 |
| FR-005 | registry.py load + get_runtime_adapter + capability | s01 | |
| FR-006 | dispatch.py build_command + run_session subprocess | s05 | TM-004, TM-005 |
| FR-007 | _lib.resolve_runtime_config registry-driven | s06 | TM-002 |
| FR-008 | session_resilience.analyze_log delegate to adapter | s07 | TM-007 |
| FR-009 | context_loop.prepare_session emit runtime_extras | s08 | TM-006 |
| FR-010 | loop.sh replace if/else with dispatch CLI | s05, s09 | TM-005 |
| FR-011 | --runtime argparse choices from registry | s08 | |
| FR-012 | Unit tests: registry, invalid runtime, command builders | s01, s02, s03, s04 | TM-001..TM-004 |
| US-001 | EPIC_RUNTIME from registry; добавить runtime без loop.sh edit | s01, s05, s06, s08 | |
| US-002 | единый SessionAnalysis; retry policy одинакова для всех runtime | s02, s07 | |
| US-003 | ClaudeAdapter extracted; claude path тестируется изолированно | s03 | |
| US-004 | zero regression на EPIC_RUNTIME=dsh | s04, s07, s09, s10 | |
| SC-001 | EPIC_RUNTIME unset → claude default | s06 | |
| SC-002 | EPIC_RUNTIME=foo → invalid_runtime_config | s01, s05, s06 | |
| SC-003 | DSH fixtures → same SessionAnalysis as before | s04, s07 | |
| SC-004 | no is_dsh in analyze_session_log main path | s07, s09 | rg audit |
| AC+ #1 | runtime_registry.yaml lists claude+dsh with capabilities | s01 | TM-001 |
| AC+ #2 | dispatch --dry-run --runtime claude prints argv | s05 | TM-003 |
| AC+ #3 | EPIC_RUNTIME=dsh + mock → invoke mock with profile (parity) | s04, s07 | TM-004 |
| AC+ #4 | Unknown runtime → loop exit 2 + JSON diagnostic | s01, s05, s06 | TM-002 |
| AC+ #5 | pytest test_runtime_config + test_dsh_runtime_adapter + test_loop_dsh_dispatch green | s01..s10 | |
| AC+ #6 | rg 'is_dsh' session_resilience — only adapter delegation or zero | s07 | rg=0 |
| AC− #1 | hardcoded {claude,dsh} frozenset в _lib.py после эпика | s06, s10 | rg=0 |
| AC− #2 | if.*dsh.*run_dsh dispatch block в loop.sh после эпика | s05, s09 | rg=0 |
| AC− #3 | silent fallback missing dsh → claude | s01, s05 | fail-closed |
| AC− #4 | orchestrator знает dsh_profile field names напрямую | s08 | generic runtime_extras |
| NFR-01 | Fail-closed: неизвестный runtime → exit 2 + JSON diagnostic | s01, s05, s06 | AC+ #4 |
| NFR-02 | Zero regression claude path | s03, s07, s09 | |
| NFR-03 | Registry-extensible: new runtime без code edit | s01, s05, s06, s08 | |
| TM-001 | registry load test | s01 | |
| TM-002 | invalid runtime fail-closed | s06 | |
| TM-003 | claude dispatch dry-run | s03, s05 | |
| TM-004 | dsh dispatch dry-run | s04, s05 | |
| TM-005 | loop.sh dsh dispatch shell | s05, s09 | |
| TM-006 | context_loop prepare runtime extras | s08 | |
| TM-007 | session_resilience adapter delegate | s07 | |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Registry YAML + loader | plan §FR-001, §FR-005 | s01 |
| Protocol dataclasses base.py | plan §FR-002 | s02 |
| ClaudeAdapter extract | plan §FR-003 | s03 |
| DshAdapter refactor | plan §FR-004 | s04 |
| Dispatch CLI + loop.sh wiring | plan §FR-006, §FR-010 | s05 |
| _lib registry-driven validation | plan §FR-007 | s06 |
| session_resilience delegate | plan §FR-008 | s07 |
| context_loop runtime_extras | plan §FR-009, §FR-011 | s08 |
| Purge is_dsh remaining callers | plan §FR-010 purge | s09 |
| Legacy standalone functions purge | plan §Replacement/sunset | s10 |
| Regression suite green | plan §Zero regression, TM-003,005,007 | s07, s09, s10 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Plug-in RuntimeAdapter registry: добавить runtime без изменения orchestration semantics | s01, s02, s05 |
| `_RUNTIME_MODES frozenset` → registry-driven validation: новый runtime = yaml entry | s01, s06 |
| claude path byte-equivalent behavior (zero regression) | s03, s07, s09 |
| dsh path через DshAdapter.analyze_log / prepare_extras / build_command | s04, s07, s08 |
| loop.sh не содержит runtime-specific if/else | s05, s09 |
| session_resilience.is_dsh branches = 0 в prod | s07, s09 |
| context_loop.prepare_session эмитит generic runtime_extras | s08 |
| Fail-closed на неизвестный runtime (invalid_runtime_config) | s01, s05, s06 |
| --runtime argparse choices = registry.list_ids() | s08 |
| Full sunset inventory scan: 0 prod callers standalone functions | s10 |
| Out of scope: capability preflight CLI, interactive registry flags | — / cut_list |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `harness/hooks/_lib.py::_RUNTIME_MODES frozenset` | A | `registry.list_ids()` | s06, s10 | no | |
| `harness/hooks/_lib.py::_RUNTIME_CONFIG_ENUMS` EPIC_RUNTIME frozenset entry | A | registry call | s06 | no | |
| `harness/hooks/session_resilience.py::is_dsh` branches | A | adapter.analyze_log | s07 | no | |
| `harness/hooks/stop-gate.py::_is_dsh_runtime` | A | registry check | s09 | no | |
| `loop/context_loop.py:1734` hardcoded `'dsh_profile'` | A | adapter.prepare_extras | s08 | no | |
| `loop/board_launch/loop_argv.py` env_extra is_dsh | A | generic extras | s09 | no | |
| `loop/loop.sh:564` if/else dsh/claude dispatch block | B | dispatch CLI | s05 | no | |
| `loop/loop.sh:694-695` EPIC_DSH_PROFILE export | B | --extras-json | s09, s10 | no | |
| `loop/runtime_adapters/dsh.py::normalize_dsh_log` (standalone) | A | DshAdapter.analyze_log | s10 | no | |
| `loop/runtime_adapters/dsh.py::detect_dsh_model_mismatch` (standalone) | A | DshAdapter.analyze_log | s10 | no | |
| `loop/runtime_adapters/dsh.py::build_dsh_command` (standalone) | A | DshAdapter.build_command | s10 | no | |
| `loop/runtime_adapters/dsh.py::build_dsh_command_from_file` (standalone) | A | DshAdapter.build_command | s10 | no | |
| `loop/runtime_adapters/common.py` re-export заглушки | A | прямые классы | s10 | no | |

Финальный purge: **s10-legacy-fallback-purge** — `sunset_inventory` + `grep_control` для всех строк A/B.

## Очередь шагов (BACK)

| step_id | title & files | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-registry-yaml-schema.yaml](s01-registry-yaml-schema.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-runtime-adapter-protocol.yaml](s02-runtime-adapter-protocol.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-claude-adapter.yaml](s03-claude-adapter.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-dsh-adapter-refactor.yaml](s04-dsh-adapter-refactor.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-dispatch-loopsh-wiring.yaml](s05-dispatch-loopsh-wiring.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-lib-resolve-runtime-registry.yaml](s06-lib-resolve-runtime-registry.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s07** | [s07-session-resilience-delegate-analyze.yaml](s07-session-resilience-delegate-analyze.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s08** | [s08-context-loop-runtime-extras-argparse.yaml](s08-context-loop-runtime-extras-argparse.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s09** | [s09-purge-is-dsh-dispatch-regression.yaml](s09-purge-is-dsh-dispatch-regression.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s10** | [s10-legacy-fallback-purge.yaml](s10-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |