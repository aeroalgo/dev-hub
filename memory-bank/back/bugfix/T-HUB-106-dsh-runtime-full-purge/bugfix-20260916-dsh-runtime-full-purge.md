# Bugfix: DSH Runtime Full Purge Test Suite Alignment
**Epic ID:** T-HUB-106-dsh-runtime-full-purge  
**Date:** 2026-09-16  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-106-dsh-runtime-full-purge/qa-20260916-dsh-runtime-full-purge.yaml
---
## 1. QA Root Cause Analysis
During full test suite execution in BACK QA (`bin/pytest -q --tb=line`), 20 test failures and 3 collection errors occurred across 10 test modules:
- `loop/tests/test_runner_cli.py::TestPathAndConfigResolution::test_load_project_environment_dsh_bridge` (BF-001)
- `loop/tests/test_stack_profile_instruction_inventory.py` (BF-002, BF-003)
- `loop/tests/test_session_wrapper.py::test_heartbeat_reports_last_dsh_activity` (BF-004)
- `loop/tests/test_runtime_sync_check.py` (BF-005, BF-006, BF-007)
- `harness/hooks/tests/test_session_start_inject.py::test_unknown_epic_runtime_fail_closed_or_documented` (BF-008)
- `loop/tests/test_board_launch_cli.py::test_runtime_flag` (BF-009)
- `loop/tests/test_phase_verify_gates.py::test_tm009_dsh_preset_files_map` (BF-010)
- `loop/tests/test_codex_hooks_bridge.py::test_claude_settings_snapshot_unchanged_after_sync` (BF-011)
- `harness/hooks/tests/test_hook_registration_consolidation.py` (BF-012, BF-013, BF-014, BF-015)
- `loop/tests/test_context_contract_materialization.py` (BF-016, BF-017)
- `loop/tests/test_hub_link_harness.py::test_product_settings_hook_paths_resolve` (BF-018)
- `loop/tests/test_runtime_adapter_protocol.py::test_session_analysis_fields` (BF-019)
- `tests/test_cc_hooks_bridge_config.py` (BF-020, BF-021, BF-022, BF-023)

**Root Cause:**
1. **Obsolete DSH-only test assertions and fixtures:** Tests explicitly checking for `DSH.md`, `dsh/presets/`, `dsh/patches/`, `DSH_HOOKS_BRIDGE`, and `dsh_abort_kind` failed after DSH runtime purge.
2. **Old hook entries in settings.json:** `.claude/settings.json` and `harness/claude/settings.harness.json` retained legacy individual hook entries instead of canonical 7 event dispatchers.
3. **Runtime-sync materialization drift:** Manifest and hooks metadata needed sync via `bin/runtime-sync --apply --runtime all`.
4. **Unknown runtime fail-closed contract:** `test_session_start_inject.py` tested old soft fallback instead of strict fail-closed `ValueError("unsupported runtime")`.

---
## 2. Changes Implemented (AC+)
- **Runner CLI tests (`loop/tests/test_runner_cli.py`):** Replaced obsolete DSH bridge test with codex project environment test.
- **Instruction inventory tests (`loop/tests/test_stack_profile_instruction_inventory.py`):** Removed deleted `DSH.md` from active entrypoints lists.
- **Session wrapper tests (`loop/tests/test_session_wrapper.py`):** Removed obsolete DSH heartbeat activity test.
- **Runtime sync & Codex bridge:** Re-materialized via `bin/runtime-sync --apply --runtime all`.
- **Session start inject tests (`harness/hooks/tests/test_session_start_inject.py`):** Updated to expect `pytest.raises(ValueError, match="unsupported runtime")`.
- **Board launch CLI tests (`loop/tests/test_board_launch_cli.py`):** Changed tested runtime flag from `dsh` to `codex`.
- **Phase verify gates tests (`loop/tests/test_phase_verify_gates.py`):** Removed obsolete DSH preset checks.
- **Hook registration & settings (`.claude/settings.json`, `harness/claude/settings.harness.json`):** Cleaned up to canonical 7 event dispatchers.
- **Context contract tests (`loop/tests/test_context_contract_materialization.py`):** Removed deleted `DSH.md` from tested files.
- **Runtime adapter protocol tests (`loop/tests/test_runtime_adapter_protocol.py`):** Removed purged `dsh_abort_kind` parameter.
- **BF-020–BF-023 evidence:** file deleted: `tests/test_cc_hooks_bridge_config.py`.
- **Bugfix queue:** All 23 items marked `done`; verification status updated to `pass`.

---
## 3. Non-Goals / Fallback Purge (AC−)
- No DSH runtime or bridges restored.
- No loose exception masks added.
- All test suites verify strictly against supported runtimes (`claude` and `codex`).

---
## 4. Integration Rule Counterparts (§0.11)
- **API / Protocol:** Runtime adapter protocol and session analysis verified.
- **Environment variables:** `EPIC_LOOP`, `EPIC_RUNTIME`, and runtime configs validated.
- **Storage & State:** `bugfix-queue.yaml` and bugfix prose report updated.
- **Materializers:** Zero drift confirmed via `bin/runtime-sync --check`.

---
## 5. Blockers Resolved
- BF-001 through BF-023: All 23 items resolved and verified PASS.

---
## 6. Verification
- Targeted checks for all touched test modules: PASS.
- Full repository test suite (`verification.command`):
  ```bash
  bin/pytest -q --tb=line
  ```
  Result: 3009 passed, 4 skipped in 105.06s.
