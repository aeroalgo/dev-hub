"""Consolidated fallback tests and golden fixtures for LLM hook fallbacks (T-HUB-023)."""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "llm_fallback"

from _lib import extract_verdict
from epic.core import extract_handoff_block
from llm_structured import AbortClassify, HandoffExtract, VerdictExtract, run_handoff_extract, run_verdict_extract
from session_resilience import classify_abort


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: Any):
    """Ensure HOOKS_LLM env flags are predictable."""
    for key in [
        "PROJECT_HOOKS_LLM_FALLBACK",
        "PROJECT_HOOKS_LLM_HANDOFF",
        "PROJECT_HOOKS_LLM_VERDICT",
        "PROJECT_HOOKS_LLM_ABORT",
        "PROJECT_HOOKS_LLM_MIN_CHARS",
        "PROJECT_HOOKS_LLM_CONFIDENCE",
        "PROJECT_HOOKS_LLM_TIMEOUT",
        "PROJECT_HOOKS_LLM_MODEL",
        "PROJECT_HOOKS_LLM_DEBUG",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_all_flags_off_zero_llm_calls():
    """SC-001: When all fallback flags are off, Agent.run is called 0 times for all hook operations."""
    text_handoff = (FIXTURES_DIR / "handoff_malformed.md").read_text()
    text_verdict = (FIXTURES_DIR / "verdict_buried.txt").read_text()
    text_abort = (FIXTURES_DIR / "abort_unknown.txt").read_text()

    with patch("llm_structured.make_hooks_extract_agent") as mock_agent_builder:
        res_handoff = extract_handoff_block(text_handoff)
        res_verdict = extract_verdict(text_verdict, agent_id="verify")
        res_abort = classify_abort(text_abort)

        assert res_handoff == ""
        assert res_verdict is None
        assert res_abort == "transient"
        mock_agent_builder.assert_not_called()


def test_handoff_fallback_recovers_malformed(monkeypatch: Any):
    """SC-002: Recover malformed handoff doc via LLM fallback using fixture."""
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_HANDOFF", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_MIN_CHARS", "10")

    malformed_text = (FIXTURES_DIR / "handoff_malformed.md").read_text() + (" " * 100)

    extracted_handoff = HandoffExtract(
        handoff_md="## Handoff\n- **Эпик:** T-HUB-023\n- **Режим/шаг:** BACK IMPLEMENT s08",
        load_now_paths=[],
        phase="BACK IMPLEMENT",
        confidence=0.95,
    )

    mock_res = MagicMock()
    mock_res.data = extracted_handoff
    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(return_value=mock_res)

    with patch("llm_structured.make_hooks_extract_agent", return_value=mock_agent):
        res = extract_handoff_block(malformed_text)
        assert res == "## Handoff\n- **Эпик:** T-HUB-023\n- **Режим/шаг:** BACK IMPLEMENT s08"
        mock_agent.run.assert_called_once()


def test_verdict_fallback_buried_pass(monkeypatch: Any):
    """SC-003: Recover buried PASS verdict via LLM fallback using fixture."""
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_VERDICT", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_MIN_CHARS", "10")

    buried_text = (FIXTURES_DIR / "verdict_buried.txt").read_text() + (" " * 100)

    mock_extract = VerdictExtract(
        verdict="PASS",
        confidence=0.92,
        reasoning="VERDICT: PASS found in log body",
    )

    mock_res = MagicMock()
    mock_res.data = mock_extract
    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(return_value=mock_res)

    with patch("llm_structured.make_hooks_extract_agent", return_value=mock_agent):
        res = extract_verdict(buried_text, agent_id="verify")
        assert res == "PASS"
        mock_agent.run.assert_called_once()


def test_abort_fallback_unknown_reason(monkeypatch: Any):
    """SC-004 / FR-008: Unknown process crash reclassified via LLM fallback using fixture."""
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_ABORT", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_MIN_CHARS", "10")

    unknown_abort_text = (FIXTURES_DIR / "abort_unknown.txt").read_text() + (" " * 100)

    mock_extract = AbortClassify(
        kind="fatal",
        reason_short="state machine collision",
        confidence=0.88,
    )

    mock_res = MagicMock()
    mock_res.data = mock_extract
    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(return_value=mock_res)

    with patch("llm_structured.make_hooks_extract_agent", return_value=mock_agent):
        res = classify_abort(unknown_abort_text)
        assert res == "fatal"
        mock_agent.run.assert_called_once()


def test_confidence_gate_rejects_low_confidence(monkeypatch: Any):
    """Low confidence output is rejected by LLM runner."""
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_VERDICT", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_CONFIDENCE", "0.8")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_MIN_CHARS", "10")

    sample_text = "Uncertain output line" + (" " * 100)
    low_conf = VerdictExtract(verdict="PASS", confidence=0.5)

    mock_res = MagicMock()
    mock_res.data = low_conf
    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(return_value=mock_res)

    with patch("llm_structured.make_hooks_extract_agent", return_value=mock_agent):
        res = run_verdict_extract(sample_text)
        assert res is None
        mock_agent.run.assert_called_once()


def test_extract_verdict_regex_only_no_llm():
    """Clear regex match returns verdict immediately without calling LLM agent."""
    text = "Everything looks good\nVERDICT: PASS\nDone."

    with patch("llm_structured.make_hooks_extract_agent") as mock_agent_builder:
        res = extract_verdict(text, agent_id="verify")
        assert res == "PASS"
        mock_agent_builder.assert_not_called()
