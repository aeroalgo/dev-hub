"""Tests for drift counter increments and legacy repair env guard."""

import os
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from epic import (
    increment_drift_counter,
    load_epic_state,
    repair_index_mirror,
    repair_fingerprint_stall,
    repair_finish_desync,
)
from _lib import extract_verdict


def test_repair_index_mirror_increments_counter(tmp_path: Path):
    # Setup dummy decompose and state
    state = load_epic_state(tmp_path)
    assert state.get("drift_counters", {}).get("index_mirror_repair", 0) == 0

    # Execute repair_index_mirror on empty path to check counter increment
    repair_index_mirror(tmp_path, "back/plan/decompose-test/index.md")
    st = load_epic_state(tmp_path)
    drift = st.get("drift_counters", {})
    if isinstance(drift, dict):
        assert drift.get("index_mirror_repair", 0) == 1
    else:
        assert getattr(drift, "index_mirror_repair", 0) == 1


def test_extract_verdict_json_fence_without_regex_fallback(tmp_path: Path):
    text = (
        '```json\n{"schema":"loop-gate-verdict/v1","agent_id":"verify",'
        '"verdict":"PASS","recorded_at":"2026-08-31T00:00:00Z"}\n```'
    )
    v = extract_verdict(text, cwd=str(tmp_path), agent_id="verify")
    assert v == "PASS"
    # Prose VERDICT is not machine input (no cwd → no sidecar pollution)
    assert extract_verdict("VERDICT: PASS", agent_id="verify") is None


def test_repair_legacy_0_env_log_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PROJECT_LOOP_REPAIR_LEGACY", "0")
    # Call repair function with legacy=0, check behavior or warning log
    res = repair_index_mirror(tmp_path, "back/plan/decompose-test/index.md")
    assert res.get("ok") is False or res.get("warning") or res.get("skipped_legacy")
