"""Tests for harness.hooks.epic_paths module (canonical v2 resolution and v1 denial)."""

from pathlib import Path
import pytest
import yaml

from harness.hooks.epic_paths import (
    assert_epic_yaml_shards,
    canonical_epic_id_for_decompose,
    discover_epic_role,
    epic_id_from_decompose_path,
    epic_id_from_plan_path,
    extract_step_basename,
    find_decompose_index_path,
    find_plan_md_path,
    is_epic_implement_step_path,
    resolve_arm_epic_target,
    role_from_memory_bank_path,
)


def test_find_decompose_index_path_v2(tmp_path: Path):
    epic_id = "T-HUB-087-epic-test"
    v2_dir = tmp_path / "memory-bank" / "back" / "plan" / epic_id / "yaml"
    v2_dir.mkdir(parents=True)
    v2_index = v2_dir / "decompose-index.yaml"
    v2_index.write_text(
        yaml.safe_dump(
            {
                "schema": "epic-decompose-index/v1",
                "plan_id": epic_id,
                "steps": [{"id": "s01", "status": "pending"}],
            }
        ),
        encoding="utf-8",
    )

    found = find_decompose_index_path(tmp_path, "back", epic_id)
    assert found == v2_index


def test_find_decompose_index_path_denies_v1_only(tmp_path: Path):
    epic_id = "T-HUB-087-legacy"
    v1_dir = tmp_path / "memory-bank" / "back" / "plan" / f"decompose-{epic_id}"
    v1_dir.mkdir(parents=True)
    v1_index = v1_dir / "index.yaml"
    v1_index.write_text(
        yaml.safe_dump(
            {
                "schema": "epic-decompose-index/v1",
                "plan_id": epic_id,
                "steps": [{"id": "s01", "status": "pending"}],
            }
        ),
        encoding="utf-8",
    )

    found = find_decompose_index_path(tmp_path, "back", epic_id)
    assert found is None


def test_find_plan_md_path_v2(tmp_path: Path):
    epic_id = "T-HUB-087-epic-test"
    v2_dir = tmp_path / "memory-bank" / "back" / "plan" / epic_id / "md"
    v2_dir.mkdir(parents=True)
    v2_plan = v2_dir / "plan.md"
    v2_plan.write_text("# Plan\n", encoding="utf-8")

    found = find_plan_md_path(tmp_path, "back", epic_id)
    assert found == v2_plan


def test_find_plan_md_path_denies_v1_only(tmp_path: Path):
    epic_id = "T-HUB-087-legacy"
    v1_dir = tmp_path / "memory-bank" / "back" / "plan"
    v1_dir.mkdir(parents=True)
    v1_plan = v1_dir / f"plan-{epic_id}.md"
    v1_plan.write_text("# Legacy Plan\n", encoding="utf-8")

    found = find_plan_md_path(tmp_path, "back", epic_id)
    assert found is None


def test_epic_id_from_plan_path_v2():
    path = Path("memory-bank/back/plan/T-HUB-087-test/md/plan.md")
    assert epic_id_from_plan_path(path) == "T-HUB-087-test"


def test_canonical_epic_id_for_decompose_v2(tmp_path: Path):
    epic_id = "T-HUB-087-test"
    v2_index = tmp_path / "memory-bank" / "back" / "plan" / epic_id / "yaml" / "decompose-index.yaml"
    v2_index.parent.mkdir(parents=True)
    v2_index.write_text(
        yaml.safe_dump({"schema": "epic-decompose-index/v1", "plan_id": epic_id, "steps": []}),
        encoding="utf-8",
    )

    assert canonical_epic_id_for_decompose(v2_index, index_path=v2_index) == epic_id


def test_resolve_arm_epic_target_v2():
    target = "memory-bank/back/plan/T-HUB-087-test/yaml/decompose-index.yaml"
    assert resolve_arm_epic_target(target) == ("T-HUB-087-test", "back")

    direct_id = "T-HUB-087-test"
    assert resolve_arm_epic_target(direct_id) == ("T-HUB-087-test", "back")


def test_assert_epic_yaml_shards():
    valid = ["memory-bank/back/plan/T-HUB-087/yaml/steps/s01.yaml"]
    assert assert_epic_yaml_shards(valid) == valid

    invalid = ["memory-bank/back/plan/T-HUB-087/yaml/steps/s01-step.md"]
    with pytest.raises(ValueError, match="Epic shard must be .yaml"):
        assert_epic_yaml_shards(invalid)
