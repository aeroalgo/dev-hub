"""Drift counters + extract_verdict (JSON/sidecar only, no LLM counter)."""

from __future__ import annotations

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib import extract_verdict
from epic_lib import default_state, load_epic_state, save_epic_state
from loop.schemas.state import DriftCounters


def test_drift_counters_defaults() -> None:
    counters = DriftCounters()
    assert counters.gate_verdict_regex_fallback == 0
    assert counters.schema_invalid == 0


def test_schemas_state_drift_counters_roundtrip(tmp_path: Path) -> None:
    st = default_state()
    assert st["drift_counters"]["gate_verdict_regex_fallback"] == 0
    st["drift_counters"]["gate_verdict_regex_fallback"] += 1
    save_epic_state(tmp_path, st)

    loaded = load_epic_state(tmp_path)
    assert loaded["drift_counters"]["gate_verdict_regex_fallback"] == 1


def test_extract_verdict_no_llm_on_ambiguous_text(tmp_path: Path) -> None:
    st = default_state()
    save_epic_state(tmp_path, st)
    v = extract_verdict(
        "some text without verdict marker", agent_id="verify", cwd=str(tmp_path)
    )
    assert v is None
    loaded = load_epic_state(tmp_path)
    assert loaded["drift_counters"]["gate_verdict_regex_fallback"] == 0
