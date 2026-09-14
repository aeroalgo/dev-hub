# Bugfix: Runtime Import Sole Path Suite Alignment
**Epic ID:** T-HUB-095-epic-runtime-import-sole-path  
**Date:** 2026-09-14  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-095-epic-runtime-import-sole-path/qa.yaml

---

## 1. QA Root Cause Analysis
During full test suite execution in BACK QA (`bin/pytest -q --tb=line`), 3 suite tests failed:
- `loop/tests/test_workflow_pack_phase_router.py::test_tm_004_arm_phase_dsh_video_pack`
- `loop/tests/test_runtime_sync_check.py::test_runtime_sync_cli_check_full_set_succeeds`
- `loop/tests/test_codex_hooks_bridge.py::test_claude_settings_snapshot_unchanged_after_sync`

**Root Cause:**
1. **Mock target desync in `test_workflow_pack_phase_router.py` (BF-001):** Following the sole-path runtime import refactoring, `arm_phase` dispatches to `loop.epic_transition.arm_epic`. The test was monkeypatching `"epic.core.arm_epic"`, causing `arm_phase` to fall through to real `arm_epic` which failed with `ValueError: Unknown role dir 'script'`.
2. **Codex agent materialization drift (BF-002, BF-003):** Edits to `harness/agents/verify-implement.md` (updating imports to sole path) required materialization sync for `.codex/agents/verify-implement.toml` and `.codex/agents/verify-implement.policy.json`. Running `bin/runtime-sync --apply --runtime codex` brought materialized artifacts into parity.

---

## 2. Changes Implemented (AC+)
- `loop/tests/test_workflow_pack_phase_router.py`: Updated `monkeypatch.setattr` target in `test_tm_004_arm_phase_dsh_video_pack` to `"loop.epic_transition.arm_epic"`.
- `.codex/agents/verify-implement.toml` & `.codex/agents/verify-implement.policy.json`: Re-materialized via `bin/runtime-sync --apply --runtime codex`.
- `memory-bank/back/bugfix/T-HUB-095-epic-runtime-import-sole-path/bugfix-queue.yaml`: Updated items `BF-001`, `BF-002`, `BF-003` to `done`; full suite verification executed and marked `pass` (2887 passed, 4 skipped).

---

## 3. Non-Goals / Fallback Purge (AC−)
- No dual import paths restored; single import path architecture preserved.
- No loose/unhandled exception masks added.
- No changes outside the targeted test and materialized agent files.

---

## 4. Integration Rule Counterparts (§0.11)
External refs and system counterparts verified against orphaned references:
- **API / Protocol:** `WorkflowPack` registry and `arm_phase` transition contracts verified.
- **Environment variables:** `EPIC_LOOP` and runtime configs validated.
- **Storage & State:** `memory-bank/back/bugfix/T-HUB-095-epic-runtime-import-sole-path/bugfix-queue.yaml`.
- **Materializers:** Parity check validated across codex runtime configurations (`bin/runtime-sync --check`).
- **Orphan check:** Zero dangling references or orphan paths introduced.

---

## 5. Blockers Resolved
- BF-001: `loop/tests/test_workflow_pack_phase_router.py::test_tm_004_arm_phase_dsh_video_pack` — PASS
- BF-002: `loop/tests/test_runtime_sync_check.py::test_runtime_sync_cli_check_full_set_succeeds` — PASS
- BF-003: `loop/tests/test_codex_hooks_bridge.py::test_claude_settings_snapshot_unchanged_after_sync` — PASS

---

## 6. Verification
- Targeted item checks:
  ```bash
  bin/pytest loop/tests/test_workflow_pack_phase_router.py -q --tb=line
  bin/pytest loop/tests/test_runtime_sync_check.py -q --tb=line
  bin/pytest loop/tests/test_codex_hooks_bridge.py -q --tb=line
  ```
- Full repository test suite (`verification.command`):
  ```bash
  bin/pytest -q --tb=line
  ```
  Result: 2887 passed, 4 skipped in 98.07s.
