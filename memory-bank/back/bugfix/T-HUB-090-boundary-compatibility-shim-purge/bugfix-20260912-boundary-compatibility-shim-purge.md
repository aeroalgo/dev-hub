# Bugfix: Boundary Compatibility Shim Purge Suite Alignment
**Epic ID:** T-HUB-090-boundary-compatibility-shim-purge  
**Date:** 2026-09-12  
**Author:** BACK BUGFIX  
**Source:** memory-bank/back/qa/T-HUB-090-boundary-compatibility-shim-purge/qa-20260912-boundary-compatibility-shim-purge.yaml

---

## 1. QA Root Cause Analysis
During full test suite execution in BACK QA (`bin/pytest -q --tb=line`), 8 suite tests failed:
- `loop/tests/test_context_loop.py::test_status_agent_policy_active_loop_agents`
- `loop/tests/test_agent_hooks.py::test_active_overlay_contains_protocol`
- `loop/tests/test_agent_hooks.py::test_spawn_map_legacy_agents_preserves_text`
- `loop/tests/test_stop_gate.py::test_stop_gate_gate_bypass_chat`
- `loop/tests/test_stop_gate.py::test_stop_gate_gate_bypass_explicit`
- `loop/tests/test_stop_gate.py::test_stop_gate_gate_fail_closed`
- `loop/tests/test_stop_gate.py::test_stop_gate_optional_no_gate`
- `loop/tests/test_stop_gate.py::test_stop_gate_decompose_finish_blocked_without_verify_pass`

**Root Cause:**
Following the purge of `_LEGACY_OVERLAYS` (hardcoded agent defaults for `explorer`, `reviewer`, `verify`, `sunset-inventory`), agent frontmatter in `.claude/agents/*.md` must explicitly define `overlay:` metadata (e.g. `managed: true`, `mode: gate`/`search`, `requires_model: true`/`false`, `default_loop: true`, `verdict: pass-fail`). Obsolete test fixtures in `test_context_loop.py`, `test_agent_hooks.py`, and `test_stop_gate.py` created mock `.claude/agents/*.md` files with bare `name: <agent>` frontmatter without `overlay:`, causing them to resolve as unmanaged agents in accordance with the new strict frontmatter metadata contract.

---

## 2. Changes Implemented (AC+)
- `loop/tests/test_context_loop.py`: Updated `test_status_agent_policy_active_loop_agents` fixture to include canonical `overlay:` frontmatter metadata for `explorer`, `reviewer`, and `verify`.
- `loop/tests/test_agent_hooks.py`: Updated `test_active_overlay_contains_protocol` and `test_spawn_map_legacy_agents_preserves_text` to write explicit `overlay:` frontmatter metadata for `verify`, `reviewer`, and `explorer`.
- `loop/tests/test_stop_gate.py`: Updated `_write_gate_fixture` to write explicit `overlay:` frontmatter metadata for `verify` (`mode: gate`, `managed: true`, `requires_model: true`, `default_loop: true`, `verdict: pass-fail`).
- `memory-bank/back/bugfix/T-HUB-090-boundary-compatibility-shim-purge/bugfix-queue.yaml`: All 8 queue items (`BF-001` through `BF-008`) resolved to `done`; full suite verification executed and marked `pass` (2834 passed, 4 skipped).

---

## 3. Non-Goals / Fallback Purge (AC−)
- No restoration of hardcoded `_LEGACY_OVERLAYS` dictionary or fallback maps in `harness/hooks/agent_registry.py`.
- Strict frontmatter parsing preserved without silent fallback.
- No modifications outside the targeted test suite fixtures.

---

## 4. Integration Rule Counterparts (§0.11)
External refs and system counterparts verified against orphaned references:
- **API / Protocol:** `AgentOverlay` schema and overlay frontmatter fields (`managed`, `mode`, `requires_model`, `default_loop`, `default_chat`, `verdict`) across `.claude/agents/*.md` definitions.
- **Environment variables:** `EPIC_LOOP`, `PROJECT_AGENT_VERIFY_MODEL`, `PROJECT_AGENT_REVIEWER_MODEL`, `PROJECT_AGENT_EXPLORER_MODEL` correctly parsed in agent policy.
- **Storage & State:** `memory-bank/back/bugfix/T-HUB-090-boundary-compatibility-shim-purge/bugfix-queue.yaml`, `.claude/runtime/spawn-gate/<session_id>.json`.
- **Events & Loggers:** Hook diagnostics and registry errors recorded without schema drift.
- **Database / Registry:** Agent registry loader in `harness/hooks/agent_registry.py` and materializers in `loop/runtime_materializers/`.
- **Orphan check:** Zero phantom paths or dangling references introduced.

---

## 5. Blockers Resolved
- BF-001: `loop/tests/test_context_loop.py::test_status_agent_policy_active_loop_agents` — PASS
- BF-002: `loop/tests/test_agent_hooks.py::test_active_overlay_contains_protocol` — PASS
- BF-003: `loop/tests/test_agent_hooks.py::test_spawn_map_legacy_agents_preserves_text` — PASS
- BF-004: `loop/tests/test_stop_gate.py::test_stop_gate_gate_bypass_chat` — PASS
- BF-005: `loop/tests/test_stop_gate.py::test_stop_gate_gate_bypass_explicit` — PASS
- BF-006: `loop/tests/test_stop_gate.py::test_stop_gate_gate_fail_closed` — PASS
- BF-007: `loop/tests/test_stop_gate.py::test_stop_gate_optional_no_gate` — PASS
- BF-008: `loop/tests/test_stop_gate.py::test_stop_gate_decompose_finish_blocked_without_verify_pass` — PASS

---

## 6. Verification
- Targeted item checks:
  ```bash
  bin/pytest loop/tests/test_context_loop.py -q --tb=line
  bin/pytest loop/tests/test_agent_hooks.py -q --tb=line
  bin/pytest loop/tests/test_stop_gate.py -q --tb=line
  ```
- Combined targeted suite:
  ```bash
  bin/pytest loop/tests/test_context_loop.py loop/tests/test_agent_hooks.py loop/tests/test_stop_gate.py -q
  ```
  Result: 161 passed.
- Full repository test suite (`verification.command`):
  ```bash
  bin/pytest -q --tb=line
  ```
  Result: 2834 passed, 4 skipped in 96.35s.
