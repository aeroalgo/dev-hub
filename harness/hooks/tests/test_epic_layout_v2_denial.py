from __future__ import annotations

import os
from pathlib import Path
import pytest
import yaml

from loop.paths.epic_layout import (
    EpicLayoutKind,
    discover_v2_epics,
    normalize_role_dir,
    resolve,
)
from harness.hooks.epic.core import (
    load_decompose_steps_fail_closed,
    resolve_pipeline_identity,
)


KNOWN_LEGACY_IMPLEMENT_TREES = [
    "T-HUB-047-harness-mb-scaffold-epic-layout",
    "T-HUB-048-workflow-pack-registry",
    "T-HUB-049-workflow-pack-phase-router",
    "T-HUB-050-workflow-pack-memory-bank-paths",
    "T-HUB-051-workflow-pack-reference-video",
    "T-HUB-052-workflow-pack-adoption-docs",
    "T-HUB-060-remove-reflect-phase",
    "T-HUB-061-boundary-cli-doctor-hygiene",
]


def test_legacy_implement_trees_registry_inventory():
    """Verify SC-002: 0 live implement/implement-* directories in BACK tree and all 8 trees are in v2 layout."""
    repo_root = Path(__file__).resolve().parents[3]
    impl_dir = repo_root / "memory-bank" / "back" / "implement"
    assert impl_dir.is_dir()

    actual_legacy = sorted([d.name for d in impl_dir.iterdir() if d.is_dir() and d.name.startswith("implement-")])
    assert actual_legacy == [], f"Found unexpected legacy implement-* directories: {actual_legacy}"

    for tree_name in KNOWN_LEGACY_IMPLEMENT_TREES:
        tree_path = impl_dir / tree_name
        assert tree_path.is_dir(), f"Expected v2 implement dir {tree_path} to exist"
        yaml_files = list(tree_path.glob("*.yaml"))
        assert len(yaml_files) > 0, f"V2 tree {tree_name} has no step yaml files"


def test_resolver_rejects_legacy_and_invalid_kinds():
    """TM-087-04 / FR-006: Layout resolver rejects removed legacy kinds and unhandled kinds."""
    with pytest.raises(ValueError, match="Unknown EpicLayoutKind"):
        resolve("back", "T-HUB-087", "plan_yaml")

    with pytest.raises(ValueError, match="Unknown EpicLayoutKind"):
        resolve("back", "T-HUB-087", "decompose_raw")

    with pytest.raises(ValueError, match="Unknown EpicLayoutKind"):
        resolve("back", "T-HUB-087", "implement_raw")

    with pytest.raises(ValueError, match="Unknown EpicLayoutKind"):
        resolve("back", "T-HUB-087", "legacy_index")


def test_resolver_rejects_path_traversal_and_invalid_characters():
    """Resolver enforces clean segments without ../ or slash injections."""
    with pytest.raises(ValueError, match="Invalid characters in epic_id"):
        resolve("back", "../T-HUB-087", EpicLayoutKind.PLAN_MD)

    with pytest.raises(ValueError, match="Invalid characters in epic_id"):
        resolve("back", "T-HUB/087", EpicLayoutKind.PLAN_MD)

    with pytest.raises(ValueError, match="Invalid characters in step_id"):
        resolve("back", "T-HUB-087", EpicLayoutKind.DECOMPOSE_STEP, step_id="../../etc/passwd")

    with pytest.raises(ValueError, match="Invalid characters in step_slug"):
        resolve("back", "T-HUB-087", EpicLayoutKind.DECOMPOSE_STEP, step_id="s01", step_slug="a/b")


def test_resolver_requires_step_id_for_step_kinds():
    """Step kinds fail-closed if step_id is omitted."""
    with pytest.raises(ValueError, match="step_id is required"):
        resolve("back", "T-HUB-087", EpicLayoutKind.DECOMPOSE_STEP)

    with pytest.raises(ValueError, match="step_id is required"):
        resolve("back", "T-HUB-087", EpicLayoutKind.IMPLEMENT_STEP)


