"""Audit tests verifying zero LLM calls on happy path and flags-off regression."""

import sys
from pathlib import Path
from unittest.mock import patch
import pytest

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib import extract_verdict
from epic.core import extract_handoff_block


def test_happy_path_verdict_regex_no_llm():
    """Verify regex verdict parsing does not invoke LLM extract runner."""
    golden_text = "Some output\nVERDICT: PASS\nAdditional text"
    with patch("llm_structured.run_verdict_extract") as mock_llm:
        verdict = extract_verdict(golden_text, agent_id="verify")
        assert verdict == "PASS"
        mock_llm.assert_not_called()


def test_happy_path_verdict_sidecar_no_llm():
    """Verify sidecar verdict file does not invoke LLM extract runner."""
    golden_text = "VERDICT: PASS"
    with patch("llm_structured.run_verdict_extract") as mock_llm:
        verdict = extract_verdict(golden_text, agent_id="verify")
        assert verdict == "PASS"
        mock_llm.assert_not_called()


def test_happy_path_handoff_no_llm():
    """Verify regex handoff block parsing does not invoke LLM extract runner."""
    golden_text = "## Handoff\n- **Эпик:** T-HUB-023\n- **Режим/шаг:** s10"
    with patch("llm_structured.run_handoff_extract") as mock_llm:
        handoff = extract_handoff_block(golden_text)
        assert "## Handoff" in handoff
        mock_llm.assert_not_called()


def test_agent_hooks_regression_flags_off(monkeypatch):
    """Verify agent hooks / fallback behavior with LLM flags turned off."""
    monkeypatch.setenv("PROJECT_HOOKS_LLM_VERDICT", "0")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_HANDOFF", "0")

    golden_text = "VERDICT: PASS"
    with patch("llm_structured.run_verdict_extract") as mock_llm:
        verdict = extract_verdict(golden_text, agent_id="verify")
        assert verdict == "PASS"
        mock_llm.assert_not_called()

    ambiguous_text = "I think it passes overall."
    with patch("llm_structured.run_verdict_extract") as mock_llm:
        verdict = extract_verdict(ambiguous_text, agent_id="verify")
        assert verdict is None
        mock_llm.assert_not_called()
