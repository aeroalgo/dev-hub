# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-102-agents-instruction-corpus
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**
**Дата:** 2026-09-16
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (BACK/FRONT: один prod-модуль или один test-file; INTEG: один UI-элемент). Shard: `sNN-<slug>.yaml` — [.cursor/templates/decompose/epic-step.yaml](../../../.cursor/templates/decompose/epic-step.yaml).

> **Path (layout v2 HARD):** этот файл = `plan/<plan_id>/md/decompose-index.md`. Machine = `plan/<plan_id>/yaml/decompose-index.yaml`. Shards = `yaml/steps/`. **FORBIDDEN** `decompose-<id>/` · `yaml/index.md` · `yaml/index.yaml` · дубль имён.
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `decompose-index.yaml` only.** `decompose-index.md` status — best-effort зеркало (`mark-index-status` / `finalize-step` / auto `repair-index-mirror` на prepare).
> **`decompose-index.yaml` contract:** `schema: epic-decompose-index/v1`, корневой список `steps:`, у шага минимум `id`, `file` (basename в `yaml/steps/`), `title`, `next_phase`, `status`. `queue:` / `step_id:` в корне индекса недопустимы.

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность |
| `tdd` | TDD-цикл для тестов обнаружения корпуса и anti-regression фикстур |

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-I2-001 | `get_active_corpus_files()` MUST discover all non-archive `harness/agents/**/*.md` (and symlink-resolved agent paths under `.agents/` if present, deduplicated by resolved path). | s01 | closed in s01 |
| FR-I2-002 | Semantic inventory (`scan_active_corpus`, violation reporting) MUST apply to discovered agents files with same `classify_instruction_line` contract as rules/skills. | s01, s05 | closed in s01, enforced s05 |
| FR-I2-003 | `harness/agents/verify-implement.md` MUST rewrite test-command sections: hub-only `bin/pytest` branch for dev-hub verify + managed `capability_checks`/evidence branch; retain scope-check and ALLOW-path constraints. | s02 | closed in s02 |
| FR-I2-004 | `harness/agents/verify-bugfix.md` MUST rewrite VERIFY/bash sections with branch-qualified runner policy; preserve subagent HARD RULE (no frontend tests). | s03 | closed in s03 |
| FR-I2-005 | `harness/agents/verify-qa.md` MUST distinguish hub full-suite reference (parent-run, hub-only) from managed capability full checks; «не гоняй pytest» subagent rule unchanged. | s04 | closed in s04 |
| FR-I2-006 | `harness/agents/gate-repair.md` MUST label any pytest mention as hub-only dev-hub self-test or parent-only action; no universal managed recipe. | s03 | closed in s03 |
| FR-I2-007 | All other `harness/agents/*.md` with positive runner literals (`pytest`, `cargo`, `npm`, raw shell test commands) MUST be scanned and rewritten or proven read-only/negative context only. | s04 | closed in s04 |
| FR-I2-008 | Inventory tests MUST include regression fixture/agent corpus test proving agents directory omission cannot recur (fail if `harness/agents` excluded from discovery). | s01, s05 | closed in s01, hardened in s05 |
| FR-I2-009 | I2 MUST NOT alter stack-profile executor, evidence schema, capability registry, receipt provenance (077), or runtime execution paths (076). | s05 | closed in s05 |
| AC+ #1 | `get_active_corpus_files()` returns all active `harness/agents/**/*.md`; omission regression test fails if agents excluded. | s01, s05 | |
| AC+ #2 | Semantic inventory FAIL on pre-rewrite agents (`verify-implement`, `verify-bugfix`, `verify-qa`, `gate-repair`); PASS after branch-qualified rewrite. | s01, s02, s03, s04, s05 | |
| AC+ #3 | Every direct runner literal in agents action context carries hub-only marker or is replaced with managed `capability_checks`/evidence language. | s01, s02, s03, s04, s05 | |
| AC+ #4 | Read-only agents (`verify-decompose`, `analyze-verify`) remain valid without false positives. | s04, s05 | |
| AC+ #5 | Hub exception for dev-hub verify/QA (`bin/pytest` with timeout) preserved under explicit hub context. | s02, s03, s04, s05 | |
| AC+ #6 | No change to 076 executor, 077 receipt, FRONT parent-only authority, or `test.e2e` vocabulary. | s05 | |
| AC+ #7 | Full hub suite green after I2 changes. | s05 | |
| AC− #1 | Нет inventory, inspectящего только cursor/claude/skills без agents. | s01, s05 | |
| AC− #2 | Нет unqualified managed pytest/cargo/npm recipe в agents action context. | s02, s03, s04, s05 | |
| AC− #3 | Нет ручного allowlist файлов agents вместо discovery glob. | s01, s05 | |
| AC− #4 | Нет dual authority: rules say capability_checks, agents say bare pytest. | s02, s03, s04, s05 | |
| AC− #5 | Нет изменения executor/evidence/incident/fingerprint runtime behavior. | s05 | |
| AC− #6 | Нет удаления valid negative/forbidden pytest phrases in agents. | s04, s05 | |
| AC− #7 | Нет duplicate corpus entries from symlinked `.agents` tree. | s01, s05 | |
| NFR-I2-001 | Agents rewrite preserves subagent role boundaries (verify = read-only where specified; no frontend test execution by subagent). | s02, s03, s04 | |
| NFR-I2-002 | Discovery addition must not double-count symlinked copies (`harness/agents` vs `.agents/agents` projection). | s01, s05 | |
| NFR-I2-003 | Classifier continues to accept negative/forbidden phrases («FORBIDDEN: pytest without timeout») without false positive on read-only agents (`verify-decompose`, `analyze-verify`). | s04, s05 | |
| NFR-I2-004 | Full hub suite regression after changes: `bin/pytest -q --tb=line` remains valid hub QA command in plan/QA matrix only. | s05 | |
| Out of scope #1 | Runtime executor, evidence write-deny (077), incident clearing (079), context fingerprint cache (078), managed capability registry behavior (076), cosmetic wording в уже scanned rules. | — | follow_up: out-of-scope |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Extend discovery | plan §Target layout / Wire-complete ladder | s01 |
| Rewrite agent instructions | plan §Target layout / Wire-complete ladder | s02, s03, s04 |
| Wire scan & classify | plan §Target layout / Wire-complete ladder | s01, s05 |
| Enforce (regression tests) | plan §Target layout / Wire-complete ladder | s05 |
| Purge unqualified runner authority | plan §Target layout / Wire-complete ladder | s05 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Детерминированное включение harness/agents/**/*.md в активный корпус инструкций без дублей | s01 |
| Branch-qualified hub self-test vs managed capability_checks для verify-implement и verify-bugfix | s02, s03 |
| Branch-qualified hub self-test vs managed capability_checks для gate-repair и verify-qa | s03, s04 |
| Валидация и нормализация остальных read-only/gate agents prompt файлов | s04 |
| Anti-regression тесты: провал CI при добавлении unqualified runner literal в agents | s05 |
| Полный sunset inventory scan, Kind I verification и green suite | s05 |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `get_active_corpus_files` без `harness/agents/**` | A | Discovery glob for agents + deduped symlink resolution | s01 | no | |
| Inventory green при stale agents corpus | A | Agents included in `scan_active_corpus` violations | s01, s05 | no | |
| Agent-specific implicit allowlist (if any test skips agents) | A | Single corpus classifier for rules + agents | s01, s05 | no | |
| n/a — agents are instruction sources, not deploy entrypoints | B | n/a | — | no | n/a |
| Treating agents as out-of-scope for instruction inventory | C | Agents in active corpus; stale line = FAIL | s01, s05 | yes | |
| Unqualified `bin/pytest` in verify agents as implicit managed default | C | Hub-only + managed capability branches | s02, s03, s04, s05 | yes | |
| «Run VERIFY pytest» without root classification | C | Explicit hub self-test vs capability_checks | s02, s03, s04, s05 | yes | |
| `harness/agents/verify-implement.md` unqualified `bin/pytest …` / `.venv/bin/pytest …` bash recipes | I | Hub-only branch + managed capability_checks branch | s02, s05 | no | |
| `harness/agents/verify-bugfix.md` `bin/pytest…` from VERIFY without scope | I | Branch-qualified VERIFY commands | s03, s05 | no | |
| `harness/agents/verify-qa.md` full-suite `bin/pytest -q --tb=line` without hub-only label | I | «Hub dev-hub parent full suite» + managed full capability alternative | s04, s05 | no | |
| `harness/agents/gate-repair.md` `bin/pytest -q --tb=line` as universal check | I | Hub-only/parent-only dev-hub self-test label | s03, s05 | no | |
| Any other agent positive runner literal without hub/negative context | I | Branch-qualified or read-only classification | s04, s05 | no | |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-agents-corpus-discovery-inventory.yaml](yaml/steps/s01-agents-corpus-discovery-inventory.yaml) | [s01…](../../implement/implement-T-HUB-102-agents-instruction-corpus/s01-agents-corpus-discovery-inventory.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-verify-implement-branch-rewrite.yaml](yaml/steps/s02-verify-implement-branch-rewrite.yaml) | [s02…](../../implement/implement-T-HUB-102-agents-instruction-corpus/s02-verify-implement-branch-rewrite.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-verify-bugfix-gate-repair-branch-rewrite.yaml](yaml/steps/s03-verify-bugfix-gate-repair-branch-rewrite.yaml) | [s03…](../../implement/implement-T-HUB-102-agents-instruction-corpus/s03-verify-bugfix-gate-repair-branch-rewrite.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-verify-qa-and-agents-parity-scan.yaml](yaml/steps/s04-verify-qa-and-agents-parity-scan.yaml) | [s04…](../../implement/implement-T-HUB-102-agents-instruction-corpus/s04-verify-qa-and-agents-parity-scan.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-legacy-fallback-purge.yaml](yaml/steps/s05-legacy-fallback-purge.yaml) | [s05…](../../implement/implement-T-HUB-102-agents-instruction-corpus/s05-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |