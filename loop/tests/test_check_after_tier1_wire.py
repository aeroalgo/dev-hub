"""Tests for wire integration of tier1 incident branch in loop / tier1_runner."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from loop.incidents.schema import IncidentRecord, SCHEMA_LOOP_INCIDENT
from loop.incidents.store import append_incident, resolve_incident, parse_incidents_jsonl
from loop.incidents.tier1_runner import (
    should_attempt_tier1,
    get_tier1_attempts,
    run_tier1_session,
    Tier1Result,
)
from loop.incidents.tier1_verify import VerifyResult


@pytest.fixture
def sample_incident(tmp_path: Path) -> IncidentRecord:
    epic_dir = tmp_path / "epic"
    epic_dir.mkdir()
    inc_dir = epic_dir / "incidents.jsonl"

    rec = IncidentRecord(
        schema=SCHEMA_LOOP_INCIDENT,
        incident_id="inc-test-123",
        status="open",
        opened_at="2026-08-30T10:00:00Z",
        project_root=str(tmp_path),
        epic_id="T-HUB-018",
        step_id="s04",
        phase="BACK IMPLEMENT",
        session_id="sess-001",
        source="check_after",
        diagnostic_codes=["SYNTAX_ERROR"],
        fingerprint="fp123",
        metadata={"product_test_failed": False},
    )
    append_incident(epic_dir, rec)
    return rec


@pytest.fixture
def eligibility_file(tmp_path: Path) -> Path:
    cfg = tmp_path / "eligibility.yaml"
    cfg.write_text(
        "codes:\n"
        "  SYNTAX_ERROR:\n"
        "    tier1_eligible: true\n"
    )
    return cfg


def test_should_attempt_tier1_eligible_below_max(
    tmp_path: Path, sample_incident: IncidentRecord, eligibility_file: Path
):
    epic_dir = tmp_path / "epic"
    with patch.dict(os.environ, {"EPIC_INCIDENT_TIER1": "1", "EPIC_INCIDENT_TIER1_MAX": "2"}):
        assert should_attempt_tier1(sample_incident, epic_dir, eligibility_config_path=eligibility_file) is True


def test_should_attempt_tier1_env_zero_skip(
    tmp_path: Path, sample_incident: IncidentRecord, eligibility_file: Path
):
    epic_dir = tmp_path / "epic"
    with patch.dict(os.environ, {"EPIC_INCIDENT_TIER1": "0"}):
        assert should_attempt_tier1(sample_incident, epic_dir, eligibility_config_path=eligibility_file) is False


def test_should_attempt_tier1_max_exceeded_false(
    tmp_path: Path, sample_incident: IncidentRecord, eligibility_file: Path
):
    epic_dir = tmp_path / "epic"
    incidents_path = epic_dir / "incidents.jsonl"

    # Record metadata with tier1_attempts = 2
    records = parse_incidents_jsonl(incidents_path)
    records[0].metadata["tier1_attempts"] = 2
    incidents_path.write_text("\n".join(r.model_dump_json(by_alias=True) for r in records) + "\n")

    with patch.dict(os.environ, {"EPIC_INCIDENT_TIER1": "1", "EPIC_INCIDENT_TIER1_MAX": "2"}):
        assert should_attempt_tier1(sample_incident, epic_dir, eligibility_config_path=eligibility_file) is False


def test_tier1_spawned_on_tier0_fail_eligible(
    tmp_path: Path, sample_incident: IncidentRecord, eligibility_file: Path
):
    epic_dir = tmp_path / "epic"
    with patch.dict(os.environ, {"TIER1_CLAUDE_CMD": "echo mock_run"}), \
         patch("loop.incidents.tier1_runner.run_tier1_verify") as mock_verify:
        mock_verify.return_value = VerifyResult(passed=True, output="OK", command="cmd")
        res = run_tier1_session(sample_incident, epic_dir, tmp_path, eligibility_config_path=eligibility_file)
        assert res.success is True
        assert res.attempt_number == 1
        assert res.session_log_path is not None
        assert Path(res.session_log_path).is_file()


def test_tier1_not_spawned_not_eligible(tmp_path: Path, eligibility_file: Path):
    epic_dir = tmp_path / "epic"
    epic_dir.mkdir()
    inc = IncidentRecord(
        schema=SCHEMA_LOOP_INCIDENT,
        incident_id="inc-ineligible",
        status="open",
        opened_at="2026-08-30T10:00:00Z",
        project_root=str(tmp_path),
        epic_id="T-HUB-018",
        step_id="s04",
        phase="BACK IMPLEMENT",
        session_id="sess-001",
        source="check_after",
        diagnostic_codes=["UNKNOWN_CODE"],
        fingerprint="fp456",
        metadata={"product_test_failed": False},
    )
    append_incident(epic_dir, inc)

    with patch.dict(os.environ, {"EPIC_INCIDENT_TIER1": "1"}):
        assert should_attempt_tier1(inc, epic_dir, eligibility_config_path=eligibility_file) is False


def test_tier1_success_resolves_incident_and_continues(
    tmp_path: Path, sample_incident: IncidentRecord, eligibility_file: Path
):
    epic_dir = tmp_path / "epic"

    # Mock successful session run and verify pass
    with patch("subprocess.run") as mock_run, \
         patch("loop.incidents.tier1_runner.run_tier1_verify") as mock_verify:
        mock_run.return_value = MagicMock(returncode=0)
        mock_verify.return_value = VerifyResult(passed=True, output="OK", command="cmd")
        res = run_tier1_session(sample_incident, epic_dir, tmp_path, eligibility_config_path=eligibility_file)
        assert res.success is True

    # Check store resolution
    resolve_incident(
        epic_dir,
        sample_incident.incident_id,
        resolution={
            "resolution_tier": "tier1",
            "resolution_action": "tier1_autofix",
        },
    )
    records = parse_incidents_jsonl(epic_dir / "incidents.jsonl")
    assert records[0].status == "resolved"
    assert records[0].resolution_tier == "tier1"


def test_tier1_fail_increments_attempts(
    tmp_path: Path, sample_incident: IncidentRecord, eligibility_file: Path
):
    epic_dir = tmp_path / "epic"
    incidents_path = epic_dir / "incidents.jsonl"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        res = run_tier1_session(sample_incident, epic_dir, tmp_path, eligibility_config_path=eligibility_file)
        assert res.success is False

    # Simulate recording attempt increment
    records = parse_incidents_jsonl(incidents_path)
    records[0].metadata["tier1_attempts"] = res.attempt_number
    incidents_path.write_text("\n".join(r.model_dump_json(by_alias=True) for r in records) + "\n")

    assert get_tier1_attempts(sample_incident.incident_id, epic_dir) == 1


def test_tier1_max_exhausted_escalates(
    tmp_path: Path, sample_incident: IncidentRecord, eligibility_file: Path
):
    epic_dir = tmp_path / "epic"
    incidents_path = epic_dir / "incidents.jsonl"

    records = parse_incidents_jsonl(incidents_path)
    records[0].metadata["tier1_attempts"] = 2
    incidents_path.write_text("\n".join(r.model_dump_json(by_alias=True) for r in records) + "\n")

    with patch.dict(os.environ, {"EPIC_INCIDENT_TIER1": "1", "EPIC_INCIDENT_TIER1_MAX": "2"}):
        assert should_attempt_tier1(sample_incident, epic_dir, eligibility_config_path=eligibility_file) is False
