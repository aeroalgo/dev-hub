"""Integration tests for Tier-0 wiring in check_after."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from loop.context_loop import check_after, save_epic_state


@pytest.fixture
def setup_epic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Set up basic epic directory structure for testing check_after tier0."""
    monkeypatch.delenv("PROJECT_ROOT", raising=False)
    monkeypatch.delenv("DEV_HUB", raising=False)
    monkeypatch.delenv("HUB_ROOT", raising=False)

    mb = tmp_path / "memory-bank"
    decomp_dir = mb / "back" / "plan" / "T-TEST-001" / "yaml"
    decomp_dir.mkdir(parents=True, exist_ok=True)

    # Decompose index.yaml
    index_yaml = decomp_dir / "decompose-index.yaml"
    index_yaml.write_text(
        "schema: epic-decompose-index/v1\nplan_id: T-TEST-001\nsteps:\n"
        "  - id: s01\n    file: steps/s01.yaml\n"
        "    title: step 1\n    status: active\n",
        encoding="utf-8"
    )

    # Decompose file s01.yaml
    decomp_shard = decomp_dir / "steps" / "s01.yaml"
    decomp_shard.parent.mkdir(parents=True, exist_ok=True)
    decomp_shard.write_text(
        "schema: epic-decompose/v1\nplan_id: T-TEST-001\nstep_id: s01\n",
        encoding="utf-8"
    )

    # Active context with valid shape
    ac = mb / "activeContext.md"
    ac.write_text(
        "---\nschema: loop-handoff/v1\nrole: BACK\nmode: IMPLEMENT\nepic_id: T-TEST-001\nstep_id: s01\n---\n\n"
        "## load_now\n1. [s01.yaml](back/plan/T-TEST-001/yaml/steps/s01.yaml)\n\n## Handoff BACK IMPLEMENT — s01\n- step: s01\n",
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
