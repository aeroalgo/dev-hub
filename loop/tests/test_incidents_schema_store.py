"""Tests for loop.incidents schema and store."""

from __future__ import annotations

from pathlib import Path
import json
import pytest

from loop.incidents import (
    SCHEMA_LOOP_INCIDENT,
    CorruptIncidentError,
    IncidentRecord,
    append_incident,
    compute_incident_id,
    list_open_incidents,
    parse_incidents_jsonl,
    resolve_incident,
)


def test_incident_v1_round_trip_all_fields():
    incident_id = compute_incident_id(
        project_root="/tmp/proj",
        epic_id="T-HUB-017",
        step_id="s01",
        session_id="sess-123",
        diagnostic_codes=["CODE_A", "CODE_B"],
        fingerprint="fp-xyz",
    )

    record = IncidentRecord(
        incident_id=incident_id,
        status="open",
        opened_at="2026-08-30T10:00:00Z",
        project_root="/tmp/proj",
        epic_id="T-HUB-017",
        step_id="s01",
        phase="BACK IMPLEMENT",
        session_id="sess-123",
        source="check_after",
        diagnostic_codes=["CODE_A", "CODE_B"],
        fingerprint="fp-xyz",
        tier0_attempts=1,
        tier0_repair_log=[{"attempt": 1, "action": "flushed_cache"}],
        metadata={"env": "test"},
    )

    dumped = record.model_dump(by_alias=True)
    assert dumped["schema"] == SCHEMA_LOOP_INCIDENT
    assert dumped["incident_id"] == incident_id

    restored = IncidentRecord.model_validate(dumped)
    assert restored.incident_id == record.incident_id
    assert restored.status == "open"
    assert restored.diagnostic_codes == ["CODE_A", "CODE_B"]
    assert restored.tier0_repair_log == [{"attempt": 1, "action": "flushed_cache"}]
    assert restored.metadata == {"env": "test"}


def test_incident_id_stable_sha256():
    id1 = compute_incident_id(
        project_root="/tmp/proj",
        epic_id="T-HUB-017",
        step_id="s01",
        session_id="sess-123",
        diagnostic_codes=["CODE_B", "CODE_A"],  # unordered input
        fingerprint="fp-xyz",
    )

    id2 = compute_incident_id(
        project_root="/tmp/proj",
        epic_id="T-HUB-017",
        step_id="s01",
        session_id="sess-123",
        diagnostic_codes=["CODE_A", "CODE_B"],
        fingerprint="fp-xyz",
    )

    assert id1 == id2
    assert len(id1) == 64  # sha256 hex string


def test_append_and_list_open_store_resolve(tmp_path: Path):
    epic_dir = tmp_path / "epic_slot"
    inc_id = compute_incident_id(
        project_root="/tmp/proj",
        epic_id="T-HUB-017",
        step_id="s01",
        session_id="sess-123",
        diagnostic_codes=["ERR_01"],
        fingerprint="fp-001",
    )

    record = IncidentRecord(
        incident_id=inc_id,
        status="open",
        opened_at="2026-08-30T10:00:00Z",
        project_root="/tmp/proj",
        epic_id="T-HUB-017",
        step_id="s01",
        phase="BACK IMPLEMENT",
        session_id="sess-123",
        source="check_after",
        diagnostic_codes=["ERR_01"],
        fingerprint="fp-001",
    )

    appended = append_incident(epic_dir, record)
    assert appended.incident_id == inc_id

    open_incidents = list_open_incidents(epic_dir)
    assert len(open_incidents) == 1
    assert open_incidents[0].incident_id == inc_id
    assert open_incidents[0].status == "open"

    # Resolve incident
    resolved = resolve_incident(
        epic_dir,
        inc_id,
        resolution_tier="tier0",
        resolution_action="retry_successful",
        resolved_at="2026-08-30T10:05:00Z",
    )
    assert resolved is not None
    assert resolved.status == "resolved"
    assert resolved.resolution_tier == "tier0"
    assert resolved.resolution_action == "retry_successful"

    assert len(list_open_incidents(epic_dir)) == 0


