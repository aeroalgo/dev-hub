# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-088-lifecycle-transition-fallback-purge
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**
**Дата:** 2026-09-11
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — [.cursor/templates/decompose/epic-step.yaml](../../../../../.cursor/templates/decompose/epic-step.yaml).

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-088-lifecycle-transition-fallback-purge/md/decompose-index.md`. Machine = `plan/T-HUB-088-lifecycle-transition-fallback-purge/yaml/decompose-index.yaml`. Shards = `yaml/steps/`.
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `decompose-index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|---|---|
| `writing-plans` | структура шагов, атомарность |
| `python-testing-patterns` | characterization and denial regression tests |
| `architecture-patterns` | canonical transition seams and fail-closed contracts |

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN | Notes |
| :--- | :--- | :--- | :--- |
| US-001 | Как loop, я хочу один phase transition owner, чтобы arm и auto-advance не расходились. | s01, s02, s05, s06 | Single transition owner in `loop.epic_transition` |
| US-002 | Как gate, я хочу typed handoff/evidence без Markdown salvage и manual PASS fallback. | s01, s03, s04, s06 | Fail-closed frontmatter and receipt enforcement |
| US-003 | Как QA/BUGFIX, я хочу сохранять текущий valid QA→BUGFIX→DONE outcome без artifact-only обхода. | s01, s04, s05, s06 | Persisted phase + receipt in BUGFIX transaction |
| FR-001 | Все production callers старых arm-функций переходят на `loop.epic_transition.arm_phase`/canonical `arm_epic` API. | s01, s02, s06 | Characterization in s01, rewiring in s02, verify in s06 |
| FR-002 | `arm_active_context_from_decompose`, `arm_pre_implement_context` и `_legacy_warn` удаляются после zero-caller proof. | s02, s05, s06 | Caller migration in s02, test rewrite in s05, deletion in s06 |
| FR-003 | `epic_resolve.py --decompose` и `context_loop.arm_session()` не вызывают legacy implementation body. | s01, s02, s06 | Caller wiring in s02, diagnostic in s01, purge in s06 |
| FR-004 | Handoff runtime принимает только typed `loop-handoff/v1`; malformed/transitional raw dict не продолжает lifecycle. | s01, s03, s06 | Characterization in s01, fail-closed enforcement in s03 |
| FR-005 | Manual BUGFIX authority и artifact-only mb-finish compatibility удаляются; verifier receipt становится обязательным. | s01, s04, s06 | Characterization in s01, enforcement in s04, purge in s06 |
| FR-006 | Legacy REFLECT остаётся исторически игнорируемым event, но не участвует в live lifecycle decisions. | s01, s05, s06 | Test assertions in s01, instruction/code audit in s05/s06 |
| FR-007 | Старые transition/handoff/BUGFIX tests удаляются или переписываются на canonical behavior and deny coverage. | s01, s05, s06 | Characterization in s01, rewrite in s05, purge in s06 |
| SC-001 | 0 production callers legacy arm symbols | s02, s06 | Import/call-site zero hits verified in s02/s06 |
| SC-002 | invalid/manual evidence cannot finish BUGFIX | s01, s04, s06 | Rejection tests and fail-closed gates in s01/s04 |
| SC-003 | valid phase transition behavior unchanged | s01, s02, s05, s06 | Parity suite green across transition lifecycle |
| SC-004 | no raw Markdown handoff fallback in runtime | s01, s03, s06 | Frontmatter schema validation in s03/s06 |
| AC+ #1 | `arm_phase`/`arm_epic` — единственный live transition owner. | s01, s02, s06 | Canonical owner absorbs logic and manages all transitions |
| AC+ #2 | Старый `--decompose` input либо нормализуется в canonical epic id, либо завершается diagnostic; он не вызывает старую arm implementation. | s01, s02, s06 | Resolved to canonical epic ID or diagnostic error |
| AC+ #3 | `LoopHandoffFrontmatter` validation failure блокирует lifecycle, а не возвращает raw dict. | s01, s03, s06 | Fail-closed handoff parsing |
| AC+ #4 | Manual BUGFIX evidence and artifact-only finish не проходят boundary. | s01, s04, s06 | Strict verifier receipt and active phase guard |
| AC+ #5 | Valid QA→BUGFIX→verify→finish flow остаётся зелёным. | s01, s04, s05, s06 | Preserved canonical BUGFIX flow |
| AC+ #6 | Legacy REFLECT records do not change phase and do not reopen compatibility path. | s01, s05, s06 | Historical event ignored without live side-effects |
| AC− #1 | Нет production import/call для `arm_active_context_from_decompose`/`arm_pre_implement_context`. | s02, s06 | Verified by import audit and purge |
| AC− #2 | Нет `authority == manual` как успешного verifier evidence. | s04, s06 | Verified by receipt integrity check |
| AC− #3 | Нет raw dict fallback из typed handoff parser. | s03, s06 | Verified by schema validator unit tests |
| AC− #4 | Нет artifact-only finish path for active BUGFIX. | s04, s06 | Verified by mb-finish transaction tests |
| AC− #5 | Нет тестов, которые закрепляют старый arm/handoff/BUGFIX contract. | s05, s06 | Verified by test refactor and sunset inventory |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Characterize all arm/finish phase behavior and direct callers | plan §До DECOMPOSE | s01 |
| Rewire transition and CLI callers to one owner | plan §До DECOMPOSE | s02 |
| Enforce typed handoff and receipt-only BUGFIX finish | plan §До DECOMPOSE | s03, s04 |
| Remove manual/artifact-only compatibility branches | plan §До DECOMPOSE | s04 |
| Delete obsolete lifecycle tests and update instructions | plan §До DECOMPOSE | s05 |
| Execute final legacy-fallback purge and full regression | plan §До DECOMPOSE | s06 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Единственный transition/evidence lifecycle owner в `loop.epic_transition` | s01, s02, s06 |
| Строгая валидация `loop-handoff/v1` frontmatter без raw dict fallback | s01, s03, s06 |
| Защита finish транзакции: обязательный verifier receipt и отказ от manual BUGFIX authority | s01, s04, s06 |
| Рефакторинг устаревших тестов и инструкций на канонические контракты | s01, s05, s06 |
| Полное удаление старых arm функций, предупреждений и fallback-веток (sunset A+B+C+I) | s02, s03, s04, s05, s06 |
| Out of scope (operational session resilience, historical archive rewriting, new lifecycle features) | — / cut_list |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `harness/hooks/epic/core.py:arm_active_context_from_decompose` | A | `loop.epic_transition.arm_phase`/`arm_epic` | s02, s06 | yes | delete in-epic |
| `harness/hooks/epic/core.py:arm_pre_implement_context` | A | canonical transition owner (`arm_phase`) | s02, s06 | yes | delete in-epic |
| `loop/epic_transition.py:_legacy_warn` | A | no public legacy callers | s02, s06 | yes | delete in-epic |
| `harness/hooks/_lib.py:match_gate_evidence` manual evidence branch | A | typed verifier receipt validator | s04, s06 | yes | delete in-epic |
| `harness/hooks/epic/core.py:_verify_pass_ready_for_step` manual BUGFIX branch | A | typed receipt validator | s04, s06 | yes | delete in-epic |
| `loop/mb_finish/impl.py` artifact-only BUGFIX finish | A | finish transaction guard + active phase | s04, s06 | yes | delete in-epic |
| `loop/schemas/active_context.py:_handoff_mode_from_legacy_markdown` | A | typed handoff parser | s03, s06 | no | delete in-epic |
| unresolved `epic_resolve.py --decompose` fallback execution | B | canonical `--epic-id` resolution or explicit diagnostic failure | s02, s06 | no | delete in-epic |
| legacy mb-finish phase omission | B | typed finish transaction | s04, s06 | yes | delete in-epic |
| typed handoff failure → raw dict fallback (`parse_handoff_meta`) | C | validation error / halt | s03, s06 | yes | delete in-epic |
| manual evidence → accepted non-authoritative PASS | C | explicit reject | s04, s06 | yes | delete in-epic |
| missing phase → artifact-only finish | C | phase + receipt requirement | s04, s06 | yes | delete in-epic |
| instructions calling old arm functions (`arm_active_context_from_decompose`, `arm_pre_implement_context`) | I | `arm_phase`/`arm_epic` | s05, s06 | no | delete in-epic |
| instructions accepting manual BUGFIX evidence | I | typed verifier receipt | s05, s06 | no | delete in-epic |
| REFLECT as live next phase | I | QA→DONE / QA→BUGFIX rules | s05, s06 | no | delete in-epic |

