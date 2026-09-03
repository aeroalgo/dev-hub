import json
import sys
from pathlib import Path
import pytest

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from epic.traceability import (
    ShardTrace,
    Evidence,
    Finding,
    TraceReport,
    run_checks,
    build_report,
    format_report,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "traceability"


def test_run_checks_critical_on_uncovered_req():
    plan_reqs = ["FR-001", "FR-002"]
    decomp_refs = {
        "s01": ShardTrace(step_id="s01", plan_refs=["plan-T-HUB-024 FR-001"]),
    }
    impl_ev = {}
    findings = run_checks(plan_reqs, decomp_refs, impl_ev)

    criticals = [f for f in findings if f.severity == "CRITICAL"]
    assert len(criticals) >= 1
    assert any("FR-002" in f.message for f in criticals)


def test_run_checks_critical_on_deferred_oos_without_follow_up():
    plan_reqs = ["FR-011"]
    decomp_refs = {
        "s01": ShardTrace(
            step_id="s01",
            plan_refs=[],
            out_of_scope=["FR-011 loop doctor — deferred follow-up"],
        ),
    }
    findings = run_checks(plan_reqs, decomp_refs, {})
    criticals = [f for f in findings if f.severity == "CRITICAL"]
    assert any("follow_up" in f.message for f in criticals)
    assert any("FR-011" in f.message for f in criticals)


def test_run_checks_valid_follow_up_oos_covers_req():
    plan_reqs = ["FR-011"]
    decomp_refs = {
        "s01": ShardTrace(
            step_id="s01",
            plan_refs=[],
            out_of_scope=["FR-011 deferred; follow_up: T-HUB-044-runtime-sync-doctor-docs"],
        ),
    }
    findings = run_checks(plan_reqs, decomp_refs, {})
    assert not any("FR-011 has no coverage" in f.message for f in findings)
    assert not any("without follow_up" in f.message for f in findings)


def test_run_checks_high_on_shard_no_plan_refs():
    plan_reqs = ["FR-001"]
    decomp_refs = {
        "s01": ShardTrace(step_id="s01", plan_refs=["FR-001"]),
        "s02": ShardTrace(step_id="s02", plan_refs=[], out_of_scope=[]),
    }
    impl_ev = {}
    findings = run_checks(plan_reqs, decomp_refs, impl_ev)

    highs = [f for f in findings if f.severity == "HIGH"]
    assert len(highs) >= 1
    assert any(f.shard == "s02" for f in highs)


def test_run_checks_high_on_completed_without_tests():
    plan_reqs = ["FR-001"]
    decomp_refs = {
        "s01": ShardTrace(step_id="s01", plan_refs=["FR-001"]),
    }
    impl_ev = {
        "s01": Evidence(step_id="s01", status="completed", files=["foo.py"], tests=[]),
    }
    findings = run_checks(plan_reqs, decomp_refs, impl_ev)

    highs = [f for f in findings if f.severity == "HIGH"]
    assert len(highs) >= 1
    assert any(f.shard == "s01" for f in highs)


def test_run_checks_strict_elevates_high_to_critical():
    plan_reqs = ["FR-001"]
    decomp_refs = {
        "s01": ShardTrace(step_id="s01", plan_refs=["FR-001"]),
        "s02": ShardTrace(step_id="s02", plan_refs=[], out_of_scope=[]),
    }
    impl_ev = {}
    findings_normal = run_checks(plan_reqs, decomp_refs, impl_ev, strict=False)
    findings_strict = run_checks(plan_reqs, decomp_refs, impl_ev, strict=True)

    assert any(f.severity == "HIGH" for f in findings_normal)
    assert not any(f.severity == "HIGH" for f in findings_strict)
    assert any(f.severity == "CRITICAL" and f.shard == "s02" for f in findings_strict)


def test_build_report_coverage_pct():
    plan_reqs = ["FR-001", "FR-002", "FR-003", "FR-004"]
    decomp_refs = {
        "s01": ShardTrace(step_id="s01", plan_refs=["FR-001", "FR-002"]),
        "s02": ShardTrace(step_id="s02", plan_refs=["FR-003"]),
    }
    impl_ev = {}
    report = build_report("T-HUB-024", plan_reqs, decomp_refs, impl_ev)

    assert report.coverage_pct == 75.0
    assert report.epic_id == "T-HUB-024"
    assert report.critical_count >= 1


def test_cli_exit0_clean_fixture(tmp_path: Path, monkeypatch):
    from epic_resolve import main

    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan-T-TEST.md").write_text(
        "# Plan T-TEST\n\n| ID | Desc |\n| FR-001 | Test |\n"
    )

    decomp_dir = plan_dir / "decompose-T-TEST"
    decomp_dir.mkdir()
    (decomp_dir / "s01.yaml").write_text("step_id: s01\nplan_refs: ['FR-001']\n")

    monkeypatch.setattr(sys, "argv", ["epic_resolve.py", "--cwd", str(tmp_path), "validate-traceability", "--epic", "T-TEST"])
    assert main() == 0


def test_cli_exit1_critical_finding(tmp_path: Path, monkeypatch):
    from epic_resolve import main

    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan-T-TEST.md").write_text(
        "# Plan T-TEST\n\n| ID | Desc |\n| FR-001 | Test 1 |\n| FR-002 | Test 2 |\n"
    )

    decomp_dir = plan_dir / "decompose-T-TEST"
    decomp_dir.mkdir()
    (decomp_dir / "s01.yaml").write_text("step_id: s01\nplan_refs: ['FR-001']\n")

    monkeypatch.setattr(sys, "argv", ["epic_resolve.py", "--cwd", str(tmp_path), "validate-traceability", "--epic", "T-TEST"])
    assert main() == 1


def test_cli_exit2_missing_plan(tmp_path: Path, monkeypatch):
    from epic_resolve import main

    monkeypatch.setattr(sys, "argv", ["epic_resolve.py", "--cwd", str(tmp_path), "validate-traceability", "--epic", "NONEXISTENT"])
    assert main() == 2


def test_cli_json_output_valid(tmp_path: Path, monkeypatch, capsys):
    from epic_resolve import main

    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan-T-TEST.md").write_text(
        "# Plan T-TEST\n\n| ID | Desc |\n| FR-001 | Test 1 |\n"
    )

    decomp_dir = plan_dir / "decompose-T-TEST"
    decomp_dir.mkdir()
    (decomp_dir / "s01.yaml").write_text("step_id: s01\nplan_refs: ['FR-001']\n")

    monkeypatch.setattr(sys, "argv", ["epic_resolve.py", "--cwd", str(tmp_path), "validate-traceability", "--epic", "T-TEST", "--json"])
    code = main()
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["epic_id"] == "T-TEST"
    assert data["coverage_pct"] == 100.0
    assert data["critical_count"] == 0
    assert "matrix" in data
    assert len(data["matrix"]) == 1
    assert data["matrix"][0]["req_id"] == "FR-001"
    assert data["matrix"][0]["covered"] is True
    assert data["matrix"][0]["shards"] == ["s01"]
