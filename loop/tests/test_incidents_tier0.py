"""Tests for loop.incidents.tier0 and registry loading."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

import pytest

from loop.incidents.registry import load_registry, get_chain, resolve_callable
from loop.incidents.schema import IncidentRecord, compute_incident_id
from loop.incidents.store import append_incident, list_open_incidents
from loop.incidents.tier0 import run_tier0_for_incident, Tier0Result
from epic_paths import epic_dir


def _incidents_slot(tmp_path: Path) -> Path:
    return epic_dir(tmp_path)


def test_registry_loads_seven_codes():
    reg = load_registry()
    assert len(reg) >= 7
    expected_codes = {
        "mark_index_missing",
        "fingerprint_stall",
        "index_mirror_drift",
        "premature_epic_done",
        "stale_owner",
        "checkpoint_drift",
        "active_context_shape_invalid",
    }
    assert expected_codes.issubset(set(reg.keys()))


def test_resolve_repair_fn_imports_epic_core_symbol():
    func = resolve_callable("epic.core.repair_finish_desync")
    assert callable(func)


def test_tier0_unknown_diagnostic_no_repair_incident_stays_open(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    inc_id = compute_incident_id(str(tmp_path), "epic1", "s01", "sess1", ["unknown_code"], "fp1")
    incident = IncidentRecord(
        schema="loop-incident/v1",
        incident_id=inc_id,
        opened_at="2026-08-30T12:00:00Z",
        project_root=str(tmp_path),
        epic_id="epic1",
        step_id="s01",
        phase="IMPLEMENT",
        session_id="sess1",
        source="check_after",
        diagnostic_codes=["unknown_code"],
        fingerprint="fp1",
    )
    appended = append_incident(_incidents_slot(tmp_path), incident)

    res = run_tier0_for_incident(tmp_path, incident)
    assert res.attempted is False
    assert res.resolved is False
    assert res.repair_exhausted is False

    open_incidents = list_open_incidents(_incidents_slot(tmp_path))
    assert len(open_incidents) == 1
    assert open_incidents[0].incident_id == appended.incident_id


def test_tier0_max_attempts_sets_repair_exhausted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    inc_id = compute_incident_id(str(tmp_path), "epic1", "s01", "sess1", ["active_context_shape_invalid"], "fp1")
    incident = IncidentRecord(
        schema="loop-incident/v1",
        incident_id=inc_id,
        opened_at="2026-08-30T12:00:00Z",
        project_root=str(tmp_path),
        epic_id="epic1",
        step_id="s01",
        phase="IMPLEMENT",
        session_id="sess1",
        source="check_after",
        diagnostic_codes=["active_context_shape_invalid"],
        fingerprint="fp1",
    )
    append_incident(_incidents_slot(tmp_path), incident)

    res = run_tier0_for_incident(tmp_path, incident)
    assert res.attempted is True
    assert res.resolved is False
    assert res.repair_exhausted is True


def test_stale_owner_repair_clear_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    from _lib import write_runner_owner, RunnerOwner
    from epic_paths import epic_dir as epic_runtime_dir

    runtime_dir = epic_runtime_dir(tmp_path)
    owner_path = runtime_dir / "runner.json"
    lock_path = runtime_dir / "runner.lock"

    # Dead PID 999999
    owner = RunnerOwner(
        pid=999999,
        host="localhost",
        started_at="2026-08-30T12:00:00Z",
        session_id="sess1",
        selected_identity="test",
        mode="test",
        model="test",
        timeout_config={},
    )
    write_runner_owner(owner_path, owner)
    lock_path.write_text("lock")

    inc_id = compute_incident_id(str(tmp_path), "epic1", "s01", "sess1", ["stale_owner"], "fp1")
    incident = IncidentRecord(
        schema="loop-incident/v1",
        incident_id=inc_id,
        opened_at="2026-08-30T12:00:00Z",
        project_root=str(tmp_path),
        epic_id="epic1",
        step_id="s01",
        phase="IMPLEMENT",
        session_id="sess1",
        source="check_after",
        diagnostic_codes=["stale_owner"],
        fingerprint="fp1",
    )
    append_incident(epic_runtime_dir(tmp_path), incident)

    res = run_tier0_for_incident(tmp_path, incident)
    assert res.attempted is True
    assert res.resolved is True
    assert res.repair_exhausted is False
    assert not owner_path.exists()
    assert not lock_path.exists()

    open_incidents = list_open_incidents(epic_runtime_dir(tmp_path))
    assert len(open_incidents) == 0


def test_tier0_mark_index_missing_resolves_incident(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    # Setup index and implement fixture
    decomp_dir = tmp_path / "memory-bank" / "back" / "plan" / "decompose-epic1"
    decomp_dir.mkdir(parents=True)
    decomp_path = decomp_dir / "s01-shard.yaml"
    (decomp_dir / "index.md").write_text("# Index\n")
    decomp_path.write_text("schema: epic-decompose/v1\nstep_id: s01\nplan_id: epic1\n")

    index_yaml = decomp_dir / "index.yaml"
    index_yaml.write_text("""schema: epic-index/v1
epic_id: epic1
plan_id: epic1
role: back
steps:
  - id: s01
    status: active
""")

    impl_dir = tmp_path / "memory-bank" / "back" / "implement" / "implement-epic1"
    impl_dir.mkdir(parents=True)
    impl_yaml = impl_dir / "s01.yaml"
    impl_yaml.write_text("""schema: epic-implement/v1
role: back
step_id: s01
plan_id: epic1
title: s01
date: '2026-08-30'
status: completed
checkpoints:
  - id: cp1
    criterion: c1
    status: done
""")

    inc_id = compute_incident_id(str(tmp_path), "epic1", "s01", "sess1", ["mark_index_missing"], "fp1")
    incident = IncidentRecord(
        schema="loop-incident/v1",
        incident_id=inc_id,
        opened_at="2026-08-30T12:00:00Z",
        project_root=str(tmp_path),
        epic_id="epic1",
        step_id="s01",
        phase="IMPLEMENT",
        session_id="sess1",
        source="check_after",
        diagnostic_codes=["mark_index_missing"],
        fingerprint="fp1",
    )
    append_incident(_incidents_slot(tmp_path), incident)

    res = run_tier0_for_incident(tmp_path, incident, decompose_path=decomp_path)
    assert res.attempted is True
    assert res.resolved is True

    # Implement shard status rolled back to in_progress
    import yaml
    data = yaml.safe_load(impl_yaml.read_text())
    assert data["status"] == "in_progress"

    open_incidents = list_open_incidents(_incidents_slot(tmp_path))
    assert len(open_incidents) == 0
