# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-087-epic-layout-v2-fallback-purge
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**
**Дата:** 2026-09-11
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — [.cursor/templates/decompose/epic-step.yaml](../../../../../.cursor/templates/decompose/epic-step.yaml).

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-087-epic-layout-v2-fallback-purge/md/decompose-index.md`. Machine = `plan/T-HUB-087-epic-layout-v2-fallback-purge/yaml/decompose-index.yaml`. Shards = `yaml/steps/`.
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `decompose-index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|---|---|
| `writing-plans` | структура шагов, атомарность |
| `python-testing-patterns` | characterization and denial regression tests |
| `architecture-patterns` | layout v2 resolver seams and fail-closed contracts |

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN | Notes |
| :--- | :--- | :--- | :--- |
| US-001 | Как loop, я хочу разрешать plan/decompose/implement только через layout v2, чтобы один epic не имел конкурирующих адресов. | s01, s03, s04, s06 | Canonical v2 resolution across all phases |
| US-002 | Как оператор миграции, я хочу перенести текущие legacy implement artifacts в v2 без потери step/status/evidence. | s01, s02, s06 | Explicit migration of 8 trees and parity check |
| US-003 | Как разработчик, я хочу, чтобы Markdown и v1 path fixtures больше не маскировали отсутствие YAML SoT. | s01, s04, s05, s06 | Fail-closed YAML index loading & denial tests |
| FR-001 | Все live plan/decompose/implement call sites используют `loop.paths.epic_layout` или canonical v2 path API. | s01, s03 | Characterization in s01, runtime wiring in s03 |
| FR-002 | Все 8 legacy `implement/implement-*` trees проходят explicit migration/parity check до удаления. | s01, s02 | Parity inventory in s01, migration & verification in s02 |
| FR-003 | `epic_paths.py` перестаёт искать `plan-*`, `decompose-*` и v1 indexes после cutover. | s03, s04, s06 | Resolver wiring in s03, fallback removal in s04/s06 |
| FR-004 | `epic_yaml.py`, `epic/core.py`, `reconcile.py`, `scan_mb.py`, `mb_load/plan_section.py` не имеют v1/Markdown execution fallback. | s03, s04, s06 | Wiring in s03, fallback removal in s04/s06 |
| FR-005 | `parse_steps_from_md`, `sync_yaml_from_md` и связанные status-write compatibility tests либо удалены, либо оставлены только в offline migration tool с отдельным non-runtime contract. | s04, s05, s06 | Runtime call removal in s04, test rewrite in s05, purge in s06 |
| FR-006 | Ошибка layout/schema не деградирует в другой layout и имеет стабильный diagnostic. | s01, s04 | Negative tests in s01, fail-closed enforcement in s04 |
| FR-007 | Obsolete path tests, fixtures и assertions удалены или переписаны на v2 behavior tests в том же эпике. | s05, s06 | Test suite refactor in s05, inventory verification in s06 |
| SC-001 | 0 active v1 layout branches в перечисленных runtime-модулях | s03, s04, s06 | Wiring in s03, fallback removal in s04, purge in s06 |
| SC-002 | 0 live `implement/implement-*` directories в BACK tree | s02, s06 | Migration in s02, verify purge in s06 |
| SC-003 | v2 arm/load/reconcile/index smoke green | s01, s03, s05, s06 | Integration tests across s01, s03, s05, s06 |
| SC-004 | legacy path invocation завершается ошибкой, а не v2 lookup | s01, s04, s05 | Negative fixtures in s01, denial in s04, tests in s05 |
| AC+ #1 | Вызов canonical v2 для каждого role/epic разрешает plan, decompose index и implement shard без wrapper-ветки. | s01, s03 | |
| AC+ #2 | Legacy `plan-*`, `decompose-*`, `implement-*` и `yaml/steps` runtime paths не вызываются и отсутствуют в active production scope. | s03, s04, s06 | |
| AC+ #3 | Текущие 8 legacy implement trees мигрированы с сохранением step ids, статусов и ссылок. | s02 | |
| AC+ #4 | Markdown index остаётся human-readable documentation, но не является источником runtime step/status. | s04 | |
| AC+ #5 | v1 path/schema input выдаёт explicit failure/diagnostic; silent fallback запрещён. | s01, s04 | |
| AC+ #6 | Тесты проверяют canonical behavior и denial старого layout, а не наличие старого файла. | s01, s05 | |
| AC− #1 | Нет dual v1/v2 resolver path. | s03, s04, s06 | |
| AC− #2 | Нет `try new except legacy` для path resolution. | s03, s04, s06 | |
| AC− #3 | Нет production caller у `parse_steps_from_md`/`sync_yaml_from_md`. | s04, s06 | |
| AC− #4 | Нет live `implement/implement-*` artifacts после migration gate. | s02, s06 | |
| AC− #5 | Нет теста, который требует legacy layout для зелёного runtime. | s05, s06 | |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Characterize v2 behavior and enumerate 8 live legacy trees | plan.md §До DECOMPOSE п.1 | s01 |
| Migrate artifacts and verify step/status/evidence parity | plan.md §До DECOMPOSE п.2 | s02 |
| Wire all runtime callers to canonical v2 resolver | plan.md §До DECOMPOSE п.3 | s03 |
| Enforce denial of old layout and YAML-only runtime loading | plan.md §До DECOMPOSE п.4 | s04 |
| Rewrite/remove path, Markdown and legacy fixture tests | plan.md §До DECOMPOSE п.5 | s05 |
| Run complete `*-legacy-fallback-purge` inventory and regression suite | plan.md §До DECOMPOSE п.6 | s06 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Единственный layout v2 для epic plan/decompose/implement без конкурирующих адресов | s01, s03, s04, s06 |
| Миграция 8 legacy implement trees без потери step/status/evidence | s01, s02, s06 |
| YAML SoT fail-closed load без fallback на Markdown | s01, s04, s05, s06 |
| Полное удаление v1 fallback / discovery ветвей и obsolete fixtures | s03, s04, s05, s06 |
| Out of scope (historical archive cleanup, new resolver redesign, operational fallback changes) | — / cut_list |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `harness/hooks/epic_paths.py:find_decompose_index_path` v1 branches | A | `loop.paths.epic_layout.resolve` | s03, s06 | yes | delete in-epic |
| `harness/hooks/epic_paths.py:find_plan_md_path`, `epic_id_from_plan_path` legacy branches | A | v2 `plan/<epic>/md/plan.md` | s03, s06 | yes | delete in-epic |
| `harness/hooks/epic_yaml.py:resolve_implement_path` leftover `yaml/steps` and `implement-*` | A | `EpicLayoutKind.IMPLEMENT_STEP` | s03, s06 | yes | delete in-epic |
| `harness/hooks/epic_yaml.py:_resolve_decompose_dir` v1 fallbacks | A | canonical v2 resolver | s03, s06 | yes | delete in-epic |
| `harness/hooks/epic/core.py:_load_decompose_steps`, `load_decompose_steps_fail_closed` Markdown fallback | A | YAML-only loader | s04, s06 | yes | delete in-epic |
| `harness/hooks/epic/reconcile.py:resolve_epic_bundle` v1 fallback | A | v2 implement dir | s03, s06 | yes | delete in-epic |
| `harness/hooks/epic_resolve.py` legacy decompose/implement checks | A | canonical layout resolver | s03, s06 | yes | delete in-epic |
| `loop/board_sync/scan_mb.py:_index_paths` v1 scan | A | v2 scan | s03, s06 | no | delete in-epic |
| `loop/mb_load/plan_section.py` legacy candidates | A | v2 plan path | s03, s06 | no | delete in-epic |
| `harness/hooks/epic_index.py:parse_steps_from_md`, `sync_yaml_from_md` runtime calls | A | v2 YAML loader / offline migration tool | s04, s06 | yes | delete in-epic |
| `loop/migrate/epic_layout_v1_to_v2.py` runtime use | A | explicit migration CLI only | s02, s06 | no | delete in-epic |
| legacy path fixtures/assertions (`loop/tests/fixtures/board_sync/.../decompose-*`, resolver v1 cases) | A | v2 fixtures & denial tests | s05, s06 | no | delete in-epic |
| `--decompose`/path-only arm input | B | `--epic-id` + canonical resolver | s03, s06 | no | delete in-epic |
| implicit v1 migration during load | B | explicit migration command | s02, s04, s06 | yes | delete in-epic |
| v2 missing → v1 path fallback | C | explicit missing/invalid diagnostic | s01, s04, s06 | yes | delete in-epic |
| YAML missing → Markdown parse fallback | C | fail-closed YAML-only load | s04, s06 | yes | delete in-epic |
| v2 implement missing → `implement-*` fallback | C | v2 missing diagnostic | s03, s04, s06 | yes | delete in-epic |
| instructions naming `decompose-*`, `plan-*.md`, `implement-*` as live paths | I | v2 resolver paths | s05, s06 | no | delete in-epic |
| migration wording that implies transparent fallback | I | explicit one-time migration then fail-closed runtime | s05, s06 | no | delete in-epic |

