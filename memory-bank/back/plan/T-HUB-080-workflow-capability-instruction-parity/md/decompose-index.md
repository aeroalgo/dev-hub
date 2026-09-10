# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-080-workflow-capability-instruction-parity
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**
**Дата:** 2026-09-07
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача. Shard: `sNN-<slug>.yaml` в `yaml/steps/`.

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-080-workflow-capability-instruction-parity/md/decompose-index.md`. Machine = `plan/T-HUB-080-workflow-capability-instruction-parity/yaml/decompose-index.yaml`. Shards = `yaml/steps/`.
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `decompose-index.yaml` only.** `decompose-index.md` status — best-effort зеркало.

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность, schema-валидация |
| `python-testing-patterns` | TDD synthetic fixtures и corpus inventory discovery tests |

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN\|eNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | The active instruction corpus MUST include every non-archive `workflow-*.mdc`, relevant `_lean/*.mdc`, role core, shared test contract, role-command skill copy, instruction entrypoint source, and executable shard template that can prescribe tests. | s01, s05 | Full corpus glob discovery and final purge verification |
| FR-002 | Every direct `pytest`, `cargo`, `npm`, `vitest`, or raw `tests:` execution recipe in an action context MUST be explicitly scoped to hub/self-test or be replaced with `capability_checks` plus typed evidence language. | s01, s02, s03, s04, s05 | Zero unqualified runner action lines across all active surfaces |
| FR-003 | BACK IMPLEMENT, TASK, BUGFIX, and QA mode workflows and gates MUST distinguish hub targeted/full checks from managed targeted/full capability checks without relying on a generic Python default. | s02, s05 | BACK workflow, mainrule-core, and _lean gates rewrite |
| FR-004 | INTEG IMPLEMENT and QA, integration core/lean gates, and the HTTP scenario wording MUST distinguish hub pytest HTTP tests from managed capability checks; frontend browser execution remains parent-only and outside the capability executor. | s03, s05 | INTEG mode and _lean gates branch qualification |
| FR-005 | FRONT core runner wording MUST carry the same hub-only condition and managed capability reference while retaining the parent-only Vitest/RTL/Playwright authority. | s03, s05 | FRONT mainrule-core rewrite preserving parent-only test authority |
| FR-006 | `harness/skills/role-command/SKILL.md` MUST be brought to semantic parity with `harness/claude/skills/role-command/SKILL.md`; the `.agents/skills` symlink must expose the corrected text. | s04, s05 | Codex role-command skill update and parity check |
| FR-007 | `harness/instructions/main.md` MUST describe both runtime entrypoint selection and the hub-versus-managed test policy; generated `AGENTS.md`/`CLAUDE.md` destinations MUST be checked for the same policy markers. | s04, s05 | Main entrypoint source update and generated entrypoint checks |
| FR-008 | Templates that create or validate plan/decompose/implement/QA/security/refactor/integration artifacts MUST not contain an unqualified executable managed runner example; examples MUST identify hub-only or capability evidence. | s04, s05 | Plan, decompose, implement, QA, security, refactor, and finish templates rewrite |
| FR-009 | The instruction inventory test MUST detect omitted active files by glob/discovery, report exact stale lines, accept negative statements and archives only under documented exclusions, and preserve hub exception tests. | s01, s05 | Active glob scanner and semantic classifier in pytest |
| FR-010 | The epic MUST not alter stack-profile capability vocabulary, resolver/executor/evidence code, receipt provenance, `test.e2e`, arbitrary shell execution, package installation, or frontend parent-only authority. | s01, s05 | Non-goals boundary preserved and verified by regression tests |
| SC-001 | 0 unqualified managed runner action lines in the active workflow corpus. | s01, s05 | Executable inventory scan over repository corpus |
| SC-002 | 100% of BACK/INTEG mode files that mention tests contain both explicit hub exception and managed capability guidance, or an explicit read-only/negative reason. | s02, s03, s05 | Corpus inventory report grouped by mode |
| SC-003 | Both role-command skill variants carry equivalent hub/managed markers and no stale generic runner sentence. | s04, s05 | Parity test over harness/skills and harness/claude/skills |
| SC-004 | All executable templates that show a test command identify hub-only scope; managed examples use declaration/evidence language. | s04, s05 | Template inventory test |
| SC-005 | Hub test fixtures remain accepted and managed tests-only proof remains rejected. | s01, s05 | Existing 076 evidence fixtures + new inventory regression |
| SC-006 | Generated runtime entrypoint destinations contain the branch policy after sync check/apply, with no manual divergent body accepted as proof. | s04, s05 | Runtime-sync fixture and entrypoint semantic check |
| SC-007 | FRONT parent-only rule remains present and no `test.e2e` capability is introduced. | s01, s03, s05 | Explicit assertions in inventory test and capability enum test |
| SC-008 | Full hub suite is green after instruction rewrites. | s05 | bin/pytest full suite verification on dev-hub itself |
| US-001 | Как автор BACK/INTEG workflow, я хочу сразу видеть hub-only и managed branches, чтобы не прописать Python runner для внешнего проекта. | s02, s03, s05 | Action sentences carry explicit branch qualification |
| US-002 | Как QA owner, я хочу, чтобы full/targeted checks в каждом mode workflow приводили к capability evidence для managed roots и сохраняли hub full/targeted exception. | s02, s03, s05 | QA mode workflows specify capability evidence and hub exceptions |
| US-003 | Как Codex/Claude operator, я хочу одинаковые правила из `.agents` и `.claude`, чтобы runtime не выбирал разные execution policies. | s01, s04, s05 | Parity between Codex and Claude skill/instruction trees |
| US-004 | Как автор нового shard/template, я хочу, чтобы пример `tests:` не обучал managed fallback, даже если он копируется из template. | s04, s05 | Scaffold templates provide scoped examples |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN\|eNN |
| :--- | :--- | :--- |
| Stage 1 — corpus contract and red inventory test | plan §Stage 1 | s01 |
| Stage 2 — BACK workflow and gate branch rewrite | plan §Stage 2 | s02 |
| Stage 3 — INTEG, FRONT, shared and Claude branch rewrite | plan §Stage 3 | s03 |
| Stage 4 — role skill, entrypoint and template parity | plan §Stage 4 | s04 |
| Stage 5 — enforce purge and independent regression | plan §Stage 5 | s05 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Eliminate residual direct runner prescriptions in active workflows after 076 | s01, s02, s03, s04, s05 |
| Preserve dev-hub self-test execution (bin/pytest) with shared timeout contract | s01, s02, s03, s05 |
| Enforce managed project test execution solely through named capability checks and typed evidence | s01, s02, s03, s04, s05 |
| Maintain strict parent-only authority for frontend Playwright/Vitest execution without test.e2e | s01, s03, s05 |
| Semantic parity between Codex (.agents) and Claude (.claude) instruction and skill views | s01, s04, s05 |
| Robust glob-based active surface discovery replacing 7-file allowlist | s01, s05 |
| Full regression suite and 076 evidence contract validation | s05 |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN\|eNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :---: | :---: | :--- |
| `loop/tests/test_stack_profile_instruction_inventory.py::test_instruction_inventory_has_no_generic_managed_test_runner` — seven-file presence check | A | Corpus discovery + action-context semantic inventory with exact stale-line diagnostics | s01, s05 | no | delete in-epic |
| `loop/tests/test_stack_profile_instruction_inventory.py::test_instruction_inventory_retains_explicit_hub_exception` — fixed four-file allowlist | A | Discovered hub exception assertions over all relevant mode/core/template surfaces | s01, s05 | no | delete in-epic |
| `loop/tests/test_stack_profile_instruction_inventory.py::test_sunset_a_b_c_i_scans_have_no_live_legacy_authority` — partial symbol checks only | A | Full Kind I scan plus existing 076 hub/managed validator tests | s01, s05 | no | delete in-epic |
| Obsolete assertions that treat “managed” presence as sufficient while allowing an unqualified action line | A | Assertions on branch semantics and no generic managed authority | s01, s05 | no | delete in-epic |
| n/a — this epic does not replace a compose service, Dockerfile CMD, deploy process, or product CLI | B | n/a | — | no | greenfield B |
| Mixed workflow sentence that silently defaults managed verification to `bin/pytest` / `.venv/bin/pytest` | C | Explicit managed `capability_checks` + typed evidence branch; missing branch is inventory failure | s01, s02, s03, s05 | yes | delete in-epic |
| `pytest HTTP outcome` or raw `tests:` prose presented without hub scope | C | Hub-only scenario label or managed evidence contract; no command fallback | s01, s03, s05 | yes | delete in-epic |
| “Python tests” in runtime entrypoint text without root classification | C | “dev-hub self-tests” versus “managed project capability checks” | s01, s04, s05 | yes | delete in-epic |
| Generated-header bypass treated as proof that a runtime destination matches source semantics | C | Required-marker semantic check over source and destination; preserve overlay behavior but fail stale policy | s01, s04, s05 | yes | delete in-epic |
| `harness/cursor/rules/back_developer/workflow-implement.mdc:39` direct `green (bin/pytest)` | I | `hub-only` branch plus managed capability/evidence branch | s02, s05 | no | delete in-epic |
| `harness/cursor/rules/back_developer/workflow-task.mdc:17` direct `.venv/bin/pytest` | I | Branch-qualified targeted hub test versus `test.targeted` capability | s02, s05 | no | delete in-epic |
| `harness/cursor/rules/back_developer/workflow-bugfix.mdc:13` direct regression `.venv/bin/pytest` | I | Branch-qualified reproduction/regression policy | s02, s05 | no | delete in-epic |
| `harness/cursor/rules/back_developer/workflow-qa.mdc:20` unconditional full `bin/pytest` | I | Hub full suite row and managed full capability row | s02, s05 | no | delete in-epic |
| `harness/cursor/rules/back_developer/mainrule-core.mdc:12,20–26` any generic runner sentence | I | Keep hub exception, attach managed branch to every action context | s02, s05 | no | delete in-epic |
| `harness/cursor/rules/back_developer/isolation_rules/_lean/implement.mdc:24` | I | `hub: targeted bin/pytest` or `managed: capability_checks` | s02, s05 | no | delete in-epic |
| `harness/cursor/rules/back_developer/isolation_rules/_lean/task.mdc:14` | I | Same branch contract for ad-hoc tasks | s02, s05 | no | delete in-epic |
| `harness/cursor/rules/back_developer/isolation_rules/_lean/bugfix.mdc:16` | I | Same branch contract for regression tests | s02, s05 | no | delete in-epic |
| `harness/cursor/rules/back_developer/isolation_rules/_lean/qa.mdc:35,41` generic pytest coverage wording | I | Hub-only coverage runner or managed capability coverage evidence | s02, s05 | no | delete in-epic |
| `harness/cursor/rules/integration_developer/workflow-implement.mdc:29,33` direct targeted pytest / HTTP outcome | I | Hub API scenario versus managed capability declaration; Playwright remains parent-only | s03, s05 | no | delete in-epic |
| `harness/cursor/rules/integration_developer/workflow-qa.mdc:12` unconditional full hub pytest | I | Hub full suite and managed full capability alternatives | s03, s05 | no | delete in-epic |
| `harness/cursor/rules/integration_developer/mainrule-core.mdc:15,21–24,36` mixed pytest scenario text | I | Branch-qualified hub API test and managed capability wording | s03, s05 | no | delete in-epic |
| `harness/cursor/rules/integration_developer/isolation_rules/_lean/implement.mdc:23–24` | I | Keep explicit hub/managed alternatives and remove bare HTTP pytest action | s03, s05 | no | delete in-epic |
| `harness/cursor/rules/integration_developer/isolation_rules/_lean/bugfix.mdc:13` | I | Hub HTTP scenario versus managed evidence | s03, s05 | no | delete in-epic |
| `harness/cursor/rules/integration_developer/isolation_rules/_lean/qa.mdc:15` | I | Hub full suite versus managed full capability checks | s03, s05 | no | delete in-epic |
| `harness/cursor/rules/front_developer/mainrule-core.mdc:9` generic pytest runner | I | Explicit hub-only note plus managed capability reference; preserve parent-only frontend tests | s03, s05 | no | delete in-epic |
| `harness/cursor/rules/shared/test-timeout.mdc` examples only where scope is ambiguous | I | Keep canonical examples but label hub-only and managed branches unambiguously | s03, s05 | no | delete in-epic |
| `harness/claude/rules/context-economy-cc.md:55` generic `.venv/bin/pytest` anti-bloat recipe | I | Hub-only command or managed capability evidence wording | s03, s05 | no | delete in-epic |
| `harness/skills/role-command/SKILL.md:10` stale generic pytest text | I | Runtime-neutral hub/managed branch matching Claude role skill | s04, s05 | no | delete in-epic |
| `harness/claude/skills/role-command/SKILL.md:10` parity drift if wording differs after rewrite | I | Same semantic policy with Claude-specific tool mechanics retained | s04, s05 | no | delete in-epic |
| `harness/instructions/main.md:41` unqualified “Python tests” sentence | I | Explicit dev-hub self-test versus managed capability statement | s04, s05 | no | delete in-epic |
| `harness/cursor/templates/{plan.md,decompose/epic-step.yaml,decompose/legacy-purge-step.yaml,implement/epic-step.yaml,qa/epic-step.yaml,integration-plan.md,refactor/epic-step.yaml,security/epic-step.yaml,finish-doc-router.md}` direct examples lacking scope | I | Scoped hub examples and capability/evidence managed examples | s04, s05 | no | delete in-epic |
| `loop/WORKFLOW.md` and `loop/README.md` direct test commands without “dev-hub self-test” label | I | Preserve operator commands with explicit hub scope | s04, s05 | no | delete in-epic |

## Очередь шагов (BACK / FRONT)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-corpus-inventory-contract.yaml](s01-corpus-inventory-contract.yaml) | [s01…](../../implement/implement-T-HUB-080-workflow-capability-instruction-parity/s01-corpus-inventory-contract.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-back-workflow-branch-rewrite.yaml](s02-back-workflow-branch-rewrite.yaml) | [s02…](../../implement/implement-T-HUB-080-workflow-capability-instruction-parity/s02-back-workflow-branch-rewrite.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-integ-front-shared-branch-rewrite.yaml](s03-integ-front-shared-branch-rewrite.yaml) | [s03…](../../implement/implement-T-HUB-080-workflow-capability-instruction-parity/s03-integ-front-shared-branch-rewrite.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s04** | [s04-runtime-skill-entrypoint-template-parity.yaml](s04-runtime-skill-entrypoint-template-parity.yaml) | [s04…](../../implement/implement-T-HUB-080-workflow-capability-instruction-parity/s04-runtime-skill-entrypoint-template-parity.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s05** | [s05-legacy-fallback-purge.yaml](s05-legacy-fallback-purge.yaml) | [s05…](../../implement/implement-T-HUB-080-workflow-capability-instruction-parity/s05-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | pending |
