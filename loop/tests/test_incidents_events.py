"""Unit tests for incident and repair event emission."""
from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest

HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from epic_events import read_event_log_result
from loop.incidents.events import (
    emit_incident_opened,
    emit_incident_resolved,
    emit_repair_applied,
)


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


def test_emit_repair_applied_appends_to_events_jsonl(setup_epic_dir: Path):
    res = emit_repair_applied(
        cwd=setup_epic_dir,
        epic_id="T-TEST-001",
        metadata={"repair_fn": "fix_func", "diagnostic_code": "code_1", "incident_id": "inc_123"},
    )
    assert res is True
    events_file = setup_epic_dir / "memory-bank" / "back" / "events" / "T-TEST-001" / "events.jsonl"
    assert events_file.is_file()

    stream = read_event_log_result(events_file, expected_epic_id="T-TEST-001", cwd=setup_epic_dir)
    assert len(stream.events) == 1
    event = stream.events[0]
    assert event["kind"] == "repair_applied"
    assert event["metadata"]["repair_fn"] == "fix_func"
    assert event["metadata"]["incident_id"] == "inc_123"


def test_emit_incident_opened_metadata(setup_epic_dir: Path):
    res = emit_incident_opened(
        cwd=setup_epic_dir,
        epic_id="T-TEST-001",
        metadata={"source": "check_after", "diagnostic_code": "code_2", "incident_id": "inc_456"},
    )
    assert res is True
    events_file = setup_epic_dir / "memory-bank" / "back" / "events" / "T-TEST-001" / "events.jsonl"
    stream = read_event_log_result(events_file, expected_epic_id="T-TEST-001", cwd=setup_epic_dir)
    assert len(stream.events) == 1
    event = stream.events[0]
    assert event["kind"] == "incident_opened"
    assert event["metadata"]["source"] == "check_after"


def test_emit_incident_resolved_metadata(setup_epic_dir: Path):
    res = emit_incident_resolved(
        cwd=setup_epic_dir,
        epic_id="T-TEST-001",
        metadata={"resolution_tier": "tier0", "incident_id": "inc_789"},
    )
    assert res is True
    events_file = setup_epic_dir / "memory-bank" / "back" / "events" / "T-TEST-001" / "events.jsonl"
    stream = read_event_log_result(events_file, expected_epic_id="T-TEST-001", cwd=setup_epic_dir)
    assert len(stream.events) == 1
    event = stream.events[0]
    assert event["kind"] == "incident_resolved"
    assert event["metadata"]["resolution_tier"] == "tier0"


def test_skip_emission_when_epic_id_unknown(tmp_path: Path):
    res = emit_repair_applied(cwd=tmp_path, epic_id=None)
    assert res is False
