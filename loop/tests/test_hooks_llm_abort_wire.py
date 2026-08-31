"""Tests for classify_abort LLM fallback wire-in."""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from session_resilience import classify_abort
from llm_structured import AbortClassify


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


def test_abort_fatal_pattern_no_llm(monkeypatch: Any):
    """Known fatal pattern -> fatal without calling LLM even if flags are on."""
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_ABORT", "1")

    reason = "CLI error: invalid flag specified"
    with patch("llm_structured.run_abort_classify") as mock_runner:
        res = classify_abort(reason)
        assert res == "fatal"
        mock_runner.assert_not_called()


def test_abort_fallback_unknown_reason(monkeypatch: Any):
    """Unknown reason + flag on + mock -> reclassify via LLM."""
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_ABORT", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_MIN_CHARS", "10")

    reason = "Some cryptic failure line from process output" + (" " * 200)
    mock_llm_res = AbortClassify(
        kind="fatal",
        reason_short="fatal internal error",
        confidence=0.9,
    )

    with patch("llm_structured.run_abort_classify", return_value=mock_llm_res) as mock_runner:
        res = classify_abort(reason)
        assert res == "fatal"
        mock_runner.assert_called_once_with(reason, exit_code=None)


def test_abort_llm_fail_soft(monkeypatch: Any):
    """LLM exception -> transient (fail-soft fallback to regex result)."""
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_ABORT", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_MIN_CHARS", "10")

    reason = "Unknown error occurred during session execution" + (" " * 200)

    with patch("llm_structured.run_abort_classify", side_effect=RuntimeError("LLM unavailable")):
        res = classify_abort(reason)
        assert res == "transient"


def test_abort_skipped_when_disabled(monkeypatch: Any):
    """When LLM abort flag is off, regex transient is returned without LLM call."""
    reason = "Some unknown error line" + (" " * 200)
    with patch("llm_structured.run_abort_classify") as mock_runner:
        res = classify_abort(reason)
        assert res == "transient"
        mock_runner.assert_not_called()
