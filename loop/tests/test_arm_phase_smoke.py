"""Smoke and characterization tests for arm_phase and lifecycle transition engine."""

import json
from pathlib import Path
from unittest.mock import patch
import pytest

from loop.epic_transition import arm_phase, normalize_registry_phase, get_phase_config
from loop.paths.epic_layout import resolve, EpicLayoutKind


def test_arm_phase_v2_layout_epic(tmp_path: Path):
    role = "back"
    epic_id = "T-SMOKE-001"

    # Setup v2 layout directories and files
    decomp_yaml = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=tmp_path)
    decomp_yaml.parent.mkdir(parents=True, exist_ok=True)
    decomp_yaml.write_text(
        "schema: epic-decompose-index/v1\n"
        "role: back\n"
        "plan_id: T-SMOKE-001\n"
        "steps:\n"
        "  - id: s01\n"
        "    title: Step 1\n"
        "    status: pending\n",
        encoding="utf-8",
    )

    plan_md = resolve(role, epic_id, EpicLayoutKind.PLAN_MD, project_root=tmp_path)
    plan_md.parent.mkdir(parents=True, exist_ok=True)
    plan_md.write_text("# Plan\n\nFR-001 smoke requirement\n", encoding="utf-8")

    step_yaml = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_STEP, step_id="s01", step_slug="init", project_root=tmp_path)
    step_yaml.parent.mkdir(parents=True, exist_ok=True)
    step_yaml.write_text(
        "schema: epic-decompose/v1\n"
        "role: back\n"
        "step_id: s01\n"
        "plan_id: T-SMOKE-001\n"
        "title: Step 1\n",
        encoding="utf-8",
    )

    # Arm phase IMPLEMENT
    res = arm_phase(tmp_path, epic_id, "IMPLEMENT", role)
    assert res.get("ok") is True or res.get("armed_step") is not None

    # Check state.json updated
    from harness.hooks.epic_paths import state_path
    state_file = state_path(tmp_path)
    assert state_file.exists()

    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state.get("armed_epic") == epic_id


def test_arm_epic_v2_finds_plan_and_yaml_steps(tmp_path: Path):
    import sys
    from pathlib import Path as P

    hooks = P(__file__).resolve().parents[2] / ".claude" / "hooks"
    if str(hooks) not in sys.path:
        sys.path.insert(0, str(hooks))
    from epic.core import arm_epic

    role = "back"
    epic_id = "T-HUB-047-harness-mb-scaffold-epic-layout"
    plan_md = resolve(role, epic_id, EpicLayoutKind.PLAN_MD, project_root=tmp_path)
    plan_md.parent.mkdir(parents=True, exist_ok=True)
    plan_md.write_text("# Plan\n", encoding="utf-8")

    idx = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=tmp_path)
    idx.parent.mkdir(parents=True, exist_ok=True)
    idx.write_text(
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic_id}\n"
        "steps:\n"
        "  - id: s09\n"
        "    file: s09-formula-render-merge.yaml\n"
        "    title: prior\n"
        "    next_phase: BACK IMPLEMENT\n"
        "    status: completed\n"
        "  - id: s10\n"
        "    file: s10-migrate-apply-dev-hub.yaml\n"
        "    title: migrate apply\n"
        "    next_phase: BACK IMPLEMENT\n"
        "    status: pending\n",
        encoding="utf-8",
    )
    md_idx = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_MD, project_root=tmp_path)
    md_idx.parent.mkdir(parents=True, exist_ok=True)
    md_idx.write_text("# index\n", encoding="utf-8")

    step9 = resolve(
        role,
        epic_id,
        EpicLayoutKind.DECOMPOSE_STEP,
        step_id="s09",
        step_slug="formula-render-merge",
        project_root=tmp_path,
    )
    step9.parent.mkdir(parents=True, exist_ok=True)
    step9.write_text(
        "schema: epic-decompose/v1\nstep_id: s09\nstatus: completed\n",
        encoding="utf-8",
    )

    step = resolve(
        role,
        epic_id,
        EpicLayoutKind.DECOMPOSE_STEP,
        step_id="s10",
        step_slug="migrate-apply-dev-hub",
        project_root=tmp_path,
    )
    step.parent.mkdir(parents=True, exist_ok=True)
    step.write_text(
        "schema: epic-decompose/v1\n"
        "step_id: s10\n"
        f"plan_id: {epic_id}\n"
        "title: migrate\n",
        encoding="utf-8",
    )

    res = arm_epic(tmp_path, epic_id, role=role)
    assert res.get("ok") is True
    assert res.get("step_id") == "s10"
    assert "yaml/steps/s10-migrate-apply-dev-hub.yaml" in str(res.get("work_shard") or "")
    ac = (tmp_path / "memory-bank" / "activeContext.md").read_text(encoding="utf-8")
    assert "step_id: s10" in ac
    assert "yaml/steps/s10-migrate-apply-dev-hub.yaml" in ac
    assert "plan-T-HUB-047" not in ac


