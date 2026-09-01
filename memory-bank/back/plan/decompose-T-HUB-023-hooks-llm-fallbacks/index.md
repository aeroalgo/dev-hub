# Decompose T-HUB-023-hooks-llm-fallbacks — hooks-structured-validation

**Plan:** [plan-T-HUB-023-hooks-llm-fallbacks.md](../plan-T-HUB-023-hooks-llm-fallbacks.md)  
**Role:** BACK  
**Next phase:** BACK IMPLEMENT  
**Generated:** 2026-08-31

---

## Shards

| ID | Title | FRs | Key files |
|:---|:------|:----|:---------|
| s01 | Env contract — load_hooks_llm_env() | FR-009 | `_lib.py`, `project.env` |
| s02 | Unified llm_structured — models + factory | FR-001, FR-002, FR-017 | `llm_structured.py` |
| s03 | JSON fence parser + parse_gate_verdict_message | FR-003, FR-004, FR-005 | `_lib.py` |
| s04 | extract_verdict — sidecar-only, no regex | FR-004, SC-001, SC-002 | `_lib.py` |
| s05 | pydantic-ai secondary — verdict/handoff/abort fail-soft | FR-006, FR-007, FR-008 | `llm_structured.py`, `_lib.py`, `session_resilience.py` |
| s06 | G1 agents — JSON fence HARD | FR-010, SC-005 | `agents/verify.md`, `reviewer.md`, `analyze-verify.md` |
| s07 | G2–G3 spawn-hard + _lib CONTRACT | FR-011, FR-012, SC-005, SC-006 | `spawn-hard.md`, `_lib.py` |
| s08 | G4 context_loop — gate JSON finalize | FR-012, SC-006 | `context_loop.py` |
| s09 | G5–G6 pretool + stop-gate JSON→sidecar wire | FR-013, AC-plus-5 | `subagent-stop.py`, `stop-gate.py`, `agent-pretool.py` |
| s10 | Drift counter — structured_extract_used | FR-009 | `_lib.py`, `llm_structured.py` |
| s11 | Tests — fence + secondary mock + rg audit | FR-014, SC-001…SC-008 | `loop/tests/test_hooks_llm_*.py`, `test_gate_structured_purge.py` |
| s12 | G7 docs — operator contract | FR-015, SC-005 | `loop/README.md`, `project.env` |
| s13 | Legacy purge — delete regex VERDICT machine paths | FR-016, SC-001, sunset-A | `_lib.py`, agents, spawn-hard, context_loop |

**Dependency order:** s01 → s02 → s03 → s04 → s05 (parallel s06–s08 after s03) → s09 → s10 → s11 → s12 → s13

---

## Requirements coverage

