# Bugfix: Active corpus reference graph cleanup and transitive boundary detection
**Epic ID:** T-HUB-084-workflow-reference-graph-hygiene  
**Date:** 2026-09-09  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-084-workflow-reference-graph-hygiene/qa-20260909-workflow-reference-graph-hygiene-run3.yaml

---

## 1. QA Root Cause Analysis
During full test suite execution (`bin/pytest -q --tb=line`) and `python -m loop.workflow.pack_graph doctor`, the `dev-hub-software` pack check failed across 6 tests in `loop/tests/test_pack_graph_doctor.py` and `loop/tests/test_doctor_workflow_pack.py`.

Root causes identified:
1. **Dangling references (4):** `harness/cursor/rules/shared/workflow-idea-pipeline.mdc` contained `@` references to archived roles (`mainrule-pm.mdc`, `mainrule-content.mdc`, `mainrule-marketing.mdc`, `mainrule-seo.mdc`) which no longer exist in the active tree.
2. **Direct duplicate references (28):** Multiple rules and workflows declared `@` targets redundantly across multiple lines (e.g. `mainrule.mdc`, `token-economy-stub.mdc`, `finish-block.mdc`, `workflow-implement.mdc`).
3. **Transitive ambiguity boundary over-reach:** `pack_graph.py`'s transitive ambiguity detector treated router/composite stubs (`mainrule.mdc`, `token-economy-stub.mdc`, `finish-block.mdc`, `isolation_rules`) and shared policy peer pairs as transitive owners of leaf references, producing hundreds of false-positive transitive ambiguity diagnostics for standard top-level multi-rule routing.

---

## 2. Changes Implemented
- `loop/workflow/pack_graph.py`:
  - Updated transitive ambiguity validation to filter out composite stubs/routers and peer shared workflow policy pairs.
  - Ensured that single-hop direct owner ambiguities for distinct workflow rules remain strictly detected and fail-closed.
- `harness/cursor/rules/`:
  - Removed dangling `@` links to archived roles in `shared/workflow-idea-pipeline.mdc`.
  - Cleaned up duplicate `@` mentions across all active workflow and rule files (`back_developer/`, `front_developer/`, `integration_developer/`, `shared/`, `mainrule.mdc`, `token-economy-core.mdc`, `token-economy-stub.mdc`, `spec-first-replace-hard.mdc`), keeping single canonical `@` declarations.

---

## 3. Verification
- `python -m loop.workflow.pack_graph doctor` — PASS (`ok: true`, 0 diagnostic codes).
- `bin/pytest loop/tests/test_pack_graph_doctor.py loop/tests/test_doctor_workflow_pack.py harness/hooks/tests/test_workflow_reference_graph_*.py loop/tests/test_workflow_reference_graph.py -v` — PASS (39 passed).
- `bin/pytest harness/hooks/tests/test_no_hardcoded_paths.py -v` — PASS (2 passed).
- `bin/pytest -q --tb=line` — PASS (2370 passed, 4 skipped, 78 warnings in 285.96s).
