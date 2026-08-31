"""Unit tests for episode retention logic."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from loop.episodes.core import episode_dir
from loop.episodes.retention import prune_episodes


def _create_dummy_episode(cwd: Path, episode_id: str, age_days: int, ended: bool = True) -> Path:
    ep_path = episode_dir(cwd, episode_id)
    ep_path.mkdir(parents=True, exist_ok=True)
    dt = datetime.now(timezone.utc) - timedelta(days=age_days)
    dt_str = dt.isoformat()

    manifest_data = {
        "schema": "loop-episode/v1",
        "episode_id": episode_id,
        "started_at": dt_str,
        "ended_at": dt_str if ended else None,
        "epic_id": "T-HUB-031",
        "role": "back",
        "armed_step": "s06",
    }
    (ep_path / "manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")
    return ep_path


def test_prune_deletes_old_episodes(tmp_path: Path) -> None:
    _create_dummy_episode(tmp_path, "ep-old-01", age_days=35)
    _create_dummy_episode(tmp_path, "ep-new-01", age_days=5)

    count = prune_episodes(tmp_path, days=30)
    assert count == 1
    assert not episode_dir(tmp_path, "ep-old-01").exists()
    assert episode_dir(tmp_path, "ep-new-01").exists()


def test_prune_keeps_recent_episodes(tmp_path: Path) -> None:
    _create_dummy_episode(tmp_path, "ep-new-01", age_days=5)
    _create_dummy_episode(tmp_path, "ep-new-02", age_days=10)

    count = prune_episodes(tmp_path, days=30)
    assert count == 0
    assert episode_dir(tmp_path, "ep-new-01").exists()
    assert episode_dir(tmp_path, "ep-new-02").exists()


def test_prune_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EPIC_EPISODE_RETENTION_DAYS", "7")
    _create_dummy_episode(tmp_path, "ep-mid-01", age_days=8)

    count = prune_episodes(tmp_path, days=None)
    assert count == 1
    assert not episode_dir(tmp_path, "ep-mid-01").exists()


def test_prune_missing_manifest_graceful(tmp_path: Path) -> None:
    bad_dir = episode_dir(tmp_path, "ep-bad-01")
    bad_dir.mkdir(parents=True, exist_ok=True)
    # No manifest.json

    count = prune_episodes(tmp_path, days=30)
    assert count == 0
    assert bad_dir.exists()


def test_prune_returns_count(tmp_path: Path) -> None:
    _create_dummy_episode(tmp_path, "ep-old-01", age_days=31)
    _create_dummy_episode(tmp_path, "ep-old-02", age_days=40)
    _create_dummy_episode(tmp_path, "ep-old-03", age_days=50)

    count = prune_episodes(tmp_path, days=30)
    assert count == 3
