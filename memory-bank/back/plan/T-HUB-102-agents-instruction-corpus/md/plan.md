# [T-HUB-102-agents-instruction-corpus] PLAN

**Дата:** 2026-09-14  
**Режим:** BACK PLAN (REPLAN spawn)  
**Уровень:** L2  
**Статус:** active  
**iteration:** 2  
**Replan-of:** `T-HUB-080-workflow-capability-instruction-parity`  
**Parent-prompt:** [memory-bank/back/plan/T-HUB-080-workflow-capability-instruction-parity/md/prompt.md](../../T-HUB-080-workflow-capability-instruction-parity/md/prompt.md) — immutable prior Epic SoT  
**Parent-replan:** [memory-bank/back/plan/T-HUB-080-workflow-capability-instruction-parity/md/replan-i2.yaml](../../T-HUB-080-workflow-capability-instruction-parity/md/replan-i2.yaml)  
**Parent I1 QA:** [memory-bank/back/qa/T-HUB-080-workflow-capability-instruction-parity/qa-20260910-workflow-capability-instruction-parity-pass.yaml](../../../qa/T-HUB-080-workflow-capability-instruction-parity/qa-20260910-workflow-capability-instruction-parity-pass.yaml)  
**Prompt (this epic):** [md/prompt.md](prompt.md)  
**Deps:** hard `T-HUB-080` (parent I1 in done; outcome continuity via Parent-prompt)  
**Batch:** replan-spawn-075-080-20260914  

→ После DECOMPOSE единственный трекер — `yaml/decompose-index.yaml`.

## Provenance

- Spawned by REPLAN of `T-HUB-080-workflow-capability-instruction-parity` on 2026-09-14.
- Prior Epic outcome SoT: `memory-bank/back/plan/T-HUB-080-workflow-capability-instruction-parity/md/prompt.md` (do not rewrite parent prompt).
- Parent remains in roadmap `done:`; this epic is the sole I2 delivery vehicle.
- I1 plan/decompose/QA under parent are historical; not overwritten.

## Outcome summary

I1 закрыл branch-qualified hub vs managed policy для `harness/cursor/rules/**`, skills, entrypoints, templates и расширил semantic inventory test. Prompt **Done when #2** требует, чтобы active instruction corpus fail validation при unqualified managed runner literal. Corpus discovery в `get_active_corpus_files()` не включает `harness/agents/*.md` — active gate/verify agent prompts остаются вне enforcement и по-прежнему предписывают unqualified `bin/pytest` / `.venv/bin/pytest` без hub-only vs managed `capability_checks` branch.

I2 закрывает только agents corpus gap: расширить discovery, переписать affected agent instructions, harden tests против регрессии. Executor, evidence schema, incident clearing, fingerprint cache — вне scope.

## Gap classification

| ID | Класс | Описание | Поверхность |
|---|---|---|---|
| G080-I2-01 | `outcome_gap` | `get_active_corpus_files()` в `loop/tests/test_stack_profile_instruction_inventory.py` (~88–135) не сканирует `harness/agents/**`. Verify/gate agents предписывают unqualified hub pytest recipes как универсальный test path. | `loop/tests/test_stack_profile_instruction_inventory.py`, `harness/agents/*.md` |
| G080-I2-02 | `legacy_removal` | Agent instruction surfaces (`verify-implement.md`, `verify-bugfix.md`, `verify-qa.md`, `gate-repair.md` и другие с test-command recipes) не содержат hub self-test vs managed `capability_checks` branch, как rules/skills уже enforce. | `harness/agents/verify-implement.md`, `verify-bugfix.md`, `verify-qa.md`, `gate-repair.md`, прочие agents при наличии runner literals |
| G080-I2-03 | `hardening` | Inventory tests MUST fail, если agents снова получат unqualified managed pytest/cargo/npm recipes; discovery MUST включать `harness/agents/**` с symlink awareness для `.agents` без дублирования trees. | `loop/tests/test_stack_profile_instruction_inventory.py` |

**Не входит в I2:** runtime executor, evidence write-deny (077), incident clearing (079), context fingerprint cache (078), managed capability registry behavior (076), cosmetic wording в уже scanned rules.

## backlog_candidates

- Cosmetic wording normalization в rules/skills, уже проходящих I1 inventory.
- Executor/evidence schema changes (076/077) — отдельные эпики.

## Technology axiom

