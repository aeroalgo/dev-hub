"""Tests for Janitor detectors."""

from pathlib import Path
import pytest
import yaml

from loop.janitor.detectors.orphan import detect_orphan_implement_yaml
from loop.janitor.detectors.dead_ref import detect_dead_plan_ref
from loop.janitor.detectors.duplicate_epic import detect_duplicate_epic_id
from loop.janitor.scan import scan


def test_detect_orphan_implement_yaml(tmp_path: Path):
    mb = tmp_path / "memory-bank" / "back"
    impl_dir = mb / "implement" / "T-HUB-999-orphan"
    impl_dir.mkdir(parents=True)
    (impl_dir / "s01.yaml").write_text("schema: epic-implement/v1\n", encoding="utf-8")

    plan_dir = mb / "plan"
    plan_dir.mkdir(parents=True)

    findings = detect_orphan_implement_yaml(tmp_path)
    assert len(findings) == 1
    assert findings[0].category == "orphan_implement_yaml"
    assert "T-HUB-999-orphan" in findings[0].description


def test_detect_dead_plan_ref(tmp_path: Path):
    mb = tmp_path / "memory-bank" / "back" / "plan" / "T-HUB-999-test" / "yaml" / "steps"
    mb.mkdir(parents=True)

    shard = mb / "s01-test.yaml"
    shard_data = {
        "schema": "epic-decompose/v1",
        "plan_id": "T-HUB-NONEXISTENT",
        "plan_refs": [
            "FR-001: memory-bank/back/plan/nonexistent.md",
        ],
    }
    shard.write_text(yaml.dump(shard_data), encoding="utf-8")

    findings = detect_dead_plan_ref(tmp_path)
    assert len(findings) >= 1
    categories = [f.category for f in findings]
    assert "dead_plan_ref" in categories


def test_detect_duplicate_epic_id(tmp_path: Path):
    mb1 = tmp_path / "memory-bank" / "back" / "plan" / "T-HUB-100-dup1" / "yaml"
    mb2 = tmp_path / "memory-bank" / "front" / "plan" / "T-HUB-100-dup2" / "yaml"
    mb1.mkdir(parents=True)
    mb2.mkdir(parents=True)

    idx1_data = {"schema": "epic-decompose-index/v1", "plan_id": "T-HUB-100-dup", "steps": []}
    idx2_data = {"schema": "epic-decompose-index/v1", "plan_id": "T-HUB-100-dup", "steps": []}

    (mb1 / "decompose-index.yaml").write_text(yaml.dump(idx1_data), encoding="utf-8")
    (mb2 / "decompose-index.yaml").write_text(yaml.dump(idx2_data), encoding="utf-8")

    findings = detect_duplicate_epic_id(tmp_path)
    assert len(findings) == 2
    assert findings[0].category == "duplicate_epic_id"
    assert findings[0].metadata["epic_id"] == "T-HUB-100-dup"


def test_scan_aggregates_detectors(tmp_path: Path):
    report = scan(tmp_path)
    assert report.cwd == str(tmp_path.resolve())
    assert report.schema == "janitor-report/v1"
