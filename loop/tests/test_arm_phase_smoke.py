"""Smoke test for arm_phase on v2 layout epic."""

import json
from pathlib import Path
from loop.epic_transition import arm_phase
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
