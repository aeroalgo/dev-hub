import sys
from pathlib import Path
import pytest

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from epic.traceability import (
    scan_ac_markers,
    enrich_with_ac,
    TraceReport,
    Finding,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "traceability"


def test_scan_ac_markers_finds_marks_in_fixture():
    tests_dir = FIXTURES_DIR / "tests"
    ac_map = scan_ac_markers(tests_dir)
    assert "FR-001" in ac_map
    assert "FR-002" in ac_map
    assert len(ac_map["FR-001"]) >= 1
    assert len(ac_map["FR-002"]) >= 1


def test_scan_ac_markers_no_dir_returns_empty(tmp_path: Path):
    assert scan_ac_markers(None) == {}
    missing_dir = tmp_path / "non_existent_dir"
    assert scan_ac_markers(missing_dir) == {}


def test_enrich_with_ac_medium_on_uncovered_req():
    report = TraceReport(
        epic_id="T-HUB-024",
        requirements=["FR-001", "FR-002"],
        shards={},
        evidence={},
        findings=[],
        coverage_pct=100.0,
    )
    ac_map = {"FR-001": ["test_foo.py"]}
    enrich_with_ac(report, ac_map, strict=False)

    mediums = [f for f in report.findings if f.severity == "MEDIUM"]
    assert len(mediums) == 1
    assert "FR-002" in mediums[0].message


def test_enrich_with_ac_strict_elevates_to_high():
    report = TraceReport(
        epic_id="T-HUB-024",
        requirements=["FR-001", "FR-002"],
        shards={},
        evidence={},
        findings=[],
        coverage_pct=100.0,
    )
    ac_map = {"FR-001": ["test_foo.py"]}
    enrich_with_ac(report, ac_map, strict=True)

    highs = [f for f in report.findings if f.severity == "HIGH"]
    assert len(highs) == 1
    assert "FR-002" in highs[0].message
    assert report.high_count == 1


def test_enrich_with_ac_noop_when_all_covered():
    report = TraceReport(
        epic_id="T-HUB-024",
        requirements=["FR-001", "FR-002"],
        shards={},
        evidence={},
        findings=[],
        coverage_pct=100.0,
    )
    ac_map = {
        "FR-001": ["test_foo.py"],
        "FR-002": ["test_bar.py"],
    }
    enrich_with_ac(report, ac_map, strict=False)
    assert len(report.findings) == 0
