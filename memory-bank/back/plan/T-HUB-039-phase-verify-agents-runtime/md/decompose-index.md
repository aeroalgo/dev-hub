# Реестр шагов — T-HUB-039-phase-verify-agents-runtime

**Plan ID:** T-HUB-039-phase-verify-agents-runtime  
**План:** [plan/T-HUB-039-phase-verify-agents-runtime/md/plan.md](../plan/T-HUB-039-phase-verify-agents-runtime/md/plan.md)  
**Machine index:** [index.yaml](index.yaml) — **канон status**  
**Дата:** 2026-08-31  
**Режим:** BACK DECOMPOSE

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки.  
> **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура agent files, docs |
| `python-testing-patterns` | test_phase_verify_gates suite |
| `diagnosing-bugs` | dead assign, dual-path diagnosis |

---

## Requirements coverage (plan → steps)

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | verify-implement.md create; alias verify.md stub | s01 | normalize_type('verify')→'verify-implement' |
| FR-002 | verify-bugfix.md create | s02 | BUGFIX ARTIFACT section required |
| FR-003 | verify-decompose.md create; FORBIDDEN pytest | s03 | GAPS→FAIL stop-gate |
| FR-004 | verify-qa.md create (ex reviewer); BLOCKED verdict | s02 | alias reviewer.md |
| FR-005 | agent-pretool uses get_verify_agent enforce | s04 | dead assign delete |
| FR-006 | spawn_validate CONTRACTS verify-bugfix path | s04 | missing_contract_sections |
| FR-010 | stop-gate FINISH blocks per phase_registry | s05 | DECOMPOSE dual gate; QA BLOCKED allow |
| FR-011 | DSH presets per-phase verify agents | s06 | 4 new + 2 stubs |
| FR-012 | test_phase_verify_gates matrix TM-001…TM-010 | s08 | ≥10 test functions |
| FR-015 | Docs README/WORKFLOW §Phase verify agents + architecture/services.md | s07, s09 | alias migration note |
| US-001 | @verify → normalize → verify-implement | s01 | alias compat |
| US-002 | verify-bugfix ALLOW bugfix artifact | s02, s04 | spawn DENY без path |
| US-003 | verify-decompose после schema CLI | s03, s05 | semantic coverage gate |
| US-004 | verify-qa BLOCKED verdict → FINISH allowed | s02, s05 | subagent-stop align |
| SC-002 | Legacy @verify / @reviewer alias works | s01, s02 | alias stubs ≥1 release |
| SC-003 | verify-decompose does NOT run pytest | s03 | FORBIDDEN in agent file |
| SC-005 | QA BLOCKED not protocol FAIL | s05 | subagent-stop.py |
| TM-001 | Agent file missing → DENY spawn | s01, s02, s03, s04 | pretool + _discover_registry |
| TM-006 | DECOMPOSE semantic FAIL → stop-gate blocks | s05 | CLI + verify-decompose |
| TM-007 | QA BLOCKED → allow FINISH + BUGFIX handoff | s05 | stop-gate path |
| TM-009 | DSH preset missing → fail-closed | s06 | preset files |
| TM-010 | Dead assign expected_verify_agent → purge | s04 | delete in-epic |
| NFR failure-coverage | matrix ≥10 rows | s08 | test_phase_verify_gates |
| NFR test-coverage | ≥5 test scenarios | s08 | TM-001…TM-010 |
| Behavior-first | каждый FR noun ∈ produces | s01–s08 | no surrogate unit alone |
| Out of scope | verify-audit, verify-plan | — | optional future epic |

---

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Agent files creation (verify-implement) | plan §FR-001 | s01 |
| Agent files creation (verify-bugfix, verify-qa) | plan §FR-002/FR-004 | s02 |
| Agent files creation (verify-decompose) | plan §FR-003 | s03 |
| Hook enforce (agent-pretool / spawn_validate / CONTRACTS) | plan §FR-005/FR-006 | s04 |
| Gate enforce (stop-gate / user-prompt / subagent-stop) | plan §FR-010 | s05 |
| DSH presets (4 new + 2 stubs) | plan §FR-011 | s06 |
| Docs / workflow rules adoption | plan §FR-015 partial | s07 |
| Test suite (TM matrix) | plan §FR-012 | s08 |
| Docs README/WORKFLOW/architecture | plan §FR-015 | s09 |
| Legacy purge (alias stubs + dead assigns) | plan §Replacement cleanup | s10 |

