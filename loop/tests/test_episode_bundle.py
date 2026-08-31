"""Tests for episode artifact bundle copying logic (s03)."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from loop.episodes.bundle import copy_artifacts
from loop.episodes.core import begin_episode, finalize_episode
from loop.incidents.trace import append_trace


def test_check_after_json_in_bundle(tmp_path: Path) -> None:
    ep_id = begin_episode(tmp_path)
    ca_res = {"sNN": "s03", "decide": "PASS", "prompt": "secret prompt"}
    manifest = finalize_episode(tmp_path, ep_id, check_after_result=ca_res)

    ep_dir = tmp_path / ".claude" / "runtime" / "episodes" / ep_id
    ca_file = ep_dir / "check_after.json"
    assert ca_file.is_file()

    content = json.loads(ca_file.read_text(encoding="utf-8"))
    assert content["sNN"] == "s03"
    assert content["decide"] == "PASS"
    assert "prompt" not in content  # secret prompt stripped when env guard not set
    assert manifest.artifact_refs.get("check_after") == "check_after.json"


def test_checkpoint_snapshot_copied(tmp_path: Path) -> None:
    epic_runtime = tmp_path / ".claude" / "runtime" / "epic"
    epic_runtime.mkdir(parents=True, exist_ok=True)
    cp_file = epic_runtime / "checkpoint.json"
    cp_file.write_text(json.dumps({"state": "ok"}), encoding="utf-8")

    ep_id = begin_episode(tmp_path)
    manifest = finalize_episode(tmp_path, ep_id)

    ep_dir = tmp_path / ".claude" / "runtime" / "episodes" / ep_id
    cp_copy = ep_dir / "checkpoint_snapshot.json"
    assert cp_copy.is_file()
    data = json.loads(cp_copy.read_text(encoding="utf-8"))
    assert data["state"] == "ok"
    assert manifest.artifact_refs.get("checkpoint_snapshot") == "checkpoint_snapshot.json"


def test_trace_tail_in_bundle(tmp_path: Path) -> None:
    epic_runtime = tmp_path / ".claude" / "runtime" / "epic"
    epic_runtime.mkdir(parents=True, exist_ok=True)

    append_trace(epic_runtime, "test_phase", action="step1")
    append_trace(epic_runtime, "test_phase", action="step2")

    ep_id = begin_episode(tmp_path)
    manifest = finalize_episode(tmp_path, ep_id)

    ep_dir = tmp_path / ".claude" / "runtime" / "episodes" / ep_id
    tt_file = ep_dir / "trace_tail.jsonl"
    assert tt_file.is_file()

    lines = [line for line in tt_file.read_text(encoding="utf-8").split("\n") if line.strip()]
    assert len(lines) == 2
    assert "step1" in lines[0]
    assert "step2" in lines[1]
    assert manifest.artifact_refs.get("trace_tail") == "trace_tail.jsonl"


def test_manifest_has_artifact_refs(tmp_path: Path) -> None:
    epic_runtime = tmp_path / ".claude" / "runtime" / "epic"
    epic_runtime.mkdir(parents=True, exist_ok=True)
    (epic_runtime / "checkpoint.json").write_text("{}", encoding="utf-8")

    ep_id = begin_episode(tmp_path)
    ca_res = {"sNN": "s03"}
    manifest = finalize_episode(tmp_path, ep_id, check_after_result=ca_res)

    assert "check_after" in manifest.artifact_refs
    assert "checkpoint_snapshot" in manifest.artifact_refs


def test_copy_failure_graceful(tmp_path: Path) -> None:
    ep_id = begin_episode(tmp_path)
    # no checkpoint, no trace, check_after passed
    manifest = finalize_episode(tmp_path, ep_id, check_after_result={"sNN": "s01"})
    assert manifest.episode_id == ep_id
    assert "check_after" in manifest.artifact_refs


def test_load_now_sha256_snapshot(tmp_path: Path) -> None:
    f1 = tmp_path / "foo.txt"
    f1.write_text("hello", encoding="utf-8")

    ep_id = begin_episode(tmp_path)
    manifest = finalize_episode(
        tmp_path,
        ep_id,
        check_after_result={"load_now_paths": [str(f1)]},
    )

    assert len(manifest.load_now_sha256) == 1
    assert len(manifest.load_now_sha256[0]) == 64
