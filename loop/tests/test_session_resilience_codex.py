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


def test_session_resilience_codex_exit0_aborted_prose_not_abort(tmp_path: Path) -> None:
    log_file = tmp_path / "codex-exit0-prose.log"
    log_file.write_text(
        "SESSION_START session=1 mode=headless command=codex\n"
        '{"type":"item.completed","item":{"type":"agent_message","text":"prev_session: aborted — retry"}}\n'
        '{"type":"item.completed","item":{"type":"command_execution","aggregated_output":'
        '"==> TRANSIENT API abort — retry after 20s\\n","exit_code":0,"status":"completed"}}\n'
        "SESSION_END session=1 exit_code=0 elapsed=100.0s\n",
        encoding="utf-8",
    )
    analysis = analyze_session_log(log_file, exit_code=0, runtime="codex")

    assert analysis["outcome"] == "clean"
    assert analysis["aborted"] is False
    assert analysis["reason"] is None
    assert analysis["retryable"] is False


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
