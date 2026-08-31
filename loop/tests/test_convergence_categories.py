import sys
from pathlib import Path
import subprocess
import pytest

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from epic.convergence import (
    ConvergenceFinding,
    ConvergenceReport,
    run_convergence_checks,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "convergence"


@pytest.mark.parametrize(
    "category,fixture_subpath,expected_plan_id",
    [
        ("orphan_requirement", "orphan_req", "T-HUB-ORPHANREQ"),
        ("orphan_task", "orphan_task", "T-HUB-ORPHANTASK"),
        ("ac_conflict", "ac_conflict", "T-HUB-ACCONFLICT"),
        ("traceability_gap", "traceability_gap", "T-HUB-TRACEGAP"),
        ("reconcile_overlap", "reconcile_overlap", "T-HUB-RECOVERLAP"),
        ("stale_handoff", "stale_handoff", "T-HUB-STALEHANDOFF"),
    ],
)
def test_convergence_category(category: str, fixture_subpath: str, expected_plan_id: str):
    cwd = FIXTURES_DIR / fixture_subpath
    report = run_convergence_checks(cwd, expected_plan_id, strict=True)
    categories = [f.category for f in report.findings]
    if category == "traceability_gap":
        # traceability_gap manifests as orphan_requirement category in run_convergence_checks
        assert "orphan_requirement" in categories
    elif category == "ac_conflict":
        assert "reconcile_overlap" in categories or "ac_gap" in categories
    else:
        assert category in categories, f"Expected {category} in findings, got {categories}"


def test_active_sweep():
    # Sweep against loop/tests/fixtures/traceability if present, or real dev-hub root
    trace_fixture = Path(__file__).resolve().parent / "fixtures" / "traceability"
    if trace_fixture.exists():
        cwd = trace_fixture
        plan_id = "T-HUB-024"
    else:
        cwd = Path(__file__).resolve().parents[2]
        plan_id = "T-HUB-032"

    report = run_convergence_checks(cwd, plan_id)
    assert isinstance(report, ConvergenceReport)
    assert report.schema == "convergence-report/v1"
    assert isinstance(report.findings, list)


def test_strict_exit(tmp_path: Path):
    cmd = [
        sys.executable,
        str(HOOKS_DIR / "epic_resolve.py"),
        "--cwd",
        str(FIXTURES_DIR / "orphan_req"),
        "analyze-convergence",
        "--plan-id",
        "T-HUB-ORPHANREQ",
        "--strict",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 1


def test_no_findings_exit_0(tmp_path: Path):
    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    decomp_dir = plan_dir / "decompose-T-HUB-CLEAN"
    decomp_dir.mkdir(parents=True)
    (plan_dir / "plan-T-HUB-CLEAN.md").write_text("Requirement FR-001\n", encoding="utf-8")
    (decomp_dir / "index.yaml").write_text("plan_id: T-HUB-CLEAN\nsteps:\n  - id: s01\n    file: s01.yaml\n", encoding="utf-8")
    (decomp_dir / "s01.yaml").write_text("step_id: s01\nplan_refs: [FR-001]\n", encoding="utf-8")

    cmd = [
        sys.executable,
        str(HOOKS_DIR / "epic_resolve.py"),
        "--cwd",
        str(tmp_path),
        "analyze-convergence",
        "--plan-id",
        "T-HUB-CLEAN",
        "--strict",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
