"""Fallback / extract_verdict tests (machine SoT = JSON fence)."""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "llm_fallback"

from _lib import extract_verdict
from epic.core import extract_handoff_block
from session_resilience import classify_abort


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: Any):
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
    text_handoff = (FIXTURES_DIR / "handoff_malformed.md").read_text()
    text_verdict = (FIXTURES_DIR / "verdict_buried.txt").read_text()
    text_abort = (FIXTURES_DIR / "abort_unknown.txt").read_text()

    with patch("llm_structured.make_gate_agent") as mock_agent_builder:
        res_handoff = extract_handoff_block(text_handoff)
        res_verdict = extract_verdict(text_verdict, agent_id="verify")
        res_abort = classify_abort(text_abort)

        assert res_handoff == ""
        assert res_verdict is None
        assert res_abort == "transient"
        mock_agent_builder.assert_not_called()


def test_verdict_buried_prose_not_machine():
    buried_text = (FIXTURES_DIR / "verdict_buried.txt").read_text() + (" " * 100)
    with patch("llm_structured.make_gate_agent") as mock_agent_builder:
        assert extract_verdict(buried_text, agent_id="verify") is None
        mock_agent_builder.assert_not_called()

    fenced = (
        buried_text
        + '\n```json\n{"schema":"loop-gate-verdict/v1","agent_id":"verify",'
        '"verdict":"PASS","recorded_at":"2026-08-31T00:00:00Z"}\n```\n'
    )
    with patch("llm_structured.make_gate_agent") as mock_agent_builder:
        assert extract_verdict(fenced, agent_id="verify") == "PASS"
        mock_agent_builder.assert_not_called()


def test_extract_verdict_json_fence_only_no_llm():
    text = (
        "Everything looks good\n"
        '```json\n{"schema":"loop-gate-verdict/v1","agent_id":"verify",'
        '"verdict":"PASS","recorded_at":"2026-08-31T00:00:00Z"}\n```\n'
        "Done."
    )
    with patch("llm_structured.make_gate_agent") as mock_agent_builder:
        assert extract_verdict(text, agent_id="verify") == "PASS"
        mock_agent_builder.assert_not_called()
