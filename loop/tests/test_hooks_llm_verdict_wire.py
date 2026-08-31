"""Tests for extract_verdict LLM fallback wire-in."""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib import extract_verdict
from llm_structured import VerdictExtract


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
    ]:
        monkeypatch.delenv(key, raising=False)


def test_extract_verdict_regex_only_no_llm():
    """When flags are off, regex returns verdict and LLM runner is not called."""
    text = "Some logs here\nVERDICT: PASS\nAll done."
    with patch("llm_structured.run_verdict_extract") as mock_runner:
        res = extract_verdict(text)
        assert res == "PASS"
        mock_runner.assert_not_called()


def test_verdict_sidecar_skips_llm(monkeypatch: Any, tmp_path: Path):
    """When sidecar returns verdict, LLM fallback is skipped even if flags on and regex misses."""
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_VERDICT", "1")

    # Mock gate verdict store record
    fake_record = MagicMock()
    fake_record.verdict = "PASS"

    text = "No verdict line here in transcript" + (" " * 200)

    with patch("loop.gate_verdict_store.read_gate_verdict", return_value=fake_record):
        with patch("llm_structured.run_verdict_extract") as mock_runner:
            res = extract_verdict(text, cwd=str(tmp_path), agent_id="verify")
            assert res == "PASS"
            mock_runner.assert_not_called()


def test_verdict_fallback_buried_pass(monkeypatch: Any):
    """Buried VERDICT recovered with flag on via LLM fallback."""
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_VERDICT", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_MIN_CHARS", "10")

    text = "Verification summary: everything passed tests, all checks green." + (" " * 200)

    mock_extract = VerdictExtract(
        verdict="PASS",
        confidence=0.9,
        reasoning="Tests passed",
    )

    with patch("llm_structured.run_verdict_extract", return_value=mock_extract) as mock_runner:
        res = extract_verdict(text, agent_id="verify")
        assert res == "PASS"
        mock_runner.assert_called_once()


def test_verdict_llm_skipped_for_non_verify_agent(monkeypatch: Any):
    """LLM verdict extract skipped if agent_id is not verify or reviewer."""
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_VERDICT", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_MIN_CHARS", "10")

    text = "Some output without verdict" + (" " * 200)

    with patch("llm_structured.run_verdict_extract") as mock_runner:
        res = extract_verdict(text, agent_id="explorer")
        assert res is None
        mock_runner.assert_not_called()
