import pytest
from pathlib import Path
import yaml

from loop.mb_scaffold.scaffold_implement import scaffold_implement, scaffold_implement_all
from loop.mb_scaffold.scaffold_decompose import (
    scaffold_decompose,
    DecomposeOutline,
    OutlineStep,
    OutlineRequirement,
)
from loop.paths.epic_layout import resolve, EpicLayoutKind


def test_scaffold_all(tmp_path: Path):
    epic_id = "T-HUB-047-test"
    role = "back"
    reqs = [OutlineRequirement(id=f"FR-00{i}", text=f"Req {i}") for i in range(1, 6)]
    steps = [
        OutlineStep(step_id=f"s0{i}", title=f"Step {i} title", maps_to=[f"FR-00{i}"])
        for i in range(1, 6)
    ]
    outline = DecomposeOutline(
        title="Test Epic",
        requirements=reqs,
        outline_steps=steps,
    )

    scaffold_decompose(epic_id=epic_id, role=role, outline=outline, project_root=tmp_path)

    res = scaffold_implement_all(epic_id=epic_id, role=role, project_root=tmp_path)
    assert res.ok
    assert len(res.created) == 5

    for i in range(1, 6):
        impl_path = resolve(
            role=role,
            epic_id=epic_id,
            kind=EpicLayoutKind.IMPLEMENT_STEP,
            step_id=f"s0{i}",
            step_slug=f"step-{i}-title",
            project_root=tmp_path,
        )
        assert impl_path.exists()
        data = yaml.safe_load(impl_path.read_text())
        assert data["schema"] == "epic-implement/v1"
        assert data["status"] == "in_progress"
        assert data["step_id"] == f"s0{i}"


def test_scaffold_implement_guard(tmp_path: Path):
    epic_id = "T-HUB-047-test"
    role = "back"
    step_id = "s01"

    scaffold_implement(epic_id=epic_id, step_id=step_id, role=role, project_root=tmp_path)
    impl_path = resolve(
        role=role,
        epic_id=epic_id,
        kind=EpicLayoutKind.IMPLEMENT_STEP,
        step_id=step_id,
        project_root=tmp_path,
    )
    data = yaml.safe_load(impl_path.read_text())
    data["status"] = "completed"
    impl_path.write_text(yaml.dump(data))

    with pytest.raises(ValueError, match="already completed"):
        scaffold_implement(epic_id=epic_id, step_id=step_id, role=role, force=False, project_root=tmp_path)

    res = scaffold_implement(epic_id=epic_id, step_id=step_id, role=role, force=True, project_root=tmp_path)
    assert res.ok
