import sys
from pathlib import Path
import pytest

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from epic.convergence import (
    ConvergenceFinding,
    ConvergenceReport,
    run_convergence_checks,
    _dedupe_findings,
)


def test_schema_constant():
    report = ConvergenceReport(plan_id="T-HUB-032")
    assert report.schema == "convergence-report/v1"
    assert ConvergenceReport.__dataclass_fields__["schema"].default == "convergence-report/v1"


def test_dedupe_findings():
    f1 = ConvergenceFinding(
        id="CF-001",
        category="orphan_requirement",
        severity="CRITICAL",
        message="Requirement FR-001 has no coverage in decompose shards",
    )
    f2 = ConvergenceFinding(
        id="CF-002",
        category="orphan_requirement",
        severity="CRITICAL",
        message="Requirement FR-001 has no coverage in decompose shards",
    )
    f3 = ConvergenceFinding(
        id="CF-003",
        category="ac_gap",
        severity="HIGH",
        message="Shard s01 missing tests",
    )
    result = _dedupe_findings([f1, f2, f3])
    assert len(result) == 2
    assert result[0].id == "CF-001"
    assert result[1].id == "CF-003"


def test_run_convergence_smoke(tmp_path: Path):
    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    decomp_dir = plan_dir / "decompose-T-HUB-TEST"
    decomp_dir.mkdir(parents=True)

    plan_file = plan_dir / "plan-T-HUB-TEST.md"
    plan_file.write_text("# Plan T-HUB-TEST\n| Path | Action |\n| `file.py` | Create |\nRequirement FR-001", encoding="utf-8")

    index_file = decomp_dir / "index.yaml"
    index_file.write_text("plan_id: T-HUB-TEST\nsteps:\n  - id: s01\n    file: s01.yaml\n", encoding="utf-8")

    shard_file = decomp_dir / "s01.yaml"
    shard_file.write_text("step_id: s01\nplan_refs: [FR-001]\n", encoding="utf-8")

    report = run_convergence_checks(tmp_path, "T-HUB-TEST")
    assert isinstance(report, ConvergenceReport)
    assert report.plan_id == "T-HUB-TEST"
    assert isinstance(report.findings, list)


def test_stale_handoff_category(tmp_path: Path):
    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    decomp_dir = plan_dir / "decompose-T-HUB-TEST"
    decomp_dir.mkdir(parents=True)
    (plan_dir / "plan-T-HUB-TEST.md").write_text("FR-001", encoding="utf-8")
    (decomp_dir / "index.yaml").write_text("plan_id: T-HUB-TEST\nsteps: []\n", encoding="utf-8")

    mb_dir = tmp_path / "memory-bank"
    active_ctx = mb_dir / "activeContext.md"
    active_ctx.write_text("## projection\n- phase: BACK IMPLEMENT\n- epic: T-HUB-TEST\n\nNo handoff block here", encoding="utf-8")

    report = run_convergence_checks(tmp_path, "T-HUB-TEST")
    stale_findings = [f for f in report.findings if f.category == "stale_handoff"]
    assert len(stale_findings) >= 1
    assert stale_findings[0].category == "stale_handoff"


def test_orphan_req_wrapping(tmp_path: Path):
    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    decomp_dir = plan_dir / "decompose-T-HUB-TEST"
    decomp_dir.mkdir(parents=True)

    (plan_dir / "plan-T-HUB-TEST.md").write_text("Requirement FR-999 is uncovered", encoding="utf-8")
    (decomp_dir / "index.yaml").write_text("plan_id: T-HUB-TEST\nsteps:\n  - id: s01\n    file: s01.yaml\n", encoding="utf-8")
    (decomp_dir / "s01.yaml").write_text("step_id: s01\nplan_refs: []\n", encoding="utf-8")

    report = run_convergence_checks(tmp_path, "T-HUB-TEST")
    criticals = [f for f in report.findings if f.severity == "CRITICAL"]
    assert len(criticals) >= 1
    orphan_reqs = [f for f in report.findings if f.category == "orphan_requirement"]
    assert len(orphan_reqs) >= 1
    assert orphan_reqs[0].severity == "CRITICAL"
