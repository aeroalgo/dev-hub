# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-071-session-identity-lock  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**  
**Дата:** 2026-09-06  
**Режим:** BACK DECOMPOSE  
**Уровень:** L3  
**Granularity:** 6 sNN (band 5–8; L3/L4 ≤9; advisory floor плана = 6; TDD red в s01; add identity+step chain в s02; wire SessionStart halt в s03; Kind I + purge unknown default в s04; matrix enforce в s05; apply≠purge → s06)

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — `.cursor/templates/decompose/epic-step.yaml`.

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-071-session-identity-lock/md/decompose-index.md`. Machine = `yaml/decompose-index.yaml`. Shards = `yaml/steps/`. **FORBIDDEN** `decompose-<id>/` · `yaml/index.md` · `yaml/index.yaml`.  
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `decompose-index.yaml` only.**  
> **Ladder:** s01 add (red tests 94cea2d3 + unknown-when-armed) → s02 add (`resolve_session_identity` + PromptScope step chain) → s03 wire+enforce (`session_start_payload` halt; one COMMAND) → s04 Kind I + purge `"unknown"` default / heading-as-COMMAND → s05 enforce (phase matrix FR-013 + TM-005/006) → s06 leftover inventory scan (apply≠purge).  
> **Justification 6 sNN:** plan §До DECOMPOSE enumerates 6 outcomes; s02 identity function ≠ s03 SessionStart wire; s04 Kind I rewrite ≠ s06 leftover inventory; s05 matrix is independent outcome (FR-008/FR-013), not a micro-ladder of s02.

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность (сессия DECOMPOSE, не `impl:`) |
| `tdd` / `python-testing-patterns` / `modern-python` / `python-anti-patterns` | Core(4) в каждом code sNN |
| `python-error-handling` | fail-closed drift halt `CONTEXT_IDENTITY_DRIFT` |
| `python-type-safety` | Pydantic Identity / Drift + LoopHandoffFrontmatter (s02) |

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR → ≥1 шаг, иначе явный `out_of_scope` + `follow_up: T-…` **уже в** `roadmap/queue.yaml`.  
> **FR verbatim (HARD):** колонка **Plan FR text** = дословный текст / nouns из `plan.md`. Remap FR = FAIL ANALYZE (`layout_dilution`).  
> Notes `deferred`/`partial` без `follow_up: T-…` = FAIL (`validate-decompose-tree`).

| Req ID | Plan FR text (verbatim) | sNN\|eNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | Single function `resolve_session_identity(state, ac_meta) -> Identity \| Drift`. Drift codes: `phase_mismatch`, `epic_mismatch`, `step_unknown_while_armed`. | s02, s03, s05 | nouns: resolve_session_identity, Drift, phase_mismatch |
| FR-002 | `build_prompt_scope` uses Identity; `step` fallback chain: `projection.step` → `state.armed_step` → `state.phase` → **empty + diagnostic**, never the string `unknown` if any of the three is set. If **nothing** armed, step may be `unarmed` (explicit) not `unknown` (ambiguous). Prefer: unarmed IDE → step=`-` documented. | s02, s04, s05 | TM-005 unarmed IDE |
| FR-003 | Literal `unknown` purged from prompt_builder as default when armed exists. Tests grep `unknown` in PromptScope for armed fixtures = 0. | s01, s02, s04, s06 | sunset A |
| FR-004 | SessionStart: if Drift → additionalContext warning **and** `ok=false` in load result if composed; do not start «work» inject of load_now bodies (072 will path-only; this epic at least doesn't lie COMMAND). | s03 | follow_up path-only: T-HUB-072-context-bundle-fail-closed |
| FR-005 | `expected_identity` from loop env (`EPIC_PHASE` / runner) if present must match state; else halt. | s03 | env vs state |
| FR-006 | Kind I: comments «step unknown OK for QA» — delete. | s04, s06 | sunset I |
| FR-007 | Do not parse `## Handoff` heading for phase when frontmatter valid (`loop-handoff/v1`). If frontmatter missing — diagnostic, migrational regex with drift counter (existing active_context parsers) **not** as COMMAND source if state armed. | s03, s04, s06 | sunset A heading-as-COMMAND |
| FR-008 | Tests: matrix phases PLAN/DECOMPOSE/ANALYZE/IMPLEMENT/AUDIT/QA/BUGFIX each has non-unknown step when armed. | s05 | + CREATIVE/CLARIFY/DONE from FR-013 |
| FR-009 | `render_prompt_scope` HARD READ still says read entrypoint then chain — **do not** expand to inline workflow (072). | s02, s04 | keep HARD READ lines |
| FR-010 | Identity fields required in halt diagnostic JSON (typed), not prose-only. | s02, s03 | halt card labeled lines = JSON fields |
| FR-011 | Concurrent dual SessionStart (065) — identity function must be pure/idempotent. | s02, s03 | mock single payload if 065 not landed; follow_up: T-HUB-065-duplicate-hooks-runtime-entrypoint |
| FR-012 | BUGFIX `bugfix_finish_required` already in finish_handoff — keep; identity lock is **start** side. | s03 | do not rewrite finish_handoff |
| FR-013 | Phase token table (locked for PromptScope.step when not IMPLEMENT sNN): PLAN→PLAN, DECOMPOSE→DECOMPOSE, ANALYZE→ANALYZE, CREATIVE→CREATIVE, CLARIFY→CLARIFY, IMPLEMENT+sNN→sNN COMMAND `{ROLE} IMPLEMENT`, AUDIT→AUDIT, QA→QA, BUGFIX→BUGFIX, DONE→DONE (should not spawn work session) halt or no COMMAND work | s02, s05 | table locked |
| FR-014 | Reproduction fixture `94cea2d3`: env/loop intended COMMAND = `BACK BUGFIX`; `state.phase` / `armed_step` = `BUGFIX`; stale AC frontmatter `mode: QA` **or** overlay leftover projection QA; **Then:** Drift halt, **not** SessionStart `COMMAND: BACK QA` plus user `BACK BUGFIX`. | s01, s03, s06 | Independent Test |
| FR-015 | ROLE comes from state/frontmatter `role` (BACK/FRONT/INTEG), not guessed from prompt regex when armed. | s02, s03 | |
| FR-016 | `session_id` if present in state/last-session must be echoed in halt diagnostic; mismatch session_id is **not** this epic (068/journal) unless cheap. | s03 | echo only; follow_up: T-HUB-068-start-finish-transaction-boundary |
| FR-017 | Wire-complete: **Add** `resolve_session_identity` → **Wire** `session_start_payload` + `build_prompt_scope` → **Enforce** pytest 94cea2d3 + matrix → **Purge** default `"unknown"` and heading-as-COMMAND. | s01–s06 | ladder |
| FR-018 | Out vs T-HUB-065: 065 deletes duplicate realpath SessionStart + injects `EPIC_RUNTIME` entrypoint. This epic **must not** reopen duplicate-hook WHAT. If 065 not landed, identity tests mock a **single** payload function. | s03 | follow_up: T-HUB-065-duplicate-hooks-runtime-entrypoint |
| FR-019 | `PromptScope.command` field (or rendered line) is the only COMMAND in additionalContext. Grep fixture output: count of lines matching `COMMAND:` or `^BACK (QA\|BUGFIX\|IMPLEMENT)` ≤ 1. | s01, s03, s06 | AC−1 |
| FR-020 | If projection.phase and state.armed_step disagree (both set, different) → Drift `phase_mismatch` even if AC frontmatter matches one of them. State vs projection: **armed_step wins for COMMAND** only if they match; if they disagree → halt (do not pick a winner silently). | s02, s03 | |
| US-001 | Как BUGFIX loop session, я вижу COMMAND BACK BUGFIX, не QA. | s01, s03 | Independent Test unit payload |
| US-002 | Как агент, я не получаю step=unknown на QA. | s01, s02, s05 | PromptScope.step == `QA` |
| US-003 | Как runner, mismatch state vs AC mode halt. | s01, s03 | CONTEXT_IDENTITY_DRIFT |
| US-004 | Как IMPLEMENT, step=sNN from armed. | s02, s05 | armed s05 → step s05 (plan Independent / TM-004) |
| US-005 | Как Codex/Claude, runtime entrypoint orthogonal (065). | s03 | skip if 065 not landed; no regress EPIC_RUNTIME |
| SC-001 | armed BUGFIX COMMAND not QA | s01, s03 | pytest |
| SC-002 | no step unknown when armed | s01, s02, s05 | pytest matrix |
| SC-003 | mismatch halt | s01, s03 | pytest diagnostic |
| SC-004 | IMPLEMENT step sNN | s02, s05 | pytest |
| SC-005 | no heading regex as COMMAND if frontmatter ok | s03, s04 | unit |
| AC+1 | One COMMAND per SessionStart, equals armed phase. | s01, s03, s06 | |
| AC+2 | step never `unknown` when armed. | s01, s02, s04, s05 | |
| AC+3 | Drift halt, not warning-continue. | s03, s06 | sunset C |
| AC+4 | Tests for 94cea2d3 reproduction. | s01, s03 | |
| AC−1 | Нет двух COMMAND строк. | s01, s03, s06 | |
| AC−2 | Нет silent continue on mismatch. | s03, s06 | |
| AC−3 | Нет `unknown` default masking missing projection. | s02, s04, s06 | |
| AC−4 | Нет regex heading SoT when frontmatter valid. | s03, s04, s06 | |
| AC−5 | Нет dual-path «prefer AC heading if richer». | s03, s06 | |
| NFR-1 | Halt faster than agent tool-use (SessionStart) | s03 | SessionStart hook, not after first tool |
| NFR-2 | Diagnostic machine-readable | s02, s03 | halt card fields |
| NFR-3 | Idempotent under dual hooks | s02, s03 | FR-011 |
| TM-001 | BUGFIX armed COMMAND — pytest — BACK BUGFIX only | s01, s03 | US-001 |
| TM-002 | QA step not unknown — pytest — step QA | s01, s02, s05 | US-002 |
| TM-003 | mismatch halt — pytest — CONTEXT_IDENTITY_DRIFT | s01, s03 | US-003 |
| TM-004 | IMPLEMENT sNN — pytest — s05 | s02, s05 | US-004; plan table says s05 |
| TM-005 | unarmed IDE — pytest — no crash | s05 | FR-002 step=`-` |
| TM-006 | epic mismatch — pytest — halt | s05 | FR-001 epic_mismatch |
| TM-007 | no heading COMMAND — unit — state wins | s03, s04 | FR-007 |
| TM-008 | matrix all phases — pytest — no unknown | s05 | FR-008 |
| Failure TM-001 | BUGFIX vs QA inject dual COMMAND | s01, s03, s06 | halt/lock |
| Failure TM-002 | step unknown agent lost shard | s01, s02, s04, s06 | never unknown |
| Failure TM-003 | AC stale mode drift | s01, s03, s06 | halt |
| Failure TM-004 | missing frontmatter regex temptation | s03, s04, s06 | state wins if armed |
| Failure TM-005 | unarmed IDE no state | s05 | documented token not crash |
| Failure TM-006 | epic_id mismatch wrong plan | s05 | halt |
| Failure TM-007 | 065 dual hook double payload | s02, s03 | idempotent; follow_up T-HUB-065 |
| Failure TM-008 | IMPLEMENT missing sNN armed implement no step | s02, s05 | diagnostic not unknown |
| Independent Test PASS | armed BUGFIX injects BUGFIX; QA step≠unknown; mismatch diagnostic. | s01, s03, s05 | |
| Independent Test FAIL | «projection usually matches» without halt fixture. | s01, s03, s06 | dilution = FAIL ANALYZE |
| Out of scope | overlay REFLECT/verify OFF | — | follow_up: T-HUB-070-phase-policy-overlay-sole-sot (hard dep, not this epic) |
| Out of scope | md inline / abort 401 / finish_qa | — | follow_up: T-HUB-072-context-bundle-fail-closed · T-HUB-073-abort-classifier-dirty-halt · T-HUB-074-qa-bugfix-lifecycle-rearm |
| Out of scope | dual SessionStart process / EPIC_RUNTIME WHAT | — | follow_up: T-HUB-065-duplicate-hooks-runtime-entrypoint |
| Out of scope | JSON session contract | — | follow_up: T-HUB-057-loop-session-json-contract |
| Out of scope | session_id mismatch journal | — | follow_up: T-HUB-068-start-finish-transaction-boundary |
| Out of scope | SessionContextService package / Variant B projector | — | Appetite cut_list |
| Product WHAT-1 | `build_prompt_scope` / `session_start_payload`: COMMAND = `{ROLE} {PHASE}` где PHASE = armed_step/projection.phase (normalized). | s02, s03 | |
| Product WHAT-2 | Если loop/env expected phase передана и ≠ state → **не** inject conflicting COMMAND; halt payload `ok=false` diagnostic `CONTEXT_IDENTITY_DRIFT`. | s03 | |
| Product WHAT-3 | AC frontmatter `mode` vs state.phase mismatch → same halt (fail-closed). | s03 | |
| Product WHAT-4 | `PromptScope.step`: if IMPLEMENT → sNN from state/index; if QA/BUGFIX/AUDIT/DECOMPOSE/ANALYZE → phase token (e.g. `QA`, `BUGFIX`), **never** `unknown` when armed. | s02, s05 | |
| Product WHAT-5 | Tests reproduce `94cea2d3`: state BUGFIX + stale projection QA → drift, not dual COMMAND. | s01, s03 | |
| Technology axiom Identity | Pydantic `EpicState` + `LoopHandoffFrontmatter` | s02 | FORBIDDEN regex `## Handoff BACK QA` as COMMAND |
| Technology axiom COMMAND | `f"{role} {armed_phase}"` from state | s02, s03 | FORBIDDEN SessionStart COMMAND ≠ loop COMMAND |
| Technology axiom step | `armed_step` / shard id (sNN) or phase name | s02, s04 | FORBIDDEN literal `unknown` when armed |
| Technology axiom mismatch | halt / `CONTEXT_IDENTITY_DRIFT` | s03 | FORBIDDEN warning + continue work |
| Technology axiom PromptScope | built from identity, runtime from EPIC_RUNTIME (065) | s02, s03 | FORBIDDEN default phase from AC heading |

