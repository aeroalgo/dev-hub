# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-027-back-plan-gstack-adapt
**План:** [plan/T-HUB-027-back-plan-gstack-adapt/md/plan.md](../plan/T-HUB-027-back-plan-gstack-adapt/md/plan.md)
**Machine index:** [index.yaml](index.yaml) — **канон status**
**Дата:** 2026-08-31
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (docs/rules или один test-file). Shard: `sNN-<slug>.yaml`.

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, workflow docs |
| `brainstorming` | Plan review batch principles (s04) |

**Per-step:** skills gate (Core + situational из skills-gate-situational); канон в каждом sNN. Docs-only шаги: `impl: []`.

---

## Requirements coverage (plan → steps)

| ID | Requirement | Steps | Rationale |
|:---|:---|:---|:---|
| FR-001 | workflow-clarify-core Product probe 6Q + квота CLARIFY | s01 | shared clarify core |
| FR-002 | clarify.md опциональная Product probe секция | s01 | template |
| FR-003 | plan.md 5 новых секций | s02, s03 | spine s02; QA/readiness/batch s03 |
| FR-004 | Eng review spine subsections + min rows | s02 | data-flow, failure matrix, self-check |
| FR-005 | workflow-plan step 2p + FINISH readiness | s04 | batch + gate |
| FR-006 | workflow-qa + lean/qa qa_consumes load | s05, s08 | add s05; purge C fallback s08 |
| FR-007 | refs gstack-adapt-027.md | s06 | telegraph doc |
| FR-008 | role-command PLAN FINISH guards | s06 | Review readiness + qa_consumes |
| FR-009 | Legacy plans без секций valid | s05, s08 | gate only new; no mutate old plans |
| US-001 | Product probe до WHAT | s01, s02 | CLARIFY + plan batch table |
| US-002 | Eng spine visible before DECOMPOSE | s02, s04 | template + workflow gate |
| US-003 | BACK QA test plan без monolith | s03, s05, s07 | template + load rule + qa yaml |
| US-004 | Review readiness FINISH table | s03, s04, s06 | template + workflow + role-command |
| US-005 | Plan review batch one chat | s03, s04 | batch log + step 2p |
| SC-001 | 100% new L3 plans have Eng spine | s02, s07 | template + spot-check rg |
| SC-002 | BACK QA closes epic via qa_consumes | s05, s07 | load rule + qa yaml coverage |
| SC-003 | DECOMPOSE consumes TM-ids not full matrix | s03 | template contract; decompose refs plan §QA consumes |
| AC+ #1 | plan.md 5 секций min rows | s02, s03 | split template edits |
| AC+ #2 | workflow-plan 2p + FINISH gate | s04 | workflow + lean |
| AC+ #3 | workflow-clarify-core 6Q + квота | s01 | clarify core |
| AC+ #4 | workflow-qa + lean qa_consumes | s05, s08 | load + purge |
| AC+ #5 | refs doc exists | s06 | gstack-adapt-027.md |
| AC+ #6 | exemplar Review readiness CLEARED | s06, s07 | refs fragment + fixture |
| AC+ #7 | rg hits template + workflow | s07 | rg matrix test |
| AC− #1 | No gstack slash install | — | out_of_scope (plan) |
| AC− #2 | No DECOMPOSE replacement | — | out_of_scope (plan) |
| AC− #3 | No browser QA in BACK | — | out_of_scope (plan) |
| AC− #4 | §0.0 SUSPENSION GUARD — no telegraph cap | s02, s03 | min-rows comments not economy |
| AC− #5 | No mandatory AskUserQuestion one-by-one | s04 | batch table only |
| AC− brownfield #1 | Old plans not FAIL | s05 | FR-009 gate wording |
| AC− brownfield #2 | Additive-only templates/rules | all | no code sunset A/B |

## Stages coverage (план канон → shards)

| Этап / фаза плана | Шаги | sNN |
|:---|:---|:---|
| Product probe CLARIFY + template | clarify-core + clarify.md | s01 |
| Plan template Eng spine | Product probe + data-flow + failures + self-check | s02 |
| Plan template QA + readiness + batch log | #qa-consumes + Review readiness + batch log | s03 |
| workflow-plan step 2p + lean gates 8–10 | batch + FINISH readiness | s04 |
| BACK QA qa_consumes load + finish-doc-router | workflow-qa + lean/qa + router hint | s05 |
| Refs + role-command guards | gstack-adapt-027 + SKILL mirror | s06 |
| Тест-стратегия: rg + dry-run + clarify regression | pytest fixture + qa yaml | s07 |
| Replacement C purge | anti-fallback rg + entrypoint inventory | s08 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
|:---|:---|
| Challenge product до HOW — не планировать мимо проблемы | s01, s02 |
| Eng spine — скрытые допущения видны до DECOMPOSE | s02, s04 |
| BACK QA lean — test matrix без monolith plan load | s03, s05, s07 |
| Review readiness — одна таблица готовности к DECOMPOSE | s03, s04, s06 |
| Plan review batch — один PLAN-чат без gstack пауз | s03, s04 |
| gstack borrowings задокументированы | s06 |
| Измеримая верификация AC+ (rg + pytest) | s07 |
| C fallback purge — no eternal full-plan QA shim | s05, s08 |
| Out of scope: gstack install, FRONT parity, browser QA, GSD layout | — / follow-up |
| Out of scope: FRONT plan mirror | follow-up (optional one-liner не блокирует) |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind (A\|B\|C) | Замена | sNN (deletes) | Fallback? | Notes |
|:---|:---:|:---|:---|:---:|:---|
| n/a — code modules | A | — | — | — | greenfield |
| n/a — entrypoints | B | — | — | — | greenfield |
| QA «full plan при неясном AC» без qa_consumes | C | plan §QA consumes first | s05, s08 | yes | delete in-epic process wording |
| Residual full-plan-first prose in QA rules | C | qa_consumes-first gate | s08 | yes | *-legacy-fallback-purge |

---

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-clarify-product-probe.yaml](s01-clarify-product-probe.yaml) | pending | no | no | BACK IMPLEMENT | completed |
| **s02** | [s02-plan-template-spine.yaml](s02-plan-template-spine.yaml) | pending | no | no | BACK IMPLEMENT | completed |
| **s03** | [s03-plan-template-qa-readiness.yaml](s03-plan-template-qa-readiness.yaml) | pending | no | no | BACK IMPLEMENT | completed |
| **s04** | [s04-workflow-plan-batch.yaml](s04-workflow-plan-batch.yaml) | pending | no | no | BACK IMPLEMENT | completed |
| **s05** | [s05-workflow-qa-consumes.yaml](s05-workflow-qa-consumes.yaml) | pending | no | no | BACK IMPLEMENT | completed |
| **s06** | [s06-refs-role-command.yaml](s06-refs-role-command.yaml) | pending | no | no | BACK IMPLEMENT | completed |
| **s07** | [s07-epic-verification-suite.yaml](s07-epic-verification-suite.yaml) | pending | no | yes | BACK IMPLEMENT | completed |
| **s08** | [s08-legacy-fallback-purge.yaml](s08-legacy-fallback-purge.yaml) | pending | no | no | BACK IMPLEMENT | completed |
**needs_creative:** нет (CREATIVE need: нет в plan).

**CREATIVE verify:** advisory — `verify-decompose-creative` (no CR gaps expected).

**Next mode:** → `BACK IMPLEMENT s01` (новый чат).
