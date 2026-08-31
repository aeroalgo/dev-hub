"""Integration tests for Tier-0 wiring in check_after."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from loop.context_loop import check_after, save_epic_state
from loop.incidents.schema import IncidentRecord, compute_incident_id
from loop.incidents.store import parse_incidents_jsonl, list_open_incidents, resolve_incident


@pytest.fixture
def setup_epic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Set up basic epic directory structure for testing check_after tier0."""
    monkeypatch.delenv("PROJECT_ROOT", raising=False)
    monkeypatch.delenv("DEV_HUB", raising=False)
    monkeypatch.delenv("HUB_ROOT", raising=False)

    mb = tmp_path / "memory-bank"
    decomp_dir = mb / "back" / "plan" / "decompose-T-TEST-001"
    decomp_dir.mkdir(parents=True, exist_ok=True)

    # Decompose index.yaml
    index_yaml = decomp_dir / "index.yaml"
    index_yaml.write_text(
        "schema: epic-decompose/v1\nplan_id: T-TEST-001\nsteps:\n  - id: s01\n    title: step 1\n    status: in_progress\n",
        encoding="utf-8"
    )

    # Decompose file s01.yaml
    decomp_shard = decomp_dir / "s01.yaml"
    decomp_shard.write_text(
        "schema: epic-decompose/v1\nplan_id: T-TEST-001\nstep_id: s01\n",
        encoding="utf-8"
    )

    # Active context with valid shape
    ac = mb / "activeContext.md"
    ac.write_text(
        "---\nschema: loop-handoff/v1\nrole: BACK\nmode: IMPLEMENT\nepic_id: T-TEST-001\nstep_id: s01\n---\n\n"
        "## load_now\n1. [s01.yaml](back/plan/decompose-T-TEST-001/s01.yaml)\n\n## Handoff BACK IMPLEMENT — s01\n- step: s01\n",
        encoding="utf-8"
    )

    # Epic state
    state = {
        "active": True,
        "armed_decompose": str(decomp_shard),
        "armed_step": "s01",
        "epic_id": "T-TEST-001",
    }
    save_epic_state(tmp_path, state)

    return tmp_path


def test_check_after_opens_incident_on_halt(setup_epic: Path):
    """cp1: verify that when finish_integrity fails (e.g. mark_index_missing), check_after opens an incident."""
    tmp_path = setup_epic

    state = {
        "active": True,
        "epic_id": "T-TEST-001",
    }
    save_epic_state(tmp_path, state)

    # Active context with invalid shape to produce diagnostic code without inline repair resolving it first
    ac = tmp_path / "memory-bank" / "activeContext.md"
    ac.write_text("INVALID ACTIVE CONTEXT CONTENT WITHOUT SECTIONS\n", encoding="utf-8")

    res = check_after(tmp_path, fingerprint_before="diff_fp")

    assert res.get("halt") is True or res.get("degraded") is True
    assert "active_context_shape_invalid" in res.get("diagnostic_codes", [])

    from epic_paths import epic_dir

    incidents = parse_incidents_jsonl(epic_dir(tmp_path) / "incidents.jsonl")
    assert len(incidents) > 0
    inc = incidents[0]
    assert "active_context_shape_invalid" in inc.diagnostic_codes


def test_check_after_tier0_auto_continue_resolved(setup_epic: Path):
    """cp2: verify that if tier0 resolves incident, check_after returns ok:True continue with incidents_resolved."""
    tmp_path = setup_epic
    mb = tmp_path / "memory-bank"

    # Save clean epic state without armed_decompose to avoid decompose file validation
    state = {
        "active": True,
        "epic_id": "T-TEST-001",
    }
    save_epic_state(tmp_path, state)

    # Create stale runner owner file (PID 999999) to trigger stale_owner diagnostic & repair
    from epic_paths import epic_dir
    e_dir = epic_dir(tmp_path)
    owner_file = e_dir / "runner.json"
    owner_file.write_text(json.dumps({
        "pid": 999999,
        "host": "localhost",
        "session_id": "dead_session",
        "started_at": "2026-08-30T00:00:00Z",
        "selected_identity": "test",
        "mode": "test"
    }), encoding="utf-8")

    lock_file = e_dir / "runner.lock"
    lock_file.write_text("lock", encoding="utf-8")

    # Call check_after
    res = check_after(tmp_path, fingerprint_before="diff_fp")

    assert res["ok"] is True
    assert not owner_file.exists()
    assert res.get("incidents_resolved") is not None


def test_check_after_tier0_repair_exhausted_halts_with_flag(setup_epic: Path):
    """cp3: verify that if repair is exhausted / unable to repair, halt payload includes repair_exhausted: True."""
    tmp_path = setup_epic
    mb = tmp_path / "memory-bank"

    # Save clean epic state without armed_decompose
    state = {
        "active": True,
        "epic_id": "T-TEST-001",
    }
    save_epic_state(tmp_path, state)

    # Active context with invalid shape
    ac = mb / "activeContext.md"
    ac.write_text("INVALID ACTIVE CONTEXT CONTENT WITHOUT SECTIONS\n", encoding="utf-8")

    res = check_after(tmp_path, fingerprint_before="diff_fp")

    assert res.get("halt") is True
    assert res.get("repair_exhausted") is True
