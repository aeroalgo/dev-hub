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


def test_resolver_rejects_invalid_kinds():
    """TM-087-04 / FR-006: Layout resolver rejects unhandled kinds."""
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
    assert str(idx_yaml).endswith("memory-bank/back/plan/T-HUB-087/yaml/decompose-index.yaml")

    impl_step = resolve("back", "T-HUB-087", EpicLayoutKind.IMPLEMENT_STEP, step_id="s01")
    assert str(impl_step).endswith("memory-bank/back/implement/T-HUB-087/s01.yaml")
