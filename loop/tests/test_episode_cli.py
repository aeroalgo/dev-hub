"""Tests for episode CLI subcommands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loop.context_loop import main
from loop.episodes.cli import episode_list, format_episode_list, scan_episodes, show_episode
from loop.episodes.core import episode_dir
from loop.schemas.episode import EpisodeManifest


@pytest.fixture
def sample_episodes(tmp_path: Path):
    ep1_dir = episode_dir(tmp_path, "20260831_120000")
    ep1_dir.mkdir(parents=True, exist_ok=True)
    m1 = EpisodeManifest(
        episode_id="20260831_120000",
        started_at="2026-08-31T12:00:00Z",
        epic_id="T-HUB-031",
        role="back",
        decide="ARM_STEP",
        armed_step="s01",
        halt_reason=None,
    )
    (ep1_dir / "manifest.json").write_text(
        json.dumps(m1.model_dump(mode="json")), encoding="utf-8"
    )

    ep2_dir = episode_dir(tmp_path, "20260831_120500")
    ep2_dir.mkdir(parents=True, exist_ok=True)
    m2 = EpisodeManifest(
        episode_id="20260831_120500",
        started_at="2026-08-31T12:05:00Z",
        epic_id="T-HUB-031",
        role="back",
        decide="HALT",
        armed_step="s02",
        halt_reason="test_halt",
    )
    (ep2_dir / "manifest.json").write_text(
        json.dumps(m2.model_dump(mode="json")), encoding="utf-8"
    )

    art_dir = ep2_dir / "artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)
    (art_dir / "log.txt").write_text("hello log", encoding="utf-8")

    return tmp_path


def test_scan_episodes_sort_desc(sample_episodes: Path):
    manifests = scan_episodes(sample_episodes)
    assert len(manifests) == 2
    assert manifests[0].episode_id == "20260831_120500"
    assert manifests[1].episode_id == "20260831_120000"


def test_episode_list_empty(tmp_path: Path, capsys):
    res = episode_list(tmp_path)
    assert res == []

    rc = main(["--cwd", str(tmp_path), "episode-list"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "No episodes found." in captured.out


def test_episode_list_output(sample_episodes: Path, capsys):
    rc = main(["--cwd", str(sample_episodes), "episode-list"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "20260831_120500" in captured.out
    assert "HALT" in captured.out
    assert "20260831_120000" in captured.out
    assert "ARM_STEP" in captured.out


def test_episode_list_last_n(sample_episodes: Path):
    res = episode_list(sample_episodes, last=1)
    assert len(res) == 1
    assert res[0]["episode_id"] == "20260831_120500"


def test_episode_show_output(sample_episodes: Path, capsys):
    rc = main(["--cwd", str(sample_episodes), "episode-show", "20260831_120500"])
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["episode_id"] == "20260831_120500"
    assert data["decide"] == "HALT"
    assert "log.txt" in data["artifacts_bundle"]


def test_episode_show_not_found(tmp_path: Path, capsys):
    rc = main(["--cwd", str(tmp_path), "episode-show", "20260831_999999"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "Episode manifest not found" in captured.err
