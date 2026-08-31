"""Tests for centralized extract chain wire-in for Handoff LLM fallback in core.py."""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from epic.core import extract_handoff_block, extract_handoff_block_llm_fallback
from llm_structured import HandoffExtract


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


def test_handoff_regex_unchanged_flags_off():
    """Golden regex input unchanged when flags off."""
    text = "## Handoff\n- **Эпик:** T-HUB-023\n- **Режим/шаг:** BACK IMPLEMENT s04"
    with patch("llm_structured.run_handoff_extract") as mock_runner:
        res = extract_handoff_block(text)
        assert res == "## Handoff\n- **Эпик:** T-HUB-023\n- **Режим/шаг:** BACK IMPLEMENT s04"
        mock_runner.assert_not_called()


def test_extract_handoff_block_skips_llm_when_regex_hits(monkeypatch: Any):
    """When regex finds ## Handoff, LLM fallback is skipped even when enabled."""
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_HANDOFF", "1")

    text = "Some intro\n## Handoff\n- **Эпик:** T-HUB-023\n## Next section"
    with patch("llm_structured.run_handoff_extract") as mock_runner:
        res = extract_handoff_block(text)
        assert res == "## Handoff\n- **Эпик:** T-HUB-023"
        mock_runner.assert_not_called()


def test_handoff_llm_fallback_recovers(monkeypatch: Any):
    """Mock LLM: malformed prose without ## Handoff heading → non-empty handoff when flags on."""
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_HANDOFF", "1")

    malformed_text = "Here is the summary of work done: Epic T-HUB-023, step s04. Next mode is BACK QA." + (" " * 200)

    extracted_handoff = HandoffExtract(
        handoff_md="## Handoff\n- **Эпик:** T-HUB-023\n- **Режим/шаг:** BACK QA",
        load_now_paths=[],
        phase="BACK QA",
        confidence=0.9,
    )

    with patch("llm_structured.run_handoff_extract", return_value=extracted_handoff):
        res = extract_handoff_block(malformed_text)
        assert res == "## Handoff\n- **Эпик:** T-HUB-023\n- **Режим/шаг:** BACK QA"
