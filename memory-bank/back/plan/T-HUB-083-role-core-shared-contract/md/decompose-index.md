# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-083-role-core-shared-contract  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — единственный источник статуса  
**Дата:** 2026-09-08  
**Режим:** BACK DECOMPOSE

Эпик извлекает общую policy границу из трёх role-core файлов, не превращая роли в generic core. Нарезка сохраняет путь `red → shared owner → role wiring → purge → semantic/full regression`; каждый outcome проверяется по реальным rule-файлам и production-adjacent semantic corpus, а не по существованию одного нового документа.

## Skills в контексте

| Skill | Зачем |
|---|---|
| `writing-plans` | Сессионный skill для атомарности и coverage decompose; не передаётся в IMPLEMENT. |
| `tdd` | Red/green цикл для semantic contract tests в `s01` и mode-W regression в `s05`. |
| `python-testing-patterns` | Структура fail-closed corpus tests и детерминированные fixture assertions. |
| `modern-python` | Python 3.12 typing/path handling в semantic test helpers. |
| `python-anti-patterns` | Не допустить broad-read, unconditional managed pytest и тестовую проверку через fallback. |

`S02–S04` — docs-only rule extraction/rewire/purge; для них `skills.impl: []`. Все `sNN` имеют `needs_creative: "no"`; творческое решение не требуется.

## Requirements coverage (plan → steps)

> Каждая FR/AC+/AC− и каждая TM из плана имеет конкретный shard и измеримый checkpoint. Для docs-only outcomes verify использует `rg`/структурный corpus scan; для semantic outcomes — runnable `bin/pytest` с явным timeout в каноническом wrapper.

| Req ID | Plan FR text (verbatim) | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | shared core is sole owner of common policy. | s02, s03, s04 | s02 создаёт owner; s03 wires consumers; s04 доказывает отсутствие A/I остатков и второго owner. |
| FR-002 | each role core imports it once and contains only role-only semantics. | s03, s04 | s03 сохраняет BACK/FRONT/INTEG deltas; s04 проверяет import cardinality, copied-body purge и role markers. |
| FR-003 | semantic tests require BACK promotion, FRONT parent-only boundary, INTEG contract fanout and hub/managed branch wording. | s01, s05 | s01 даёт red corpus и per-role assertions; s05 закрывает mode-W/full-regression matrix. |
| AC+ #1 | Common policy changes in one source. | s02, s03, s04 | Shared file — единственный common owner; role files содержат ссылку, а не копию. |
| AC+ #2 | Missing import, copied common prose or missing role marker fails. | s01, s03, s04 | Red tests и fail-closed scans проверяют все три failure conditions. |
| AC+ #3 | No mode W needs compensating changes. | s05 | Regression test подтверждает, что остальные workflow modes не требуют role-specific компенсации после extraction. |
| AC− #1 | No generic core replacing role responsibility; no unconditional managed pytest; no weakening lifecycle/UI/contract guards. | s03, s04, s05 | Role marker matrix, runner branch scan, negative guard assertions и full suite. |
| TM-083-01 | common import | s01, s02, s03 | Red test → shared contract → три canonical imports. |
| TM-083-02 | no copied body | s01, s03, s04 | Corpus rejects copied common paragraphs and duplicate owner. |
| TM-083-03 | BACK lifecycle | s01, s03, s05 | Promotion/transition assertions остаются в BACK core и проходят regression. |
| TM-083-04 | FRONT parent-only | s01, s03, s05 | Parent-only test boundary и visible-UI semantics остаются в FRONT core. |
| TM-083-05 | INTEG contract | s01, s03, s05 | Element-first, §Contract и BACK/FRONT/GAP fanout остаются в INTEG core. |
| TM-083-06 | full suite | s05 | Полный hub suite запускается только parent после decompose, как QA evidence. |
| Independent test | Общая policy имеет одного владельца, а уникальные обязанности каждой роли не растворяются при extraction. | s01, s03, s04, s05 | Named semantic tests + structural sunset scan + full regression. |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| classify/red tests | plan §Draft stages, пункт 1 | s01 |
| shared core contract creation | plan §Draft stages, пункт 2 | s02 |
| rewire role cores while retaining role-only semantics | plan §WHAT и §HOW / Eng spine | s03 |
| purge copied common prose and duplicate instruction surfaces | plan §Draft stages, пункт 3; Replacement / sunset A/C/I | s04 |
| role fixtures and semantic matrix | plan §Draft stages, пункт 4; TM-083-03..05 | s05 |
| targeted semantic checks and full suite | plan TM-083-06 | s05 |
| add → wire → enforce → purge for the sole shared policy owner | behavior-first/spec-first canon | s02, s03, s04, s05 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| One common policy source can be changed once and observed by all three roles. | s02, s03, s04 |
| Each role consumes the shared contract exactly once. | s03, s04 |
| BACK promotion/lifecycle remains explicit and independent from extraction. | s01, s03, s05 |
| FRONT visible-UI and parent-only test boundary remains explicit and cannot be weakened by the shared file. | s01, s03, s05 |
| INTEG element-first contract and BACK/FRONT/GAP fanout remains explicit. | s01, s03, s05 |
| Hub runner keeps the bounded `bin/pytest` branch while managed projects keep capability/evidence verification; no unconditional managed pytest. | s02, s03, s04, s05 |
| Missing import, copied common prose, missing marker and duplicate owner fail closed. | s01, s04, s05 |
| No mode W receives compensating changes or a hidden second policy source. | s05 |
| Out of scope: generic role core, product runtime behavior, and weakening of lifecycle/UI/contract guards. | —; explicit AC−, no follow-up |

## Replacement cleanup (plan → steps)

> Brownfield replacement is explicit. Every non-`n/a` sunset row has a concrete owner with non-empty `deletes:` and a final `s04-role-core-legacy-fallback-purge` inventory. Kind B is explicitly `n/a`; no deployment/entrypoint surface is invented for a rule-only extraction.

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| Common paragraphs copied in `back/front/integration mainrule-core.mdc` | A | `shared/role-core-contract.mdc` + one import per role | s03, s04 | no | s03 removes known copies after wiring; s04 scans and deletes residual bodies. |
| A role core accepted without the shared policy import | C | fail-closed semantic validation | s04 | yes | Missing import is a validation failure, never a local fallback or standalone success. |
| Duplicate MEMORY BANK / format / runner prose in role cores | I | single shared import and role-only markers | s03, s04 | no | Includes instructions that would otherwise create a second active policy source. |
| n/a — no B entrypoint/deploy replacement | — | — | — | — | Rule-only extraction; no B surface in the plan. |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-role-core-contract-red-tests.yaml](../yaml/steps/s01-role-core-contract-red-tests.yaml) — semantic corpus for common owner and role guards | [s01…](../../implement/T-HUB-083-role-core-shared-contract/s01-role-core-contract-red-tests.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s02** | [s02-shared-role-core-contract.yaml](../yaml/steps/s02-shared-role-core-contract.yaml) — shared owner for loading, format and runner policy | [s02…](../../implement/T-HUB-083-role-core-shared-contract/s02-shared-role-core-contract.yaml) | no | no | BACK IMPLEMENT | pending |
| **s03** | [s03-role-core-wiring-and-preservation.yaml](../yaml/steps/s03-role-core-wiring-and-preservation.yaml) — one import plus BACK/FRONT/INTEG-only semantics | [s03…](../../implement/T-HUB-083-role-core-shared-contract/s03-role-core-wiring-and-preservation.yaml) | no | no | BACK IMPLEMENT | pending |
| **s04** | [s04-role-core-legacy-fallback-purge.yaml](../yaml/steps/s04-role-core-legacy-fallback-purge.yaml) — A/C/I sunset inventory and fail-closed purge | [s04…](../../implement/T-HUB-083-role-core-shared-contract/s04-role-core-legacy-fallback-purge.yaml) | no | no | BACK IMPLEMENT | pending |
| **s05** | [s05-role-core-semantic-regression.yaml](../yaml/steps/s05-role-core-semantic-regression.yaml) — mode-W matrix and full suite evidence | [s05…](../../implement/T-HUB-083-role-core-shared-contract/s05-role-core-semantic-regression.yaml) | no | yes | BACK IMPLEMENT | pending |

Следующая фаза после DECOMPOSE — **BACK ANALYZE**. Переход к IMPLEMENT до `validate-decompose-tree` exit 0, `validate-traceability` с `CRITICAL=0` и обязательного ANALYZE с `critical_count=0` запрещён.
