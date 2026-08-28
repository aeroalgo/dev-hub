from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RESILIENCE = ROOT / ".claude" / "hooks" / "session_resilience.py"


def _load_resilience():
    hooks = str(RESILIENCE.parent)
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    spec = importlib.util.spec_from_file_location("session_resilience_dsh", RESILIENCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


from loop.runtime_adapters.dsh import (
    build_dsh_command,
    build_dsh_command_from_file,
    detect_dsh_model_mismatch,
    normalize_dsh_log,
)


def test_build_dsh_command_default_profile() -> None:
    assert build_dsh_command("epic-implement", "do the work") == [
        "dsh",
        "--profile",
        "epic-implement",
        "--no-open",
        "do the work",
    ]


def test_build_dsh_command_custom_bin() -> None:
    assert build_dsh_command("custom", "prompt", dsh_bin="npx") == [
        "npx",
        "--profile",
        "custom",
        "--no-open",
        "prompt",
    ]


def test_build_dsh_command_prompt_inline() -> None:
    prompt = "line one\nline two"
    assert build_dsh_command("profile", prompt)[-1] == prompt


def test_build_dsh_command_from_file(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("prompt from file", encoding="utf-8")

    assert build_dsh_command_from_file("profile", prompt_file) == [
        "dsh",
        "--profile",
        "profile",
        "--no-open",
        "prompt from file",
    ]


def test_normalize_dsh_log_passthrough() -> None:
    raw_log = "plain dsh output\n"
    assert normalize_dsh_log(raw_log) == raw_log


def test_normalize_dsh_log_session_end_jsonl() -> None:
    raw_log = json.dumps({"event": {"type": "session_end", "content": "done"}})
    assert normalize_dsh_log(raw_log) == "done"


def test_normalize_dsh_log_result_jsonl() -> None:
    raw_log = json.dumps({"type": "result", "result": "completed"})
    assert normalize_dsh_log(raw_log) == "completed"


def test_normalize_dsh_log_empty() -> None:
    assert normalize_dsh_log("") == ""


@pytest.mark.parametrize("raw_log", ["{not-json}\n", '{"type": "result"}\n'])
def test_normalize_dsh_log_malformed_jsonl(raw_log: str) -> None:
    assert normalize_dsh_log(raw_log) == raw_log


def _fixture(name: str) -> Path:
    return ROOT / "loop" / "tests" / "fixtures" / name


def test_dsh_model_mismatch_detected_from_jsonl_mapping() -> None:
    raw_log = json.dumps(
        {
            "type": "result",
            "requested_model": "provider/alpha",
            "actual_model": "provider/beta",
        }
    )

    reason = detect_dsh_model_mismatch(raw_log, "provider/alpha")

    assert reason is not None
    assert reason.startswith("model_substitution:")
    assert "requested=provider/alpha" in reason
    assert "actual=provider/beta" in reason


def test_dsh_model_mismatch_ignores_unverified_or_equivalent_models() -> None:
    ordinary_log = json.dumps(
        {
            "type": "result",
            "requested_model": "provider/alpha",
            "actual_model": "provider/alpha[1m]",
        }
    )
    unrelated_log = json.dumps({"type": "result", "result": "completed"})

    assert detect_dsh_model_mismatch(ordinary_log, "provider/alpha") is None
    assert detect_dsh_model_mismatch(unrelated_log, "provider/alpha") is None
    assert detect_dsh_model_mismatch(
        json.dumps(
            {
                "type": "result",
                "requested_model": "provider/alpha",
                "actual_model": "provider/beta",
            }
        ),
        None,
    ) is None


def test_analyze_dsh_model_substitution_is_permanent(tmp_path: Path) -> None:
    resilience = _load_resilience()
    log = tmp_path / "dsh-model-mismatch.jsonl"
    log.write_text(
        json.dumps(
            {
                "type": "result",
                "requested_model": "provider/alpha",
                "actual_model": "provider/beta",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    analysis = resilience.analyze_session_log(
        log, exit_code=1, expected_model="provider/alpha", runtime="dsh"
    )

    assert analysis["outcome"] == "permanent_failure"
    assert analysis["aborted"] is True
    assert analysis["retryable"] is False
    assert analysis["abort_kind"] == "fatal"
    assert analysis["reason"].startswith("model_substitution:")


def test_analyze_claude_path_unaffected(tmp_path: Path) -> None:
    resilience = _load_resilience()
    log = tmp_path / "claude.log"
    log.write_text("clean session output\n", encoding="utf-8")

    analysis = resilience.analyze_session_log(log, exit_code=0, runtime="claude")

    assert analysis["outcome"] == "clean"
    assert analysis["aborted"] is False


def test_analyze_dsh_completed_exit0() -> None:
    resilience = _load_resilience()

    analysis = resilience.analyze_session_log(
        _fixture("dsh_session_completed.jsonl"), exit_code=0, runtime="dsh"
    )

    assert analysis["outcome"] == "clean"
    assert analysis["aborted"] is False


def test_analyze_dsh_transient_http429() -> None:
    resilience = _load_resilience()

    analysis = resilience.analyze_session_log(
        _fixture("dsh_session_transient.jsonl"), exit_code=1, runtime="dsh"
    )

    assert analysis["outcome"] == "transient_abort"
    assert analysis["retryable"] is True
    assert analysis["abort_kind"] == "transient"


def test_analyze_dsh_permanent_auth() -> None:
    resilience = _load_resilience()
    log = _fixture("dsh_session_permanent.jsonl")

    analysis = resilience.analyze_session_log(log, exit_code=1, runtime="dsh")

    assert analysis["outcome"] == "permanent_failure"
    assert analysis["retryable"] is False
    assert analysis["abort_kind"] == "fatal"


def test_analyze_dsh_exit0_incomplete_finish(tmp_path: Path) -> None:
    resilience = _load_resilience()
    log = tmp_path / "dsh-incomplete.jsonl"
    log.write_text('{"type":"result","result":"partial"}\n', encoding="utf-8")

    analysis = resilience.analyze_session_log(log, exit_code=0, runtime="dsh")

    assert analysis["aborted"] is True
    assert analysis["retryable"] is False
    assert analysis["reason"] == "dsh incomplete FINISH"
    assert analysis["abort_kind"] == "fatal"
