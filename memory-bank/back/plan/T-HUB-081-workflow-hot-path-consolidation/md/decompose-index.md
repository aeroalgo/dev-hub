# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-081-workflow-hot-path-consolidation  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — канон status  
**Дата:** 2026-09-08  
**Режим:** BACK DECOMPOSE  
**Уровень:** L3  
**Granularity:** 5 sNN (advisory band 5–8; без micro-ladder; TDD остаётся внутри capability step)

Каждый шаг — outcome-first задача для одного cutover слоя; shard: `yaml/steps/sNN-<slug>.yaml` по `.cursor/templates/decompose/epic-step.yaml`.

> **Layout v2:** этот файл = `plan/<plan_id>/md/decompose-index.md`; machine status = `yaml/decompose-index.yaml`; shards = `yaml/steps/`. `md/decompose-index.md` не загружается в IMPLEMENT hot path.  
> **Ownership:** после cutover один активный владелец каждого режима — `## Hot path` внутри canonical `workflow-*.mdc`; standalone quick-path files удалены.  
> **Ordering:** s01 corpus contract → s02 embed → s03 rewire active callers → s04 delete sources → s05 full A+B+C+I purge.

## Skills в контексте

| Skill | Зачем |
|---|---|
| `writing-plans` | структура и атомарность DECOMPOSE-сессии; не входит в `impl:` |
| `tdd` · `python-testing-patterns` · `modern-python` · `python-anti-patterns` | Core(4) для code/test shards; docs-only shards имеют `impl: []` |

**Per-step:** каждый YAML содержит top-level `skills.code_surface` и `skills.impl`; session skill `writing-plans` не копируется в `impl:`. Ситуационные skills не нужны: scope — corpus tests и docs-only workflow instruction surfaces.

## Requirements coverage (plan → steps)

> Каждая строка ниже — дословная формулировка plan FR/AC/AC−/TM либо явно идентифицируемый plan outcome. Covered row имеет measurable verify в соответствующем shard; нет `deferred` без follow-up.

| Req ID | Plan FR / AC text (verbatim) | sNN | Notes / measurable verify |
|---|---|---|---|
| FR-001 | BACK DECOMPOSE, IMPLEMENT, PLAN и INTEG PLAN получают `## Hot path` в canonical `workflow-*.mdc`. | s02 | 4 workflow files each contain `## Hot path`; `rg` marker command |
| FR-002 | embedded path сохраняет scope-lock/FINISH, coverage+sunset и PLAN clarify/queue/prompt соответственно. | s02 | required marker groups in targeted `rg` checks |
| FR-003 | active standalone `back-decompose`, `back-implement`, `back-plan`, `integ-plan` cheatsheets и их ссылки удалены. | s03, s04, s05 | no active old-path rg; four files absent |
| FR-004 | corpus test проверяет один hot-path owner, required mode markers и no dangling link. | s01, s05 | named corpus test and full targeted run |
| AC+1 | Default route режима читает одним документом меньше, не меняя обязательный gate. | s03, s04 | same-file owner and source absence; gates remain declared |
| AC+2 | Injected old cheatsheet reference или пропущенный marker ломает test. | s01, s03, s04 | negative corpus fixtures/checks |
| AC+3 | Archive/history не классифицируется как active caller. | s01, s05 | explicit active corpus exclusion test |
| AC−1 | Нельзя инлайнить `_lean/implement.mdc` или ослаблять lazy FINISH. | s02, s03 | marker/forbidden-content checks |
| AC−2 | Нет двух active quick-path sources и compatibility alias. | s04, s05 | source absence + duplicate-owner inventory |
| AC−3 | Нет изменения runtime/router/skill selection. | s02, s03, s04, s05 | files allowlist excludes runtime; B inventory = n/a |
| TM-081-01 | stale cheatsheet link → target test fails. | s01, s03, s04, s05 | dangling-link corpus test |
| TM-081-02 | four mode routes → Hot path + required marker pass. | s01, s02, s05 | one owner + marker corpus |
| TM-081-03 | removed source scan → zero active callers. | s03, s04, s05 | active scope `rg` = zero |
| TM-081-04 | full hub suite → `bin/pytest -q --tb=line` PASS. | s05 | QA consume recorded; full suite is BACK QA, not targeted IMPLEMENT |
| Outcome invariant | Краткий маршрут и полный workflow живут в одном каноническом документе; обязательные гейты не теряются при сокращении чтения. | s02, s03, s04, s05 | same-file Hot path + gate marker scan + source purge |
| AC− / forbidden change | Изменение runtime, scope lock или длинных lean contracts. | — | Explicitly forbidden by plan; no implementation shard is required. |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
|---|---|---|
| Red corpus inventory: owner, marker, dangling-link and exclusion contract | plan §Draft stages #1; FR-004; TM-081-01..03 | s01 |
| Embed four mode-specific Hot paths without copying lean gates | plan §Draft stages #2; FR-001/002; AC−1 | s02 |
| Rewire active router/role-command/workflow callers to same-file owner | plan §HOW / Eng spine; FR-003; AC+1 | s03 |
| Delete standalone source files after caller migration | plan §Draft stages #3; FR-003; AC−2 | s04 |
| A+B+C+I sunset inventory, source/Instruction purge and regression scan | plan §Draft stages #4; §Replacement / sunset; TM-081-03/04 | s05 |
| Behavior-first ladder: add → wire → enforce → purge | shared behavior-first §3–§4 | s01 add contract → s02 embed → s03 wire → s04/s05 enforce+purge |
| Preserve lean gate boundaries and lazy FINISH | plan §AC−; workflow DECOMPOSE/IMPLEMENT Gates | s02, s03, s05 |
| QA handoff for targeted corpus and full suite | plan §QA consumes | s05 (targeted evidence; BACK QA full suite) |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
|---|---|
| Один canonical owner для BACK DECOMPOSE Hot path | s02, s04, s05 |
| Один canonical owner для BACK IMPLEMENT Hot path | s02, s03, s04, s05 |
| Один canonical owner для BACK PLAN Hot path | s02, s03, s04, s05 |
| Один canonical owner для INTEG PLAN Hot path | s02, s03, s04, s05 |
| Default route читает на один документ меньше | s03, s04 |
| Обязательные DECOMPOSE coverage/ANALYZE markers сохранены | s02, s05 |
| Обязательные IMPLEMENT scope-lock/FINISH markers сохранены | s02, s03, s05 |
| BACK PLAN clarify/queue/prompt route сохранён | s02, s03, s05 |
| INTEG PLAN inventory/queue/reconcile/prompt route сохранён | s02, s03, s05 |
| Нет active dangling old reference или compatibility alias | s01, s03, s04, s05 |
| Archive/history не false-positive | s01, s05 |
| Runtime/router/skill selection не меняются | s02–s05, B = n/a inventory |
| Full hub suite | s05 → BACK QA consume |