def test_legacy_v1_only_tree_is_not_discovered_as_v2(tmp_path: Path):
    """SC-004 / AC+ #6: Legacy v1 files alone do not satisfy v2 discovery."""
    mb_back = tmp_path / "memory-bank" / "back"
    (mb_back / "plan").mkdir(parents=True)
    (mb_back / "implement").mkdir(parents=True)

    # v1 plan
    (mb_back / "plan" / "plan-T-LEGACY-001.md").write_text("# Old Plan\n", encoding="utf-8")
    # v1 decompose
    (mb_back / "plan" / "decompose-T-LEGACY-001").mkdir()
    (mb_back / "plan" / "decompose-T-LEGACY-001" / "index.yaml").write_text(
        "schema: epic-decompose-index/v1\nsteps: []\n", encoding="utf-8"
    )
    # v1 implement
    (mb_back / "implement" / "implement-T-LEGACY-001").mkdir()

    epics = discover_v2_epics(tmp_path)
    assert ("back", "T-LEGACY-001") not in epics
    assert ("back", "plan-T-LEGACY-001.md") not in epics
    assert ("back", "decompose-T-LEGACY-001") not in epics


def test_missing_v2_index_fails_closed(tmp_path: Path):
    """TM-087-02 / US-003: Missing v2 decompose-index returns index_not_found fail-closed."""
    epic_id = "T-HUB-MISSING-YAML"
    plan_md = resolve("back", epic_id, EpicLayoutKind.PLAN_MD, project_root=tmp_path)
    plan_md.parent.mkdir(parents=True, exist_ok=True)
    plan_md.write_text("# Plan\n", encoding="utf-8")

    missing_yaml = resolve("back", epic_id, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=tmp_path)
    assert not missing_yaml.exists()

    result = load_decompose_steps_fail_closed(tmp_path, missing_yaml.relative_to(tmp_path).as_posix())
    assert result["ok"] is False
    assert result["diagnostic_code"] == "index_not_found"
    assert result["steps"] == []


def test_invalid_yaml_syntax_fails_closed(tmp_path: Path):
    """TM-087-02: Corrupted decompose index YAML denies loading fail-closed."""
    epic_id = "T-HUB-INVALID-YAML"
    decomp_yaml = resolve("back", epic_id, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=tmp_path)
    decomp_yaml.parent.mkdir(parents=True, exist_ok=True)
    decomp_yaml.write_text("schema: [unclosed list\n", encoding="utf-8")

    result = load_decompose_steps_fail_closed(tmp_path, decomp_yaml.relative_to(tmp_path).as_posix())
    assert result["ok"] is False
    assert result["diagnostic_code"] == "index_invalid"


def test_canonical_v2_paths_have_no_wrapper_or_legacy_prefixes():
    """AC+ #1 / AC- #1: Canonical v2 paths strictly adhere to v2 hierarchy."""
    plan_md = resolve("back", "T-HUB-087", EpicLayoutKind.PLAN_MD)
    assert "plan-T-HUB-087" not in str(plan_md)
    assert str(plan_md).endswith("memory-bank/back/plan/T-HUB-087/md/plan.md")

    idx_yaml = resolve("back", "T-HUB-087", EpicLayoutKind.DECOMPOSE_INDEX_YAML)
    assert "decompose-T-HUB-087" not in str(idx_yaml)
    assert str(idx_yaml).endswith("memory-bank/back/plan/T-HUB-087/yaml/decompose-index.yaml")

    impl_step = resolve("back", "T-HUB-087", EpicLayoutKind.IMPLEMENT_STEP, step_id="s01")
    assert "implement-T-HUB-087" not in str(impl_step)
    assert str(impl_step).endswith("memory-bank/back/implement/T-HUB-087/s01.yaml")
