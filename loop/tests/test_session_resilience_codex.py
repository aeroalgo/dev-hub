from __future__ import annotations

from pathlib import Path
import pytest

from harness.hooks.session_resilience import analyze_session_log
from loop.runtime_adapters.common import get_adapter_for_runtime

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_session_resilience_codex_completed(tmp_path: Path):
    log_file = FIXTURES_DIR / "codex_session_completed.log"
    analysis = analyze_session_log(log_file, exit_code=0, runtime="codex")

    assert analysis["outcome"] == "clean"
    assert analysis["aborted"] is False
    assert analysis["reason"] is None
    assert analysis["retryable"] is False
    assert analysis["abort_kind"] is None


def test_session_resilience_codex_aborted(tmp_path: Path):
    log_file = FIXTURES_DIR / "codex_session_aborted.log"
    analysis = analyze_session_log(log_file, exit_code=1, runtime="codex")

    assert analysis["outcome"] == "transient_abort"
    assert analysis["aborted"] is True
    assert analysis["reason"] == "aborted"
    assert analysis["retryable"] is True
    assert analysis["abort_kind"] == "transient"


def test_session_resilience_codex_auth_fail(tmp_path: Path):
    log_file = FIXTURES_DIR / "codex_session_auth_fail.log"
    analysis = analyze_session_log(log_file, exit_code=1, runtime="codex")

    assert analysis["outcome"] == "permanent_failure"
    assert analysis["aborted"] is True
    assert analysis["reason"] == "auth_failed"
    assert analysis["retryable"] is False
    assert analysis["abort_kind"] == "fatal"


def test_session_resilience_codex_binary_missing(tmp_path: Path):
    log_file = FIXTURES_DIR / "codex_session_binary_missing.log"
    analysis = analyze_session_log(log_file, exit_code=127, runtime="codex")

    assert analysis["outcome"] == "permanent_failure"
    assert analysis["aborted"] is True
    assert analysis["reason"] == "command not found"
    assert analysis["retryable"] is False
    assert analysis["abort_kind"] == "fatal"