| Выбор | Machine boundary | FORBIDDEN после I2 |
|---|---|---|
| Agent verify/gate instructions | Явная hub-only branch (dev-hub self-test: `bin/pytest` + timeout) ИЛИ managed `capability_checks` + typed evidence | Unqualified `bin/pytest` / `.venv/bin/pytest` / `pytest` как default для любого root |
| Corpus discovery | `get_active_corpus_files()` включает `harness/agents/**/*.md` (+ symlink-resolved `.agents/agents/**` если projection exists, без double-count) | Inventory, inspectящий только cursor/claude/skills allowlist |
| Semantic classifier | Reuse `classify_instruction_line` для agents corpus | Отдельный weaker allowlist для agents |
| Managed verification | Named `capability_checks` из stack profile (076 SoT) | Raw runner literal, cargo, npm как managed default в agent prompts |
| Hub exception | Explicit hub/dev-hub marker перед `bin/pytest` | Global ban на слово pytest в negative/read-only contexts |

## User Stories и Independent Test

| # | Story | Priority | Independent Test |
|---|---|---|---|
| US-001 | Как verify-implement subagent, я должен видеть hub-only vs managed branch, чтобы не запускать `bin/pytest` в managed project root. | P0 | Corpus scan включает `harness/agents/verify-implement.md`; stale unqualified line fails; rewritten branch passes. |
| US-002 | Как verify-qa/verify-bugfix/gate-repair agent, я должен следовать той же policy, что rules/skills, при описании test commands. | P0 | All four named agents pass semantic inventory; no unqualified action runner literal. |
| US-003 | Как maintainer inventory test, я хочу, чтобы новый agent file с `bin/pytest` без hub marker автоматически ломал CI. | P0 | Temp fixture under `harness/agents/` with stale line → inventory FAIL; removal → PASS. |

### Acceptance Scenarios — US-001

- **Given:** `harness/agents/verify-implement.md` содержит `bin/pytest …` или `timeout 300s .venv/bin/pytest …` без hub-only context.
- **When:** `get_active_corpus_files()` + semantic scan runs.
- **Then:** FAIL с path, line, reason; agent file included in discovered corpus.

- **Given:** rewritten agent text with «Hub (dev-hub self-test): `bin/pytest …`» and «Managed: declare `capability_checks` + typed evidence; FORBIDDEN raw runner».
- **When:** inventory runs.
- **Then:** PASS; hub exception preserved for dev-hub verify context.

### Acceptance Scenarios — US-002

- **Given:** `verify-bugfix.md` instructs `bin/pytest…` from VERIFY section unconditionally.
- **When:** classifier evaluates action context.
- **Then:** FAIL until branch-qualified rewrite.

- **Given:** `verify-qa.md` references full suite `bin/pytest -q --tb=line` for hub QA review gate.
- **When:** inventory runs with hub-only marker on full-suite row.
- **Then:** PASS; subagent «не гоняй pytest» rule preserved alongside hub-only parent suite reference.

- **Given:** `gate-repair.md` mentions `bin/pytest -q --tb=line` as parent action before verify-qa.
- **When:** inventory runs.
- **Then:** PASS only if labeled hub-only / parent-only dev-hub self-test; FAIL if readable as managed default.

### Acceptance Scenarios — US-003

- **Given:** developer adds `harness/agents/new-verify.md` with unqualified `cargo test`.
- **When:** inventory discovery runs.
- **Then:** new file auto-included; test FAIL without allowlist update.

## Functional Requirements (FR)

- **FR-001:** `get_active_corpus_files()` MUST discover all non-archive `harness/agents/**/*.md` (and symlink-resolved agent paths under `.agents/` if present, deduplicated by resolved path).
- **FR-002:** Semantic inventory (`scan_active_corpus`, violation reporting) MUST apply to discovered agents files with same `classify_instruction_line` contract as rules/skills.
- **FR-003:** `harness/agents/verify-implement.md` MUST rewrite test-command sections: hub-only `bin/pytest` branch for dev-hub verify + managed `capability_checks`/evidence branch; retain scope-check and ALLOW-path constraints.
- **FR-004:** `harness/agents/verify-bugfix.md` MUST rewrite VERIFY/bash sections with branch-qualified runner policy; preserve subagent HARD RULE (no frontend tests).
- **FR-005:** `harness/agents/verify-qa.md` MUST distinguish hub full-suite reference (parent-run, hub-only) from managed capability full checks; «не гоняй pytest» subagent rule unchanged.
- **FR-006:** `harness/agents/gate-repair.md` MUST label any pytest mention as hub-only dev-hub self-test or parent-only action; no universal managed recipe.
- **FR-007:** All other `harness/agents/*.md` with positive runner literals (`pytest`, `cargo`, `npm`, raw shell test commands) MUST be scanned and rewritten or proven read-only/negative context only.
- **FR-008:** Inventory tests MUST include regression fixture/agent corpus test proving agents directory omission cannot recur (fail if `harness/agents` excluded from discovery).
- **FR-009:** I2 MUST NOT alter stack-profile executor, evidence schema, capability registry, receipt provenance (077), or runtime execution paths (076).

## NFR

- **NFR-001:** Agents rewrite preserves subagent role boundaries (verify = read-only where specified; no frontend test execution by subagent).
- **NFR-002:** Discovery addition must not double-count symlinked copies (`harness/agents` vs `.agents/agents` projection).
- **NFR-003:** Classifier continues to accept negative/forbidden phrases («FORBIDDEN: pytest without timeout») without false positive on read-only agents (`verify-decompose`, `analyze-verify`).
- **NFR-004:** Full hub suite regression after changes: `bin/pytest -q --tb=line` remains valid hub QA command in plan/QA matrix only.

## Target layout

| Surface / owner | Paths | I2 responsibility |
|---|---|---|
| Corpus discovery | `loop/tests/test_stack_profile_instruction_inventory.py` | Add `harness/agents/**/*.md` glob; symlink dedup. |
| Verify implement | `harness/agents/verify-implement.md` | Branch-qualified hub/managed test policy in bash/VERIFY sections. |
| Verify bugfix | `harness/agents/verify-bugfix.md` | Same branch contract for VERIFY commands. |
| Verify QA | `harness/agents/verify-qa.md` | Hub full-suite parent reference vs managed capability wording. |
| Gate repair | `harness/agents/gate-repair.md` | Hub-only/parent-only pytest mentions. |
| Verify decompose | `harness/agents/verify-decompose.md` | Read-only gate agent instruction surface. |
| Analyze verify | `harness/agents/analyze-verify.md` | Read-only gate agent instruction surface. |
| Explorer agent | `harness/agents/explorer.md` | Read-only codebase explorer agent prompt. |
| Sunset inventory | `harness/agents/sunset-inventory.md` | Read-only sunset extraction agent prompt. |
| Reconcile verify | `harness/agents/reconcile-verify.md` | Read-only reconciliation agent prompt. |
| Other verify agents | `harness/agents/verify-edit.md` | Read-only phase verify agent prompt. |

**Wire-complete ladder I2:** extend discovery → rewrite agent instructions → wire scan → enforce (regression tests) → purge unqualified agent runner authority.

## Sunset A / B / C / I (Kind I)

### A. Code / tests

| Устаревает (path / symbol) | Замена | Policy |
|---|---|---|
| `get_active_corpus_files` без `harness/agents/**` | Discovery glob for agents + deduped symlink resolution | delete in-epic |
| Inventory green при stale agents corpus | Agents included in `scan_active_corpus` violations | delete in-epic |
| Agent-specific implicit allowlist (if any test skips agents) | Single corpus classifier for rules + agents | delete in-epic |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
|---|---|---|
| n/a — agents are instruction sources, not deploy entrypoints | n/a | n/a |

### C. Fallbacks / soft-fail

| Устаревает | Замена (fail-closed) | Policy |
|---|---|---|
| Treating agents as out-of-scope for instruction inventory | Agents in active corpus; stale line = FAIL | delete in-epic |
| Unqualified `bin/pytest` in verify agents as implicit managed default | Hub-only + managed capability branches | delete in-epic |
| «Run VERIFY pytest» without root classification | Explicit hub self-test vs capability_checks | delete in-epic |

### I. Instruction surfaces (Kind I)

| Устаревает (path / phrase) | Замена | Policy |
|---|---|---|
| `harness/agents/verify-implement.md` unqualified `bin/pytest …` / `.venv/bin/pytest …` bash recipes | Hub-only branch + managed capability_checks branch | delete in-epic |
| `harness/agents/verify-bugfix.md` `bin/pytest…` from VERIFY without scope | Branch-qualified VERIFY commands | delete in-epic |
| `harness/agents/verify-qa.md` full-suite `bin/pytest -q --tb=line` without hub-only label | «Hub dev-hub parent full suite» + managed full capability alternative | delete in-epic |
| `harness/agents/gate-repair.md` `bin/pytest -q --tb=line` as universal check | Hub-only/parent-only dev-hub self-test label | delete in-epic |
| Any other agent positive runner literal without hub/negative context | Branch-qualified or read-only classification | delete in-epic |

