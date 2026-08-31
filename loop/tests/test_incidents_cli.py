"""Tests for CLI subcommands incident-status and incident-retry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from loop.context_loop import main
from loop.incidents.schema import IncidentRecord
from loop.incidents.store import reset_tier1_attempts


from epic_paths import epic_dir


def _create_epic_dir(tmp_path: Path, records: list[dict[str, Any]]) -> Path:
    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    edir = epic_dir(tmp_path)
    edir.mkdir(parents=True, exist_ok=True)
    incidents_file = edir / "incidents.jsonl"
    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    incidents_file.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return edir


def _valid_record(incident_id: str, diagnostic_codes: list[str], tier1_attempts: int = 0, status: str = "open") -> dict[str, Any]:
    return {
        "schema": "loop-incident/v1",
        "incident_id": incident_id,
        "status": status,
        "opened_at": "2026-08-30T10:00:00Z",
        "project_root": "/tmp/test",
        "epic_id": "T-TEST-001",
        "step_id": "s01",
        "phase": "BACK IMPLEMENT",
        "session_id": "sess-1",
        "source": "check_after",
        "diagnostic_codes": diagnostic_codes,
        "fingerprint": "fp-123",
        "tier0_attempts": 1,
        "tier0_repair_log": [],
        "metadata": {"tier1_attempts": tier1_attempts},
    }


def test_incident_status_empty_store(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    epic_dir = _create_epic_dir(tmp_path, [])
    active_ctx = tmp_path / "memory-bank" / "activeContext.md"
    active_ctx.write_text(f"## load_now\n1. [index.yaml]({epic_dir.relative_to(tmp_path)}/index.yaml)\n", encoding="utf-8")

    code = main(["--cwd", str(tmp_path), "incident-status"])
    assert code == 0
    captured = capsys.readouterr().out
    assert "0 open incidents" in captured


def test_incident_status_with_open_incident(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    record = _valid_record("inc-12345", ["active_context_shape_invalid"], tier1_attempts=2)
    epic_dir = _create_epic_dir(tmp_path, [record])
    active_ctx = tmp_path / "memory-bank" / "activeContext.md"
    active_ctx.write_text(f"## load_now\n1. [index.yaml]({epic_dir.relative_to(tmp_path)}/index.yaml)\n", encoding="utf-8")

    code = main(["--cwd", str(tmp_path), "incident-status"])
    assert code == 0
    captured = capsys.readouterr().out
    assert "inc-12345" in captured
    assert "active_context_shape_invalid" in captured


def test_incident_status_json_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    record = _valid_record("inc-12345", ["active_context_shape_invalid"], tier1_attempts=2)
    epic_dir = _create_epic_dir(tmp_path, [record])
    active_ctx = tmp_path / "memory-bank" / "activeContext.md"
    active_ctx.write_text(f"## load_now\n1. [index.yaml]({epic_dir.relative_to(tmp_path)}/index.yaml)\n", encoding="utf-8")

    code = main(["--cwd", str(tmp_path), "incident-status", "--json"])
    assert code == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["open_count"] == 1
    assert data["incidents"][0]["incident_id"] == "inc-12345"


def test_reset_tier1_attempts_updates_store(tmp_path: Path) -> None:
    record = _valid_record("inc-999", ["active_context_shape_invalid"], tier1_attempts=3, status="escalated")
    epic_dir = _create_epic_dir(tmp_path, [record])

    updated = reset_tier1_attempts(epic_dir, "inc-999")
    assert updated is not None
    assert updated.metadata.get("tier1_attempts") == 0
    assert updated.status == "open"


def test_incident_retry_eligible_resets_attempts(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    record = _valid_record("inc-eligible", ["active_context_shape_invalid"], tier1_attempts=3)
    epic_dir = _create_epic_dir(tmp_path, [record])
    active_ctx = tmp_path / "memory-bank" / "activeContext.md"
    active_ctx.write_text(f"## load_now\n1. [index.yaml]({epic_dir.relative_to(tmp_path)}/index.yaml)\n", encoding="utf-8")

    code = main(["--cwd", str(tmp_path), "incident-retry", "inc-eligible"])
    assert code == 0
    captured = capsys.readouterr().out
    assert "Ready for tier1 retry on next loop iteration" in captured


def test_incident_retry_not_eligible_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    record = _valid_record("inc-ineligible", ["unknown_fatal"], tier1_attempts=3)
    epic_dir = _create_epic_dir(tmp_path, [record])
    active_ctx = tmp_path / "memory-bank" / "activeContext.md"
    active_ctx.write_text(f"## load_now\n1. [index.yaml]({epic_dir.relative_to(tmp_path)}/index.yaml)\n", encoding="utf-8")

    code = main(["--cwd", str(tmp_path), "incident-retry", "inc-ineligible"])
    assert code == 1
    captured = capsys.readouterr().err
    assert "not eligible for tier1 retry" in captured or "not eligible" in captured.lower()


def test_incident_retry_unknown_id_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    epic_dir = _create_epic_dir(tmp_path, [])
    active_ctx = tmp_path / "memory-bank" / "activeContext.md"
    active_ctx.write_text(f"## load_now\n1. [index.yaml]({epic_dir.relative_to(tmp_path)}/index.yaml)\n", encoding="utf-8")

    code = main(["--cwd", str(tmp_path), "incident-retry", "inc-nonexistent"])
    assert code == 1
    captured = capsys.readouterr().err
    assert "not found" in captured.lower()
