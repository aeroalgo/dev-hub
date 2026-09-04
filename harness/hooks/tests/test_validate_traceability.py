import pytest
from pathlib import Path
from epic.traceability import (
    parse_plan_requirements,
    parse_decompose_refs,
    run_checks,
    build_report,
)
from epic_resolve import main
import sys
import json


def test_md_primary_missing_fr(tmp_path: Path):
    """cp1: plan.md with FR-001, FR-002; decompose shard fr_ids: [FR-001] -> CRITICAL FR-002 uncovered."""
    plan_md_path = tmp_path / "plan.md"
    plan_md_path.write_text(
        "# Plan Test\n\n"
        "## Requirements\n\n"
        "FR-001 First requirement\n"
        "FR-002 Second requirement\n",
        encoding="utf-8",
    )

    reqs = parse_plan_requirements(plan_md_path)
    assert reqs == ["FR-001", "FR-002"]

    decomp_dir = tmp_path / "decompose"
    decomp_dir.mkdir()
    (decomp_dir / "s01.yaml").write_text("""schema: epic-decompose/v1
role: back
step_id: s01
plan_contract:
  fr_ids:
    - FR-001
""")

    decomp_refs = parse_decompose_refs(decomp_dir)
    findings = run_checks(reqs, decomp_refs, impl_ev={}, strict=False)

    critical_findings = [f for f in findings if f.severity == "CRITICAL"]
    assert len(critical_findings) == 1
    assert "FR-002" in critical_findings[0].message
    assert "no coverage" in critical_findings[0].message


def test_md_primary_pass(tmp_path: Path):
    """cp2: plan.md FR-001; decompose fr_ids: [FR-001] -> CRITICAL=0, PASS."""
    plan_md_path = tmp_path / "plan.md"
    plan_md_path.write_text(
        "# Plan Test\n\n"
        "## Requirements\n\n"
        "FR-001 First requirement\n",
        encoding="utf-8",
    )

    reqs = parse_plan_requirements(plan_md_path)
    assert reqs == ["FR-001"]

    decomp_dir = tmp_path / "decompose"
    decomp_dir.mkdir()
    (decomp_dir / "s01.yaml").write_text("""schema: epic-decompose/v1
role: back
step_id: s01
plan_contract:
  fr_ids:
    - FR-001
""")

    decomp_refs = parse_decompose_refs(decomp_dir)
    findings = run_checks(reqs, decomp_refs, impl_ev={}, strict=False)

    critical_findings = [f for f in findings if f.severity == "CRITICAL"]
    assert len(critical_findings) == 0

    report = build_report("T-TEST", reqs, decomp_refs, impl_ev={})
    assert report.critical_count == 0
    assert report.coverage_pct == 100.0


def test_yaml_plan_rejected(tmp_path: Path):
    """plan.yaml is not a valid requirements SoT — fail closed."""
    plan_yaml_path = tmp_path / "plan.yaml"
    plan_yaml_path.write_text(
        "schema: epic-plan/v1\n"
        "requirements:\n"
        "  - id: FR-001\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="plan.md only"):
        parse_plan_requirements(plan_yaml_path)


def test_cli_v2_plan_md_primary(tmp_path: Path, monkeypatch, capsys):
    """CLI validate-traceability primary resolution from layout v2 plan.md."""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan" / "T-TEST-CLI"
    md_dir = mb_dir / "md"
    yaml_dir = mb_dir / "yaml"
    steps_dir = yaml_dir / "steps"
    md_dir.mkdir(parents=True)
    steps_dir.mkdir(parents=True)

    (md_dir / "plan.md").write_text(
        "# Plan T-TEST-CLI\n\n"
        "## Requirements\n\n"
        "FR-001 CLI requirement 1\n",
        encoding="utf-8",
    )

    (steps_dir / "s01.yaml").write_text("""schema: epic-decompose/v1
role: back
step_id: s01
plan_contract:
  fr_ids:
    - FR-001
""")

    monkeypatch.setattr(
        sys,
        "argv",
        ["epic_resolve.py", "--cwd", str(tmp_path), "validate-traceability", "--epic", "T-TEST-CLI", "--json"],
    )
    code = main()
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["epic_id"] == "T-TEST-CLI"
    assert data["coverage_pct"] == 100.0
    assert data["critical_count"] == 0
    assert data["matrix"][0]["req_id"] == "FR-001"
    assert data["matrix"][0]["covered"] is True
