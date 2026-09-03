# Decompose: T-HUB-044-runtime-sync-doctor-docs

**Plan:** [plan/T-HUB-044-runtime-sync-doctor-docs/md/plan.md](../plan/T-HUB-044-runtime-sync-doctor-docs/md/plan.md)  
**Role:** BACK  
**Next phase:** BACK IMPLEMENT  
**Date:** 2026-09-02

---

## Steps queue

| Step | Title | Files |
|------|-------|-------|
| s01 | README runtime table + WORKFLOW.md registry pointer | README.md, loop/WORKFLOW.md |
| s02 | codex-loop-pilot runbook | docs/runbooks/codex-loop-pilot.md |
| s03 | Doctor runtime checks: registry_valid, sync_drift, binary_codex | loop/incidents/doctor.py |
| s04 | Board launch --runtime choices from registry (add codex) | loop/board_sync/cli.py, loop/board_launch/loop_argv.py |
| s05 | hub-link AGENTS.md stub + architecture services.md row | bin/hub-link, memory-bank/architecture/services.md |
| s06 | Tests test_doctor_runtime.py + doc link audit | loop/tests/test_doctor_runtime.py |

---

## Requirements coverage

| Requirement | sNN | Measurable verify |
|-------------|-----|-------------------|
| FR-001: README §Supported agents — codex loop ✅, prerequisites | s01 | `rg 'codex-loop-pilot' README.md` |
| FR-002: loop/WORKFLOW.md — runtime registry reference | s01 | `rg 'runtime_registry' loop/WORKFLOW.md` |
| FR-003: docs/runbooks/codex-loop-pilot.md | s02 | `test -f docs/runbooks/codex-loop-pilot.md` |
| FR-004: harness/README.md (if not done in 041) | — | Deferred: epic 041 owner; out_of_scope s05 |
| FR-005: Extend doctor: runtime_registry_ok, runtime_sync_ok, runtime_binary_ok | s03 | `rg '_check_runtime_registry_valid\|_check_runtime_sync_drift\|_check_runtime_binary_ok' loop/incidents/doctor.py` |
| FR-006: board_sync/cli.py + loop_argv.py — runtime choices from registry | s04 | `.venv/bin/pytest loop/tests/test_board_launch_cli.py -q -k codex` |
| FR-007: bin/hub-link AGENTS stub — harness + codex | s05 | `rg 'harness\|EPIC_RUNTIME' bin/hub-link` |
| FR-008: memory-bank/architecture/services.md — S-HUB-RUNTIME-SYNC row | s05 | `rg 'S-HUB-RUNTIME-SYNC' memory-bank/architecture/services.md` |
| FR-009: pytest: doctor runtime checks with mocks | s06 | `.venv/bin/pytest loop/tests/test_doctor_runtime.py -q --tb=line` |
| AC+ #1: README runtime table includes codex loop + runbook link | s01 | `rg 'codex-loop-pilot' README.md` |
| AC+ #2: codex-loop-pilot.md exists with EPIC_RUNTIME=codex + runtime-sync steps | s02 | `rg 'EPIC_RUNTIME=codex' docs/runbooks/codex-loop-pilot.md` |
| AC+ #3: doctor --json includes runtime sync/registry diagnostics | s03 | `.venv/bin/python loop/context_loop.py doctor --format json \| python3 -c "import sys,json; d=json.load(sys.stdin); assert 'runtime_registry_valid' in [c['name'] for c in d['checklist']]"` |
| AC+ #4: board --runtime codex accepted | s04 | `.venv/bin/pytest loop/tests/test_board_launch_cli.py -q -k codex` |
| AC+ #5: test_doctor_runtime.py green | s06 | `.venv/bin/pytest loop/tests/test_doctor_runtime.py -q --tb=line` |
| AC− #1: Stale README «loop не запускает Codex» | s01 | `rg 'не запускает Codex' README.md; echo exit=$?` → empty |
| AC− #2: Doctor silent pass when runtime-sync drift on EPIC_RUNTIME=codex | s03 | `rg '_check_runtime_sync_drift' loop/incidents/doctor.py` |
| US-001: operator runbook codex loop | s02 | runbook steps exist |
| US-002: doctor preflight drift/missing binary | s03 | doctor --json reports codex status |
| US-003: README актуальная runtime matrix | s01 | README lists codex loop ✅ |
| US-004: board arm loop --runtime codex | s04 | board CLI accepts codex |
| TM-001: doctor runtime json | s06 | pytest test_doctor_runtime.py |
| TM-002: board codex runtime | s04+s06 | pytest test_board_launch_cli.py -k codex |
| TM-003: runbook exists | s06 | file path fixture |
| TM-004: README not stale | s06 | grep no «не запускает Codex» |