## Очередь шагов (BACK / FRONT)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-contracts-and-seams.yaml](s01-contracts-and-seams.yaml) | [s01…](../../implement/T-HUB-087-epic-layout-v2-fallback-purge/s01-contracts-and-seams.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-migrate-legacy-implement-trees.yaml](s02-migrate-legacy-implement-trees.yaml) | [s02…](../../implement/T-HUB-087-epic-layout-v2-fallback-purge/s02-migrate-legacy-implement-trees.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-wire-runtime-v2-resolvers.yaml](s03-wire-runtime-v2-resolvers.yaml) | [s03…](../../implement/T-HUB-087-epic-layout-v2-fallback-purge/s03-wire-runtime-v2-resolvers.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s04** | [s04-yaml-sot-and-fail-closed-loading.yaml](s04-yaml-sot-and-fail-closed-loading.yaml) | [s04…](../../implement/T-HUB-087-epic-layout-v2-fallback-purge/s04-yaml-sot-and-fail-closed-loading.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s05** | [s05-obsolete-test-and-fixture-rewrite.yaml](s05-obsolete-test-and-fixture-rewrite.yaml) | [s05…](../../implement/T-HUB-087-epic-layout-v2-fallback-purge/s05-obsolete-test-and-fixture-rewrite.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s06** | [s06-legacy-fallback-purge.yaml](s06-legacy-fallback-purge.yaml) | [s06…](../../implement/T-HUB-087-epic-layout-v2-fallback-purge/s06-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | pending |
