from __future__ import annotations
import pytest
from pathlib import Path
from harness.hooks.session_resilience import analyze_session_log
from loop.runtime_adapters.common import get_adapter_for_runtime
from loop.runtime_adapters.base import RuntimeAdapter
from loop.runtime_adapters.claude import ClaudeAdapter
from loop.runtime_adapters.codex import CodexAdapter


def test_common_get_adapter_for_runtime_factory():
    claude_adapter = get_adapter_for_runtime("claude")
    assert isinstance(claude_adapter, RuntimeAdapter)
    assert isinstance(claude_adapter, ClaudeAdapter)

    codex_adapter = get_adapter_for_runtime("codex")
    assert isinstance(codex_adapter, RuntimeAdapter)
    assert isinstance(codex_adapter, CodexAdapter)

    with pytest.raises(ValueError, match="Unknown runtime"):
        get_adapter_for_runtime("nonexistent_runtime_xyz")

    with pytest.raises(ValueError, match="Unknown runtime: dsh"):
        get_adapter_for_runtime("dsh")


def test_session_resilience_claude_clean_exit_no_reason(tmp_path: Path):
    log_file = tmp_path / "session.log"
    log_file.write_text("{\"type\": \"result\", \"subtype\": \"success\"}\n", encoding="utf-8")
    analysis = analyze_session_log(log_file, exit_code=0, runtime="claude")
    assert analysis["outcome"] == "clean"
    assert analysis["aborted"] is False
    assert analysis["reason"] is None
    assert analysis["retryable"] is False
    assert analysis["abort_kind"] is None


def test_session_resilience_claude_mismatch_sets_reason(tmp_path: Path):
    log_file = tmp_path / "session.log"
    log_file.write_text(
        "Model \"claude-3-5-sonnet\" is restricted by your organization's settings. Using claude-3-haiku instead\n",
        encoding="utf-8",
    )
    analysis = analyze_session_log(
        log_file,
        exit_code=0,
        expected_model="claude-3-5-sonnet",
        runtime="claude",
    )
    assert analysis["outcome"] == "permanent_failure"
    assert analysis["aborted"] is True
    assert analysis["retryable"] is False
    assert analysis["abort_kind"] == "fatal"
    assert analysis["reason"] is not None
    assert "model_substitution" in analysis["reason"]


def test_session_resilience_delegates_to_adapter(tmp_path: Path):
    log_file = tmp_path / "session.log"
    log_file.write_text("API Error: overloaded\n", encoding="utf-8")
    analysis = analyze_session_log(log_file, exit_code=1, runtime="claude")
    assert analysis["outcome"] == "transient_abort"
    assert analysis["aborted"] is True
    assert analysis["retryable"] is True
    assert analysis["abort_kind"] == "transient"
    assert analysis["reason"] is not None


@pytest.mark.parametrize(
    "log_content,expected_abort_kind,expected_outcome",
    [
        (
            "API Error: 401 {\"error\":{\"message\":\"All connections banned\"}}\n",
            "fatal",
            "permanent_failure",
        ),
        (
            "All connections banned\n",
            "fatal",
            "permanent_failure",
        ),
        (
            "API Error: 401 Unauthorized\n",
            "fatal",
            "permanent_failure",
        ),
        (
            "API Error: weird unknown error\n",
            "fatal",
            "unknown_failure",
        ),
    ],
)
def test_banned_and_401_and_unknown_api_errors_not_retryable(
    tmp_path: Path, log_content: str, expected_abort_kind: str, expected_outcome: str
):
    log_file = tmp_path / "session.log"
    log_file.write_text(log_content, encoding="utf-8")
    analysis = analyze_session_log(log_file, exit_code=1, runtime="claude")
    assert analysis["retryable"] is False
    assert analysis["outcome"] == expected_outcome
    assert analysis["outcome"] != "transient_abort"
    assert analysis["abort_kind"] == expected_abort_kind
