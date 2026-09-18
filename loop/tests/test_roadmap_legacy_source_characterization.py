from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import loop.roadmap_queue as rq
from loop.runner import RunnerConfig
from loop.runner.orchestrator import ContextLoopPort, IncidentTracker, LoopRunner, SessionPort


def test_discover_source_queues_batches(tmp_path: Path) -> None:
    """Characterization: discover_source_queues finds batches in roadmap/batches/."""
    batches_dir = tmp_path / "memory-bank" / "back" / "roadmap" / "batches"
    batches_dir.mkdir(parents=True)
    batch_file = batches_dir / "batch-01.yaml"
    batch_file.write_text("dummy: true\n", encoding="utf-8")

    # Canon queue inside batches (if named queue.yaml) should be ignored
    canon_in_batch = batches_dir / "queue.yaml"
    canon_in_batch.write_text("dummy: canon\n", encoding="utf-8")

    discovered = rq.discover_source_queues(tmp_path, role="back")
    assert discovered == [batch_file]


def test_discover_source_queues_plan_dir_legacy(tmp_path: Path) -> None:
    """Characterization: discover_source_queues ignores legacy plan/ slug queues."""
    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    plan_dir.mkdir(parents=True)
    legacy_slug = plan_dir / "roadmap-foo-epics.queue.yaml"
    legacy_slug.write_text("dummy: true\n", encoding="utf-8")

    # Non-matching files should not be discovered
    non_matching = plan_dir / "other.queue.yaml"
    non_matching.write_text("dummy: true\n", encoding="utf-8")

    discovered = rq.discover_source_queues(tmp_path, role="back")
    assert legacy_slug not in discovered
    assert non_matching not in discovered
    assert discovered == []


def test_discover_source_queues_empty_and_archive(tmp_path: Path) -> None:
    """Characterization: archive directory is ignored and empty root returns empty list."""
    archive_dir = tmp_path / "memory-bank" / "back" / "roadmap" / "archive"
    archive_dir.mkdir(parents=True)
    archived_file = archive_dir / "archived-batch.yaml"
    archived_file.write_text("dummy: true\n", encoding="utf-8")

    discovered = rq.discover_source_queues(tmp_path, role="back")
    assert discovered == []


def test_queue_rel_from_roadmap_characterization() -> None:
    """Characterization: queue_rel_from_roadmap resolves canon, bare dir, and legacy .md."""
    # Canon paths
    assert rq.queue_rel_from_roadmap("memory-bank/back/roadmap/queue.yaml") == "memory-bank/back/roadmap/queue.yaml"
    assert rq.queue_rel_from_roadmap("memory-bank/back/plan/custom.queue.yaml") == "memory-bank/back/plan/custom.queue.yaml"

    # Bare roadmap directory
    assert rq.queue_rel_from_roadmap("memory-bank/back/roadmap") == "memory-bank/back/roadmap/queue.yaml"
    assert rq.queue_rel_from_roadmap("memory-bank/back/roadmap/") == "memory-bank/back/roadmap/queue.yaml"

    # Legacy markdown roadmap path raises ValueError (fail-closed)
    with pytest.raises(ValueError, match="legacy .md roadmap path is forbidden"):
        rq.queue_rel_from_roadmap("memory-bank/back/plan/roadmap-epics.md")


def test_incident_tracker_record_trace_characterization(tmp_path: Path) -> None:
    """Characterization: IncidentTracker.record_trace executes without raising exception."""
    tracker = IncidentTracker()
    # Should execute safely even with missing loop.epic_paths module
    tracker.record_trace(
        tmp_path,
        phase="IMPLEMENT",
        action="test_action",
        decide="test_decision",
        episode_id="ep-01",
        detail={"info": "characterization"},
    )


def test_incident_tracker_attempt_tier1_disabled_characterization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Characterization: attempt_tier1 returns False when disabled or disallowed by env."""
    tracker_disabled = IncidentTracker(tier1_enabled=False)
    assert tracker_disabled.attempt_tier1(tmp_path) is False

    tracker_enabled = IncidentTracker(tier1_enabled=True)
    monkeypatch.setenv("EPIC_INCIDENT_TIER1", "0")
    assert tracker_enabled.attempt_tier1(tmp_path) is False


def test_incident_tracker_uses_canonical_epic_path_owner() -> None:
    """The runner must not retain a bare-import fallback for epic paths."""
    source = Path("loop/runner/orchestrator.py").read_text(encoding="utf-8")
    assert "from epic_paths import" not in source
    assert "except ImportError" not in source
    assert "DSH_PATH" not in source
    assert 'runtime/dev-hub/epic/checkpoint.json' not in source
    assert 'self.config.state_dir / "checkpoint.json"' in source


def test_roadmap_queue_uses_package_imports() -> None:
    """Roadmap runtime must not bootstrap a second bare-module import surface."""
    source = Path("loop/roadmap_queue.py").read_text(encoding="utf-8")
    assert "__import__(\"sys\")" not in source
    assert "from analyze_gate import" not in source
    assert "from epic import" not in source
    assert "from epic_paths import" not in source
