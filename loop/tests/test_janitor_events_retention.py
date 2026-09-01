"""Tests for events retention and orphan events directory detectors."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from loop.janitor.detectors.events_retention import (
    detect_orphan_events_dir,
    detect_episode_retention_exceeded,
)


def test_detect_orphan_events(tmp_path: Path) -> None:
    events_dir = tmp_path / "runtime" / "events"
    events_dir.mkdir(parents=True)

    orphan_dir = events_dir / "ep_orphan_123"
    orphan_dir.mkdir()

    valid_dir = events_dir / "ep_valid_456"
    valid_dir.mkdir()

    episodes_dir = tmp_path / "runtime" / "episodes" / "ep_valid_456"
    episodes_dir.mkdir(parents=True)
    manifest = {
        "schema": "loop-episode/v1",
        "episode_id": "ep_valid_456",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "epic_id": "T-HUB-034",
        "role": "back",
        "armed_step": "s03",
    }
    (episodes_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    findings = detect_orphan_events_dir(tmp_path)
    assert len(findings) == 1
    assert findings[0].category == "orphan_events_dir"
    assert "ep_orphan_123" in findings[0].target_path


def test_detect_retention_exceeded(tmp_path: Path) -> None:
    episodes_dir = tmp_path / "runtime" / "episodes"
    episodes_dir.mkdir(parents=True)

    # Fresh episode
    fresh_ep = episodes_dir / "ep_fresh"
    fresh_ep.mkdir()
    fresh_manifest = {
        "schema": "loop-episode/v1",
        "episode_id": "ep_fresh",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "epic_id": "T-HUB-034",
        "role": "back",
        "armed_step": "s03",
    }
    (fresh_ep / "manifest.json").write_text(json.dumps(fresh_manifest), encoding="utf-8")

    # Old episode (40 days old)
    old_ep = episodes_dir / "ep_old"
    old_ep.mkdir()
    old_time = datetime.now(timezone.utc) - timedelta(days=40)
    old_manifest = {
        "schema": "loop-episode/v1",
        "episode_id": "ep_old",
        "started_at": old_time.isoformat(),
        "epic_id": "T-HUB-034",
        "role": "back",
        "armed_step": "s03",
    }
    (old_ep / "manifest.json").write_text(json.dumps(old_manifest), encoding="utf-8")

    findings = detect_episode_retention_exceeded(tmp_path, max_age_days=30)
    assert len(findings) == 1
    assert findings[0].category == "episode_retention_exceeded"
    assert "ep_old" in findings[0].target_path
