# Bugfix: Wire TodoWrite policy interceptor in phase runner

**Epic ID:** T-HUB-079-orchestrator-lifecycle-reliability  
**Date:** 2026-09-09  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-079-orchestrator-lifecycle-reliability/qa-20260909-orchestrator-lifecycle-reliability-review.yaml

---

## 1. QA Root Cause Analysis
During QA review of epic `T-HUB-079-orchestrator-lifecycle-reliability`, finding AC+ #5 was raised:
- TodoWrite requests were evaluated post-hoc from logs rather than being actively intercepted and bounded by the phase runner during execution.
- `handle_todowrite_request` and `enforce_phase_todowrite_policy` needed to be wired to enforce the start+finish lifecycle boundary and reject the third and subsequent requests deterministically without triggering side-effects.

---

## 2. Changes Implemented
- `loop/context_loop.py`:
  - Implemented `enforce_phase_todowrite_policy(phase, requests, max_allowed=2)` to process batches of requests against `TodoWritePolicy`.
  - Implemented `handle_todowrite_request(policy, payload, apply)` to guard against side effects when exceeding phase quota.
  - Ensured `_validate_todowrite_session` extracts violations and halts execution on policy breaches.
- `harness/hooks/session_resilience.py`:
  - Updated session log analysis to parse raw and structured TodoWrite requests and serialize policy decisions and violations into companion telemetry.
- `loop/tests/test_todowrite_policy.py`:
  - Added unit tests `test_enforce_phase_todowrite_policy_runner` and `test_handle_todowrite_request_hook`, verifying that start and finish events are permitted with side effects enabled, while 3rd and 4th events are rejected with `todowrite_limit_exceeded` and `side_effect=False` without executing the `apply` callback.

---

## 3. Verification
Targeted regression suite:
```
bin/pytest loop/tests/test_todowrite_policy.py loop/tests/test_reducer_qa_bugfix.py loop/tests/test_orchestrator_lifecycle_regression.py loop/tests/test_lifecycle_reducer.py
40 passed
```
Full repository suite:
```
bin/pytest -q --tb=line
2508 passed
```