## Stages coverage (plan/canon → steps)

> Каждый этап/фаза плана и канон-дока → sNN. Не растворять в layout.

| Этап / фаза | Источник | sNN\|eNN |
| :--- | :--- | :--- |
| s01 — red tests 94cea2d3 + unknown step matrix | plan §До DECOMPOSE #1 · FR-014 · US-001/002/003 · AC+4 · Independent Test | s01 |
| s02 — resolve_session_identity + PromptScope step chain | plan §До DECOMPOSE #2 · FR-001/002/013/017 Add · Technology axiom | s02 |
| s03 — session_start_payload halt on drift | plan §До DECOMPOSE #3 · FR-004/005/019/020 · Wire+Enforce SessionStart | s03 |
| s04 — Kind I + purge unknown default | plan §До DECOMPOSE #4 · FR-003/006/007 · sunset A/I | s04 |
| s05 — phase matrix tests | plan §До DECOMPOSE #5 · FR-008/013 · TM-005/006/008 | s05 |
| s06 — purge leftover | plan §До DECOMPOSE #6 · Replacement A+B+C+I · FR-017 Purge | s06 |
| Data flow load_epic_state → parse AC → resolve → PromptScope → render | plan §Eng review spine Data flow | s02, s03 |
| Halt diagnostic shape CONTEXT_IDENTITY_DRIFT | plan §Halt diagnostic shape | s02, s03 |
| Wire-complete add→wire→enforce→purge | plan FR-017 · behavior-first §3 | s01–s06 |
| Independent Test PASS/FAIL | plan §Independent Test | s01, s03, s06 |

