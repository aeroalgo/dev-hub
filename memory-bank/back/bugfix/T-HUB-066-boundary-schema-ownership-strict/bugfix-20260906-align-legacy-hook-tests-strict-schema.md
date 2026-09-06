---
schema: loop-bugfix/v1
epic_id: T-HUB-066-boundary-schema-ownership-strict
date: 2026-09-06
source: qa §Fix plan
slug: align-legacy-hook-tests-strict-schema
---

# BUGFIX — Align legacy hook tests with strict GateVerdictRecord schema

## 1. Root Cause
`GateVerdictRecord` schema was updated to require `step_id`, `session_id`, and `epic_id` as non-empty string fields (strict boundary ownership). Legacy hook tests in `test_agent_hooks.py`, `test_codex_hooks_bridge.py`, `test_dsh_epic_gate_gaps.py`, `test_hooks_llm_fence.py`, `test_hooks_llm_secondary.py`, `test_hooks_llm_wire.py`, and `test_schemas_gate_verdict.py` omitted these fields in mock fences or direct instantiations, triggering validation errors and test failures during the QA full suite run.

## 2. Changes Made
- `harness/hooks/llm_structured.py`: Added `session_id` to `GateVerdictOutput` and threaded `session_id` into `run_gate_verdict_llm`.
- `loop/tests/test_agent_hooks.py`: Updated `_gate_fence` helper with default `step_id`, `session_id`, and `epic_id` matching strict schema.
- `loop/tests/test_codex_hooks_bridge.py`: Updated valid fence test payload to include `step_id`, `session_id`, and `epic_id`.
- `loop/tests/test_dsh_epic_gate_gaps.py`: Updated test fence payload with `step_id`, `session_id`, and `epic_id`.
- `loop/tests/test_hooks_llm_fence.py`: Added `step_id`, `session_id`, and `epic_id` to test message parsers and payloads.
- `loop/tests/test_hooks_llm_secondary.py`: Updated `GateVerdictOutput` mock and `run_gate_verdict_llm` invocation to include `session_id`.
- `loop/tests/test_hooks_llm_wire.py`: Added `session_id` and required fields to parse and sidecar write test messages.
- `loop/tests/test_schemas_gate_verdict.py`: Added required `step_id`, `session_id`, and `epic_id` to `write_gate_verdict` calls in `test_sidecar_pass_overrides_transcript_fail`.

## 3. Verification
- Targeted pytest: `bin/pytest -q loop/tests/test_agent_hooks.py loop/tests/test_codex_hooks_bridge.py loop/tests/test_dsh_epic_gate_gaps.py loop/tests/test_hooks_llm_fence.py loop/tests/test_hooks_llm_secondary.py loop/tests/test_hooks_llm_wire.py loop/tests/test_schemas_gate_verdict.py --tb=short` -> 71 passed.
