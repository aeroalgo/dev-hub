from __future__ import annotations

import pytest
from pathlib import Path

from harness.hooks.session_resilience import analyze_session_log
from loop.runtime_adapters.common import get_adapter_for_runtime
from loop.runtime_adapters.base import RuntimeAdapter
from loop.runtime_adapters.claude import ClaudeAdapter
from loop.runtime_adapters.dsh import DshAdapter


def test_common_get_adapter_for_runtime_factory():
    claude_adapter = get_adapter_for_runtime("claude")
    assert isinstance(claude_adapter, RuntimeAdapter)
    assert isinstance(claude_adapter, ClaudeAdapter)

    dsh_adapter = get_adapter_for_runtime("dsh")
    assert isinstance(dsh_adapter, RuntimeAdapter)
    assert isinstance(dsh_adapter, DshAdapter)

    with pytest.raises(ValueError, match="Unknown runtime"):
        get_adapter_for_runtime("nonexistent_runtime_xyz")


def test_session_resilience_claude_clean_exit_no_reason(tmp_path: Path):
    log_file = tmp_path / "session.log"
    log_file.write_text('{"type": "result", "subtype": "success"}\n', encoding="utf-8")

    analysis = analyze_session_log(log_file, exit_code=0, runtime="claude")

    assert analysis["outcome"] == "clean"
    assert analysis["aborted"] is False
    assert analysis["reason"] is None
    assert analysis["retryable"] is False
    assert analysis["abort_kind"] is None


def test_session_resilience_dsh_mismatch_sets_reason(tmp_path: Path):
    log_file = tmp_path / "session.log"
    log_file.write_text(
        '{"requested_model": "claude-3-5-sonnet", "actual_model": "claude-3-haiku"}\n',
        encoding="utf-8",
    )

    analysis = analyze_session_log(
        log_file,
        exit_code=0,
        expected_model="claude-3-5-sonnet",
        runtime="dsh",
    )

    assert analysis["outcome"] == "permanent_failure"
    assert analysis["aborted"] is True
    assert analysis["retryable"] is False
    assert analysis["abort_kind"] == "fatal"
    assert analysis["reason"] is not None
    assert "model_substitution" in analysis["reason"]


def test_session_resilience_delegates_to_adapter_not_is_dsh(tmp_path: Path):
    log_file = tmp_path / "session.log"
    log_file.write_text("API Error: 503 Service Unavailable\n", encoding="utf-8")

    analysis = analyze_session_log(log_file, exit_code=1, runtime="dsh")

    assert analysis["outcome"] == "transient_abort"
    assert analysis["aborted"] is True
    assert analysis["retryable"] is True
    assert analysis["abort_kind"] == "transient"
    assert analysis["reason"] is not None
    assert "dsh_transient" in analysis["reason"]