## Outcome map (plan → steps)

> **HARD:** не ужимать Goal/NFR плана до infra-slug.

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Одна сессия = одна identity; SessionStart COMMAND совпадает с armed_step | s01, s02, s03 |
| step никогда не литерал `unknown` если armed | s01, s02, s04, s05 |
| Mismatch → halt CONTEXT_IDENTITY_DRIFT, не dual COMMAND / не warning-continue | s01, s03, s06 |
| Reproduction 94cea2d3 (BUGFIX loop + QA SessionStart) → Drift | s01, s03 |
| IMPLEMENT step = sNN; QA/BUGFIX/AUDIT = phase token | s02, s05 |
| Machine-readable halt diagnostic (typed fields, not prose-only) | s02, s03 |
| Halt at SessionStart (faster than agent tool-use) | s03 |
| Idempotent identity under dual SessionStart | s02, s03 |
| Kind I «step unknown OK for QA» gone | s04, s06 |
| Heading regex not COMMAND SoT when loop-handoff/v1 valid | s03, s04, s06 |
| Fail-closed: no silent winner when projection vs armed disagree | s02, s03 |
| Independent Test FAIL path («projection usually matches» without halt) | s01, s03, s06 |
| Out of scope (не в этой нарезке) | — / follow-up 065/057/068/070/072/073/074 + Appetite cut |