## AC

1. `get_active_corpus_files()` returns all active `harness/agents/**/*.md`; omission regression test fails if agents excluded.
2. Semantic inventory FAIL on pre-rewrite agents (`verify-implement`, `verify-bugfix`, `verify-qa`, `gate-repair`); PASS after branch-qualified rewrite.
3. Every direct runner literal in agents action context carries hub-only marker or is replaced with managed `capability_checks`/evidence language.
4. Read-only agents (`verify-decompose`, `analyze-verify`) remain valid without false positives.
5. Hub exception for dev-hub verify/QA (`bin/pytest` with timeout) preserved under explicit hub context.
6. No change to 076 executor, 077 receipt, FRONT parent-only authority, or `test.e2e` vocabulary.
7. Full hub suite green after I2 changes.

### AC−

1. Нет inventory, inspectящего только cursor/claude/skills без agents.
2. Нет unqualified managed pytest/cargo/npm recipe в agents action context.
3. Нет ручного allowlist файлов agents вместо discovery glob.
4. Нет dual authority: rules say capability_checks, agents say bare pytest.
5. Нет изменения executor/evidence/incident/fingerprint runtime behavior.
6. Нет удаления valid negative/forbidden pytest phrases in agents.
7. Нет duplicate corpus entries from symlinked `.agents` tree.

## QA consumes (#qa-consumes)

| ID | Priority | Scenario | Command / fixture | Expected | Maps |
|---|---|---|---|---|---|
| TM-080-I2-01 | P0 | Agents corpus discovery | `bin/pytest loop/tests/test_stack_profile_instruction_inventory.py -q --tb=line -k 'agents or corpus'` | `harness/agents/**` in discovered set; omission test FAIL if excluded | FR-001,008; AC-1 |
| TM-080-I2-02 | P0 | verify-implement branch parity | same test `-k implement or verify_implement` | Stale unqualified lines FAIL pre-rewrite; PASS post-rewrite | FR-003; AC-2,3 |
| TM-080-I2-03 | P0 | verify-bugfix / verify-qa / gate-repair | same test `-k 'bugfix or verify_qa or gate_repair'` | All named agents branch-qualified; exact path diagnostics | FR-004,005,006; AC-2,3 |
| TM-080-I2-04 | P0 | Agents regression guard | fixture test adding stale agent line | Inventory FAIL on regression; PASS after fix | FR-008; G080-I2-03 |
| TM-080-I2-05 | P1 | Read-only agents unaffected | `-k 'decompose or analyze_verify'` | No false positive on FORBIDDEN/read-only agents | NFR-003; AC-4 |
| TM-080-I2-06 | P1 | Full hub regression | `bin/pytest -q --tb=line` | Entire suite green; I1 rules parity intact | AC-7; FR-009 |

## Review readiness

| Gate | Required | Status | Evidence |
|---|---|---|---|
| Prompt Epic alignment | I2 gaps ⊆ Done when #2 + Forbidden after | done | Agents omission breaks corpus validation requirement |
| Gap-only scope | No executor/evidence expansion | done | FR-009; out-of-scope epics listed |
| Technology axiom | Same classifier as I1 rules | done | Reuse classify_instruction_line |
| qa_consumes | ≥3 TM | done | TM-080-I2-01…06 |
| Delivery closure | P0 boundaries | done | See below |

## Delivery closure

| Capability / outcome | Classification | Production entrypoint | Enforcement | Independent test | Follow-up |
|---|---|---|---|---|---|
| Agents in active instruction corpus | `outcome_gap` | `get_active_corpus_files()` + scan | Discovery regression test | TM-080-I2-01 | n/a |
| Branch-qualified verify/gate agent prompts | `legacy_removal` | `harness/agents/verify-*.md`, `gate-repair.md` | Semantic inventory FAIL on stale lines | TM-080-I2-02,03 | n/a |
| Anti-regression for agents runner drift | `hardening` | Inventory fixture tests | Fail on reintroduced unqualified recipes | TM-080-I2-04 | n/a |

## Appetite

| Поле | Значение |
|---|---|
| `timebox_days` | `1` |
| `cut_list` | `['cosmetic rules wording already green', '076 executor changes', '077 evidence schema', '079 incident clearing', '078 fingerprint cache', 'runtime dashboard']` |

## Следующий режим

→ **BACK DECOMPOSE T-HUB-102-agents-instruction-corpus** (iteration 2)
