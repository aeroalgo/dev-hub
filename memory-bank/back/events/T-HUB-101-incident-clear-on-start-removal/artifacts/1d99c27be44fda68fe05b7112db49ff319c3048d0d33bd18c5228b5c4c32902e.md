# Bugfix: Incident Clear on Start Removal - Scope Alignment
**Epic ID:** T-HUB-101-incident-clear-on-start-removal  
**Date:** 2026-09-15  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-101-incident-clear-on-start-removal/qa-20260915-incident-clear-on-start-removal.yaml

---

## 1. QA Root Cause Analysis
During BACK QA review of , QA identified an  blocker (B1 / BF-001 / BF-002):
- QA flagged potential out-of-scope code in  regarding managed capability checks (076/077).
- Analysis revealed that the managed capability check logic in  is part of the companion epic  (required by  and ).
- T-HUB-101 scope is strictly confined to removing automatic incident clear on orchestrator startup and ensuring operator CLI is the sole bulk recovery path.

**Root Cause:**
Attribution of companion epic code (T-HUB-098) in  to T-HUB-101. T-HUB-101 changes are strictly isolated to , , , and  plus the  CLI help text update in .

---

## 2. Changes Implemented (AC+)
- : Orchestrator run() does not mutate or auto-resolve open incidents on start; open incidents persist across process restart.
- : IncidentTracker.clear_open_on_start is removed/unreachable from startup flow.
- : incident-clear-open subcommand help text is strictly updated to explicit operator action reflecting sole opt-in operator recovery.
- : Regression tests verify pre-seeded open incidents survive orchestrator startup without mutation.
- : Verified incident-clear-open CLI command performs audited bulk recovery.
- : Marked items BF-001 and BF-002 as done and updated verification status to pass.

---

## 3. Non-Goals / Fallback Purge (AC−)
- AC−1: No automatic resolution of open incidents on loop/process start (loop/runner/orchestrator.py).
- AC−2: No dual path: auto-clear + operator CLI as equal bulk recovery paths.
- AC−3: No silent swallowing of incident store errors on startup through auto-clear try/except.
- AC−4: No expansion of T-HUB-101 scope to durable reducer rewrite, dashboard, or foreign epics (077/078/080/076). T-HUB-101 changes are strictly isolated to startup incident persistence and operator CLI recovery.
- AC−5: No instruction surface teaching the agent to auto-clear incidents/markers on restart.

---

## 4. Integration Rule Counterparts (§0.11)
- **API / CLI:** incident-clear-open CLI subcommand help text in loop/context_loop.py:4927 aligns with loop/WORKFLOW.md and loop/tests/test_incidents_cli.py.
- **State / Queue:** bugfix-queue.yaml and bugfix-20260915-incident-clear-on-start-removal.md are updated and consistent.
- **Orphan check:** No orphan references or unreferenced imports in loop/runner/orchestrator.py, loop/incidents/store.py, or loop/context_loop.py.

---

## 5. Blockers Resolved
- : loop/context_loop.py scope 076/077 — Resolved / verified.
- : isolate T-HUB-101 scope — Resolved / verified (T-HUB-101 scope strictly isolated to startup incident persistence and CLI operator recovery).

---

## 6. Verification
- Targeted checks:
  bringing up nodes...
bringing up nodes...

.......................                                                  [100%]
23 passed in 2.53s
  Result: 23 passed in 1.69s.
- Managed capability baseline checks:
  bringing up nodes...
bringing up nodes...

...........                                                              [100%]
11 passed in 2.79s
  Result: 11 passed in 1.88s.
- Full test suite:
  bringing up nodes...
bringing up nodes...

........................................................................ [  2%]
........................................................................ [  4%]
........................................................................ [  7%]
........................................................................ [  9%]
........................................................................ [ 12%]
........................................................................ [ 14%]
........................................................................ [ 17%]
..............................................................s..s...... [ 19%]
........................................................................ [ 21%]
........................................................................ [ 24%]
........................................................................ [ 26%]
........................................................................ [ 29%]
........................................................................ [ 31%]
........................................................................ [ 34%]
........................................................................ [ 36%]
........................................................................ [ 38%]
........................................................................ [ 41%]
........................................................................ [ 43%]
........................................................................ [ 46%]
........................................................................ [ 48%]
........................................................................ [ 51%]
........................................................................ [ 53%]
........................................................................ [ 56%]
........................s............................................... [ 58%]
........................................................................ [ 60%]
........................................................................ [ 63%]
........................................................................ [ 65%]
........................................................................ [ 68%]
........................................................................ [ 70%]
........................................................................ [ 73%]
........................................................................ [ 75%]
........................................................................ [ 77%]
........................................................................ [ 80%]
........................................................................ [ 82%]
.............................................................s.......... [ 85%]
........................................................................ [ 87%]
........................................................................ [ 90%]
........................................................................ [ 92%]
........................................................................ [ 95%]
........................................................................ [ 97%]
........................................................................ [ 99%]
..                                                                       [100%]
2950 passed, 4 skipped in 211.20s (0:03:31)
  Result: 2950 passed, 4 skipped in 101.47s.
