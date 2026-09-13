# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-089-event-dag-roadmap-fallback-purge
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**
**Дата:** 2026-09-12
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — [.cursor/templates/decompose/epic-step.yaml](../../../../../.cursor/templates/decompose/epic-step.yaml).

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-089-event-dag-roadmap-fallback-purge/md/decompose-index.md`. Machine = `plan/T-HUB-089-event-dag-roadmap-fallback-purge/yaml/decompose-index.yaml`. Shards = `yaml/steps/`.
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `decompose-index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|---|---|
| `writing-plans` | структура шагов, атомарность |
| `python-testing-patterns` | characterization and denial regression tests |
| `architecture-patterns` | canonical v2 schema enforcement and fail-closed boundaries |
| `python-design-patterns` | validator abstractions and caller rewires |
| `python-anti-patterns` | purge implicit fallback branches and legacy adapters |

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN | Notes |
| :--- | :--- | :--- | :--- |
| US-001 | Как lifecycle reducer, я хочу читать только canonical event v2 и игнорировать dead history без adapter branch. | s01, s02, s05, s06 | Canonical event v2 reader and isolated historical ignore |
| US-002 | Как DAG runner, я хочу выполнять только v2 manifest с explicit autonomous contract. | s01, s03, s05, s06 | DAG v2 validation before arm, denial of v1 manifests |
| US-003 | Как roadmap runner, я хочу одну v2 queue и YAML-only merge. | s01, s04, s05, s06 | Roadmap v2 queue enforcement, purge v1 and markdown mirror |
| FR-001 | `read_event_log_result` consumes canonical v2 live logs; v1 conversion is removed from live read path. | s01, s02, s06 | Live event reader fails closed on non-v2 logs |
| FR-002 | `migrate_event_log` is isolated as explicit offline migration or deleted if no supported consumer remains. | s01, s02, s06 | Offline migration boundary isolated from live execution |
| FR-003 | `reflection_done` remains a dead historical kind only where required for archive replay; it cannot affect phase or trigger fallback. | s01, s02, s05, s06 | Historical classifier retained for archive, dead in live |
| FR-004 | `loop/context_loop._arm_dag_next` rejects v1 manifests instead of calling `adapt_manifest` implicitly. | s01, s03, s06 | Direct v2 manifest validation in `_arm_dag_next` |
| FR-005 | `QUEUE_VERSION_V1`, `LEGACY_DEFAULT_QUEUE`, legacy plan lookup and Markdown mirror are removed from normal roadmap runtime. | s01, s04, s06 | Roadmap v2 queue only, purge v1 and legacy path probing |
| FR-006 | `roadmap_merge` writes only `roadmap/queue.yaml`; `canon_md_rel` and `_render_merged_roadmap_md` are removed when no dry-run/API caller remains. | s01, s04, s06 | YAML-only roadmap merge, delete markdown mirror renderers |
| FR-007 | v2 behavior, explicit denial and historical archive semantics are covered by tests; adapter-only tests are deleted. | s01, s05, s06 | Test suite refactoring to assert v2 contracts and denial |
| SC-001 | no live v1 event/DAG/queue adapters | s02, s03, s04, s06 | Verified by AST/rg audit and purge |
| SC-002 | v2 event/DAG/roadmap flows green | s01, s02, s03, s04, s05, s06 | Verified by targeted pytest suites |
| SC-003 | legacy inputs fail closed | s01, s02, s03, s04, s06 | Verified by negative fixtures and denial assertions |
| SC-004 | archive preservation decision is executable | s01, s02, s05, s06 | Verified by archive migration/retention tests |
| AC+ #1 | Live reducer never calls `adapt_v1_event`. | s01, s02, s06 | Removed from live reader path |
| AC+ #2 | Live DAG arm never calls `adapt_manifest` for v1. | s01, s03, s06 | Replaced with strict v2 validation before arm |
| AC+ #3 | Default roadmap parser never probes `plan/roadmap-epics.queue.yaml`. | s01, s04, s06 | Removed legacy default queue fallback |
| AC+ #4 | No runtime code builds or writes a Markdown roadmap mirror. | s01, s04, s06 | Removed `canon_md_rel` and `_render_merged_roadmap_md` |
| AC+ #5 | Archived `reflection_done` remains non-semantic and does not alter lifecycle. | s01, s02, s05, s06 | Verified harmless in event replay |
| AC+ #6 | Tests retain valid v2 and historical ignore behavior, but delete adapter success tests when adapter is removed. | s01, s05, s06 | Rewritten test suites |
| AC− #1 | Нет v1 adapter invocation from live event/DAG/roadmap call sites. | s02, s03, s04, s06 | Verified by call site scan |
| AC− #2 | Нет legacy queue fallback when v2 queue is missing. | s04, s06 | Verified by missing queue error tests |
| AC− #3 | Нет `canon_md_rel`/Markdown mirror production dependency. | s04, s06 | Verified by AST/import audit |
| AC− #4 | Нет тестов, которые требуют v1 migration as runtime success. | s05, s06 | Verified by test suite audit |
| AC− #5 | Archive compatibility is explicit, bounded and not a hidden fallback. | s02, s06 | Verified by migration tool isolation |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Characterize v2 event/DAG/roadmap flows and archive requirements | plan §До DECOMPOSE | s01 |
| Split live readers from explicit migration/retention tools | plan §До DECOMPOSE | s02 |
| Wire all consumers to v2 validators and queue | plan §До DECOMPOSE | s03, s04 |
| Enforce denial of v1 inputs and missing v2 queue | plan §До DECOMPOSE | s02, s03, s04 |
| Delete mirror/adapter tests and rewrite v2/deny coverage | plan §До DECOMPOSE | s05 |
| Run final purge inventory and full regression | plan §До DECOMPOSE | s06 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Единственные v2 event/DAG/roadmap runtime contracts в проде | s01, s02, s03, s04, s06 |
| Отделение архивной миграции событий от live runtime reducer | s01, s02, s06 |
| Строгая валидация v2 DAG манифестов в `_arm_dag_next` без авто-адаптации | s01, s03, s06 |
| Исключительно YAML roadmap-queue/v2 без fallback на v1 и без markdown mirror | s01, s04, s06 |
| Рефакторинг тестов и инструкций на канонические v2 контракты и fail-closed denial | s01, s05, s06 |
| Полный sunset inventory scan и удаление legacy fallback веток (Kind A+B+C+I) | s02, s03, s04, s05, s06 |
| Out of scope (redesign of v2 schemas, archive rewrite beyond current migration contract, new roadmap features) | — / cut_list |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `harness/hooks/epic_events.py:adapt_v1_event` live branch | A | v2 event validator | s02, s06 | yes | delete in-epic |
| `loop/dag.py:adapt_manifest`, `migrate_manifest` live arm calls | A | v2 `validate_manifest` | s03, s06 | yes | delete in-epic |
| `loop/roadmap_queue.py:QUEUE_VERSION_V1` runtime support | A | v2 queue (`roadmap-queue/v2`) | s04, s06 | yes | delete in-epic |
| `loop/roadmap_queue.py:_render_merged_roadmap_md`, `canon_md_rel` | A | YAML queue result | s04, s06 | no | delete in-epic |
| `loop/roadmap_queue.py:resolve_epic_slug` legacy plan/decompose probes | A | canonical epic identity | s04, s06 | yes | delete in-epic |
| implicit event/DAG/roadmap migration during runtime | B | explicit offline migration CLI or diagnostic error | s02, s03, s04, s06 | yes | delete in-epic |
| `write_md`/mirror preview in roadmap merge | B | YAML-only merge output | s04, s06 | no | delete in-epic |
| non-v2 event → adapter in `read_event_log_result` | C | schema error / fail-closed | s02, s06 | yes | delete in-epic |
| invalid DAG → inferred v2/autonomous false in `_arm_dag_next` | C | validation failure | s03, s06 | yes | delete in-epic |
| missing v2 queue → `LEGACY_DEFAULT_QUEUE` probe in `resolve_queue_path` | C | queue_missing error | s04, s06 | yes | delete in-epic |
| roadmap docs naming Markdown mirror as SoT | I | v2 queue YAML | s05, s06 | no | delete in-epic |
| runbook suggesting v1 DAG/event input | I | v2 schemas + explicit migration | s05, s06 | no | delete in-epic |

