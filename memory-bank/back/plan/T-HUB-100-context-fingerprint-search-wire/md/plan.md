# [T-HUB-100-context-fingerprint-search-wire] PLAN

**Дата:** 2026-09-14  
**Режим:** BACK PLAN (REPLAN spawn)  
**Уровень:** L2  
**Статус:** active  
**iteration:** 2  
**Replan-of:** `T-HUB-078-context-budget-enforcement`  
**Parent-prompt:** [memory-bank/back/plan/T-HUB-078-context-budget-enforcement/md/prompt.md](../../T-HUB-078-context-budget-enforcement/md/prompt.md) — immutable prior Epic SoT  
**Parent-replan:** [memory-bank/back/plan/T-HUB-078-context-budget-enforcement/md/replan-i2.yaml](../../T-HUB-078-context-budget-enforcement/md/replan-i2.yaml)  
**Parent I1 QA:** [memory-bank/back/qa/T-HUB-078-context-budget-enforcement/qa-20260908-context-budget-enforcement.yaml](../../../qa/T-HUB-078-context-budget-enforcement/qa-20260908-context-budget-enforcement.yaml)  
**Prompt (this epic):** [md/prompt.md](prompt.md)  
**Deps:** hard `T-HUB-078` (parent I1 in done; outcome continuity via Parent-prompt)  
**Batch:** replan-spawn-075-080-20260914  

→ После DECOMPOSE единственный трекер — `yaml/decompose-index.yaml`.

## Provenance

- Spawned by REPLAN of `T-HUB-078-context-budget-enforcement` on 2026-09-14.
- Prior Epic outcome SoT: `memory-bank/back/plan/T-HUB-078-context-budget-enforcement/md/prompt.md` (do not rewrite parent prompt).
- Parent remains in roadmap `done:`; this epic is the sole I2 delivery vehicle.
- I1 plan/decompose/QA under parent are historical; not overwritten.

## Outcome (verbatim summary из prompt.md Epic)

Root agents and subagents receive exactly the context and discovery authority they need, with one measurable read policy shared by Claude Code and Codex.

**Done when (кратко):**

1. Repetition and monolithic context loads cannot occur silently for either root agents or subagents.
2. Claude Code and Codex produce equivalent decisions for equivalent read and edit actions.
3. Legitimate narrow investigation remains possible with explicit evidence, including after a file changes.

**Forbidden after (кратко):** Read-all recovery, provider-specific bypasses, **search-by-convenience**, or **cached test results after relevant change**.

## Gap classification (только critical work I2)

| ID | Class | Описание | Surfaces |
|---|---|---|---|
| G078-1 | `hardening` + `legacy_removal` | `TestFingerprintCache` в `harness/hooks/context_scope.py` (~441–529) unit-tested, но **не** подключён к Bash/PreToolUse (`pretool_policy.py`). Повтор того же test command после relevant file change может silently reuse cached outcome — нарушение Forbidden «cached test results after relevant change» и FR-006 I1. Wire в `BashPolicyAdapter` (или эквивалент): deny cached re-run или invalidate + force re-execution evidence; fail-closed. | `harness/hooks/context_scope.py`; `harness/hooks/pretool_policy.py` `BashPolicyAdapter` (~450–489) |
| G078-2 | `hardening` + `outcome_gap` | Search scope enforcement только при `is_epic_loop_env()` (`pretool_policy.py` ~463–477). Outcome требует **одну** измеримую policy для root+subagents; search-by-convenience Forbidden. Wire search-scope deny whenever context ledger/policy active for actor (not only EPIC_LOOP), без global token metering. | `harness/hooks/pretool_policy.py`; `harness/hooks/context_scope.py` `ScopeResolver`; context ledger activation gate |

**Anti-carry (не входит в I2):** capability evidence / incidents (076/077), agents prompts (080), duplicate-read / plan-jump (I1 met), provider="claude" hardcode polish if parity green.

## backlog_candidates (NOT shards)

| ID | Описание | Почему backlog |
|---|---|---|
| BC-078-1 | provider="claude" hardcoded branch polish | Parity tests already green per I1 QA |
| BC-078-2 | duplicate-read / plan-jump enforcement | Already met I1 — no critical gap |

## Technology axiom

| Выбор | Machine boundary | FORBIDDEN после I2 |
|---|---|---|
| Test fingerprint cache | `TestFingerprintCache.lookup` invoked from Bash pretool before test command allowed | silent reuse after relevant path change |
| Cache invalidation | edit/post-tool invalidates entries via existing `invalidate_path` | stale cache hit |
| Search scope | `ScopeResolver.evaluate_search` when ledger/policy active | rg/grep outside allowlist without graphify |
| Policy activation | deterministic «context policy active» predicate (session + shard context), not EPIC_LOOP env only | provider-specific bypass |

