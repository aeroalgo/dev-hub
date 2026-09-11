"""Tests for epic layout v1 to v2 migration script."""

import json
import os
import shutil
from pathlib import Path
import pytest
import yaml

from loop.migrate.epic_layout_v1_to_v2 import (
    discover_v1_epics,
    is_migrated,
    migrate_epic,
    migrate_all,
)


@pytest.fixture
def v1_fixture(tmp_path: Path) -> Path:
    """Create a temporary project root with v1 memory-bank structure."""
    mb = tmp_path / "memory-bank" / "back"
    plan_dir = mb / "plan"
    impl_dir = mb / "implement"
    qa_dir = mb / "qa"

    plan_dir.mkdir(parents=True)
    impl_dir.mkdir(parents=True)
    qa_dir.mkdir(parents=True)

    epic_id = "T-HUB-047-test"

    # v1 plan
    plan_file = plan_dir / f"plan-{epic_id}.md"
    plan_file.write_text(f"# Plan {epic_id}\nRef: decompose-{epic_id}/index.yaml\n", encoding="utf-8")

    # v1 decompose
    decomp_dir = plan_dir / f"decompose-{epic_id}"
    decomp_dir.mkdir()
    (decomp_dir / "index.md").write_text(f"# Decompose index {epic_id}\n", encoding="utf-8")
    index_yaml_data = {
        "schema": "epic-decompose-index/v1",
        "plan_id": epic_id,
        "steps": [
            {"id": "s01", "file": "s01-step.yaml", "status": "completed"},
            {"id": "s02", "file": "s02-step.yaml", "status": "pending"},
        ],
    }
    (decomp_dir / "index.yaml").write_text(yaml.dump(index_yaml_data), encoding="utf-8")
    (decomp_dir / "s01-step.yaml").write_text(
        f"schema: epic-decompose/v1\nplan_id: {epic_id}\nref: plan-{epic_id}.md\n", encoding="utf-8"
    )

    # v1 implement
    impl_epic_dir = impl_dir / f"implement-{epic_id}"
    impl_epic_dir.mkdir()
    (impl_epic_dir / "s01-step.yaml").write_text(
        f"schema: epic-implement/v1\nplan_id: {epic_id}\ndecompose_ref: memory-bank/back/plan/decompose-{epic_id}/s01-step.yaml\n",
        encoding="utf-8",
    )

    # v1 qa
    (qa_dir / f"qa-{epic_id}.yaml").write_text(f"schema: epic-qa/v1\nplan_id: {epic_id}\n", encoding="utf-8")

    return tmp_path


def test_dry_run_no_changes(v1_fixture: Path):
    """CP1: --dry-run returns planned moves, 0 changes to filesystem."""
    res = migrate_epic("T-HUB-047-test", role="back", cwd=v1_fixture, dry_run=True)
    assert res["status"] == "dry_run"
    assert len(res["moved"]) >= 4

    # Check v1 files still exist
    v1_plan = v1_fixture / "memory-bank" / "back" / "plan" / "plan-T-HUB-047-test.md"
    assert v1_plan.exists()
    v1_decomp = v1_fixture / "memory-bank" / "back" / "plan" / "decompose-T-HUB-047-test"
    assert v1_decomp.exists()

    # Check v2 files do NOT exist yet
    v2_plan = v1_fixture / "memory-bank" / "back" / "plan" / "T-HUB-047-test" / "md" / "plan.md"
    assert not v2_plan.exists()


def test_apply_idempotent(v1_fixture: Path):
    """CP2: --apply moves files; repeating --apply is idempotent with 0 changes."""
    epic_id = "T-HUB-047-test"
    res1 = migrate_epic(epic_id, role="back", cwd=v1_fixture, dry_run=False)
    assert res1["status"] == "migrated"
    assert len(res1["moved"]) >= 4

    # Verify v1 is gone and v2 exists
    v1_plan = v1_fixture / "memory-bank" / "back" / "plan" / f"plan-{epic_id}.md"
    assert not v1_plan.exists()
    v1_decomp = v1_fixture / "memory-bank" / "back" / "plan" / f"decompose-{epic_id}"
    assert not v1_decomp.exists()

    v2_plan_md = v1_fixture / "memory-bank" / "back" / "plan" / epic_id / "md" / "plan.md"
    v2_decomp_idx = v1_fixture / "memory-bank" / "back" / "plan" / epic_id / "yaml" / "decompose-index.yaml"
    v2_decomp_step = v1_fixture / "memory-bank" / "back" / "plan" / epic_id / "yaml" / "steps" / "s01-step.yaml"
    v2_impl_step = v1_fixture / "memory-bank" / "back" / "implement" / epic_id / "s01-step.yaml"
    v2_qa_yaml = v1_fixture / "memory-bank" / "back" / "qa" / epic_id / "qa.yaml"

    assert v2_plan_md.exists()
    assert v2_decomp_idx.exists()
    assert v2_decomp_step.exists()
    assert v2_impl_step.exists()
    assert v2_qa_yaml.exists()

    assert is_migrated(epic_id, role="back", cwd=v1_fixture)

    # 2nd run: idempotent skip
    res2 = migrate_epic(epic_id, role="back", cwd=v1_fixture, dry_run=False)
    assert res2["status"] == "skipped"
    assert res2["moved"] == []


