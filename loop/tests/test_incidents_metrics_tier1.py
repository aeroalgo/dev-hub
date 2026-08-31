"""Unit tests for Tier-1 incident metrics and lifecycle event emissions."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from epic_events import read_event_log_result
from loop.incidents.events import (
    emit_event,
    emit_tier1_spawn,
    emit_tier1_verify_pass,
    emit_tier1_verify_fail,
    emit_tier1_escalated,
    TIER1_SPAWN,
    TIER1_VERIFY_PASS,
    TIER1_VERIFY_FAIL,
    TIER1_ESCALATED,
)
from loop.incidents.metrics import load_metrics, increment_counter, VALID_COUNTERS
from loop.incidents.schema import IncidentRecord
from loop.incidents.tier1_runner import run_tier1_session
from loop.incidents.tier1_verify import VerifyResult


@pytest.fixture
def setup_epic_dir(tmp_path: Path):
    mb = tmp_path / "memory-bank"
    decomp_dir = mb / "back" / "plan" / "decompose-T-TEST-001"
    decomp_dir.mkdir(parents=True, exist_ok=True)
    index_yaml = decomp_dir / "index.yaml"
    index_yaml.write_text(
        "schema: epic-decompose/v1\nplan_id: T-TEST-001\nsteps:\n  - id: s01\n    title: step 1\n    status: in_progress\n",
        encoding="utf-8"
    )
    decomp_shard = decomp_dir / "s01.yaml"
    decomp_shard.write_text(
        "schema: epic-decompose/v1\nplan_id: T-TEST-001\nstep_id: s01\n",
        encoding="utf-8"
    )
    ac = mb / "activeContext.md"
    ac.write_text(
        "---\nschema: loop-handoff/v1\nrole: BACK\nmode: IMPLEMENT\nepic_id: T-TEST-001\nstep_id: s01\n---\n\n"
        "## load_now\n1. [s01.yaml](back/plan/decompose-T-TEST-001/s01.yaml)\n\n## Handoff BACK IMPLEMENT — s01\n- step: s01\n",
        encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def sample_incident(tmp_path: Path) -> IncidentRecord:
    epic_dir = tmp_path / "epic"
    epic_dir.mkdir(parents=True, exist_ok=True)
    return IncidentRecord(
        schema="loop-incident/v1",
        incident_id="inc_t1_123",
        epic_id="T-TEST-001",
        step_id="s01",
        phase="BACK IMPLEMENT",
        session_id="sess-001",
        source="check_after",
        diagnostic_codes=["SYNTAX_ERROR"],
        runbook_rel="docs/runbooks/syntax_error.md",
        opened_at="2026-08-30T12:00:00Z",
        project_root=str(tmp_path),
        status="open",
        fingerprint="fp123",
        metadata={"product_test_failed": False},
    )


def test_tier1_spawn_event_written_to_jsonl(setup_epic_dir: Path):
    res = emit_tier1_spawn(
        cwd=setup_epic_dir,
        incident_id="inc_t1_123",
        attempt_number=1,
        metadata={"diagnostic_codes": ["SYNTAX_ERROR"]},
        epic_id="T-TEST-001",
    )
    assert res is True
    events_file = setup_epic_dir / "memory-bank" / "back" / "events" / "T-TEST-001" / "events.jsonl"
    assert events_file.is_file()

    stream = read_event_log_result(events_file, expected_epic_id="T-TEST-001", cwd=setup_epic_dir)
    assert len(stream.events) == 1
    event = stream.events[0]
    assert event["kind"] == TIER1_SPAWN
    assert event["metadata"]["incident_id"] == "inc_t1_123"
    assert event["metadata"]["attempt_number"] == 1


def test_tier1_verify_pass_event(setup_epic_dir: Path):
    res = emit_tier1_verify_pass(
        cwd=setup_epic_dir,
        incident_id="inc_t1_123",
        attempt_number=1,
        epic_id="T-TEST-001",
    )
    assert res is True
    events_file = setup_epic_dir / "memory-bank" / "back" / "events" / "T-TEST-001" / "events.jsonl"
    stream = read_event_log_result(events_file, expected_epic_id="T-TEST-001", cwd=setup_epic_dir)
    assert len(stream.events) == 1
    assert stream.events[0]["kind"] == TIER1_VERIFY_PASS


def test_tier1_verify_fail_event(setup_epic_dir: Path):
    res = emit_tier1_verify_fail(
        cwd=setup_epic_dir,
        incident_id="inc_t1_123",
        attempt_number=1,
        epic_id="T-TEST-001",
    )
    assert res is True
    events_file = setup_epic_dir / "memory-bank" / "back" / "events" / "T-TEST-001" / "events.jsonl"
    stream = read_event_log_result(events_file, expected_epic_id="T-TEST-001", cwd=setup_epic_dir)
    assert len(stream.events) == 1
    assert stream.events[0]["kind"] == TIER1_VERIFY_FAIL


def test_tier1_escalated_event(setup_epic_dir: Path):
    res = emit_tier1_escalated(
        cwd=setup_epic_dir,
        incident_id="inc_t1_123",
        attempt_number=2,
        epic_id="T-TEST-001",
    )
    assert res is True
    events_file = setup_epic_dir / "memory-bank" / "back" / "events" / "T-TEST-001" / "events.jsonl"
    stream = read_event_log_result(events_file, expected_epic_id="T-TEST-001", cwd=setup_epic_dir)
    assert len(stream.events) == 1
    assert stream.events[0]["kind"] == TIER1_ESCALATED


def test_verify_pass_increments_resolved(tmp_path: Path):
    epic_dir = tmp_path / "epic"
    epic_dir.mkdir(parents=True, exist_ok=True)
    increment_counter(epic_dir, "tier1_resolved_total")
    metrics = load_metrics(epic_dir)
    assert metrics.counters["tier1_resolved_total"] == 1


def test_tier1_resolved_total_increments(tmp_path: Path):
    epic_dir = tmp_path / "epic"
    epic_dir.mkdir(parents=True, exist_ok=True)
    increment_counter(epic_dir, "tier1_resolved_total")
    metrics = load_metrics(epic_dir)
    assert metrics.counters["tier1_resolved_total"] == 1


def test_escalated_increments_counter(tmp_path: Path):
    epic_dir = tmp_path / "epic"
    epic_dir.mkdir(parents=True, exist_ok=True)
    increment_counter(epic_dir, "tier1_escalated_total")
    metrics = load_metrics(epic_dir)
    assert metrics.counters["tier1_escalated_total"] == 1


def test_tier1_escalated_total_increments(tmp_path: Path):
    epic_dir = tmp_path / "epic"
    epic_dir.mkdir(parents=True, exist_ok=True)
    increment_counter(epic_dir, "tier1_escalated_total")
    metrics = load_metrics(epic_dir)
    assert metrics.counters["tier1_escalated_total"] == 1


def test_payload_no_secrets(setup_epic_dir: Path):
    res = emit_tier1_spawn(
        cwd=setup_epic_dir,
        incident_id="inc_t1_999",
        attempt_number=1,
        metadata={
            "prompt": "secret prompt text",
            "token": "sk-secret-12345",
            "api_key": "secret_key_abc",
            "safe_field": "ok_value",
        },
        epic_id="T-TEST-001",
    )
    assert res is True
    events_file = setup_epic_dir / "memory-bank" / "back" / "events" / "T-TEST-001" / "events.jsonl"
    stream = read_event_log_result(events_file, expected_epic_id="T-TEST-001", cwd=setup_epic_dir)
    assert len(stream.events) == 1
    metadata = stream.events[0]["metadata"]
    assert "prompt" not in metadata
    assert "token" not in metadata
    assert "api_key" not in metadata
    assert metadata.get("safe_field") == "ok_value"


def test_event_payload_no_secrets_no_prompt(setup_epic_dir: Path):
    test_payload_no_secrets(setup_epic_dir)


def test_run_tier1_session_emits_events_and_metrics(setup_epic_dir: Path, sample_incident: IncidentRecord):
    epic_dir = setup_epic_dir / "epic"
    epic_dir.mkdir(parents=True, exist_ok=True)
    inc_path = epic_dir / "incidents.jsonl"
    inc_path.write_text(sample_incident.model_dump_json(by_alias=True) + "\n", encoding="utf-8")

    with patch("subprocess.run") as mock_run, \
         patch("loop.incidents.tier1_runner.run_tier1_verify") as mock_verify, \
         patch.dict(os.environ, {"EPIC_INCIDENT_TIER1": "1"}):

        mock_run.return_value = MagicMock(returncode=0)
        mock_verify.return_value = VerifyResult(passed=True, output="OK", command="pytest")

        res = run_tier1_session(sample_incident, epic_dir, setup_epic_dir)
        assert res.success is True

        metrics = load_metrics(epic_dir)
        assert metrics.counters.get("tier1_attempts_total") == 1
        assert metrics.counters.get("tier1_resolved_total") == 1
