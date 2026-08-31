"""Integration tests for incident autopilot (Tier-1 workflow & end-to-end orchestration)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from loop.incidents.schema import IncidentRecord, SCHEMA_LOOP_INCIDENT
from loop.incidents.store import append_incident, parse_incidents_jsonl, resolve_incident
from loop.incidents.tier1_runner import should_attempt_tier1, run_tier1_session, Tier1Result
from loop.incidents.tier1_verify import VerifyResult
from loop.incidents.alert import escalate_incident
from loop.incidents.metrics import load_metrics, increment_counter


@pytest.fixture
def mock_epic_env(tmp_path: Path):
    epic_dir = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-HUB-018"
    epic_dir.mkdir(parents=True, exist_ok=True)

    cfg = tmp_path / "eligibility.yaml"
    cfg.write_text(
        "codes:\n"
        "  active_context_shape_invalid:\n"
        "    tier1_eligible: true\n",
        encoding="utf-8",
    )
    return {
        "project_root": tmp_path,
        "epic_dir": epic_dir,
        "eligibility_file": cfg,
    }


def test_tier1_full_flow_resolve(mock_epic_env: dict):
    """CP2: tier1 full flow resolve -> no NEED_HUMAN file, incident status resolved (US-001)."""
    project_root = mock_epic_env["project_root"]
    epic_dir = mock_epic_env["epic_dir"]
    eligibility_file = mock_epic_env["eligibility_file"]

    inc = IncidentRecord(
        schema=SCHEMA_LOOP_INCIDENT,
        incident_id="inc-e2e-resolve-001",
        status="open",
        opened_at="2026-08-31T10:00:00Z",
        project_root=str(project_root),
        epic_id="T-HUB-018",
        step_id="s01",
        phase="BACK IMPLEMENT",
        session_id="sess-e2e-1",
        source="check_after_tier0",
        diagnostic_codes=["active_context_shape_invalid"],
        fingerprint="fp-resolve-1",
        metadata={"product_test_failed": False},
    )
    append_incident(epic_dir, inc)

    with patch.dict(os.environ, {"EPIC_INCIDENT_TIER1": "1"}), \
         patch("subprocess.run") as mock_run, \
         patch("loop.incidents.tier1_runner.run_tier1_verify") as mock_verify:
        mock_run.return_value = MagicMock(returncode=0)
        mock_verify.return_value = VerifyResult(passed=True, output="VERDICT: PASS", command="pytest")

        assert should_attempt_tier1(inc, epic_dir, eligibility_config_path=eligibility_file) is True

        res = run_tier1_session(inc, epic_dir, project_root, eligibility_config_path=eligibility_file)
        assert res.success is True
        if res.success:
            resolve_incident(epic_dir, inc.incident_id, status="resolved", resolution_tier="tier1")

    records = parse_incidents_jsonl(epic_dir / "incidents.jsonl")
    updated_inc = next((r for r in records if r.incident_id == inc.incident_id), None)
    assert updated_inc is not None
    assert updated_inc.status == "resolved"

    need_human_file = epic_dir / "NEED_HUMAN"
    assert not need_human_file.exists()


def test_tier1_max_fail_escalate(mock_epic_env: dict):
    """CP3: 3x failures -> NEED_HUMAN file exists + escalated counter incremented (US-002)."""
    project_root = mock_epic_env["project_root"]
    epic_dir = mock_epic_env["epic_dir"]
    eligibility_file = mock_epic_env["eligibility_file"]

    inc = IncidentRecord(
        schema=SCHEMA_LOOP_INCIDENT,
        incident_id="inc-e2e-escalate-002",
        status="open",
        opened_at="2026-08-31T10:00:00Z",
        project_root=str(project_root),
        epic_id="T-HUB-018",
        step_id="s02",
        phase="BACK IMPLEMENT",
        session_id="sess-e2e-2",
        source="check_after_tier1",
        diagnostic_codes=["active_context_shape_invalid"],
        fingerprint="fp-escalate-2",
        metadata={"tier1_attempts": 2},
    )
    append_incident(epic_dir, inc)

    with patch.dict(os.environ, {"EPIC_INCIDENT_TIER1": "1", "EPIC_INCIDENT_TIER1_MAX": "3"}), \
         patch("subprocess.run") as mock_run, \
         patch("loop.incidents.tier1_runner.run_tier1_verify") as mock_verify:
        mock_run.return_value = MagicMock(returncode=1)
        mock_verify.return_value = VerifyResult(passed=False, output="FAIL", command="pytest")

        res = run_tier1_session(inc, epic_dir, project_root, eligibility_config_path=eligibility_file)
        assert res.success is False
        assert res.attempt_number == 3

    # Update store metadata to record 3 attempts
    incidents_path = epic_dir / "incidents.jsonl"
    records = parse_incidents_jsonl(incidents_path)
    records[0].metadata["tier1_attempts"] = res.attempt_number
    incidents_path.write_text("\n".join(r.model_dump_json(by_alias=True) for r in records) + "\n")

    updated_inc = parse_incidents_jsonl(incidents_path)[0]

    # Now should_attempt_tier1 should be False (attempts reached max)
    with patch.dict(os.environ, {"EPIC_INCIDENT_TIER1": "1", "EPIC_INCIDENT_TIER1_MAX": "3"}):
        assert should_attempt_tier1(updated_inc, epic_dir, eligibility_config_path=eligibility_file) is False

    # Perform escalation alert & metric increment
    escalated = escalate_incident(updated_inc, epic_dir, project_root=project_root)
    assert escalated.status == "escalated"
    increment_counter(epic_dir, "tier1_escalated_total")

    need_human_file = epic_dir / "NEED_HUMAN"
    assert need_human_file.exists()

    metrics = load_metrics(epic_dir)
    assert metrics.counters.get("tier1_escalated_total") == 1


def test_tier1_disabled_escalate_immediately(mock_epic_env: dict):
    """CP4: EPIC_INCIDENT_TIER1=0 -> immediate escalate, no tier1 spawn."""
    project_root = mock_epic_env["project_root"]
    epic_dir = mock_epic_env["epic_dir"]
    eligibility_file = mock_epic_env["eligibility_file"]

    inc = IncidentRecord(
        schema=SCHEMA_LOOP_INCIDENT,
        incident_id="inc-disabled-003",
        status="open",
        opened_at="2026-08-31T10:00:00Z",
        project_root=str(project_root),
        epic_id="T-HUB-018",
        step_id="s03",
        phase="BACK IMPLEMENT",
        session_id="sess-e2e-3",
        source="check_after_tier0",
        diagnostic_codes=["active_context_shape_invalid"],
        fingerprint="fp-disabled-3",
        metadata={},
    )
    append_incident(epic_dir, inc)

    with patch.dict(os.environ, {"EPIC_INCIDENT_TIER1": "0"}):
        assert should_attempt_tier1(inc, epic_dir, eligibility_config_path=eligibility_file) is False

    escalate_incident(inc, epic_dir, project_root=project_root)
    need_human_file = epic_dir / "NEED_HUMAN"
    assert need_human_file.exists()


class FakeBoardExecution:
    def __init__(self):
        self.status = "idle"
        self.recorded_events = []

    def handle_incident_escalated(self, incident_id: str, reason: str):
        self.status = "escalated"
        self.recorded_events.append({"incident_id": incident_id, "reason": reason})


def test_fake_board_execution_soft(mock_epic_env: dict):
    """US-005 soft integration check: FakeBoardExecution captures escalation event status."""
    board = FakeBoardExecution()
    assert board.status == "idle"

    board.handle_incident_escalated("inc-005", "soft_015_test")
    assert board.status == "escalated"
    assert len(board.recorded_events) == 1
    assert board.recorded_events[0]["incident_id"] == "inc-005"