def test_ref_update(v1_fixture: Path):
    """CP3: Internal references in yaml/md files are updated."""
    epic_id = "T-HUB-047-test"
    migrate_epic(epic_id, role="back", cwd=v1_fixture, dry_run=False)

    # Check updated plan.md
    v2_plan_md = v1_fixture / "memory-bank" / "back" / "plan" / epic_id / "md" / "plan.md"
    content = v2_plan_md.read_text(encoding="utf-8")
    assert f"plan/{epic_id}/yaml/decompose-index.yaml" in content or f"{epic_id}/yaml/decompose-index.yaml" in content
    assert f"decompose-{epic_id}/" not in content

    # Check updated implement step
    v2_impl_step = v1_fixture / "memory-bank" / "back" / "implement" / epic_id / "s01-step.yaml"
    impl_content = v2_impl_step.read_text(encoding="utf-8")
    assert f"decompose-{epic_id}/" not in impl_content
    assert f"{epic_id}/yaml/steps/" in impl_content or f"plan/{epic_id}/yaml/steps/" in impl_content


def test_active_implement_guard(v1_fixture: Path):
    """CP4: active IMPLEMENT guard: in_progress steps + --apply without --force raises error."""
    epic_id = "T-HUB-047-test"
    # Set step to in_progress
    idx_yaml = v1_fixture / "memory-bank" / "back" / "plan" / f"decompose-{epic_id}" / "index.yaml"
    data = yaml.safe_load(idx_yaml.read_text(encoding="utf-8"))
    data["steps"][1]["status"] = "in_progress"
    idx_yaml.write_text(yaml.dump(data), encoding="utf-8")

    # Without force -> raises RuntimeError
    with pytest.raises(RuntimeError, match="Active IMPLEMENT guard"):
        migrate_epic(epic_id, role="back", cwd=v1_fixture, dry_run=False, force=False)

    # With force -> succeeds
    res = migrate_epic(epic_id, role="back", cwd=v1_fixture, dry_run=False, force=True)
    assert res["status"] == "migrated"
    assert res["warning"] == "in_progress steps forced"


def test_discover_v1_implement_without_v1_plan(tmp_path: Path):
    """Discover epics that only have legacy implement/implement-* directory."""
    mb = tmp_path / "memory-bank" / "back"
    impl_dir = mb / "implement" / "implement-T-HUB-999-legacy-impl"
    impl_dir.mkdir(parents=True)
    (impl_dir / "s01-step.yaml").write_text("schema: epic-implement/v1\n", encoding="utf-8")

    # plan is already v2
    v2_plan = mb / "plan" / "T-HUB-999-legacy-impl" / "yaml"
    v2_plan.mkdir(parents=True)
    (v2_plan / "decompose-index.yaml").write_text("schema: epic-decompose-index/v1\nsteps: []\n", encoding="utf-8")

    epics = discover_v1_epics(cwd=tmp_path)
    assert ("back", "T-HUB-999-legacy-impl") in epics
    assert not is_migrated("T-HUB-999-legacy-impl", role="back", cwd=tmp_path)

    res = migrate_epic("T-HUB-999-legacy-impl", role="back", cwd=tmp_path, dry_run=False)
    assert res["status"] == "migrated"
    assert not impl_dir.exists()
    assert (mb / "implement" / "T-HUB-999-legacy-impl" / "s01-step.yaml").exists()
    assert is_migrated("T-HUB-999-legacy-impl", role="back", cwd=tmp_path)


def test_migrated_8_live_implement_trees_parity():
    """Verify all 8 migrated legacy implement trees have full step parity and no implement-* dirs remain."""
    root = Path(__file__).resolve().parent.parent.parent.parent
    mb_back = root / "memory-bank" / "back"

    legacy_dirs = list((mb_back / "implement").glob("implement-*"))
    assert len(legacy_dirs) == 0, f"Expected 0 implement-* dirs, found: {legacy_dirs}"

    migrated_epics = [
        "T-HUB-047-harness-mb-scaffold-epic-layout",
        "T-HUB-048-workflow-pack-registry",
        "T-HUB-049-workflow-pack-phase-router",
        "T-HUB-050-workflow-pack-memory-bank-paths",
        "T-HUB-051-workflow-pack-reference-video",
        "T-HUB-052-workflow-pack-adoption-docs",
        "T-HUB-060-remove-reflect-phase",
        "T-HUB-061-boundary-cli-doctor-hygiene",
    ]

    for epic_id in migrated_epics:
        decomp_yaml = mb_back / "plan" / epic_id / "yaml" / "decompose-index.yaml"
        assert decomp_yaml.exists(), f"Decompose index missing for {epic_id}"

        data = yaml.safe_load(decomp_yaml.read_text(encoding="utf-8"))
        expected_step_files = sorted([s["file"] for s in data.get("steps", [])])

        v2_impl_dir = mb_back / "implement" / epic_id
        assert v2_impl_dir.exists(), f"Implement dir missing for {epic_id}"

        actual_step_files = sorted([f.name for f in v2_impl_dir.iterdir() if f.is_file()])
        assert actual_step_files == expected_step_files, (
            f"Step parity mismatch for {epic_id}: expected {expected_step_files}, got {actual_step_files}"
        )
