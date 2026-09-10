# Bugfix: Verifier Identity Deduplication and Companion Telemetry Retry Relation (AC 1 / §0.11.2)
**Epic ID:** T-HUB-079-orchestrator-lifecycle-reliability  
**Date:** 2026-09-10  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-079-orchestrator-lifecycle-reliability/qa-20260910-lifecycle-reliability-v6.yaml
---
## 1. QA Root Cause Analysis
During QA review of epic T-HUB-079-orchestrator-lifecycle-reliability, reviewer verify-qa identified:
- **AC 1 / AC−1 (Verifier Idempotency Key Deduplication):** In SubagentLifecycle (loop/runtime_adapters/subagent_lifecycle.py), subagent completion deduplication was keyed only on `f"{thread}:{wait_id}:{verdict}"`. When identical verifier requests were dispatched across multiple threads or multiple wait calls within the same session/gate context, the thread and wait ID differences caused duplicate subagent-start.py and subagent-stop.py invocations.
- **§0.11.2 (Companion Telemetry Retry Relation):** SessionTelemetryCompanion (loop/telemetry.py) did not expose an explicit `retry_relation` field in its serialized dictionary or companion record, and _append_terminal_session_companion in loop/context_loop.py omitted passing `retry_chain_id`, `retry_count`, and `epoch`.

## 2. Changes Implemented
- `loop/runtime_adapters/subagent_lifecycle.py`:
  - Implemented `_verifier_identity_key` leveraging `current_gate_identity` to generate stable deduplication keys: `{session_id}:{role}:{step}:{epoch}:{agent}:{verdict}`.
  - Enhanced `SubagentLifecycle.process_item` to verify `_verifier_identity_key`, thread dedupe, and state-level deduplication before dispatching `_start_and_stop`.
  - Updated `_already_processed` to check both tool_use_id-specific and verifier identity keys in `verdict_recorded_agents`.
- `loop/telemetry.py`:
  - Added `retry_relation` property to `SessionTelemetryCompanion` returning `{"retry_chain_id": ..., "retry_count": ..., "epoch": ..., "is_retry": ...}`.
  - Updated `to_dict()` and `from_dict()` to serialize and deserialize `retry_relation` seamlessly.
- `loop/context_loop.py`:
  - Updated `_append_terminal_session_companion` to pass `retry_chain_id`, `retry_count=epoch`, and `epoch=epoch` to `SessionTelemetryCompanion`.
- `loop/tests/test_subagent_lifecycle.py`:
  - Added `test_shared_lifecycle_deduplicates_by_verifier_identity` verifying that 8 concurrent threads for the same verifier identity and subsequent wait calls trigger exactly 1 start/stop execution.
- `loop/tests/test_lifecycle_telemetry.py`:
  - Added assertions for `retry_relation` property and dictionary serialization.

## 3. Verification
- `bin/pytest loop/tests/test_subagent_lifecycle.py loop/tests/test_lifecycle_telemetry.py loop/tests/test_orchestrator_lifecycle_regression.py -q --tb=line` -> 36 passed
- `bin/pytest -q --tb=line loop/tests/test_lifecycle* loop/tests/test_subagent* loop/tests/test_idempotent* loop/tests/test_orchestrator* harness/hooks/tests/` -> 368 passed

## 4. Follow-up Gate Repair
- `loop/telemetry.py`: `from_dict()` now restores `retry_chain_id`, `retry_count`, and `epoch` from `retry_relation` when present.
- `loop/runtime_adapters/subagent_lifecycle.py`: guarded `process_item()` with `threading.Lock` so pending/completed deduplication remains atomic across concurrent wait events.
- `loop/tests/test_subagent_lifecycle.py`: added a `ThreadPoolExecutor` regression test for concurrent `process_item()` calls.
- `loop/tests/test_lifecycle_telemetry.py`: added a deserialization regression test for nested retry relation fields.
- Verification: `timeout 300s .venv/bin/pytest loop/tests/test_subagent_lifecycle.py loop/tests/test_lifecycle_telemetry.py loop/tests/test_orchestrator_lifecycle_regression.py -q --tb=line` -> 37 passed in 2.10s.
