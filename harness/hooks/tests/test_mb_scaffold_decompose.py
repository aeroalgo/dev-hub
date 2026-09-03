import pytest
from pathlib import Path
import yaml

from loop.mb_scaffold.scaffold_decompose import scaffold_decompose
from loop.schemas.plan_spec import PlanSpec, PlanSummary, Requirement, OutlineStep
from loop.paths.epic_layout import resolve, EpicLayoutKind


def test_scaffold_decompose_5steps(tmp_path: Path):
    epic_id = "T-HUB-047-test"
    role = "back"
    reqs = [Requirement(id=f"FR-00{i}", text=f"Req {i}") for i in range(1, 6)]
    steps = [
        OutlineStep(step_id=f"s0{i}", title=f"Step {i} title", maps_to=[f"FR-00{i}"])
        for i in range(1, 6)
    ]
    spec = PlanSpec(
        plan_id=epic_id,
        level="epic",
        title="Test Epic",
        summary=PlanSummary(step_count_floor=5, requirement_count=5),
        requirements=reqs,
        outline_steps=steps,
    )

    res = scaffold_decompose(epic_id=epic_id, role=role, plan_spec=spec, project_root=tmp_path)
    assert res.ok
    assert len(res.created) == 7  # 2 index files + 5 step files

    # Verify s01..s05 files exist and delta is empty list
    for i in range(1, 6):
        step_path = resolve(
            role=role,
            epic_id=epic_id,
            kind=EpicLayoutKind.DECOMPOSE_STEP,
            step_id=f"s0{i}",
            step_slug=f"step-{i}-title",
            project_root=tmp_path,
        )
        assert step_path.exists()
        data = yaml.safe_load(step_path.read_text())
        assert data["step_id"] == f"s0{i}"
        assert data["goal"] == ""
        assert data["delta"] == []
        assert data["plan_contract"]["fr_ids"] == [f"FR-00{i}"]


def test_scaffold_guard_nooverwrite(tmp_path: Path):
    epic_id = "T-HUB-047-test"
    role = "back"
    step = OutlineStep(step_id="s01", title="Step 1", maps_to=["FR-001"])
    spec = PlanSpec(
        plan_id=epic_id,
        level="epic",
        title="Test Epic",
        summary=PlanSummary(step_count_floor=1, requirement_count=1),
        requirements=[],
        outline_steps=[step],
    )

    scaffold_decompose(epic_id=epic_id, role=role, plan_spec=spec, project_root=tmp_path)

    # Fill goal in s01
    step_path = resolve(
        role=role,
        epic_id=epic_id,
        kind=EpicLayoutKind.DECOMPOSE_STEP,
        step_id="s01",
        step_slug="step-1",
        project_root=tmp_path,
    )
    data = yaml.safe_load(step_path.read_text())
    data["goal"] = "Real non-empty goal written by agent"
    step_path.write_text(yaml.dump(data))

    # Without force -> must raise ValueError
    with pytest.raises(ValueError, match="non-empty goal"):
        scaffold_decompose(epic_id=epic_id, role=role, plan_spec=spec, force=False, project_root=tmp_path)

    # With force -> succeeds
    res = scaffold_decompose(epic_id=epic_id, role=role, plan_spec=spec, force=True, project_root=tmp_path)
    assert res.ok


def test_formula_merge(tmp_path: Path):
    epic_id = "T-HUB-047-test"
    role = "back"
    steps = [
        OutlineStep(step_id="s01", title="Initial title 1", maps_to=["FR-001"]),
        OutlineStep(step_id="s02", title="Initial title 2", maps_to=["FR-002"]),
    ]
    spec = PlanSpec(
        plan_id=epic_id,
        level="epic",
        title="Test Epic",
        summary=PlanSummary(step_count_floor=2, requirement_count=2),
        requirements=[],
        outline_steps=steps,
    )

    res = scaffold_decompose(
        epic_id=epic_id,
        role=role,
        plan_spec=spec,
        formula_id="hooks-epic",
        project_root=tmp_path,
    )
    assert res.ok

    # s01 has title "env-contract"
    s01_path = resolve(
        role=role,
        epic_id=epic_id,
        kind=EpicLayoutKind.DECOMPOSE_STEP,
        step_id="s01",
        step_slug="env-contract",
        project_root=tmp_path,
    )
    assert s01_path.exists()
    s01_data = yaml.safe_load(s01_path.read_text())
    assert s01_data["title"] == "env-contract"

    # s02 has title "unified-llm-models"
    s02_path = resolve(
        role=role,
        epic_id=epic_id,
        kind=EpicLayoutKind.DECOMPOSE_STEP,
        step_id="s02",
        step_slug="unified-llm-models",
        project_root=tmp_path,
    )
    assert s02_path.exists()
    s02_data = yaml.safe_load(s02_path.read_text())
    assert s02_data["title"] == "unified-llm-models"

    # Floor expanded to 8 steps from hooks-epic
    assert len(res.created) == 10  # 2 index files + 8 step files