def test_arm_phase_pre_implement_phases_characterization(tmp_path: Path):
    """Characterize arm_phase for pre-implement lifecycle phases: PLAN, DECOMPOSE, ANALYZE, CREATIVE, CLARIFY."""
    epic_id = "T-CHAR-001"
    role = "back"

    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / f"plan-{epic_id}.md"
    plan_file.write_text("# Plan\nFR-001 characterization\n", encoding="utf-8")

    for phase in ["PLAN", "DECOMPOSE", "ANALYZE", "CREATIVE", "CLARIFY"]:
        res = arm_phase(tmp_path, epic_id, phase, role)
        assert res.get("ok") is True, f"arm_phase failed for {phase}: {res}"
        assert str(res.get("armed_step") or "").upper() == phase
        assert res.get("role") == role
        assert "memory-bank/activeContext.md" in str(res.get("handoff") or "")


def test_arm_phase_with_role_prefixes_and_composite(tmp_path: Path):
    """Characterize normalize_registry_phase and role prefixes like BACK IMPLEMENT, FRONT DECOMPOSE, INTEG QA."""
    assert normalize_registry_phase("BACK IMPLEMENT") == "IMPLEMENT"
    assert normalize_registry_phase("FRONT DECOMPOSE") == "DECOMPOSE"
    assert normalize_registry_phase("INTEG QA") == "QA"
    assert normalize_registry_phase("PLAN REFACTOR") == "PLAN"

    # Verify configs exist for canonical phases
    for p in ["PLAN", "DECOMPOSE", "ANALYZE", "IMPLEMENT", "TASK", "REFACTOR", "BUGFIX", "AUDIT", "QA", "DONE"]:
        cfg = get_phase_config(p)
        assert isinstance(cfg, dict)
        assert "finish_gates" in cfg or "finish_gates_dict" in cfg


def test_arm_phase_implement_with_decompose_rel_characterization(tmp_path: Path):
    """Characterize arm_phase routing when decompose_rel is provided."""
    role = "back"
    epic_id = "T-CHAR-002"

    decomp_yaml = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=tmp_path)
    decomp_yaml.parent.mkdir(parents=True, exist_ok=True)
    decomp_yaml.write_text(
        "schema: epic-decompose-index/v1\n"
        "role: back\n"
        f"plan_id: {epic_id}\n"
        "steps:\n"
        "  - id: s01\n"
        "    file: s01.yaml\n"
        "    title: Step 1\n"
        "    status: pending\n"
        "    next_phase: BACK IMPLEMENT\n",
        encoding="utf-8",
    )
    step_file = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_STEP, step_id="s01", step_slug="step1", project_root=tmp_path)
    step_file.parent.mkdir(parents=True, exist_ok=True)
    step_file.write_text("schema: epic-decompose/v1\nstep_id: s01\n", encoding="utf-8")

    rel_decomp = str(decomp_yaml.relative_to(tmp_path))
    res = arm_phase(tmp_path, epic_id, "IMPLEMENT", role, decompose_rel=rel_decomp)
    assert res.get("ok") is True
    assert res.get("armed_step") == "s01"


def test_arm_phase_anti_loop_diagnostics_characterization(tmp_path: Path):
    """Characterize step_loop_forbidden when trying to arm the same step that just finished."""
    from harness.hooks.epic.core import save_epic_state

    save_epic_state(
        tmp_path,
        {
            "active": True,
            "armed_epic": "T-CHAR-LOOP",
            "last_finished_step": "s02",
            "last_finished_epic": "T-CHAR-LOOP",
        },
    )

    with patch(
        "epic.core.arm_epic",
        return_value={"ok": True, "step_id": "s02", "epic_id": "T-CHAR-LOOP"},
    ):
        res = arm_phase(tmp_path, "T-CHAR-LOOP", "IMPLEMENT", "back")
        assert res.get("ok") is False
        assert res.get("diagnostic_code") == "step_loop_forbidden"
        assert "step_loop_forbidden" in (res.get("diagnostic_codes") or [])


def test_arm_phase_locked_context_diagnostic_characterization(tmp_path: Path):
    """Characterize ActiveContextLocked diagnostic behavior."""
    from _lib import ActiveContextLocked

    with patch(
        "epic.core.arm_epic",
        side_effect=ActiveContextLocked("ActiveContext locked by another process"),
    ):
        res = arm_phase(tmp_path, "T-CHAR-LOCK", "IMPLEMENT", "back")
        assert res.get("ok") is False
        assert res.get("diagnostic_code") == "runner_owns_active_context"
        assert res.get("epic_id") == "T-CHAR-LOCK"
