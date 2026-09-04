import pytest
from pathlib import Path

from loop.mb_scaffold.scaffold_plan import scaffold_plan
from loop.paths.epic_layout import resolve, EpicLayoutKind


def test_scaffold_plan(tmp_path: Path):
    epic_id = "T-HUB-047-test"
    role = "back"

    res = scaffold_plan(epic_id=epic_id, role=role, title="My Epic", project_root=tmp_path)
    assert res.ok
    assert len(res.created) == 1

    plan_md = resolve(role=role, epic_id=epic_id, kind=EpicLayoutKind.PLAN_MD, project_root=tmp_path)

    assert plan_md.exists()
    assert not (plan_md.parent.parent / "yaml" / "plan.yaml").exists()

    md_text = plan_md.read_text()
    assert "# Plan: My Epic" in md_text
    assert "## Goal" in md_text
    assert "## Requirements" in md_text

    with pytest.raises(ValueError, match="already exists"):
        scaffold_plan(epic_id=epic_id, role=role, title="My Epic", force=False, project_root=tmp_path)

    res_force = scaffold_plan(epic_id=epic_id, role=role, title="My Epic 2", force=True, project_root=tmp_path)
    assert res_force.ok
    assert "# Plan: My Epic 2" in plan_md.read_text()
