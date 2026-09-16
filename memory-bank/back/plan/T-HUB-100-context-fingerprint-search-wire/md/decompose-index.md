# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-100-context-fingerprint-search-wire  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**  
**Дата:** 2026-09-15  
**Режим:** BACK DECOMPOSE  
**Уровень:** L2  
**Granularity:** 5 sNN (band 5–8; red fixtures in s01; context policy active predicate & search scope in s02; test fingerprint cache bash wiring in s03; posttool edit invalidation in s04; sunset & integration in s05).

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — `.cursor/templates/decompose/epic-step.yaml`.

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-100-context-fingerprint-search-wire/md/decompose-index.md`. Machine = `yaml/decompose-index.yaml`. Shards = `yaml/steps/`.  
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `decompose-index.yaml` only.**  
> **Ladder:** s01 red tests → s02 context policy active predicate & search scope → s03 test fingerprint cache bash wiring → s04 posttool edit invalidation → s05 legacy fallback purge & integration.

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность (сессия DECOMPOSE, не `impl:`) |
| `tdd` / `python-testing-patterns` / `modern-python` / `python-anti-patterns` | Core(4) в каждом code sNN |

**Per-step:** skills gate в каждом `sNN`. Session skills (`writing-plans`, `brainstorming`) **FORBIDDEN** в `impl:`.

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR / US / SC → ≥1 шаг, иначе `out_of_scope` + `follow_up:` уже в `memory-bank/back/roadmap/queue.yaml`.  
> Колонка **Plan FR text** = дословно из `plan.md`. Covered row ⇒ measurable `verify` (не map-only).

| Req ID | Plan FR text (verbatim) | sNN | Notes / measurable verify |
| :--- | :--- | :--- | :--- |
| FR-001 | Introduce `is_context_policy_active(cwd, context) -> bool` (or reuse existing ledger session predicate) that is true for root and subagent when shard/context loaded — strictly broader than `is_epic_loop_env()` but fail-closed when context unknown (no silent allow of unscoped search). | s01, s02, s05 | `bin/pytest harness/hooks/tests/test_context_scope_policy.py -k test_is_context_policy_active` |
| FR-002 | Wire `TestFingerprintCache` into `BashPolicyAdapter.evaluate`: detect normalized test commands (reuse `normalize_test_command` / fingerprint helpers from `context_scope.py`); on hit with valid fingerprint → return deny or cached-no-op envelope per I1 FR-006 semantics; on post-edit invalidation → miss/deny re-run until fresh execution recorded. | s01, s03, s05 | `bin/pytest harness/hooks/tests/test_context_scope_policy.py -k test_bash_pretool_test_cache` |
| FR-003 | Connect edit/write post-tool path to `TestFingerprintCache.invalidate_path` for changed canonical paths (if not already wired end-to-end); ensure invalidation occurs before subsequent Bash test command decision. | s01, s04, s05 | `bin/pytest harness/hooks/tests/test_posttool_dispatch.py -k test_write_posttool_invalidates_test_cache` |
| FR-004 | Move search scope check in `BashPolicyAdapter` behind `is_context_policy_active` instead of `is_epic_loop_env()` alone; preserve `ScopeResolver.evaluate_search` contract (graphify + exception_reason). | s01, s02, s05 | `bin/pytest harness/hooks/tests/test_context_scope_policy.py -k test_search_outside_scope_denied` |
| FR-005 | Ensure subagent events supply same `ScopeResolver` inputs (shard files, delta, graphify evidence) as root; no provider-specific bypass (`claude` vs `codex` adapters call shared policy). | s01, s02, s05 | `bin/pytest harness/hooks/tests/test_context_scope_policy.py -k test_subagent_search_scope` |
| FR-006 | Preserve I1 duplicate-read, plan-jump, and edit-invalidation behaviors; full regression TM-078-01…11 from I1 QA remain green. | s01, s05 | `bin/pytest harness/hooks/tests/test_context_ledger.py harness/hooks/tests/test_context_ledger_adapters.py` |
| US-I2-001 | Как IMPLEMENT agent, я не могу повторно «прогнать» тот же test command после изменения relevant file и получить cached PASS без re-execution. | s01, s03, s04, s05 | `test_edit_invalidates_test_cache_miss` |
| US-I2-002 | Как root agent вне EPIC_LOOP но с active context ledger, я не могу rg за пределами shard allowlist без graphify. | s01, s02, s05 | `test_search_outside_scope_denied_non_loop` |
| US-I2-003 | Как subagent, я получаю ту же search deny decision что root при equivalent scope. | s01, s02, s05 | `test_subagent_search_parity` |
| US-I2-004 | Как operator, legitimate search inside shard paths still works without graphify. | s01, s02, s05 | `test_in_shard_search_allowed` |
| US-I2-001 (AS) | TestFingerprintCache wired to Bash pretool: repeat test cmd unchanged -> cached decision; edit relevant file -> miss/deny fresh run. | s01, s03, s04, s05 | `test_context_scope_policy.py` |
| US-I2-002 (AS) | Search scope beyond EPIC_LOOP: ledger active, not EPIC_LOOP, search outside scope -> deny search_outside_scope_denied. | s01, s02, s05 | `test_context_scope_policy.py` |
| US-I2-003 (AS) | In-scope search still allowed: search command targets only paths under shard allowlist -> allow; no graphify required. | s01, s02, s05 | `test_context_scope_policy.py` |
| US-I2-004 (AS) | I1 ledger behaviors preserved: duplicate-read and plan-jump rules unchanged. | s01, s05 | `test_context_ledger.py` |
| NFR-001 | Cache and search decisions emit same `DecisionReceipt` schema as I1 ledger. | s02, s03, s05 | `test_context_scope_policy.py` |
| NFR-002 | No global token metering introduced. | s01–s05 | scope lock |
| NFR-003 | Test command detection MUST reuse existing normalizers — no duplicate regex folklore. | s03, s05 | code audit in `context_scope.py` |
| NFR-004 | Fail-closed: ambiguous policy activation → deny broad search, not allow. | s02, s05 | `test_context_scope_policy.py` |
| AC− 1 | No cached test PASS after relevant file change when Bash pretool allows command. | s01, s04, s05 | negative cache assertion |
| AC− 2 | No search outside allowlist when context policy active, regardless of EPIC_LOOP env. | s01, s02, s05 | negative search assertion |
| AC− 3 | No provider-specific search bypass for subagents. | s01, s02, s05 | adapter parity assertion |
| AC− 4 | No global token budget meter introduced. | s01–s05 | scope lock |
| AC− 5 | No regression of I1 duplicate-read / plan-jump gates. | s01, s05 | regression guard |
| AC− 6 | No scope into capability evidence or agents corpus. | — | follow_up: T-HUB-077, follow_up: T-HUB-080 |
| TM-I2-078-01 | Repeat test cmd unchanged → cache hit/deny policy (P0). | s01, s03, s05 | `test_bash_pretool_test_cache_hit` |
| TM-I2-078-02 | Edit relevant file → repeat test cmd → no stale cache (P0). | s01, s04, s05 | `test_edit_invalidates_test_cache_miss` |
| TM-I2-078-03 | Ledger active, not EPIC_LOOP, search outside scope → deny (P0). | s01, s02, s05 | `test_search_outside_scope_denied_non_loop` |
| TM-I2-078-04 | In-shard search allowed without graphify (P1). | s01, s02, s05 | `test_in_shard_search_allowed` |
| TM-I2-078-05 | Subagent equivalent search deny (P1). | s01, s02, s05 | `test_subagent_search_parity` |
| TM-I2-078-06 | I1 duplicate-read regression (P1). | s01, s05 | `test_context_ledger.py` |

## Stages coverage

| Stage | Focus | sNN |
|-------|-------|-----|
| Stage 1 | TDD Red: failing fixtures for test cache pretool, posttool invalidation, and search scope outside EPIC_LOOP | s01 |
| Stage 2 | Predicate & Search: is_context_policy_active helper and ScopeResolver evaluation in BashPolicyAdapter | s02 |
| Stage 3 | Pretool Cache: wire TestFingerprintCache lookup into BashPolicyAdapter with DecisionReceipt emission | s03 |
| Stage 4 | Posttool Invalidation: connect WritePostToolAdapter to TestFingerprintCache.invalidate_path | s04 |
| Stage 5 | Sunset & Integration: inventory audit, fallback purge, full TM-I2-078-01..06 matrix | s05 |

## Outcome map

| Outcome | Production entrypoints | Shards | Verification |
|---------|------------------------|--------|--------------|
| Policy active predicate | `harness/hooks/context_ledger.py` | s02 | `test_context_scope_policy.py` |
| Search scope pretool enforcement | `harness/hooks/pretool_policy.py`, `harness/hooks/context_scope.py` | s02 | `test_context_scope_policy.py` |
| Test fingerprint cache pretool | `harness/hooks/pretool_policy.py`, `harness/hooks/context_scope.py` | s03 | `test_context_scope_policy.py` |
| Posttool edit cache invalidation | `harness/hooks/posttool_policy.py`, `harness/hooks/context_scope.py` | s04 | `test_posttool_dispatch.py` |
| Sunset & regression closure | `harness/hooks/context_scope.py`, `harness/hooks/pretool_policy.py`, `harness/hooks/posttool_policy.py` | s05 | `test_context_scope_policy.py`, `test_context_ledger.py`, `test_posttool_dispatch.py` |

## Replacement cleanup (plan → steps)

> **HARD (brownfield replace):** каждая поверхность plan sunset **A/B/C/I** → ≥1 `sNN` с непустым `deletes:` (или OOS + follow-up в queue).  
> Completeness ladder: **add → wire → enforce → purge**. Add-only на sole-path FR = FAIL (`optional_sot`).

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `TestFingerprintCache` dead code (unit-only) | A | Bash pretool live lookup/record | s03, s05 | no | `harness/hooks/context_scope.py` |
| Search scope gated only on `is_epic_loop_env()` | A | `is_context_policy_active` gate | s02, s05 | no | `harness/hooks/pretool_policy.py` |
| Bash test command without fingerprint check | B | pretool cache decision | s03, s05 | no | `harness/hooks/pretool_policy.py` |
| Non-loop sessions unscoped search | B | ScopeResolver when policy active | s02, s05 | no | `harness/hooks/pretool_policy.py` |
| Silent reuse of test result after file change | C | invalidate + deny/miss | s04, s05 | no | no fallback |
| «Convenience» rg anywhere when ledger exists | C | deny without graphify | s02, s05 | no | no fallback |
| Instruction surfaces: diagnostics only | I | code enforcement primary | s05 | no | full agents corpus owned by follow_up: T-HUB-102 |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-red-tests-fingerprint-and-search-scope.yaml](../yaml/steps/s01-red-tests-fingerprint-and-search-scope.yaml) | [s01…](../../implement/T-HUB-100-context-fingerprint-search-wire/s01-red-tests-fingerprint-and-search-scope.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-context-policy-active-predicate-and-search-scope.yaml](../yaml/steps/s02-context-policy-active-predicate-and-search-scope.yaml) | [s02…](../../implement/T-HUB-100-context-fingerprint-search-wire/s02-context-policy-active-predicate-and-search-scope.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-test-fingerprint-cache-bash-pretool-wiring.yaml](../yaml/steps/s03-test-fingerprint-cache-bash-pretool-wiring.yaml) | [s03…](../../implement/T-HUB-100-context-fingerprint-search-wire/s03-test-fingerprint-cache-bash-pretool-wiring.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-posttool-edit-invalidation-wiring.yaml](../yaml/steps/s04-posttool-edit-invalidation-wiring.yaml) | [s04…](../../implement/T-HUB-100-context-fingerprint-search-wire/s04-posttool-edit-invalidation-wiring.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-legacy-fallback-purge.yaml](../yaml/steps/s05-legacy-fallback-purge.yaml) | [s05…](../../implement/T-HUB-100-context-fingerprint-search-wire/s05-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
**needs_creative:** все `no` (plan: CREATIVE need нет).
