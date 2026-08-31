"""Tests for LLM runners in llm_structured.py."""

import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from llm_structured import (
    AbortClassify,
    HandoffExtract,
    VerdictExtract,
    run_abort_classify,
    run_handoff_extract,
    run_verdict_extract,
)


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


def test_runners_no_call_when_disabled(monkeypatch: Any):
    """When HOOKS_LLM flags are off (default), runners return None without Agent.run."""
    sample = "x" * 300
    with patch("llm_structured.make_hooks_extract_agent") as mock_make:
        assert run_handoff_extract(sample) is None
        assert run_verdict_extract(sample) is None
        assert run_abort_classify(sample) is None
        mock_make.assert_not_called()


def test_runners_skip_below_min_chars(monkeypatch: Any):
    """When input is shorter than MIN_CHARS, return None without network/Agent call."""
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_HANDOFF", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_VERDICT", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_ABORT", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_MIN_CHARS", "200")

    short_sample = "Short text under 200 chars"
    with patch("llm_structured.make_hooks_extract_agent") as mock_make:
        assert run_handoff_extract(short_sample) is None
        assert run_verdict_extract(short_sample) is None
        assert run_abort_classify(short_sample) is None
        mock_make.assert_not_called()


def test_runners_fail_soft_on_exception(monkeypatch: Any):
    """When Agent raises exception, return None without crashing (fail-soft)."""
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_HANDOFF", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_VERDICT", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_ABORT", "1")

    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(side_effect=RuntimeError("API error"))

    sample = "A" * 250
    with patch("llm_structured.make_hooks_extract_agent", return_value=mock_agent):
        assert run_handoff_extract(sample) is None
        assert run_verdict_extract(sample) is None
        assert run_abort_classify(sample) is None


def test_run_handoff_extract_mock_success(monkeypatch: Any):
    """Successful extraction of handoff return HandoffExtract if confidence ok."""
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_HANDOFF", "1")

    expected = HandoffExtract(
        handoff_md="## Handoff\n- info",
        load_now_paths=["path/a"],
        phase="BACK IMPLEMENT",
        confidence=0.9,
    )
    mock_res = MagicMock()
    mock_res.data = expected

    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(return_value=mock_res)

    sample = "B" * 250
    with patch("llm_structured.make_hooks_extract_agent", return_value=mock_agent):
        res = run_handoff_extract(sample)
        assert res == expected


def test_run_verdict_extract_low_confidence_returns_none(monkeypatch: Any):
    """If confidence is below threshold, return None."""
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_VERDICT", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_CONFIDENCE", "0.8")

    low_conf = VerdictExtract(verdict="PASS", confidence=0.6)
    mock_res = MagicMock()
    mock_res.data = low_conf

    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(return_value=mock_res)

    sample = "C" * 250
    with patch("llm_structured.make_hooks_extract_agent", return_value=mock_agent):
        res = run_verdict_extract(sample)
        assert res is None


def test_run_abort_classify_mock_fatal(monkeypatch: Any):
    """Successful abort classification returns AbortClassify."""
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_ABORT", "1")

    expected = AbortClassify(kind="fatal", reason_short="context limit", confidence=0.95)
    mock_res = MagicMock()
    mock_res.data = expected

    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(return_value=mock_res)

    sample = "D" * 250
    with patch("llm_structured.make_hooks_extract_agent", return_value=mock_agent):
        res = run_abort_classify(sample)
        assert res == expected
