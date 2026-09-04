"""Test session-start / arm_phase auto-scaffold (FR-016 / cp3)."""
import json
import subprocess
import sys
from pathlib import Path
import pytest
import yaml

from epic.core import save_epic_state, default_state
from loop.paths.epic_layout import resolve, EpicLayoutKind
from loop.epic_transition import arm_phase


def test_session_start_autoscaffold_valid_plan(tmp_path: Path):
    role = "back"
    epic_id = "T-AUTO-001"

    # Setup valid plan.yaml
    plan_yaml = resolve(role, epic_id, EpicLayoutKind.PLAN_YAML, project_root=tmp_path)
    plan_yaml.parent.mkdir(parents=True, exist_ok=True)
    plan_yaml.write_text(
        f"schema: epic-plan/v1\n"
        f"plan_id: {epic_id}\n"
        f"level: epic\n"
        f"title: Auto Scaffold Test\n"
        f"summary:\n"
        f"  step_count_floor: 2\n"
        f"  requirement_count: 2\n"
        f"requirements:\n"
        f"  - id: FR-001\n"
        f"    text: First req\n"
        f"  - id: FR-002\n"
        f"    text: Second req\n"
        f"outline_steps:\n"
        f"  - step_id: s01\n"
        f"    title: Step one\n"
        f"    maps_to: [FR-001]\n"
        f"  - step_id: s02\n"
        f"    title: Step two\n"
        f"    maps_to: [FR-002]\n",
        encoding="utf-8",
    )

    # Set state as armed for DECOMPOSE
    st = default_state()
    st.update(
        {
            "active": True,
            "status": "running",
            "armed_epic": epic_id,
            "role": role,
            "armed_step": "DECOMPOSE",
        }
    )
    save_epic_state(tmp_path, st)

    # Invoke session-start script
    session_start_py = Path(__file__).resolve().parents[1] / "session-start.py"
    proc = subprocess.run(
        [sys.executable, str(session_start_py)],
        input=json.dumps({"cwd": str(tmp_path)}),
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0

    # Verify decompose tree was created
    decomp_yaml = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=tmp_path)
    assert decomp_yaml.is_file()
    decomp_md = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_MD, project_root=tmp_path)
    assert decomp_md.is_file()

    s01_yaml = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_STEP, step_id="s01", step_slug="step-one", project_root=tmp_path)
    assert s01_yaml.is_file()
    s02_yaml = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_STEP, step_id="s02", step_slug="step-two", project_root=tmp_path)
    assert s02_yaml.is_file()


def test_session_start_autoscaffold_invalid_plan_fail_closed(tmp_path: Path):
    role = "back"
    epic_id = "T-AUTO-002"

    # Setup invalid plan.yaml (missing required fields / corrupt schema)
    plan_yaml = resolve(role, epic_id, EpicLayoutKind.PLAN_YAML, project_root=tmp_path)
    plan_yaml.parent.mkdir(parents=True, exist_ok=True)
    plan_yaml.write_text(
        f"schema: epic-plan/v1\n"
        f"plan_id: {epic_id}\n"
        f"corrupted_field: true\n",
        encoding="utf-8",
    )

    # Set state as armed for DECOMPOSE
    st = default_state()
    st.update(
        {
            "active": True,
            "status": "running",
            "armed_epic": epic_id,
            "role": role,
            "armed_step": "DECOMPOSE",
        }
    )
    save_epic_state(tmp_path, st)

    # Invoke session-start script
    session_start_py = Path(__file__).resolve().parents[1] / "session-start.py"
    proc = subprocess.run(
        [sys.executable, str(session_start_py)],
        input=json.dumps({"cwd": str(tmp_path)}),
        text=True,
        capture_output=True,
    )
    # Fail closed on invalid plan.yaml
    assert proc.returncode != 0

    # Ensure no partial decompose index was written
    decomp_yaml = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=tmp_path)
    assert not decomp_yaml.exists()


def test_arm_phase_autoscaffold_valid_plan(tmp_path: Path):
    role = "back"
    epic_id = "T-AUTO-003"

    plan_yaml = resolve(role, epic_id, EpicLayoutKind.PLAN_YAML, project_root=tmp_path)
    plan_yaml.parent.mkdir(parents=True, exist_ok=True)
    plan_yaml.write_text(
        f"schema: epic-plan/v1\n"
        f"plan_id: {epic_id}\n"
        f"level: epic\n"
        f"title: Auto Scaffold Arm Phase Test\n"
        f"summary:\n"
        f"  step_count_floor: 1\n"
        f"  requirement_count: 1\n"
        f"requirements:\n"
        f"  - id: FR-001\n"
        f"    text: First req\n"
        f"outline_steps:\n"
        f"  - step_id: s01\n"
        f"    title: Step one\n"
        f"    maps_to: [FR-001]\n",
        encoding="utf-8",
    )

    res = arm_phase(tmp_path, epic_id=epic_id, phase="DECOMPOSE", role=role)
    assert res.get("ok") is True

    decomp_yaml = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=tmp_path)
    assert decomp_yaml.is_file()