---

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Phase-specific verify subagents **реально работают** на FINISH (agent files on disk) | s01, s02, s03 |
| spawn normalize+contract: @verify→verify-implement, @reviewer→verify-qa | s01, s02, s04 |
| stop-gate/pretool enforce по get_verify_agent(phase) | s04, s05 |
| DSH presets per-phase (не только verify.prompt.md monolithic) | s06 |
| spawn-hard + workflow docs обновлены | s07 |
| TM-001…TM-010 failure matrix covered | s08 |
| loop/README, WORKFLOW, architecture актуальны | s09 |
| Alias stubs / dead assigns очищены (brownfield rollup) | s10 |
| QA BLOCKED → FINISH allowed (не protocol FAIL) | s05 |
| DECOMPOSE semantic coverage gate (verify-decompose после CLI) | s03, s05 |
| Out of scope (verify-audit, verify-plan, hard analyze-verify default) | — / future epic |

---

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `.claude/agents/verify.md` (monolithic) | A | `.claude/agents/verify-implement.md` | s10 | yes (alias stub) | s01 rewrite stub; s10 delete |
| `.claude/agents/reviewer.md` (monolithic) | A | `.claude/agents/verify-qa.md` | s10 | yes (alias stub) | s02 rewrite stub; s10 delete |
| `dsh/presets/verify.prompt.md` (monolithic) | B | `dsh/presets/verify-implement.prompt.md` | s10 | yes (alias stub) | s06 rewrite stub; s10 delete |
| `dsh/presets/reviewer.prompt.md` (monolithic) | B | `dsh/presets/verify-qa.prompt.md` | s10 | yes (alias stub) | s06 rewrite stub; s10 delete |
| `agent-pretool.py: expected_verify_agent` dead assign | A | enforce branch (uses result) | s04 | no | delete in-epic s04 |

---

## Очередь шагов (BACK)

| step_id | title & files | needs_creative | tdd | status |
| :--- | :--- | :---: | :---: | :--- |
| **s01** | [s01-verify-implement-agent-file.yaml](s01-verify-implement-agent-file.yaml) — verify-implement.md + verify.md stub + _lib.py ALIAS | no | yes | completed |
| **s02** | [s02-verify-bugfix-qa-agent-files.yaml](s02-verify-bugfix-qa-agent-files.yaml) — verify-bugfix.md + verify-qa.md + reviewer.md stub | no | yes | completed |
| **s03** | [s03-verify-decompose-analyze-verify.yaml](s03-verify-decompose-analyze-verify.yaml) — verify-decompose.md + analyze-verify.md align | no | yes | completed |
| **s04** | [s04-agent-pretool-spawn-validate-enforce.yaml](s04-agent-pretool-spawn-validate-enforce.yaml) — agent-pretool.py + spawn_validate.py + _lib.py CONTRACTS | no | yes | completed |
| **s05** | [s05-stop-gate-user-prompt-per-phase.yaml](s05-stop-gate-user-prompt-per-phase.yaml) — stop-gate.py + user-prompt.py + subagent-stop.py | no | yes | completed |
| **s06** | [s06-dsh-presets-epic-gate-mapping.yaml](s06-dsh-presets-epic-gate-mapping.yaml) — 4× verify-*.prompt.md + 2 stubs | no | yes | completed |
| **s07** | [s07-spawn-hard-finish-block-workflow-docs.yaml](s07-spawn-hard-finish-block-workflow-docs.yaml) — spawn-hard.md + workflow-*.mdc + _lean/*.mdc | no | no | completed |
| **s08** | [s08-test-phase-verify-gates-suite.yaml](s08-test-phase-verify-gates-suite.yaml) — loop/tests/test_phase_verify_gates.py | no | yes | completed |
| **s09** | [s09-docs-readme-workflow-architecture.yaml](s09-docs-readme-workflow-architecture.yaml) — loop/README.md + architecture/services.md | no | no | completed |
| **s10** | [s10-legacy-fallback-purge.yaml](s10-legacy-fallback-purge.yaml) — delete alias stubs + dead assigns purge | no | yes | completed |