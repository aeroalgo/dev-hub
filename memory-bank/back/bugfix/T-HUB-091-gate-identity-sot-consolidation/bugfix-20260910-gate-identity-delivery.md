# Bugfix: test_agent_pretool activeContext fallback for uninitialized epic state
**Epic ID:** T-HUB-091-gate-identity-sot-consolidation  
**Date:** 2026-09-10  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-091-gate-identity-sot-consolidation/qa-20260910-gate-identity-sot-consolidation-run2.yaml

---

## 1. QA Root Cause Analysis
During QA re-run on T-HUB-091, `loop/tests/test_stop_gate.py::test_agent_pretool_allows_verify_without_result_yaml` failed with `AssertionError: assert 'deny' == 'allow'`.
Root cause: When `load_epic_state` returns unarmed default state (in test environments or fresh sessions without `.claude/runtime/epic.json`), `current_gate_identity` returned empty `epic_id` and `step_id`. As a result, `ensure_gate_identity_prompt` inside `validate_spawn_input` rejected the spawn with `prompt_incomplete:GATE_IDENTITY`.

---

## 2. Changes Implemented
- `harness/hooks/_lib.py` (`current_gate_identity`): When `state` lacks `epic_id`/`step_id`, fallback to `activeContext.md` frontmatter and Handoff block to resolve identity before falling back to empty.
- `.claude/hooks/_lib.py`: Synchronized with `harness/hooks/_lib.py`.

---

## 3. AC+
- AC+1: `test_agent_pretool_allows_verify_without_result_yaml` passes and allows verify spawn when `activeContext.md` contains valid frontmatter/handoff without requiring pre-existing `.claude/runtime/epic.json`.
- AC+2: Full test suite passes completely with zero failures (`bin/pytest -q --tb=line`).

---

## 4. AC−
- AC−1: No regression in strict ownership enforcement when frozen `session_start_identity` is present in state.
- AC−2: No fallback to raw unvalidated `projection.step` when `session_start_identity` is set.
- AC−3: No unrelated test removals, scope creep, or edits outside the specified allowlist.

---

## 5. §0.11
- Counterparts: `harness/hooks/_lib.py` counterpart is `.claude/hooks/_lib.py`, kept in strict parity.

---

## 6. Verification
- `bin/pytest loop/tests/test_stop_gate.py -k test_agent_pretool_allows_verify_without_result_yaml` — PASS
- `bin/pytest loop/tests/test_stop_gate.py` — PASS (74 passed)
- `bin/pytest -q --tb=line` — PASS (all tests pass)
