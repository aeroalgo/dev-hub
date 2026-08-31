"""Tests for loop episode schema and core module functions."""

import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from loop.schemas.episode import EpisodeManifest, EPISODE_SCHEMA
from loop.episodes import begin_episode, finalize_episode, episode_dir


def test_episode_manifest_schema():
    """cp1: EpisodeManifest validation with minimal fields."""
    manifest = EpisodeManifest(
        episode_id="20260831_120000_thub031_abcd",
        started_at="2026-08-31T12:00:00Z",
        epic_id="T-HUB-031",
        role="back",
        armed_step="s01",
    )
    assert manifest.schema == EPISODE_SCHEMA
    assert manifest.episode_id == "20260831_120000_thub031_abcd"
    assert manifest.incident_ids == []

    with pytest.raises(ValidationError):
        EpisodeManifest.model_validate({"schema": "invalid-schema/v1"})


def test_episode_manifest_full():
    """test full fields including lists/optionals."""
    manifest = EpisodeManifest(
        episode_id="20260831_120000_thub031_abcd",
        started_at="2026-08-31T12:00:00Z",
        ended_at="2026-08-31T12:05:00Z",
        epic_id="T-HUB-031",
        role="back",
        armed_step="s01",
        sNN="s01",
        prompt_hash="abc123hash",
        fingerprint_before="fp_before",
        fingerprint_after="fp_after",
        decide="ADVANCE",
        incident_ids=["INC-1"],
        event_seq_range=[1, 10],
        load_now_paths=["path/a"],
        load_now_sha256=["sha256_a"],
    )
    assert manifest.decide == "ADVANCE"
    assert manifest.incident_ids == ["INC-1"]


def test_begin_episode_creates_dir(tmp_path: Path):
    """cp2: begin_episode creates episode_dir, returns episode_id string, contains manifest-stub."""
    ep_id = begin_episode(tmp_path, epic_id="T-HUB-031", role="back", armed_step="s01")
    assert isinstance(ep_id, str)
    assert "thub031" in ep_id

    ep_path = episode_dir(tmp_path, ep_id)
    assert ep_path.is_dir()
    stub_file = ep_path / "manifest-stub.json"
    assert stub_file.is_file()

    stub_data = json.loads(stub_file.read_text(encoding="utf-8"))
    assert stub_data["episode_id"] == ep_id
    assert stub_data["epic_id"] == "T-HUB-031"


def test_finalize_episode_writes_manifest(tmp_path: Path):
    """cp3: finalize_episode writes valid manifest.json."""
    ep_id = begin_episode(tmp_path, epic_id="T-HUB-031", role="back", armed_step="s01")
    check_after = {
        "sNN": "s01",
        "decide": "ADVANCE",
        "load_now_paths": ["loop/schemas/episode.py"],
    }
    manifest = finalize_episode(tmp_path, ep_id, check_after_result=check_after)
    assert isinstance(manifest, EpisodeManifest)
    assert manifest.sNN == "s01"
    assert manifest.decide == "ADVANCE"
    assert manifest.ended_at is not None

    ep_path = episode_dir(tmp_path, ep_id)
    manifest_file = ep_path / "manifest.json"
    assert manifest_file.is_file()


def test_episode_dir_path(tmp_path: Path):
    """cp4: episode_dir returns path under runtime/<slug>/episodes/<episode_id>/."""
    ep_path = episode_dir(tmp_path, "ep_123")
    assert ep_path.name == "ep_123"
    assert "episodes" in ep_path.parts


def test_canary_episode_created_and_valid(tmp_path: Path):
    """Integration canary test: begin_episode -> prepare mock -> finalize -> valid episode package."""
    ep_id = begin_episode(tmp_path, epic_id="T-HUB-031", role="back", armed_step="s06")
    assert isinstance(ep_id, str)

    check_after = {
        "sNN": "s06",
        "decide": "ADVANCE",
        "load_now_paths": ["loop/schemas/episode.py"],
    }
    manifest = finalize_episode(tmp_path, ep_id, check_after_result=check_after)
    assert manifest.episode_id == ep_id
    assert manifest.schema == EPISODE_SCHEMA
    assert manifest.epic_id == "T-HUB-031"
    assert manifest.role == "back"
    assert manifest.armed_step == "s06"
    assert manifest.ended_at is not None

    ep_path = episode_dir(tmp_path, ep_id)
    manifest_file = ep_path / "manifest.json"
    assert manifest_file.is_file()

    # Validate json content directly against EpisodeManifest pydantic model
    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    loaded_manifest = EpisodeManifest.model_validate(data)
    assert loaded_manifest.episode_id == ep_id


def test_episode_id_format(tmp_path: Path):
    """Episode ID format check."""
    ep_id = begin_episode(tmp_path, epic_id="T-HUB-031")
    parts = ep_id.split("_")
    assert len(parts) >= 4
    # date part YYYYMMDD
    assert len(parts[0]) == 8
    # time part HHMMSS
    assert len(parts[1]) == 6
