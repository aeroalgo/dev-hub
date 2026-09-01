"""Tests for Janitor GcEngine whitelist and repair functionality."""

from __future__ import annotations

from pathlib import Path
import pytest

from loop.janitor.gc import GcEngine, GcWhitelistError, GcResult
from loop.janitor.schema import JanitorFinding


def test_gc_refuses_non_whitelist(tmp_path: Path) -> None:
    engine = GcEngine(cwd=tmp_path)
    finding = JanitorFinding(
        category="orphan_implement_yaml",
        description="Forbidden target path",
        target_path="src/critical_file.py",
        actionable=True,
    )

    with pytest.raises(GcWhitelistError, match="not in the whitelist"):
        engine.apply_repair(finding, dry_run=True)

    with pytest.raises(GcWhitelistError, match="not in the whitelist"):
        engine.apply_repair(finding, dry_run=False)


def test_gc_dry_run_no_writes(tmp_path: Path) -> None:
    engine = GcEngine(cwd=tmp_path)

    # Episode retention exceeded finding
    ep_dir = tmp_path / "runtime" / "episodes" / "ep_old_1"
    ep_dir.mkdir(parents=True)
    target_rel = "runtime/episodes/ep_old_1"

    finding = JanitorFinding(
        category="episode_retention_exceeded",
        description="Episode retention exceeded",
        target_path=target_rel,
        actionable=True,
    )

    result = engine.apply_repair(finding, dry_run=True)
    assert isinstance(result, GcResult)
    assert result.success is True
    assert result.dry_run is True
    assert ep_dir.exists()  # Ensure dry run did not delete file/dir


def test_gc_apply_episode_prune(tmp_path: Path) -> None:
    engine = GcEngine(cwd=tmp_path)

    ep_dir = tmp_path / "runtime" / "episodes" / "ep_old_2"
    ep_dir.mkdir(parents=True)
    (ep_dir / "manifest.json").write_text("{}", encoding="utf-8")
    target_rel = "runtime/episodes/ep_old_2"

    finding = JanitorFinding(
        category="episode_retention_exceeded",
        description="Episode retention exceeded",
        target_path=target_rel,
        actionable=True,
    )

    result = engine.apply_repair(finding, dry_run=False)
    assert result.success is True
    assert result.dry_run is False
    assert not ep_dir.exists()


def test_gc_apply_index_mirror_patch(tmp_path: Path) -> None:
    engine = GcEngine(cwd=tmp_path)

    index_md = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-TEST" / "index.md"
    index_md.parent.mkdir(parents=True)
    index_md.write_text("# Plan Index\n", encoding="utf-8")

    finding = JanitorFinding(
        category="stale_index_status",
        description="Index mirror drift",
        target_path="memory-bank/back/plan/decompose-T-TEST/index.md",
        actionable=True,
    )

    result = engine.apply_repair(finding, dry_run=False)
    assert result.success is True
    assert result.action == "index_mirror_patch"
