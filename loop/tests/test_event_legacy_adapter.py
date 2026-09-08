from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from epic_events import (  # noqa: E402
    EVENT_SCHEMA,
    adapt_v1_event,
    read_event_log_result,
)


def test_v1_records_adapt_in_physical_legacy_order_without_mtime_sorting(tmp_path: Path) -> None:
    event_path = tmp_path / "events.jsonl"
    first = {"t": "2026-08-05T12:00:00+00:00", "kind": "qa_pass", "artifact": "memory-bank/qa/first.yaml"}
    second = {"t": "2026-08-05T11:00:00+00:00", "kind": "bugfix_done", "artifact": "memory-bank/bugfix/second.md"}
    event_path.write_text(
        json.dumps(first) + "\n" + json.dumps(second) + "\n", encoding="utf-8"
    )

    result = read_event_log_result(
        event_path,
        expected_epic_id="demo",
        cwd=tmp_path,
    )

    assert result.invalid_count == 0
    assert [event["seq"] for event in result.events] == [1, 2]
    assert [event["artifact"] for event in result.events] == [
        "memory-bank/qa/first.yaml",
        "memory-bank/bugfix/second.md",
    ]
    assert all(event["schema"] == EVENT_SCHEMA for event in result.events)


def test_v1_adapter_assigns_deterministic_identity_and_bounded_metadata() -> None:
    legacy = {
        "kind": "qa_fail",
        "artifact": "memory-bank/qa/demo.yaml",
        "t": "2026-08-05T12:00:00+00:00",
        "runner": "loop",
        "prompt": "do not retain this",
        "huge": "x" * 500,
    }

    first = adapt_v1_event(legacy, seq=4, epic_id="demo")
    second = adapt_v1_event(legacy, seq=4, epic_id="demo")

    assert first.valid and second.valid
    assert first.event == second.event
    assert first.event is not None
    assert first.event["metadata"] == {"runner": "loop"}
    assert "prompt" not in first.event["metadata"]
    assert len(first.event["artifact_sha256"]) == 64


def test_malformed_legacy_record_is_counted_and_does_not_become_pending(tmp_path: Path) -> None:
    event_path = tmp_path / "events.jsonl"
    event_path.write_text(
        json.dumps({"kind": "not-valid", "artifact": "memory-bank/x"}) + "\n"
        + "not-json\n",
        encoding="utf-8",
    )

    result = read_event_log_result(event_path, expected_epic_id="demo", cwd=tmp_path)

    assert result.events == ()
    assert result.invalid_count == 2
    assert {item.code for item in result.diagnostics} == {"kind", "invalid_json"}


def test_gate_sidecars_in_event_log_are_ignored_without_invalidating_events(
    tmp_path: Path,
) -> None:
    """Gate receipts are sidecars, not lifecycle events, and must not poison the log."""
    event_path = tmp_path / "events.jsonl"
    canonical = {
        "schema": "loop-event/v2",
        "event_id": "a" * 32,
        "seq": 1,
        "kind": "phase_transition",
        "artifact": "memory-bank/back/plan/demo/index.yaml",
        "artifact_sha256": "b" * 64,
        "epic_id": "demo",
        "epoch": 0,
        "t": "2026-08-05T12:00:00+00:00",
        "metadata": {},
    }
    gate_evidence = {
        "schema": "loop-gate-evidence/v1",
        "phase": "QA",
        "epic_id": "demo",
        "step_id": "QA",
        "verdict": "PASS",
        "agent_id": "verify-qa",
        "recorded_at": "2026-08-05T12:01:00+00:00",
    }
    gate_verdict = {
        "schema": "loop-gate-verdict/v1",
        "agent_id": "verify-qa",
        "session_id": "session",
        "epic_id": "demo",
        "step_id": "QA",
        "phase": "QA",
        "verdict": "PASS",
        "recorded_at": "2026-08-05T12:01:00+00:00",
    }
    event_path.write_text(
        "\n".join(json.dumps(item) for item in (canonical, gate_evidence, gate_verdict))
        + "\n",
        encoding="utf-8",
    )

    result = read_event_log_result(event_path, expected_epic_id="demo", cwd=tmp_path)

    assert result.diagnostics == ()
    assert result.invalid_count == 0
    assert [event["kind"] for event in result.events] == ["phase_transition"]