## Replacement cleanup (plan → steps)

> **HARD (brownfield replace):** каждая поверхность plan sunset **A/B/C/I** → ≥1 `sNN` с непустым `deletes:` (или out_of_scope + follow-up epic **уже в** `roadmap/queue.yaml`).  
> Completeness ladder: **add → wire → enforce → purge**. Add-only на sole-path FR = FAIL (`optional_sot`).  
> Greenfield → n/a. Здесь brownfield: default `"unknown"` + heading-as-COMMAND + warning-continue.

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN\|eNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `loop/prompt_builder.py` `PromptScope.step` default `"unknown"` when armed (`or "unknown"` L154) | A | `projection.step` → `armed_step` → `phase` → empty+diagnostic / unarmed `-` | s02, s04, s06 | no | FR-002/003; epic field `or "unknown"` L155 — only if used as step-mask; epic unknown out unless cheap |
| COMMAND from stale AC heading (`handoff_mode_from_text` / `## Handoff BACK QA` as COMMAND source when frontmatter valid) | A | `resolve_session_identity` + `LoopHandoffFrontmatter` | s03, s04, s06 | no | FR-007; regex may remain for missing-frontmatter diagnostic, **not** COMMAND if state armed |
| `session_start_payload` injects COMMAND from AC/projection without identity lock | A | identity first; halt card on Drift | s03, s06 | no | as-built L1504–1533 fills projection from handoff heading |
| `loop/tests/test_prompt_builder.py` cases that require step=`unknown` for armed fixtures | A | rewrite on new contract | s01, s04, s06 | no | obsolete tests |
| n/a (same SessionStart hook) | B | SessionStart same | s06 | no | plan B n/a; inventory row for completeness |
| warning + continue on mismatch | C | halt `CONTEXT_IDENTITY_DRIFT` | s03, s06 | yes | AC−2; FORBIDDEN silent continue |
| dual-path «prefer AC heading if richer» | C | fail-closed identity | s03, s06 | yes | AC−5 |
| pick winner silently when projection.phase ≠ armed_step | C | Drift `phase_mismatch` | s02, s03, s06 | yes | FR-020 |
| docs / comments «step unknown OK for QA» | I | armed always has step token | s04, s06 | no | FR-006 |
| instructions teaching regex `## Handoff BACK QA` as COMMAND SoT when frontmatter valid | I | identity / frontmatter SoT | s04, s06 | no | Technology axiom |
| render_prompt_scope teaching `phase: unknown` as normal armed state | I | phase token or `-` | s04, s06 | no | L170 `scope.phase or 'unknown'` — purge as default for armed |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-identity-red-tests.yaml](../yaml/steps/s01-identity-red-tests.yaml) | [s01…](../../implement/T-HUB-071-session-identity-lock/s01-identity-red-tests.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-resolve-session-identity.yaml](../yaml/steps/s02-resolve-session-identity.yaml) | [s02…](../../implement/T-HUB-071-session-identity-lock/s02-resolve-session-identity.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-session-start-halt-wire.yaml](../yaml/steps/s03-session-start-halt-wire.yaml) | [s03…](../../implement/T-HUB-071-session-identity-lock/s03-session-start-halt-wire.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-kind-i-unknown-purge.yaml](../yaml/steps/s04-kind-i-unknown-purge.yaml) | [s04…](../../implement/T-HUB-071-session-identity-lock/s04-kind-i-unknown-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-phase-matrix-enforce.yaml](../yaml/steps/s05-phase-matrix-enforce.yaml) | [s05…](../../implement/T-HUB-071-session-identity-lock/s05-phase-matrix-enforce.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-legacy-fallback-purge.yaml](../yaml/steps/s06-legacy-fallback-purge.yaml) | [s06…](../../implement/T-HUB-071-session-identity-lock/s06-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
**needs_creative:** все `no` (plan: CREATIVE need нет).

**Next after DECOMPOSE FINISH:** `BACK ANALYZE T-HUB-071-session-identity-lock` only. **FORBIDDEN** ANALYZE deferred → IMPLEMENT.
