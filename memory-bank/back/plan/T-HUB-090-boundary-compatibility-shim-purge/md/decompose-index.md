# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-090-boundary-compatibility-shim-purge
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**
**Дата:** 2026-09-12
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — [.cursor/templates/decompose/epic-step.yaml](../../../../../.cursor/templates/decompose/epic-step.yaml).

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-090-boundary-compatibility-shim-purge/md/decompose-index.md`. Machine = `plan/T-HUB-090-boundary-compatibility-shim-purge/yaml/decompose-index.yaml`. Shards = `yaml/steps/`.
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `decompose-index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|---|---|
| `writing-plans` | структура шагов, атомарность |
| `python-testing-patterns` | characterization and negative regression testing |
| `architecture-patterns` | canonical metadata and registry boundaries |
| `python-design-patterns` | single dispatcher refactoring and typed errors |
| `python-anti-patterns` | purge dead aliases, hardcoded maps, and blind module reflection |

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN | Notes |
| :--- | :--- | :--- | :--- |
| US-001 | Как runtime, я хочу получать agent overlay из canonical metadata, а не из hardcoded legacy map. | s01, s02, s06 | Canonical metadata enforcement and `_LEGACY_OVERLAYS` deletion |
| US-002 | Как оператор, я хочу canonical board commands, а legacy handlers не должны жить скрытым вторым route. | s01, s03, s06 | Single canonical board CLI dispatcher and delete `_dispatch_legacy` |
| US-003 | Как maintainer, я хочу удалить dead API aliases без удаления operational PATH/LLM/DSH resilience. | s01, s04, s05, s06 | Dead aliases purge, runtime scan purge, operational resilience classification |
| FR-001 | `_LEGACY_OVERLAYS` is removed from managed agent resolution after metadata coverage is proven. | s01, s02, s06 | Enforce metadata frontmatter, remove `_LEGACY_OVERLAYS` map |
| FR-002 | `loop/board_sync/cli.py` has one canonical dispatch route; unused `_print_result_legacy` is deleted and legacy command handlers are removed or explicitly denied. | s01, s03, s06 | Purge `_print_result_legacy` and legacy dispatch paths |
| FR-003 | Runtime adapter alias/module scan is removed only where registry/config coverage proves no dynamic implementation dependency; runtime failure remains explicit. | s01, s04, s06 | Clean `_RUNTIME_ALIASES` and remove blind module attribute scan |
| FR-004 | Dead aliases `ABORT_PATTERNS`, `_handoff_mode_from_legacy_markdown`, `checkpoint_prompt_lines` and `validate_shard_yaml` are removed after external-import scan. | s01, s05, s06 | Purge confirmed dead aliases from session resilience and epic YAML |
| FR-005 | Session resilience parameters retained for active callers are not falsely classified as dead; only zero-caller compatibility surface is deleted. | s01, s04, s05, s06 | Verify active callers, retain operational resilience parameters |
| FR-006 | DSH lowercase canonical tools remain; compatibility aliases are deleted only after client/reference scan proves no supported caller. | s01, s04, s05, s06 | Retain supported DSH aliases and operational fallbacks with explicit classification |
| FR-007 | Tests for deleted symbols/legacy handlers are removed or rewritten to canonical behavior; operational fallback tests remain. | s01, s05, s06 | Rewrite obsolete tests to canonical contracts and explicit denial |
| SC-001 | no hardcoded managed-agent fallback for covered agents | s01, s02, s06 | Verified by agent registry/materializer tests |
| SC-002 | no internal callers of deleted aliases | s01, s03, s04, s05, s06 | Verified by AST/rg audit across codebase |
| SC-003 | canonical board/runtime paths green | s01, s03, s04, s06 | Verified by board CLI and runtime adapter tests |
| SC-004 | operational fallbacks still bounded and explicit | s01, s04, s05, s06 | Verified by operational resilience and recovery regression tests |
| AC+ #1 | Every managed agent has canonical overlay metadata before `_LEGACY_OVERLAYS` is removed. | s01, s02, s06 | Frontmatter overlay metadata verified across all managed agents |
| AC+ #2 | Board CLI canonical commands no longer route through an unused legacy printer/dispatcher. | s01, s03, s06 | Single dispatcher in `loop/board_sync/cli.py` |
| AC+ #3 | Deleted aliases have zero production, test-support and configuration references, or are explicitly retained with owner and reason in the plan. | s01, s04, s05, s06 | Validated by zero-match rg and caller inventory |
| AC+ #4 | PATH/npx, LLM secondary model, runtime configuration failure and DSH alias behavior are not accidentally removed. | s01, s04, s05, s06 | Preserved and classified as operational reliability |
| AC+ #5 | Canonical runtime/agent/board tests replace old alias tests. | s01, s05, s06 | Obsolete tests rewritten to canonical contracts |
| AC− #1 | Нет hardcoded legacy agent defaults for agents with metadata SOT. | s01, s02, s06 | No `_LEGACY_OVERLAYS` fallback in agent registry |
| AC− #2 | Нет dead public alias definitions without caller proof. | s01, s04, s05, s06 | Zero dead alias definitions in production modules |
| AC− #3 | Нет legacy CLI handler silently reachable from canonical commands. | s01, s03, s06 | Single canonical CLI command routing |
| AC− #4 | Operational fallback is not converted into silent success or removed without replacement. | s01, s04, s06 | Explicit failure and bounded recovery |
| AC− #5 | Нет obsolete tests importing deleted symbols. | s01, s05, s06 | Zero test imports of deleted aliases |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Inventory metadata, CLI, registry and external/dynamic references | plan §До DECOMPOSE | s01 |
| Enforce metadata completeness and canonical board/runtime ownership | plan §До DECOMPOSE | s02, s03 |
| Remove proven dead aliases and old printer/route | plan §До DECOMPOSE | s03, s04, s05 |
| Decide DSH alias and runtime scan rows from reference evidence; retain only bounded operational fallbacks | plan §До DECOMPOSE | s04, s05 |
| Rewrite/delete obsolete tests and instructions | plan §До DECOMPOSE | s05 |
| Run final purge scan and reliability regression | plan §До DECOMPOSE | s06 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Canonical boundary APIs без dead compatibility aliases в проде | s01, s02, s03, s04, s05, s06 |
| Единственный источник истины для agent overlay из canonical frontmatter | s01, s02, s06 |
| Единый canonical dispatcher для board sync CLI без legacy маршрутов | s01, s03, s06 |
| Типизированный lookup runtime адаптеров из registry без слепого сканирования модулей | s01, s04, s06 |
| Удаление мертвых алиасов ABORT_PATTERNS, _handoff_mode_from_legacy_markdown, checkpoint_prompt_lines, validate_shard_yaml | s01, s05, s06 |
| Сохранение и явная классификация operational resilience (PATH/npx, LLM fallback, DSH aliases) | s01, s04, s05, s06 |
| Полный sunset inventory scan и удаление legacy fallback веток (Kind A+B+C+I) | s02, s03, s04, s05, s06 |
| Out of scope (DSH alias removal, new runtime registry design, operational fallback redesign) | — / cut_list |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `harness/hooks/agent_registry.py:_LEGACY_OVERLAYS` | A | canonical agent frontmatter | s02, s06 | yes | delete in-epic |
| `harness/hooks/agent_registry.py:_legacy_or_default` legacy map merge | A | canonical metadata validation | s02, s06 | yes | delete in-epic |
| `loop/board_sync/cli.py:_print_result_legacy` | A | canonical result printers | s03, s06 | no | delete in-epic |
| `loop/board_sync/cli.py:_dispatch_legacy` | A | canonical CLI dispatcher | s03, s06 | yes | delete in-epic |
| `loop/runtime_adapters/common.py:_RUNTIME_ALIASES` unreferenced aliases | A | typed runtime registry | s04, s06 | yes | delete in-epic |
| `loop/runtime_adapters/common.py` module attribute scan fallback | A | registry-owned typed adapter | s04, s06 | yes | delete in-epic |
| `harness/hooks/session_resilience.py:ABORT_PATTERNS` alias | A | `_FATAL_ABORT_PATTERNS` / `_TRANSIENT_ABORT_PATTERNS` | s05, s06 | yes | delete in-epic |
| `loop/schemas/active_context.py:_handoff_mode_from_legacy_markdown` alias | A | `handoff_mode_from_text` | s05, s06 | yes | delete in-epic |
| `harness/hooks/epic_yaml.py:checkpoint_prompt_lines` alias | A | `step_context_prompt_lines` | s05, s06 | yes | delete in-epic |
| `harness/hooks/epic_yaml.py:validate_shard_yaml` alias | A | `validate_shard_yaml_full` | s05, s06 | yes | delete in-epic |
| old board command forms with no supported caller | B | canonical CLI | s03, s06 | yes | delete in-epic |
| missing agent metadata → hardcoded legacy overlay fallback | C | metadata validation error / fail-closed | s02, s06 | yes | delete in-epic |
| registry miss → blind module scan fallback | C | typed registry error / fail-closed | s04, s06 | yes | delete in-epic |
| dead API aliases fallback | C | canonical functions | s05, s06 | yes | delete in-epic |
| docs/instructions naming old board route or agent default map | I | canonical metadata / registry route | s05, s06 | no | delete in-epic |

## Очередь шагов (BACK / FRONT)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-contracts-and-characterization.yaml](s01-contracts-and-characterization.yaml) | [s01…](../../implement/T-HUB-090-boundary-compatibility-shim-purge/s01-contracts-and-characterization.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-canonicalize-agent-overlay-metadata.yaml](s02-canonicalize-agent-overlay-metadata.yaml) | [s02…](../../implement/T-HUB-090-boundary-compatibility-shim-purge/s02-canonicalize-agent-overlay-metadata.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-canonical-board-cli-dispatch.yaml](s03-canonical-board-cli-dispatch.yaml) | [s03…](../../implement/T-HUB-090-boundary-compatibility-shim-purge/s03-canonical-board-cli-dispatch.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-typed-runtime-adapter-registry-dispatch.yaml](s04-typed-runtime-adapter-registry-dispatch.yaml) | [s04…](../../implement/T-HUB-090-boundary-compatibility-shim-purge/s04-typed-runtime-adapter-registry-dispatch.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-dead-alias-purge-and-obsolete-test-rewrite.yaml](s05-dead-alias-purge-and-obsolete-test-rewrite.yaml) | [s05…](../../implement/T-HUB-090-boundary-compatibility-shim-purge/s05-dead-alias-purge-and-obsolete-test-rewrite.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-legacy-fallback-purge.yaml](s06-legacy-fallback-purge.yaml) | [s06…](../../implement/T-HUB-090-boundary-compatibility-shim-purge/s06-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |