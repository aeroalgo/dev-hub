"""Session-start / arm_phase must NOT autoscaffold decompose from plan.yaml (purged)."""
import json
import subprocess
import sys
from pathlib import Path

from epic.core import save_epic_state, default_state
from loop.paths.epic_layout import resolve, EpicLayoutKind
from loop.epic_transition import arm_phase


def test_session_start_no_autoscaffold_with_plan_md(tmp_path: Path):
    role = "back"
    epic_id = "T-AUTO-001"

    plan_md = resolve(role, epic_id, EpicLayoutKind.PLAN_MD, project_root=tmp_path)
    plan_md.parent.mkdir(parents=True, exist_ok=True)
    plan_md.write_text(
        "# Plan: Auto Scaffold Test\n\n"
        "## Requirements\n\n"
        "FR-001 First req\n"
        "FR-002 Second req\n",
        encoding="utf-8",
    )

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

    session_start_py = Path(__file__).resolve().parents[1] / "session-start.py"
    proc = subprocess.run(
        [sys.executable, str(session_start_py)],
        input=json.dumps({"cwd": str(tmp_path)}),
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0

    decomp_yaml = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=tmp_path)
    assert not decomp_yaml.exists()
    decomp_md = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_MD, project_root=tmp_path)
    assert not decomp_md.exists()


def test_session_start_no_scaffold_from_leftover_plan_yaml(tmp_path: Path):
    role = "back"
    epic_id = "T-AUTO-002"

    leftover = (
        tmp_path
        / "memory-bank"
        / role
        / "plan"
        / epic_id
        / "yaml"
        / "plan.yaml"
    )
    leftover.parent.mkdir(parents=True, exist_ok=True)
    leftover.write_text(
        "schema: epic-plan/v1\n"
        f"plan_id: {epic_id}\n"
        "requirements:\n"
        "  - id: FR-001\n"
        "outline_steps:\n"
        "  - step_id: s01\n"
        "    title: Step one\n"
        "    maps_to: [FR-001]\n",
        encoding="utf-8",
    )

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

    session_start_py = Path(__file__).resolve().parents[1] / "session-start.py"
    proc = subprocess.run(
        [sys.executable, str(session_start_py)],
        input=json.dumps({"cwd": str(tmp_path)}),
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0

    decomp_yaml = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=tmp_path)
    assert not decomp_yaml.exists()


def test_arm_phase_no_autoscaffold(tmp_path: Path):
    role = "back"
    epic_id = "T-AUTO-003"

    plan_md = resolve(role, epic_id, EpicLayoutKind.PLAN_MD, project_root=tmp_path)
    plan_md.parent.mkdir(parents=True, exist_ok=True)
    plan_md.write_text("# Plan\n\nFR-001 First req\n", encoding="utf-8")

    res = arm_phase(tmp_path, epic_id=epic_id, phase="DECOMPOSE", role=role)
    assert res.get("ok") is True

    decomp_yaml = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=tmp_path)
    assert not decomp_yaml.exists()
