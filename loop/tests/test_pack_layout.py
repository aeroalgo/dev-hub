"""Tests for loop.paths.pack_layout module."""

import pytest
from pathlib import Path
from unittest.mock import patch

from loop.paths.pack_layout import (
    ArtifactLayout,
    PackLayoutError,
    resolve_mb_root,
)
from loop.workflow.schemas import WorkflowPack


def test_artifact_layout_enum():
    """ArtifactLayout enum defines software_epic_v1 and production_epic_v1."""
    assert ArtifactLayout.software_epic_v1 == "software-epic-v1"
    assert ArtifactLayout.production_epic_v1 == "production-epic-v1"
    assert ArtifactLayout.software_epic_v1.value == "software-epic-v1"
    assert ArtifactLayout.production_epic_v1.value == "production-epic-v1"


def test_resolve_mb_root_software_pack_default(tmp_path: Path):
    """resolve_mb_root(cwd) for software pack returns cwd / 'memory-bank'."""
    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    mb_root = resolve_mb_root(cwd=tmp_path)
    assert mb_root == tmp_path / "memory-bank"


def test_resolve_mb_root_software_pack_explicit(tmp_path: Path):
    """resolve_mb_root with an explicit software WorkflowPack."""
    pack = WorkflowPack(
        id="dev-hub-software",
        roles=["back", "front", "integration"],
        command_prefixes=["BACK", "FRONT", "INTEG"],
        phase_registry="loop/schemas/phase_registry.yaml",
        memory_bank="custom-memory-bank",
        rules_root=".cursor/rules",
        artifact_layout="software-epic-v1",
    )
    mb_root = resolve_mb_root(cwd=tmp_path, pack=pack)
    assert mb_root == tmp_path / "custom-memory-bank"


def test_resolve_mb_root_missing_manifest_or_invalid_pack(tmp_path: Path):
    """Missing or invalid pack manifest fails closed with PackLayoutError."""
    # When resolve_workflow_pack returns ok=False
    with patch("loop.paths.pack_layout.resolve_workflow_pack") as mock_resolve:
        from loop.workflow.schemas import PackResolveResult
        mock_resolve.return_value = PackResolveResult(
            ok=False,
            pack_id="non-existent",
            pack=None,
            diagnostic_codes=["invalid_workflow_pack"],
        )
        with pytest.raises(PackLayoutError, match="Failed to resolve workflow pack"):
            resolve_mb_root(cwd=tmp_path)


def test_resolve_mb_root_cwd_mismatch_or_non_existent(tmp_path: Path):
    """Pass non-existent or invalid cwd fails closed or handles properly."""
    non_existent = tmp_path / "does_not_exist"
    # When pack has missing paths or resolution fails
    with patch("loop.paths.pack_layout.resolve_workflow_pack") as mock_resolve:
        from loop.workflow.schemas import PackResolveResult
        mock_resolve.return_value = PackResolveResult(
            ok=False,
            pack_id="",
            pack=None,
            diagnostic_codes=["invalid_workflow_pack_registry"],
        )
        with pytest.raises(PackLayoutError):
            resolve_mb_root(cwd=non_existent)
