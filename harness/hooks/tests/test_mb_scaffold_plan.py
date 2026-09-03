import pytest
from pathlib import Path
import yaml

from loop.mb_scaffold.scaffold_plan import scaffold_plan
from loop.paths.epic_layout import resolve, EpicLayoutKind


def test_scaffold_plan(tmp_path: Path):
    epic_id = "T-HUB-047-test"
    role = "back"

    res = scaffold_plan(epic_id=epic_id, role=role, title="My Epic", project_root=tmp_path)
    assert res.ok
    assert len(res.created) == 2

    plan_md = resolve(role=role, epic_id=epic_id, kind=EpicLayoutKind.PLAN_MD, project_root=tmp_path)
    plan_yaml = resolve(role=role, epic_id=epic_id, kind=EpicLayoutKind.PLAN_YAML, project_root=tmp_path)

    assert plan_md.exists()
    assert plan_yaml.exists()

    md_text = plan_md.read_text()
    assert "# Plan: My Epic" in md_text
    assert "## Goal" in md_text

    yaml_data = yaml.safe_load(plan_yaml.read_text())
    assert yaml_data["schema"] == "epic-plan/v1"
    assert yaml_data["plan_id"] == epic_id
    assert yaml_data["title"] == "My Epic"

    # Fail closed on existing without force
    with pytest.raises(ValueError, match="already exists"):
        scaffold_plan(epic_id=epic_id, role=role, title="My Epic", force=False, project_root=tmp_path)

    # Overwrite with force
    res_force = scaffold_plan(epic_id=epic_id, role=role, title="My Epic 2", force=True, project_root=tmp_path)
    assert res_force.ok