## User Stories + Independent Test

| # | Story | P | Independent Test |
|---|---|---|---|
| US-I2-001 | Как IMPLEMENT agent, я не могу повторно «прогнать» тот же test command после изменения relevant file и получить cached PASS без re-execution. | P0 | Edit file in shard scope → Bash same pytest command → DENY or forced miss requiring fresh run; cache entry invalidated. |
| US-I2-002 | Как root agent вне EPIC_LOOP но с active context ledger, я не могу rg за пределами shard allowlist без graphify. | P0 | Non-EPIC_LOOP fixture with ledger active → search outside files → DENY `search_outside_scope_denied`. |
| US-I2-003 | Как subagent, я получаю ту же search deny decision что root при equivalent scope. | P0 | Subagent invocation fixture → identical deny/allow as root for same command. |
| US-I2-004 | Как operator, legitimate search inside shard paths still works without graphify. | P1 | rg limited to declared file → allow. |

**Independent Test (epic):** Run test command → cache record. Re-run without edits → cached no-op/deny per policy. Edit relevant source → re-run → cache miss or deny until fresh execution. Enable ledger without EPIC_LOOP → broad rg denied; graphify-backed exception allows with receipt. In-shard search allowed.

## Acceptance Scenarios

### US-I2-001 — TestFingerprintCache wired to Bash pretool

- **Given:** session with active context policy; prior successful test command recorded in `TestFingerprintCache`; relevant file unchanged.
- **When:** agent repeats identical normalized test command via Bash.
- **Then:** pretool returns cached reference or explicit deny (no silent full re-execution skip inconsistent with policy); decision receipt documents cache hit.

- **Given:** same session; agent edits file listed in cache entry `relevant_paths` (or diff fingerprint changes).
- **When:** agent repeats identical test command.
- **Then:** cache lookup misses or returns deny requiring re-execution; **Forbidden** cached PASS after change violated → fail-closed.

### US-I2-002 — Search scope beyond EPIC_LOOP

- **Given:** context ledger/policy active for root agent; `is_epic_loop_env()` false; shard files allowlist populated.
- **When:** agent runs search command targeting path outside allowlist without graphify evidence.
- **Then:** `BashPolicyAdapter` denies with `search_outside_scope_denied`; same behavior when actor is subagent with derived identity.

### US-I2-003 — In-scope search still allowed

- **Given:** search command targets only paths under shard allowlist.
- **When:** pretool evaluates via `ScopeResolver`.
- **Then:** allow; no graphify required.

### US-I2-004 — I1 ledger behaviors preserved

- **Given:** duplicate Read unchanged range in IMPLEMENT.
- **When:** Read pretool evaluates.
- **Then:** I1 duplicate deny still applies; new Bash wiring does not disable ledger.

## Functional requirements

- **FR-001:** Introduce `is_context_policy_active(cwd, context) -> bool` (or reuse existing ledger session predicate) that is true for root and subagent when shard/context loaded — strictly broader than `is_epic_loop_env()` but fail-closed when context unknown (no silent allow of unscoped search).
- **FR-002:** Wire `TestFingerprintCache` into `BashPolicyAdapter.evaluate`: detect normalized test commands (reuse `normalize_test_command` / fingerprint helpers from `context_scope.py`); on hit with valid fingerprint → return deny or cached-no-op envelope per I1 FR-006 semantics; on post-edit invalidation → miss/deny re-run until fresh execution recorded.
- **FR-003:** Connect edit/write post-tool path to `TestFingerprintCache.invalidate_path` for changed canonical paths (if not already wired end-to-end); ensure invalidation occurs before subsequent Bash test command decision.
- **FR-004:** Move search scope check in `BashPolicyAdapter` behind `is_context_policy_active` instead of `is_epic_loop_env()` alone; preserve `ScopeResolver.evaluate_search` contract (graphify + exception_reason).
- **FR-005:** Ensure subagent events supply same `ScopeResolver` inputs (shard files, delta, graphify evidence) as root; no provider-specific bypass (`claude` vs `codex` adapters call shared policy).
- **FR-006:** Preserve I1 duplicate-read, plan-jump, and edit-invalidation behaviors; full regression TM-078-01…11 from I1 QA remain green.

## NFR

| ID | Requirement |
|---|---|
| NFR-001 | Cache and search decisions emit same `DecisionReceipt` schema as I1 ledger. |
| NFR-002 | No global token metering introduced. |
| NFR-003 | Test command detection MUST reuse existing normalizers — no duplicate regex folklore. |
| NFR-004 | Fail-closed: ambiguous policy activation → deny broad search, not allow. |

