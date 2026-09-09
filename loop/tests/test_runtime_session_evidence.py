from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.hooks.session_resilience import analyze_session_log
from loop.runtime.session_events import append_session_events, parse_session_events, summarize_session_events


def test_codex_events_are_runtime_neutral_and_content_free() -> None:
    raw = "\n".join(
        [
            "SESSION_START session=s-1 mode=headless command=codex",
            '{"type":"item.started","item":{"type":"command_execution","id":"cmd-1"}}',
            '{"type":"item.completed","item":{"type":"command_execution","status":"completed","aggregated_output":"secret output"}}',
            '{"type":"item.completed","item":{"type":"agent_message","text":"FINISH"}}',
            "SESSION_END session=s-1 exit_code=0 elapsed=1.0s",
        ]
    )

    events = parse_session_events(raw, "codex")
    summary = summarize_session_events(events, exit_code=0)

    assert [event.event_type for event in events] == [
        "session_start",
        "tool_start",
        "tool_end",
        "assistant_message",
        "session_end",
    ]
    assert summary["semantic_status"] == "complete"
    assert summary["task_complete"] is True
    assert all("secret output" not in json.dumps(event.metadata) for event in events)


def test_exit_zero_without_finish_is_process_clean_but_semantically_incomplete(tmp_path: Path) -> None:
    log = tmp_path / "session.log"
    log.write_text(
        "SESSION_START session=s-2 mode=headless command=codex\n"
        '{"type":"item.completed","item":{"type":"command_execution","status":"completed"}}\n'
        "SESSION_END session=s-2 exit_code=0 elapsed=1.0s\n",
        encoding="utf-8",
    )

    result = analyze_session_log(log, exit_code=0, runtime="codex")

    assert result["outcome"] == "clean"
    assert result["aborted"] is False
    assert result["semantic_status"] == "incomplete"
    assert result["task_complete"] is False
    assert result["event_summary"]["event_counts"]["tool_end"] == 1


def test_plain_finish_marker_is_semantic_completion() -> None:
    fixture = Path(__file__).parent / "fixtures" / "codex_session_completed.log"
    result = analyze_session_log(fixture, exit_code=0, runtime="codex")

    assert result["outcome"] == "clean"
    assert result["semantic_status"] == "complete"
    assert result["task_complete"] is True


@pytest.mark.parametrize("runtime", ["claude", "codex"])
def test_timeout_with_finish_marker_is_not_completion(tmp_path: Path, runtime: str) -> None:
    log = tmp_path / f"{runtime}-timeout.log"
    log.write_text(
        "SESSION_START session=s-timeout\n"
        '{"type":"assistant","message":"FINISH"}\n'
        "SESSION_END session=s-timeout exit_code=124\n",
        encoding="utf-8",
    )

    result = analyze_session_log(log, exit_code=124, runtime=runtime)

    assert result["outcome"] == "timeout"
    assert result["aborted"] is True
    assert result["retryable"] is True
    assert result["semantic_status"] == "incomplete"
    assert result["task_complete"] is False


def test_finish_in_failed_command_output_is_not_semantic_completion(tmp_path: Path) -> None:
    log = tmp_path / "finish-command-failed.log"
    log.write_text(
        "SESSION_START session=s-gate\n"
        '{"type":"item.completed","item":{"type":"command_execution",'
        '"command":"python harness/hooks/epic_resolve.py mb-finish analyze",'
        '"aggregated_output":"verdict_wrong_step", "exit_code":2, "status":"failed"}}\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"FINISH"}}\n'
        "SESSION_END session=s-gate exit_code=0\n",
        encoding="utf-8",
    )

    result = analyze_session_log(log, exit_code=0, runtime="codex")

    assert result["aborted"] is True
    assert result["retryable"] is True
    assert result["reason"] == "gate_integrity:verdict_wrong_step"
    assert result["semantic_status"] == "complete"


def test_started_session_without_session_end_is_not_success(tmp_path: Path) -> None:
    log = tmp_path / "missing-end.log"
    log.write_text(
        "SESSION_START session=s-missing-end\n"
        '{"type":"item.completed","item":{"type":"agent_message","text":"FINISH"}}\n',
        encoding="utf-8",
    )

    result = analyze_session_log(log, exit_code=0, runtime="codex")

    assert result["outcome"] == "malformed_result"
    assert result["aborted"] is True
    assert result["retryable"] is True
    assert result["reason"] == "session_end_missing"


def test_session_event_stream_keeps_step_role_and_runtime(tmp_path: Path) -> None:
    events = parse_session_events("SESSION_START session=s-3\nSESSION_END session=s-3 exit_code=0\n", "dsh")
    target = append_session_events(
        tmp_path,
        events,
        session_id="s-3",
        step_id="s05",
        epic_id="T-HUB-083",
        role="back",
        phase="IMPLEMENT",
        outcome="clean",
    )

    assert target == tmp_path / "session-events.jsonl"
    rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["schema"] == "loop-session-events/v1"
    assert {row["runtime"] for row in rows} == {"dsh"}
    assert {row["step_id"] for row in rows} == {"s05"}
    assert {row["role"] for row in rows} == {"back"}
