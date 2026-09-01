"""Audit tests: extract_verdict machine SoT = JSON fence (no LLM)."""

import sys
from pathlib import Path
from unittest.mock import patch

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib import extract_verdict
from epic.core import extract_handoff_block


def _fence(verdict: str = "PASS") -> str:
    return (
        "Some output\n"
        "```json\n"
        f'{{"schema":"loop-gate-verdict/v1","agent_id":"verify",'
        f'"verdict":"{verdict}","recorded_at":"2026-08-31T12:00:00Z"}}\n'
        "```\n"
        "Additional text"
    )


def test_happy_path_verdict_json_fence_no_llm():
    with patch("llm_structured.make_gate_agent") as mock_llm:
        verdict = extract_verdict(_fence("PASS"), agent_id="verify")
        assert verdict == "PASS"
        mock_llm.assert_not_called()


def test_happy_path_verdict_prose_not_machine():
    with patch("llm_structured.make_gate_agent") as mock_llm:
        assert extract_verdict("VERDICT: PASS", agent_id="verify") is None
        mock_llm.assert_not_called()


def test_happy_path_handoff_no_llm():
    golden_text = "## Handoff\n- **Эпик:** T-HUB-023\n- **Режим/шаг:** s10"
    with patch("llm_structured.make_gate_agent") as mock_llm:
        handoff = extract_handoff_block(golden_text)
        assert "## Handoff" in handoff
        mock_llm.assert_not_called()


def test_agent_hooks_regression_flags_off(monkeypatch):
    monkeypatch.setenv("PROJECT_HOOKS_LLM_VERDICT", "0")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_HANDOFF", "0")

    with patch("llm_structured.make_gate_agent") as mock_llm:
        assert extract_verdict(_fence("PASS"), agent_id="verify") == "PASS"
        mock_llm.assert_not_called()

    with patch("llm_structured.make_gate_agent") as mock_llm:
        assert extract_verdict("I think it passes overall.", agent_id="verify") is None
        mock_llm.assert_not_called()
