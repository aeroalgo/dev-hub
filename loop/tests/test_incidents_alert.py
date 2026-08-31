"""Tests for incident escalation and webhook alerting (s06)."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from loop.incidents.alert import (
    escalate_incident,
    post_webhook,
    print_stderr_banner,
    write_need_human_file,
)
from loop.incidents.schema import IncidentRecord, compute_incident_id
from loop.incidents.store import parse_incidents_jsonl, _write_incidents_jsonl


@pytest.fixture
def sample_incident() -> IncidentRecord:
    inc_id = compute_incident_id(
        project_root="/app",
        epic_id="T-HUB-018",
        step_id="s06",
        session_id="sess-1",
        diagnostic_codes=["syntax_error", "test_failure"],
        fingerprint="fp123",
    )
    return IncidentRecord(
        incident_id=inc_id,
        opened_at="2026-08-30T10:00:00Z",
        project_root="/app",
        epic_id="T-HUB-018",
        step_id="s06",
        phase="BACK IMPLEMENT",
        session_id="sess-1",
        source="test",
        diagnostic_codes=["syntax_error", "test_failure"],
        fingerprint="fp123",
        status="open",
        runbook_rel="docs/runbooks/syntax_error.md",
    )


def test_write_need_human_file_content(tmp_path: Path, sample_incident: IncidentRecord) -> None:
    epic_dir = tmp_path / "runtime" / "test-epic" / "epic"
    need_human_file = write_need_human_file(epic_dir, sample_incident)

    assert need_human_file.exists()
    content = need_human_file.read_text(encoding="utf-8")
    assert "NEED_HUMAN: incident_syntax_error,test_failure" in content
    assert f"incident_id: {sample_incident.incident_id}" in content
    assert "runbook: docs/runbooks/syntax_error.md" in content


def test_post_webhook_payload_no_secrets(
    monkeypatch: pytest.MonkeyPatch, sample_incident: IncidentRecord
) -> None:
    sent_payload: dict | None = None

    class MockResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def mock_urlopen(req, timeout=None):
        nonlocal sent_payload
        sent_payload = json.loads(req.data.decode("utf-8"))
        return MockResponse()

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    success = post_webhook(
        sample_incident,
        url="http://localhost:9999/webhook",
        project_root="/app",
    )

    assert success is True
    assert sent_payload is not None
    assert sent_payload["schema"] == "loop-alert/v1"
    assert sent_payload["incident_id"] == sample_incident.incident_id
    assert sent_payload["diagnostic_codes"] == ["syntax_error", "test_failure"]
    assert sent_payload["epic_id"] == "T-HUB-018"
    assert sent_payload["step_id"] == "s06"
    assert sent_payload["project_root"] == "/app"
    # Secrets check: no env / tokens / sensitive keys
    for key in sent_payload:
        assert "secret" not in key.lower()
        assert "token" not in key.lower()


def test_webhook_500_fail_closed(
    monkeypatch: pytest.MonkeyPatch, sample_incident: IncidentRecord
) -> None:
    import urllib.error

    def mock_urlopen(req, timeout=None):
        raise urllib.error.HTTPError("http://localhost:9999/webhook", 500, "Internal Server Error", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    # Should log error and return False fail-closed without throwing
    success = post_webhook(
        sample_incident,
        url="http://localhost:9999/webhook",
        project_root="/app",
    )
    assert success is False


def test_webhook_no_url_no_call(sample_incident: IncidentRecord, monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def mock_urlopen(req, timeout=None):
        nonlocal called
        called = True

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    success = post_webhook(sample_incident, url=None)
    assert success is True
    assert called is False


def test_escalate_sets_store_status_escalated(tmp_path: Path, sample_incident: IncidentRecord) -> None:
    epic_dir = tmp_path / "epic"
    epic_dir.mkdir(parents=True)
    incidents_file = epic_dir / "incidents.jsonl"
    _write_incidents_jsonl(incidents_file, [sample_incident])

    updated = escalate_incident(sample_incident, epic_dir=epic_dir)
    assert updated.status == "escalated"
    assert updated.resolution_tier == "escalation"

    records = parse_incidents_jsonl(incidents_file)
    assert len(records) == 1
    assert records[0].status == "escalated"
    assert records[0].resolution_tier == "escalation"


def test_stderr_banner_contains_incident_id(
    capsys: pytest.CaptureFixture, sample_incident: IncidentRecord
) -> None:
    print_stderr_banner(sample_incident)
    captured = capsys.readouterr()
    assert f"NEED_HUMAN ESCALATION: Incident {sample_incident.incident_id}" in captured.err
    assert "syntax_error, test_failure" in captured.err
    assert "docs/runbooks/syntax_error.md" in captured.err
