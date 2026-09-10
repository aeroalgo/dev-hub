from __future__ import annotations

from pathlib import Path
import json

from harness.hooks.session_resilience import analyze_session_log


def _cmd_item(command: str, output_obj: dict, *, exit_code: int, status: str) -> str:
    return json.dumps(
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": command,
                "aggregated_output": json.dumps(output_obj),
                "exit_code": exit_code,
                "status": status,
            },
        },
        separators=(",", ":"),
    )


def test_failed_finish_step_from_log_parses_step(tmp_path: Path) -> None:
    from harness.hooks.session_resilience import failed_finish_step_from_log

    failed = _cmd_item(
        "python harness/hooks/epic_resolve.py mb-finish implement --step s03",
        {"ok": False, "diagnostic_codes": ["verify_pass_missing"]},
        exit_code=2,
        status="failed",
    )
    log = tmp_path / "fail.log"
    log.write_text(failed + "\n", encoding="utf-8")
    assert failed_finish_step_from_log(log.read_text(encoding="utf-8")) == "s03"


def test_later_failed_redo_after_ok_finish_does_not_poison(tmp_path: Path) -> None:
    """Parent mb-finish redo after automatic ok:true must not fail the session."""
    ok = _cmd_item(
        "python harness/hooks/epic_resolve.py mb-finish implement --step s03",
        {"ok": True, "finished_step": "s03", "diagnostic_codes": []},
        exit_code=0,
        status="completed",
    )
    redo = _cmd_item(
        "python harness/hooks/epic_resolve.py mb-finish implement --step s03",
        {"ok": False, "diagnostic_codes": ["verify_pass_missing"]},
        exit_code=2,
        status="failed",
    )
    log = tmp_path / "ok-then-redo.log"
    log.write_text(
        "\n".join(
            [
                "SESSION_START session=s-ok mode=headless command=codex",
                ok,
                redo,
                '{"type":"item.completed","item":{"type":"agent_message","text":"done"}}',
                "SESSION_END session=s-ok exit_code=0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    result = analyze_session_log(log, exit_code=0, runtime="codex")
    assert result["aborted"] is False
    assert result["retryable"] is False
    assert result.get("reason") is None
    assert result.get("gate_diagnostic") is None


def test_later_successful_mb_finish_clears_earlier_verdict_stale(tmp_path: Path) -> None:
    """Earlier failed finish must not poison session close after a later ok:true mb-finish."""
    failed = _cmd_item(
        "python harness/hooks/epic_resolve.py mb-finish bugfix",
        {"ok": False, "diagnostic_codes": ["verdict_stale"]},
        exit_code=2,
        status="failed",
    )
    ok = _cmd_item(
        "python harness/hooks/epic_resolve.py mb-finish bugfix",
        {"ok": True, "finished_step": "BUGFIX", "next_phase": "QA"},
        exit_code=0,
        status="completed",
    )
    finish = json.dumps(
        {"type": "item.completed", "item": {"type": "agent_message", "text": "FINISH"}},
        separators=(",", ":"),
    )
    log = tmp_path / "finish-stale-then-ok.log"
    log.write_text(
        "\n".join(
            [
                "SESSION_START session=s-bugfix",
                failed,
                ok,
                finish,
                "SESSION_END session=s-bugfix exit_code=0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    result = analyze_session_log(log, exit_code=0, runtime="codex")
    assert result["aborted"] is False
    assert result["retryable"] is False
    assert result.get("reason") is None
    assert result.get("gate_diagnostic") is None
    assert result["outcome"] == "clean"
    assert result["semantic_status"] == "complete"


def test_plain_text_later_ok_mb_finish_clears_earlier_verdict_stale(tmp_path: Path) -> None:
    log = tmp_path / "finish-stale-plain.log"
    log.write_text(
        "\n".join(
            [
                "SESSION_START session=s-plain",
                "mb-finish bugfix verdict_stale",
                "mb-finish bugfix {\"ok\": true, \"finished_step\": \"BUGFIX\"}",
                "FINISH",
                "SESSION_END session=s-plain exit_code=0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    result = analyze_session_log(log, exit_code=0, runtime="claude")
    assert result["aborted"] is False
    assert result.get("gate_diagnostic") is None
    assert result["outcome"] == "clean"


def test_last_mb_finish_still_reports_verdict_stale_when_unresolved(tmp_path: Path) -> None:
    failed = _cmd_item(
        "python harness/hooks/epic_resolve.py mb-finish bugfix",
        {"ok": False, "diagnostic_codes": ["verdict_stale"]},
        exit_code=2,
        status="failed",
    )
    finish = json.dumps(
        {"type": "item.completed", "item": {"type": "agent_message", "text": "FINISH"}},
        separators=(",", ":"),
    )
    log = tmp_path / "finish-stale-last.log"
    log.write_text(
        "\n".join(
            [
                "SESSION_START session=s-stale-last",
                failed,
                finish,
                "SESSION_END session=s-stale-last exit_code=0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    result = analyze_session_log(log, exit_code=0, runtime="codex")
    assert result["aborted"] is True
    assert result["retryable"] is True
    assert result["reason"] == "gate_integrity:verdict_stale"


def test_failed_finish_without_ok_true_still_aborts(tmp_path: Path) -> None:
    failed = _cmd_item(
        "python harness/hooks/epic_resolve.py mb-finish analyze",
        {"ok": False, "diagnostic_codes": ["verdict_wrong_step"]},
        exit_code=2,
        status="failed",
    )
    finish = json.dumps(
        {"type": "item.completed", "item": {"type": "agent_message", "text": "FINISH"}},
        separators=(",", ":"),
    )
    log = tmp_path / "finish-wrong-step.log"
    log.write_text(
        "\n".join(
            [
                "SESSION_START session=s-gate",
                failed,
                finish,
                "SESSION_END session=s-gate exit_code=0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    result = analyze_session_log(log, exit_code=0, runtime="codex")
    assert result["aborted"] is True
    assert result["reason"] == "gate_integrity:verdict_wrong_step"