def test_idempotency_same_fingerprint_session_updates_not_duplicates(tmp_path: Path):
    epic_dir = tmp_path / "epic_slot"
    inc_id = compute_incident_id(
        project_root="/tmp/proj",
        epic_id="T-HUB-017",
        step_id="s01",
        session_id="sess-123",
        diagnostic_codes=["ERR_01"],
        fingerprint="fp-001",
    )

    record1 = IncidentRecord(
        incident_id=inc_id,
        status="open",
        opened_at="2026-08-30T10:00:00Z",
        project_root="/tmp/proj",
        epic_id="T-HUB-017",
        step_id="s01",
        phase="BACK IMPLEMENT",
        session_id="sess-123",
        source="check_after",
        diagnostic_codes=["ERR_01"],
        fingerprint="fp-001",
        tier0_attempts=1,
    )

    append_incident(epic_dir, record1)

    record2 = IncidentRecord(
        incident_id=inc_id,
        status="open",
        opened_at="2026-08-30T10:01:00Z",
        project_root="/tmp/proj",
        epic_id="T-HUB-017",
        step_id="s01",
        phase="BACK IMPLEMENT",
        session_id="sess-123",
        source="check_after",
        diagnostic_codes=["ERR_01"],
        fingerprint="fp-001",
        tier0_attempts=1,
    )

    updated = append_incident(epic_dir, record2)
    assert updated.tier0_attempts == 2

    records_in_store = parse_incidents_jsonl(epic_dir / "incidents.jsonl")
    assert len(records_in_store) == 1
    assert records_in_store[0].tier0_attempts == 2


def test_corrupt_jsonl_raises_or_returns_fail_closed(tmp_path: Path):
    fixture_path = Path("loop/tests/fixtures/incidents/corrupt_incidents.jsonl")
    with pytest.raises(CorruptIncidentError) as exc_info:
        parse_incidents_jsonl(fixture_path)

    assert "Line content" in str(exc_info.value) or "invalid JSON" in str(exc_info.value)


def test_resolve_all_open_incidents(tmp_path: Path):
    from loop.incidents.store import resolve_all_open_incidents

    epic_dir = tmp_path / "epic"
    epic_dir.mkdir()
    open_a = IncidentRecord(
        incident_id="aaa",
        status="open",
        opened_at="2026-08-31T10:00:00Z",
        project_root="/tmp/proj",
        epic_id="T-HUB-033",
        step_id="s04",
        phase="AUDIT",
        session_id="sess-1",
        source="check_after",
        diagnostic_codes=["finish_integrity_decompose_missing"],
        fingerprint="fp-a",
    )
    closed_b = {
        "schema": "loop-incident/v1",
        "incident_id": "bbb",
        "status": "resolved",
        "opened_at": "2026-08-31T09:00:00Z",
        "resolved_at": "2026-08-31T09:30:00Z",
        "project_root": "/tmp/proj",
        "epic_id": "T-HUB-033",
        "step_id": "s01",
        "phase": "IMPLEMENT",
        "session_id": "sess-0",
        "source": "check_after",
        "diagnostic_codes": ["stale_owner"],
        "fingerprint": "fp-b",
        "tier0_attempts": 0,
        "tier0_repair_log": [],
        "resolution_tier": "tier0",
        "resolution_action": "clear_stale_runner_lock",
        "metadata": {},
    }
    append_incident(epic_dir, open_a)
    path = epic_dir / "incidents.jsonl"
    path.write_text(
        path.read_text(encoding="utf-8") + json.dumps(closed_b, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    cleared = resolve_all_open_incidents(epic_dir)
    assert len(cleared) == 1
    assert cleared[0].incident_id == "aaa"
    assert cleared[0].status == "resolved"
    assert cleared[0].resolution_tier == "loop_restart"
    assert cleared[0].resolved_at

    assert list_open_incidents(epic_dir) == []
    all_recs = parse_incidents_jsonl(path)
    assert len(all_recs) == 2
    assert {r.status for r in all_recs} == {"resolved"}