## Очередь шагов (BACK / FRONT)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-characterize-flows-and-archive-boundaries.yaml](s01-characterize-flows-and-archive-boundaries.yaml) | [s01…](../../implement/T-HUB-089-event-dag-roadmap-fallback-purge/s01-characterize-flows-and-archive-boundaries.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-purge-live-event-fallbacks.yaml](s02-purge-live-event-fallbacks.yaml) | [s02…](../../implement/T-HUB-089-event-dag-roadmap-fallback-purge/s02-purge-live-event-fallbacks.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-enforce-v2-dag-validation-and-purge-arm-adapters.yaml](s03-enforce-v2-dag-validation-and-purge-arm-adapters.yaml) | [s03…](../../implement/T-HUB-089-event-dag-roadmap-fallback-purge/s03-enforce-v2-dag-validation-and-purge-arm-adapters.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-purge-roadmap-v1-and-markdown-mirror.yaml](s04-purge-roadmap-v1-and-markdown-mirror.yaml) | [s04…](../../implement/T-HUB-089-event-dag-roadmap-fallback-purge/s04-purge-roadmap-v1-and-markdown-mirror.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-rewrite-obsolete-tests-and-instructions.yaml](s05-rewrite-obsolete-tests-and-instructions.yaml) | [s05…](../../implement/T-HUB-089-event-dag-roadmap-fallback-purge/s05-rewrite-obsolete-tests-and-instructions.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-legacy-fallback-purge.yaml](s06-legacy-fallback-purge.yaml) | [s06…](../../implement/T-HUB-089-event-dag-roadmap-fallback-purge/s06-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |