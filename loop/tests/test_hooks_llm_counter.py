"""Tests for llm_fallback_used drift counter integration."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib import extract_verdict
from epic_lib import default_state, load_epic_state, save_epic_state
from llm_structured import VerdictExtract
from loop.schemas.state import DriftCounters


def test_drift_counters_llm_fallback_default_zero() -> None:
    counters = DriftCounters()
    assert counters.llm_fallback_used == 0


def test_schemas_state_llm_fallback_field(tmp_path: Path) -> None:
    st = default_state()
    assert st["drift_counters"]["llm_fallback_used"] == 0
    st["drift_counters"]["llm_fallback_used"] += 1
    save_epic_state(tmp_path, st)

    loaded = load_epic_state(tmp_path)
    assert loaded["drift_counters"]["llm_fallback_used"] == 1


def test_increment_llm_fallback_used_on_verdict_apply(tmp_path: Path) -> None:
    st = default_state()
    save_epic_state(tmp_path, st)

    mock_extract = VerdictExtract(verdict="PASS", confidence=0.9, rationale="ok")
    with patch("_lib.hooks_llm_enabled", return_value=True), patch(
        "llm_structured.run_verdict_extract", return_value=mock_extract
    ):
        v = extract_verdict("some text without verdict marker", agent_id="verify", cwd=tmp_path)
        assert v == "PASS"

    loaded = load_epic_state(tmp_path)
    assert loaded["drift_counters"]["llm_fallback_used"] == 1