## Replacement cleanup (plan → steps)

> Brownfield replace. Completeness ladder: **add → wire → enforce → purge**. Every A/B/C/I row has an owning step with `deletes:`; final s05 contains `sunset_inventory` + executable `grep_control`. B is explicit `n/a`, because the plan forbids runtime/entrypoint changes.

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
|---|:---:|---|---|:---:|---|
| `shared/cheatsheets/back-decompose.mdc` as active owner | A | `back_developer/workflow-decompose.mdc#Hot path` | s04, s05 | no | delete after s02/s03 |
| `shared/cheatsheets/back-implement.mdc` as active owner | A | `back_developer/workflow-implement.mdc#Hot path` | s04, s05 | no | FRONT/INTEG callers migrated in s03 |
| `shared/cheatsheets/back-plan.mdc` as active owner | A | `back_developer/workflow-plan.mdc#Hot path` | s04, s05 | no | no compatibility alias |
| `shared/cheatsheets/integ-plan.mdc` as active owner | A | `integration_developer/workflow-plan.mdc#Hot path` | s04, s05 | no | no second INTEG source |
| compose/CLI/deploy/runtime/router/skill-selection entrypoints | B | n/a — preserve unchanged | s05 inventory | no | explicit out-of-scope / no-op row |
| active caller following deleted standalone source | C | same-file canonical Hot path | s03, s05 | yes | old reference must fail scan; no silent fallback |
| compatibility alias / duplicate quick-path source | C | no alias; canonical section only | s04, s05 | yes | alias without follow-up forbidden |
| Kind I instruction requiring separate cheatsheet read | I | canonical workflow `## Hot path` instruction | s03, s05 | no | role-command and mainrule rewired |
| obsolete test asserting standalone source is owner | A | negative source-absence / canonical-owner test | s01, s04, s05 | no | rewrite/delete in same epic |
| archive/history mention of old route | I | preserve archive/history and exclude from active corpus | s01, s05 | no | not an active caller; no purge required |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
|---|---|---|:---:|:---:|---|---|
| **s01** | [s01-corpus-owner-contract.yaml](../yaml/steps/s01-corpus-owner-contract.yaml) | [s01](../../implement/T-HUB-081-workflow-hot-path-consolidation/s01-corpus-owner-contract.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-embed-canonical-hot-paths.yaml](../yaml/steps/s02-embed-canonical-hot-paths.yaml) | [s02](../../implement/T-HUB-081-workflow-hot-path-consolidation/s02-embed-canonical-hot-paths.yaml) | no | no (docs-only) | BACK IMPLEMENT | completed |
| **s03** | [s03-rewire-active-callers.yaml](../yaml/steps/s03-rewire-active-callers.yaml) | [s03](../../implement/T-HUB-081-workflow-hot-path-consolidation/s03-rewire-active-callers.yaml) | no | no (docs-only) | BACK IMPLEMENT | completed |
| **s04** | [s04-delete-standalone-sources.yaml](../yaml/steps/s04-delete-standalone-sources.yaml) | [s04](../../implement/T-HUB-081-workflow-hot-path-consolidation/s04-delete-standalone-sources.yaml) | no | no (docs-only) | BACK IMPLEMENT | pending |
| **s05** | [s05-legacy-fallback-purge.yaml](../yaml/steps/s05-legacy-fallback-purge.yaml) | [s05](../../implement/T-HUB-081-workflow-hot-path-consolidation/s05-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
`needs_creative`: все `no`; plan не содержит open CR и не требует BACK CREATIVE.  
`TDD`: s01 и s05 держат corpus/regression test red→implementation→green внутри шага; docs-only s02–s04 не являются самостоятельным red-test ladder.  
**Next after DECOMPOSE:** BACK ANALYZE (обязателен; `ANALYZE deferred` запрещён).
