import sys
from pathlib import Path
import pytest

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from epic.traceability import (
    parse_plan_requirements,
    parse_decompose_refs,
    parse_implement_evidence,
    ShardTrace,
    Evidence,
    TraceReport,
    Finding,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "traceability"


def test_parse_plan_requirements_extracts_fr_sc_us():
    plan_path = FIXTURES_DIR / "plan.md"
    reqs = parse_plan_requirements(plan_path)
    assert reqs == ["FR-001", "FR-002", "FR-003", "FR-004"]


def test_parse_plan_requirements_empty_on_missing_table(tmp_path: Path):
    missing_file = tmp_path / "non_existent.md"
    assert parse_plan_requirements(missing_file) == []

    no_table_file = tmp_path / "empty.md"
    no_table_file.write_text("# Title\n\nNo requirements here.\n")
    assert parse_plan_requirements(no_table_file) == []


def test_parse_decompose_refs_collects_plan_refs():
    decompose_dir = FIXTURES_DIR / "decompose"
    shards = parse_decompose_refs(decompose_dir)
    assert "s01" in shards
    assert "s02" in shards
    assert shards["s01"].plan_refs == ["plan-T-HUB-024 FR-001", "plan-T-HUB-024 FR-002"]
    assert shards["s02"].plan_refs == ["plan-T-HUB-024 FR-003"]


def test_parse_decompose_refs_out_of_scope_collected():
    decompose_dir = FIXTURES_DIR / "decompose"
    shards = parse_decompose_refs(decompose_dir)
    assert shards["s01"].out_of_scope == ["FR-004 is out of scope for now"]
    assert shards["s02"].out_of_scope == []


def test_parse_implement_evidence_reads_status_files_tests():
    implement_dir = FIXTURES_DIR / "implement"
    evidence_map = parse_implement_evidence(implement_dir)
    assert "s01" in evidence_map
    ev = evidence_map["s01"]
    assert ev.status == "completed"
    assert ev.files == [".claude/hooks/epic/traceability.py"]
    assert ev.tests == ["loop/tests/test_traceability_parsers.py"]


def test_parse_implement_evidence_defaults_on_missing_keys(tmp_path: Path):
    imp_dir = tmp_path / "implement"
    imp_dir.mkdir()
    shard_file = imp_dir / "s01-empty.yaml"
    shard_file.write_text("step_id: s01\n")

    evidence_map = parse_implement_evidence(imp_dir)
    assert "s01" in evidence_map
    ev = evidence_map["s01"]
    assert ev.status == "pending"
    assert ev.files == []
    assert ev.tests == []