## Target layout (paths)

| Path | Responsibility I2 |
|---|---|
| `harness/hooks/context_scope.py` | `TestFingerprintCache`, `ScopeResolver`, test command normalize helpers |
| `harness/hooks/pretool_policy.py` | `BashPolicyAdapter` — wire cache + search activation gate |
| `harness/hooks/agent-pretool.py` | Adapter registration order |
| `harness/hooks/agent-posttool.py` | Edit invalidation → cache invalidate (if gap) |
| `harness/hooks/context_ledger.py` | Policy active predicate integration |
| `harness/hooks/tests/test_context_scope*.py` | Extend cache+pretool integration |
| `harness/hooks/tests/test_pretool_policy*.py` | Search deny outside EPIC_LOOP; test cache deny |

**Not in 078 scope:** capability evidence, incidents, agents prompts.

## Sunset A / B / C / I

### A. Code / modules

| Устаревает | Замена | Policy |
|---|---|---|
| `TestFingerprintCache` dead code (unit-only) | Bash pretool live lookup/record | delete in-epic (unwired path) |
| Search scope gated only on `is_epic_loop_env()` | `is_context_policy_active` gate | delete in-epic |

### B. Entrypoints

| Устаревает | Замена | Policy |
|---|---|---|
| Bash test command without fingerprint check | pretool cache decision | delete in-epic |
| Non-loop sessions unscoped search | ScopeResolver when policy active | delete in-epic |

### C. Fallbacks

| Устаревает | Замена | Policy |
|---|---|---|
| Silent reuse of test result after file change | invalidate + deny/miss | delete in-epic |
| «Convenience» rg anywhere when ledger exists | deny without graphify | delete in-epic |

### I. Instruction surfaces

| Устаревает | Замена | Policy |
|---|---|---|
| — | Minimal: diagnostics only | full agents OWNED BY 080; I2 code enforcement primary |

## AC−

1. No cached test PASS after relevant file change when Bash pretool allows command.
2. No search outside allowlist when context policy active, regardless of EPIC_LOOP env.
3. No provider-specific search bypass for subagents.
4. No global token budget meter introduced.
5. No regression of I1 duplicate-read / plan-jump gates.
6. No scope into capability evidence or agents corpus.

## QA consumes (#qa-consumes)

| ID | P | Scenario | Command / fixture | Expected | Maps |
|---|---|---|---|---|---|
| TM-I2-078-01 | P0 | Repeat test cmd unchanged → cache hit/deny policy | pretool bash fixture | cached decision; no false execution claim | FR-002 |
| TM-I2-078-02 | P0 | Edit relevant file → repeat test cmd → no stale cache | edit + bash fixture | miss/deny; requires fresh run | FR-002,3 |
| TM-I2-078-03 | P0 | Ledger active, not EPIC_LOOP, search outside scope → deny | pretool bash fixture | `search_outside_scope_denied` | FR-001,4 |
| TM-I2-078-04 | P1 | In-shard search allowed without graphify | pretool bash fixture | allow | FR-004 |
| TM-I2-078-05 | P1 | Subagent equivalent search deny | subagent pretool fixture | same decision as root | FR-005 |
| TM-I2-078-06 | P1 | I1 duplicate-read regression | existing TM-078-02 fixture | unchanged deny | FR-006 |

## Review readiness

| Gate | Required | Status | Evidence |
|---|---|---|---|
| I1 QA PASS | yes | done | qa-20260908-context-budget-enforcement.yaml |
| Gap scope G078-1/G078-2 only | yes | done | Gap table |
| Forbidden after quoted | yes | done | Outcome section |
| qa_consumes ≥3 TM | yes | done | TM-I2-078-01…06 |
| Anti-carry | yes | done | backlog + AC− |
| Pending Required | none | done | — |

## Delivery closure

| Outcome slice | Class | Production entrypoint | Enforcement | Independent test |
|---|---|---|---|---|
| Test cache wired to Bash | legacy_removal + hardening | `BashPolicyAdapter` + `TestFingerprintCache` | fingerprint lookup/invalidate | TM-I2-078-01, TM-I2-078-02 |
| Search scope beyond EPIC_LOOP | outcome_gap + hardening | `BashPolicyAdapter` + `ScopeResolver` | policy-active gate | TM-I2-078-03, TM-I2-078-04, TM-I2-078-05 |
| I1 ledger preserved | regression | existing pretool adapters | no dual policy | TM-I2-078-06 |

## Следующий режим

→ `BACK DECOMPOSE T-HUB-100-context-fingerprint-search-wire` (iteration 2).
