from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
RESILIENCE = HOOKS / "session_resilience.py"
sys.path.insert(0, str(HOOKS))
FIXTURE = ROOT / "loop" / "tests" / "fixtures" / "fake_claude.py"

def _load_resilience():
    spec = importlib.util.spec_from_file_location("session_resilience_wrapper", RESILIENCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run_wrapper(tmp_path: Path, mode: str, *fixture_args: str) -> tuple[int, str]:
    log = tmp_path / f"{mode}.log"
    proc = subprocess.run(
        [
            sys.executable,
            str(RESILIENCE),
            "run-session",
            "--mode",
            mode,
            "--session-id",
            f"session-{mode}",
            "--timeout",
            "2",
            "--kill-grace",
            "0.2",
            "--log",
            str(log),
            "--",
            sys.executable,
            str(FIXTURE),
            *fixture_args,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.returncode, log.read_text(encoding="utf-8")


@pytest.mark.parametrize("mode", ["headless", "interactive"])
def test_clean_modes_share_markers_and_combined_log(tmp_path: Path, mode: str) -> None:
    rc, log = _run_wrapper(tmp_path, mode, "clean")

    assert rc == 0
    assert "SESSION_START session=" in log
    assert "stdout: clean" in log
    assert "stderr: clean" in log
    assert "SESSION_END session=" in log
    assert "exit_code=0" in log


def test_timeout_terminates_fake_claude_and_records_metadata(tmp_path: Path) -> None:
    rc, log = _run_wrapper(tmp_path, "headless", "hang")

    assert rc == 124
    assert "SESSION_TIMEOUT session=" in log
    assert "SESSION_END session=" in log
    assert "exit_code=124" in log


def test_idle_timeout_emits_heartbeat_and_retryable_api_error(tmp_path: Path) -> None:
    sr = _load_resilience()
    log = tmp_path / "idle-heartbeat.log"
    rc = sr.run_session(
        [sys.executable, str(FIXTURE), "hang"],
        mode="headless",
        session_id="idle-hb",
        timeout=5,
        kill_grace=0.2,
        heartbeat_sec=0.2,
        idle_timeout=0.6,
        log_path=log,
    )
    text = log.read_text(encoding="utf-8")
    assert rc == 124
    assert "SESSION_HEARTBEAT session=idle-hb" in text
    assert "SESSION_IDLE_TIMEOUT session=idle-hb" in text
    assert "API Error: Stream idle timeout - no tool_use/tool_result" in text
    analysis = sr.analyze_session_log(log, exit_code=rc, attempt=1)
    assert analysis["aborted"]
    assert analysis["retryable"]
    assert analysis["abort_kind"] == "transient"


def test_idle_timeout_ignores_stream_noise_without_tools(tmp_path: Path) -> None:
    sr = _load_resilience()
    log = tmp_path / "idle-noise.log"
    rc = sr.run_session(
        [sys.executable, str(FIXTURE), "noise"],
        mode="headless",
        session_id="idle-noise",
        timeout=5,
        kill_grace=0.2,
        heartbeat_sec=0.2,
        idle_timeout=0.6,
        log_path=log,
    )
    text = log.read_text(encoding="utf-8")
    assert rc == 124
    assert "SESSION_IDLE_TIMEOUT session=idle-noise" in text
    assert "input_json_delta" in text
    assert "API Error: Stream idle timeout - no tool_use/tool_result" in text


def test_tool_progress_resets_idle_timeout(tmp_path: Path) -> None:
    sr = _load_resilience()
    log = tmp_path / "idle-tool-reset.log"
    started = time.monotonic()
    rc = sr.run_session(
        [sys.executable, str(FIXTURE), "tool-then-noise"],
        mode="headless",
        session_id="idle-tool",
        timeout=5,
        kill_grace=0.2,
        heartbeat_sec=0.2,
        idle_timeout=0.8,
        log_path=log,
    )
    elapsed = time.monotonic() - started
    text = log.read_text(encoding="utf-8")
    assert rc == 124
    assert "SESSION_IDLE_TIMEOUT session=idle-tool" in text
    assert '"type":"tool_use"' in text
    assert elapsed >= 0.8
    assert elapsed < 2.5


def test_timeout_kills_process_group_and_releases_runner_lock(tmp_path: Path) -> None:
    resilience = _load_resilience()
    lock_path = tmp_path / "runner.lock"
    log = tmp_path / "hang.log"
    first = subprocess.Popen(
        [
            sys.executable,
            str(RESILIENCE),
            "run-session",
            "--mode",
            "headless",
            "--session-id",
            "session-lock-1",
            "--timeout",
            "0.1",
            "--kill-grace",
            "0.1",
            "--log",
            str(log),
            "--",
            sys.executable,
            str(FIXTURE),
            "hang",
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    first.wait(timeout=5)

    import fcntl

    with lock_path.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    assert first.returncode == 124
    assert resilience.run_session is not None


def test_abrupt_stream_detected_on_exit_zero_without_result(tmp_path: Path) -> None:
    """stream-json without result is abrupt even when Claude exits 0 (server mid-response).

    Live gap: API Error appears on terminal via stream filter, log has balanced
    message_start/stop, exit_code=0 → old heuristic returned clean → no retry.
    """
    sr = _load_resilience()
    log = tmp_path / "exit0_no_result.log"
    log.write_text(
        "SESSION_START session=1 mode=headless command=claude\n"
        '{"type":"stream_event","event":{"type":"message_start"}}\n'
        '{"type":"stream_event","event":{"type":"content_block_start"}}\n'
        '{"type":"stream_event","event":{"type":"message_stop"}}\n'
        "SESSION_END session=1 exit_code=0 elapsed=12.0s\n",
        encoding="utf-8",
    )
    reason = sr.detect_abort_in_log(log, exit_code=0)
    assert reason is not None
    assert "no result event" in reason
    analysis = sr.analyze_session_log(log, exit_code=0, attempt=1)
    assert analysis["aborted"]
    assert analysis["retryable"]
    assert analysis["abort_kind"] == "transient"


def test_clean_when_result_present_exit_zero(tmp_path: Path) -> None:
    """Successful stream-json always ends with type=result — that stays clean."""
    sr = _load_resilience()
    log = tmp_path / "clean_result.log"
    log.write_text(
        "SESSION_START session=1 mode=headless command=claude\n"
        '{"type":"stream_event","event":{"type":"message_start"}}\n'
        '{"type":"stream_event","event":{"type":"message_stop"}}\n'
        '{"type":"result","subtype":"success","result":"ok"}\n'
        "SESSION_END session=1 exit_code=0 elapsed=12.0s\n",
        encoding="utf-8",
    )
    reason = sr.detect_abort_in_log(log, exit_code=0)
    assert reason is None, f"expected clean, got: {reason!r}"
    analysis = sr.analyze_session_log(log, exit_code=0, attempt=1)
    assert not analysis["aborted"]
    assert analysis["outcome"] == "clean"


def test_abrupt_stream_detected_on_nonzero_exit(tmp_path: Path) -> None:
    """stream_event without result event MUST be classified as abort when exit_code != 0."""
    sr = _load_resilience()
    log = tmp_path / "abrupt.log"
    log.write_text(
        '{"type":"stream_event","event":{"type":"content_block_start"}}\n',
        encoding="utf-8",
    )
    reason = sr.detect_abort_in_log(log, exit_code=1)
    assert reason == "abrupt stream termination (no result event in JSONL)"
    analysis = sr.analyze_session_log(log, exit_code=1, attempt=1)
    assert analysis["aborted"]
    assert analysis["retryable"]


def test_log_cap_truncation_yields_transient(tmp_path: Path) -> None:
    """When log cap is hit, SESSION_LOG_TRUNCATED marker must make non-zero exit retryable."""
    sr = _load_resilience()
    log = tmp_path / "capped.log"
    log.write_text(
        "SESSION_START session=x mode=headless command=claude\n"
        '{"type":"stream_event","event":{"type":"content_block_start"}}\n'
        "SESSION_LOG_TRUNCATED\n"
        "SESSION_END session=x exit_code=1 elapsed=100.0s\n",
        encoding="utf-8",
    )
    reason = sr.detect_abort_in_log(log, exit_code=1)
    assert reason is not None and "log truncated" in reason
    analysis = sr.analyze_session_log(log, exit_code=1, attempt=1)
    assert analysis["aborted"]
    assert analysis["retryable"], f"truncated log with exit=1 must be retryable, got: {analysis}"


def test_truncated_user_jsonl_not_classified_as_abort(tmp_path: Path) -> None:
    """Truncated JSONL with type=user containing 'malformed' in tool_result must not trigger abort detection."""
    sr = _load_resilience()
    log = tmp_path / "trunc.log"
    # Simulate a truncated JSONL line that starts as type=user but is cut mid-stream.
    # The tool_result content contains the word 'malformed' (from epic_lib.py source).
    truncated_user_line = (
        '{"type":"user","message":{"role":"user","content":[{"tool_use_id":"abc","type":"tool_result",'
        '"content":"1\\t#!/usr/bin/env python3\\n2\\t\\"\\"\\"Epic helpers: activeContext cursor\\n'
        "malformed input to pending.\\\"\\\"\\\"\\n1072\\t    if decompose is None"
    )
    log.write_text(truncated_user_line + "\n", encoding="utf-8")
    reason = sr.detect_abort_in_log(log)
    assert reason is None, f"truncated user JSONL must not be detected as abort, got: {reason!r}"
    analysis = sr.analyze_session_log(log, exit_code=0, attempt=1)
    assert not analysis["aborted"]
    assert analysis["outcome"] == "clean"


def test_stalled_mid_stream_is_transient(tmp_path: Path) -> None:
    """'Response stalled mid-stream' without 'may be incomplete' must still be retryable."""
    sr = _load_resilience()
    log = tmp_path / "stalled.log"
    log.write_text(
        "SESSION_START session=x mode=headless command=claude\n"
        "API Error: Response stalled mid-stream.\n"
        "SESSION_END session=x exit_code=1 elapsed=30.0s\n",
        encoding="utf-8",
    )
    reason = sr.detect_abort_in_log(log, exit_code=1)
    assert reason is not None, f"expected abort reason, got: {reason!r}"
    assert "stalled" in reason.lower(), f"expected 'stalled' in reason, got: {reason!r}"
    analysis = sr.analyze_session_log(log, exit_code=1, attempt=1)
    assert analysis["aborted"]
    assert analysis["retryable"], f"stalled mid-stream must be retryable, got: {analysis}"


def test_stream_idle_timeout_is_retryable(tmp_path: Path) -> None:
    """'API Error: Stream idle timeout' must be detected as transient and retryable."""
    sr = _load_resilience()
    log = tmp_path / "idle.log"
    log.write_text(
        "SESSION_START session=x mode=headless command=claude\n"
        '{"type":"result","terminal_reason":"api_error","result":"API Error: Stream idle timeout - no chunks received","subtype":"success"}\n'
        "SESSION_END session=x exit_code=1 elapsed=491.0s\n",
        encoding="utf-8",
    )
    reason = sr.detect_abort_in_log(log, exit_code=1)
    assert reason is not None, f"expected abort reason, got: {reason!r}"
    assert "idle" in reason.lower(), f"expected 'idle' in reason, got: {reason!r}"
    analysis = sr.analyze_session_log(log, exit_code=1, attempt=1)
    assert analysis["aborted"]
    assert analysis["retryable"], f"idle timeout must be retryable, got: {analysis}"
    assert analysis["abort_kind"] == "transient"


def test_stream_idle_timeout_backoff_is_larger(tmp_path: Path) -> None:
    """Idle timeout backoff must be >= DEFAULT_IDLE_BACKOFF_SEC (60s), larger than default 20s."""
    sr = _load_resilience()
    log = tmp_path / "idle.log"
    log.write_text(
        "SESSION_START session=x mode=headless command=claude\n"
        '{"type":"result","terminal_reason":"api_error","result":"API Error: Stream idle timeout - no chunks received","subtype":"success"}\n'
        "SESSION_END session=x exit_code=1 elapsed=491.0s\n",
        encoding="utf-8",
    )
    analysis = sr.analyze_session_log(log, exit_code=1, attempt=1)
    assert analysis["backoff_sec"] >= sr.DEFAULT_IDLE_BACKOFF_SEC, (
        f"idle timeout backoff must be >= {sr.DEFAULT_IDLE_BACKOFF_SEC}s, got: {analysis['backoff_sec']}"
    )


def test_is_idle_timeout_helper() -> None:
    sr = _load_resilience()
    assert sr.is_idle_timeout("API Error: Stream idle timeout - no chunks received")
    assert sr.is_idle_timeout("stream idle timeout")
    assert not sr.is_idle_timeout("API Error: overloaded")
    assert not sr.is_idle_timeout(None)
    assert not sr.is_idle_timeout("")


def test_server_error_mid_response_with_epic_stream_end_is_transient_retryable(tmp_path: Path) -> None:
    """'API Error: Server error mid-response' + '--- epic stream end ---' must be transient and retryable.

    Regression for: after this exact abort, the outer loop must resume next iteration
    (inner retry up to cap, then resume_outer → continue).
    """
    sr = _load_resilience()
    log = tmp_path / "server_error.log"
    log.write_text(
        "SESSION_START session=x mode=headless command=claude\n"
        "API Error: Server error mid-response. The response above may be incomplete.\n"
        "--- epic stream end ---\n"
        "SESSION_END session=x exit_code=1 elapsed=123.4s\n",
        encoding="utf-8",
    )
    reason = sr.detect_abort_in_log(log, exit_code=1)
    assert reason is not None, f"expected abort reason, got: {reason!r}"
    assert "Server error mid-response" in reason
    analysis = sr.analyze_session_log(log, exit_code=1, attempt=1)
    assert analysis["aborted"]
    assert analysis["retryable"], f"server error mid-response + epic stream end must be retryable, got: {analysis}"
    assert analysis["abort_kind"] == "transient"


def test_cli_rejects_unknown_mode(tmp_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(RESILIENCE),
            "run-session",
            "--mode",
            "unknown",
            "--session-id",
            "bad",
            "--timeout",
            "1",
            "--kill-grace",
            "0.1",
            "--log",
            str(tmp_path / "bad.log"),
            "--",
            sys.executable,
            str(FIXTURE),
            "clean",
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 2


def test_org_model_restriction_is_permanent_even_on_exit_zero(tmp_path: Path) -> None:
    """Silent allowlist downgrade must not be treated as a clean DECOMPOSE/IMPLEMENT."""
    sr = _load_resilience()
    log = tmp_path / "restricted.log"
    restricted = (
        'Model "agy/claude-sonnet-4-6" is restricted by your organization\'s settings. '
        "Using antigravity/gemini-3.1-flash-lite[1m] instead."
    )
    log.write_text(
        "SESSION_START session=3 mode=headless command=claude\n"
        "EXPECTED_MODEL agy/claude-sonnet-4-6\n"
        + json.dumps(
            {
                "type": "system",
                "subtype": "informational",
                "content": restricted,
                "level": "warning",
            }
        )
        + "\n"
        + json.dumps(
            {
                "type": "system",
                "subtype": "init",
                "model": "antigravity/gemini-3.1-flash-lite[1m]",
            }
        )
        + "\n"
        '{"type":"result","subtype":"success","result":"ok"}\n'
        "SESSION_END session=3 exit_code=0 elapsed=12.0s\n",
        encoding="utf-8",
    )
    reason = sr.detect_abort_in_log(
        log, exit_code=0, expected_model="agy/claude-sonnet-4-6"
    )
    assert reason is not None
    assert reason.startswith("model_substitution:")
    assert "gemini-3.1-flash-lite" in reason
    analysis = sr.analyze_session_log(
        log, exit_code=0, attempt=1, expected_model="agy/claude-sonnet-4-6"
    )
    assert analysis["aborted"] is True
    assert analysis["retryable"] is False
    assert analysis["abort_kind"] == "fatal"
    assert analysis["outcome"] == "permanent_failure"


def test_init_model_alias_is_not_substitution(tmp_path: Path) -> None:
    """OmniRoute init id (gemini-default) ≠ CLI id — still OK without restriction msg."""
    sr = _load_resilience()
    log = tmp_path / "alias.log"
    log.write_text(
        "SESSION_START session=1 mode=headless command=claude\n"
        + json.dumps(
            {
                "type": "system",
                "subtype": "init",
                "model": "gemini-default",
            }
        )
        + "\n"
        '{"type":"result","subtype":"success","result":"ok"}\n'
        "SESSION_END session=1 exit_code=0 elapsed=1.0s\n",
        encoding="utf-8",
    )
    assert (
        sr.detect_abort_in_log(
            log, exit_code=0, expected_model="agy/gemini-3.5-flash-medium"
        )
        is None
    )
    analysis = sr.analyze_session_log(
        log, exit_code=0, attempt=1, expected_model="agy/gemini-3.5-flash-medium"
    )
    assert analysis["aborted"] is False
    assert analysis["outcome"] == "clean"


def test_run_session_kills_on_model_restriction(tmp_path: Path) -> None:
    """Wrapper must kill the child as soon as org swap appears (exit 125)."""
    sr = _load_resilience()
    fixture = tmp_path / "emit_restricted.py"
    fixture.write_text(
        "import json, sys, time\n"
        "msg = ("
        "'Model \\\"agy/claude-sonnet-4-6\\\" is restricted by your organization\\'s settings. '"
        "'Using antigravity/gemini-3.1-flash-lite[1m] instead.'"
        ")\n"
        "sys.stdout.write(json.dumps({"
        "'type':'system','subtype':'informational','content':msg,'level':'warning'"
        "}) + '\\n')\n"
        "sys.stdout.flush()\n"
        "time.sleep(30)\n"
        "print('should-not-reach')\n",
        encoding="utf-8",
    )
    log = tmp_path / "kill.log"
    rc = sr.run_session(
        [sys.executable, str(fixture)],
        mode="headless",
        session_id="sub",
        timeout=5,
        kill_grace=0.2,
        log_path=log,
        expected_model="agy/claude-sonnet-4-6",
    )
    text = log.read_text(encoding="utf-8")
    assert rc == sr.MODEL_SUBSTITUTION_EXIT
    assert "MODEL_SUBSTITUTION" in text
    assert "model_substitution:" in text
    assert "should-not-reach" not in text