---

## Stages coverage

| Stage (plan §До DECOMPOSE) | sNN | Delta | Files changed |
|----------------------------|-----|-------|---------------|
| s01: README + WORKFLOW updates | s01 | edit README runtime table; edit WORKFLOW.md §Runtime registry | README.md, loop/WORKFLOW.md |
| s02: codex-loop-pilot runbook | s02 | new file docs/runbooks/codex-loop-pilot.md | codex-loop-pilot.md |
| s03: doctor runtime checks | s03 | add 3 _check_* functions + wire in run_doctor() | loop/incidents/doctor.py |
| s04: board launch registry runtime | s04 | extend choices codex; env_extra EPIC_RUNTIME | loop/board_sync/cli.py, loop/board_launch/loop_argv.py |
| s05: hub-link AGENTS stub + architecture row | s05 | edit bin/hub-link stub text; add services.md row | bin/hub-link, memory-bank/architecture/services.md |
| s06: tests + doc link audit | s06 | new test_doctor_runtime.py; doc assertions | loop/tests/test_doctor_runtime.py |

All plan stages map 1:1 to sNN steps. No stage dissolved into scaffolding.

---

## Outcome map

| User/system outcome | sNN |
|--------------------|-----|
| Operator can follow codex runbook without chat → headless loop | s02 |
| Doctor --json surfaces runtime drift before loop start, no silent pass | s03 |
| README accurately shows codex loop ✅ with runbook link; stale row removed | s01 |
| Board arm accepts --runtime codex; env_extra EPIC_RUNTIME forwarded | s04 |
| hub-link stamps harness/ + EPIC_RUNTIME into AGENTS.md on every product link | s05 |
| architecture/services.md traceable runtime-sync service row | s05 |
| pytest suite covers all doctor runtime checks with mocks | s06 |

---

## Replacement cleanup

| Устаревшее | Замена | Owner | Policy |
|-----------|--------|-------|--------|
| README строка «loop не запускает Codex» / ❌ codex loop | ✅ codex loop + runbook link | s01 | delete in-epic |
| hardcoded `choices=("dsh", "claude")` в board_sync/cli.py | `choices=("claude", "dsh", "codex")` | s04 | replace in-epic |

No greenfield stubs — both replacements have explicit delete/replace in their sNN.  
No legacy-fallback-purge needed: s04 replaces choices inline (no shim chain).

---

## ANALYZE deferred

ANALYZE deferred: no code exists to analyze (docs + new test file + small extension of doctor.py).  
Brownfield touchpoints: `loop/incidents/doctor.py` (extend), `loop/board_sync/cli.py` (choices), `loop/board_launch/loop_argv.py` (env_extra) — all small, targeted changes with measurable verify at each cp. No architectural risk warranting pre-implement ANALYZE gate.

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | README runtime table + WORKFLOW.md registry pointer · [yaml](s01-readme-workflow-updates.yaml) | BACK IMPLEMENT | completed |
| **s02** | codex-loop-pilot runbook — install/auth/sync/EPIC_RUNTIME=codex · [yaml](s02-codex-loop-pilot-runbook.yaml) | BACK IMPLEMENT | completed |
| **s03** | Doctor runtime checks: registry_valid, sync_drift, binary_codex · [yaml](s03-doctor-runtime-checks.yaml) | BACK IMPLEMENT | completed |
| **s04** | Board launch --runtime choices from registry (add codex) · [yaml](s04-board-launch-registry-runtime.yaml) | BACK IMPLEMENT | completed |
| **s05** | hub-link AGENTS.md stub + architecture services.md runtime-sync row · [yaml](s05-hub-link-agents-stub-arch-row.yaml) | BACK IMPLEMENT | completed |
| **s06** | Tests test_doctor_runtime.py + doc link audit · [yaml](s06-tests-doc-link-audit.yaml) | BACK IMPLEMENT | completed |