| Requirement | Type | Covered by | Status |
|:-----------|:-----|:---------|:-------|
| FR-001 (GateVerdictRecord schema) | FR | s02 | ✓ |
| FR-002 (GateVerdictValue enum) | FR | s02 | ✓ |
| FR-003 (fence parser primary path) | FR | s03 | ✓ |
| FR-004 (extract_verdict sidecar-only) | FR | s03, s04 | ✓ |
| FR-005 (invalid JSON → fail-closed) | FR | s03 | ✓ |
| FR-006 (verdict secondary pydantic-ai runner) | FR | s05 | ✓ |
| FR-007 (handoff secondary runner) | FR | s05 | ✓ |
| FR-008 (abort secondary runner / classify_abort) | FR | s05 | ✓ |
| FR-009 (load_hooks_llm_env + per-domain flags) | FR | s01, s10 | ✓ |
| FR-010 (G1 agents JSON fence HARD) | FR | s06 | ✓ |
| FR-011 (G2–G3 spawn-hard + _lib CONTRACT) | FR | s07 | ✓ |
| FR-012 (G4 context_loop gate JSON) | FR | s07, s08 | ✓ |
| FR-013 (G5–G6 pretool/stop-gate JSON→sidecar) | FR | s09 | ✓ |
| FR-014 (tests JSON valid/invalid/missing + mock) | FR | s11 | ✓ |
| FR-015 (G7 docs — README operator contract) | FR | s12 | ✓ |
| FR-016 (legacy regex VERDICT purge) | FR | s13 | ✓ |
| FR-017 (unified llm_structured 021+023) | FR | s02 | ✓ |
| SC-001 (no VERDICT regex machine path) | SC | s04, s13, s11 | ✓ |
| SC-002 (valid JSON fence → sidecar → extract_verdict enum) | SC | s03, s04, s11 | ✓ |
| SC-003 (invalid/missing JSON → fail-closed) | SC | s03, s11 | ✓ |
| SC-004 (valid JSON skips pydantic-ai Agent.run) | SC | s05, s11 | ✓ |
| SC-005 (agents + spawn-hard contain JSON contract) | SC | s06, s07, s11 | ✓ |
| SC-006 (context_loop gate JSON not VERDICT line) | SC | s08, s11 | ✓ |
| SC-007 (classify_abort pydantic-ai enum only) | SC | s05, s11 | ✓ |
| SC-008 (T-HUB-021 LogSummary regression green) | SC | s11 | ✓ |
| US-001 (structured verdict JSON) | US | s02, s03, s04 | ✓ |
| US-002 (pydantic-ai secondary fail-soft) | US | s05 | ✓ |
| US-003 (hook parses fenced JSON → model_validate, not regex) | US | s03, s04, s09 | ✓ |
| AC+ 1 (subagents emit fenced JSON / extract from sidecar) | AC+ | s03, s04, s06 | ✓ |
| AC+ 2 (extract_verdict sidecar-only) | AC+ | s04 | ✓ |
| AC+ 3 (pydantic-ai secondary on JSON miss only) | AC+ | s05 | ✓ |
| AC+ 4 (G1–G4 prompt inventory aligned) | AC+ | s06, s07, s08 | ✓ |
| AC+ 5 (G5–G6 pretool/stop-gate JSON→sidecar) | AC+ | s09 | ✓ |
| AC+ 6 (legacy regex deleted) | AC+ | s13 | ✓ |
| AC+ 7 (mocked tests + CI fail-closed without LLM) | AC+ | s11 | ✓ |
| AC− 1 (no regex VERDICT machine input) | AC− | s04, s13 | ✓ |
| AC− 2 (no pydantic-ai when valid JSON) | AC− | s05, s11 | ✓ |
| AC− 3 (no silent PASS on ValidationError) | AC− | s03, s05 | ✓ |
| AC− 4 (no legacy free-text LLM fallback) | AC− | s05 | ✓ |
| AC− 5 (hook never crashes on bad JSON) | AC− | s03, s05 | ✓ |

---

## Stages coverage

| Plan stage | Covered by shards |
|:-----------|:-----------------|
| Env contract + flags | s01 |
| Unified models module (021+023) | s02 |
| Primary fence parser + sidecar write | s03 |
| extract_verdict sidecar-only | s04 |
| pydantic-ai secondary runners | s05 |
| G1 agent prompts JSON fence | s06 |
| G2–G3 spawn + CONTRACT strings | s07 |
| G4 context_loop packed prompts | s08 |
| G5–G6 hook wire (pretool + stop-gate) | s09 |
| Drift / metrics counter | s10 |
| Tests (all SCs) | s11 |
| Docs / README operator | s12 |
| Legacy purge + final rg proof | s13 |

---

## Outcome map

| Plan goal | Achieved by | Measurable |
|:----------|:-----------|:-----------|
| No `VERDICT:` regex in machine path | s04 (delete regex), s13 (purge + rg proof) | rg 0 hits |
| valid JSON fence → sidecar → typed enum | s03 (fence parser + write), s04 (sidecar-only read) | pytest roundtrip |
| Invalid/missing JSON → fail-closed | s03 (return None), s09 (block) | pytest SC-003 |
| valid JSON skips pydantic-ai Agent.run | s05 (flag check first), s04 (short-circuit) | mock call count 0 |
| agents / spawn-hard have JSON HARD contract | s06 (agents), s07 (spawn-hard + _lib) | rg loop-gate-verdict |
| context_loop prompts reference gate JSON | s08 | rg loop-gate-verdict |
| pydantic-ai secondary fail-soft runners | s05 (runners), s11 (mocked tests) | pytest |
| operator can configure via env | s01 (load_hooks_llm_env), s12 (README) | rg + docs |
| T-HUB-021 regression green | s02 (unified), s11 (SC-008) | pytest |

