"""Tests for Janitor detectors."""

from pathlib import Path
import pytest
import yaml

from loop.janitor.detectors.orphan import detect_orphan_implement_yaml
from loop.janitor.detectors.stale_index import detect_stale_index_status
from loop.janitor.detectors.dead_ref import detect_dead_plan_ref
from loop.janitor.detectors.duplicate_epic import detect_duplicate_epic_id
from loop.janitor.scan import scan


def test_detect_orphan_implement_yaml(tmp_path: Path):
    mb = tmp_path / "memory-bank" / "back"
    impl_dir = mb / "implement" / "implement-T-HUB-999-orphan"
    impl_dir.mkdir(parents=True)
    (impl_dir / "s01.yaml").write_text("schema: epic-implement/v1\n", encoding="utf-8")

    plan_dir = mb / "plan"
    plan_dir.mkdir(parents=True)

    findings = detect_orphan_implement_yaml(tmp_path)
    assert len(findings) == 1
    assert findings[0].category == "orphan_implement_yaml"
    assert "T-HUB-999-orphan" in findings[0].description


def test_detect_stale_index(tmp_path: Path):
    mb = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-HUB-999-test"
    mb.mkdir(parents=True)

    index_yaml = mb / "index.yaml"
    index_yaml_data = {
        "schema": "epic-decompose-index/v1",
        "epic_id": "T-HUB-999-test",
        "steps": [
            {"id": "s01", "status": "completed"},
        ],
    }
    index_yaml.write_text(yaml.dump(index_yaml_data), encoding="utf-8")

    index_md = mb / "index.md"
    index_md_content = """# Index
| Step | Title | Status |
|---|---|---|
| **s01** | [s01.yaml](s01.yaml) | pending |
"""
    index_md.write_text(index_md_content, encoding="utf-8")

    findings = detect_stale_index_status(tmp_path)
    assert len(findings) == 1
    assert findings[0].category == "stale_index_status"
    assert findings[0].metadata["step_id"] == "s01"
    assert findings[0].metadata["md_status"] == "pending"
    assert findings[0].metadata["yaml_status"] == "completed"


def test_detect_dead_plan_ref(tmp_path: Path):
    mb = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-HUB-999-test"
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
    mb1 = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-HUB-100-dup1"
    mb2 = tmp_path / "memory-bank" / "front" / "plan" / "decompose-T-HUB-100-dup2"
    mb1.mkdir(parents=True)
    mb2.mkdir(parents=True)

    idx1_data = {"schema": "epic-decompose-index/v1", "epic_id": "T-HUB-100-dup", "steps": []}
    idx2_data = {"schema": "epic-decompose-index/v1", "epic_id": "T-HUB-100-dup", "steps": []}

    (mb1 / "index.yaml").write_text(yaml.dump(idx1_data), encoding="utf-8")
    (mb2 / "index.yaml").write_text(yaml.dump(idx2_data), encoding="utf-8")

    findings = detect_duplicate_epic_id(tmp_path)
    assert len(findings) == 2
    assert findings[0].category == "duplicate_epic_id"
    assert findings[0].metadata["epic_id"] == "T-HUB-100-dup"


def test_scan_aggregates_detectors(tmp_path: Path):
    report = scan(tmp_path)
    assert report.cwd == str(tmp_path.resolve())
    assert report.schema == "janitor-report/v1"