## Очередь шагов (BACK / FRONT)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-contracts-and-characterization.yaml](s01-contracts-and-characterization.yaml) | [s01…](../../implement/T-HUB-088-lifecycle-transition-fallback-purge/s01-contracts-and-characterization.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-canonicalize-transition-owner-and-callers.yaml](s02-canonicalize-transition-owner-and-callers.yaml) | [s02…](../../implement/T-HUB-088-lifecycle-transition-fallback-purge/s02-canonicalize-transition-owner-and-callers.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s03** | [s03-typed-handoff-and-fail-closed-parsing.yaml](s03-typed-handoff-and-fail-closed-parsing.yaml) | [s03…](../../implement/T-HUB-088-lifecycle-transition-fallback-purge/s03-typed-handoff-and-fail-closed-parsing.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s04** | [s04-enforce-verifier-receipt-and-bugfix-transaction.yaml](s04-enforce-verifier-receipt-and-bugfix-transaction.yaml) | [s04…](../../implement/T-HUB-088-lifecycle-transition-fallback-purge/s04-enforce-verifier-receipt-and-bugfix-transaction.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s05** | [s05-obsolete-test-and-instruction-rewrite.yaml](s05-obsolete-test-and-instruction-rewrite.yaml) | [s05…](../../implement/T-HUB-088-lifecycle-transition-fallback-purge/s05-obsolete-test-and-instruction-rewrite.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s06** | [s06-legacy-fallback-purge.yaml](s06-legacy-fallback-purge.yaml) | [s06…](../../implement/T-HUB-088-lifecycle-transition-fallback-purge/s06-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | pending |