---

## Replacement cleanup

Brownfield replace — non-empty deletes:

| Item | Old path / symbol | Replaced by | Owner shard | grep_control |
|:-----|:-----------------|:-----------|:-----------|:-------------|
| A | `_lib.py` regex block in `extract_verdict()` (строки ~1316–1327) | sidecar-only path | s04 | `rg 're\.finditer.*VERDICT' .claude/hooks/_lib.py → 0` |
| B | `_lib.py` CONTRACT strings `VERDICT-first` (строки ~39–65) | JSON fence CONTRACT | s07 | `rg 'первая строка.*VERDICT' .claude/hooks/_lib.py → 0` |
| C | `gate_verdict_regex_fallback` drift counter call | drift counter `structured_extract_used` | s04, s10 | `rg 'gate_verdict_regex_fallback' .claude/hooks/ → 0` |
| D | `agents/*.md` machine-first `VERDICT: PASS|FAIL` строка | JSON fence HARD + optional prose summary | s06 | `rg 'loop-gate-verdict' agents/ → ≥3` |
| E | `spawn-hard.md` VERDICT machine instruction | JSON fence contract | s07 | `rg 'loop-gate-verdict' spawn-hard.md → ≥1` |
| F | `context_loop.py` VERDICT machine instruction | gate JSON sidecar reference | s08 | `rg 'loop-gate-verdict' loop/context_loop.py → ≥1` |

Финальный purge + полный inventory scan: **s13** (`grep_control` checkpoints cp1–cp3).

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | Env contract — structured gate flags + load_hooks_llm_env() · [yaml](s01-env-contract-load-hooks-llm-env.yaml) | BACK IMPLEMENT | completed |
| **s02** | Unified llm_structured — LogSummary + enum models + factory · [yaml](s02-unified-llm-structured-models-factory.yaml) | BACK IMPLEMENT | completed |
| **s03** | JSON fence parser + parse_gate_verdict_message + sidecar write · [yaml](s03-json-fence-parser-parse-gate-verdict-message.yaml) | BACK IMPLEMENT | completed |
| **s04** | extract_verdict — sidecar-only, no regex · [yaml](s04-extract-verdict-sidecar-only.yaml) | BACK IMPLEMENT | completed |
| **s05** | pydantic-ai secondary — verdict/handoff/abort runners fail-soft · [yaml](s05-pydantic-ai-secondary-runners-fail-soft.yaml) | BACK IMPLEMENT | completed |
| **s06** | G1 agents — JSON fence HARD (verify/reviewer/analyze-verify.md) · [yaml](s06-g1-agents-json-fence-hard.yaml) | BACK IMPLEMENT | completed |
| **s07** | G2–G3 spawn-hard + _lib CONTRACT strings aligned · [yaml](s07-g2-g3-spawn-hard-lib-contract.yaml) | BACK IMPLEMENT | completed |
| **s08** | G4 context_loop — gate JSON finalize steps (replace VERDICT: prose) · [yaml](s08-g4-context-loop-gate-json-finalize.yaml) | BACK IMPLEMENT | completed |
| **s09** | G5–G6 pretool + stop-gate JSON → sidecar wire · [yaml](s09-g5-g6-pretool-stop-gate-json-sidecar-wire.yaml) | BACK IMPLEMENT | completed |
| **s10** | Drift counter — structured_extract_used (json|pydantic-ai tag) · [yaml](s10-drift-counter-structured-extract-used.yaml) | BACK IMPLEMENT | completed |
| **s11** | Tests — JSON fence valid/invalid/missing; pydantic-ai mock; spawn rg audit · [yaml](s11-tests-json-fence-secondary-mock-spawn-audit.yaml) | BACK IMPLEMENT | completed |
| **s12** | G7 docs — README + project.env operator structured gate contract · [yaml](s12-g7-docs-operator-structured-gate-contract.yaml) | BACK IMPLEMENT | completed |
| **s13** | Legacy purge — delete regex VERDICT/handoff/abort machine paths · [yaml](s13-legacy-purge-regex-verdict-handoff-abort.yaml) | BACK IMPLEMENT | completed |