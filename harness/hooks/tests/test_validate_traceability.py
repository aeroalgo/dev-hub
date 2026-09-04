import pytest
import warnings
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


def test_yaml_primary_missing_fr(tmp_path: Path):
    """cp1: fixture: plan.yaml with requirements [FR-001, FR-002]; decompose shard with fr_ids: [FR-001] -> CRITICAL='FR-002 uncovered'."""
    plan_yaml_path = tmp_path / "plan.yaml"
    plan_yaml_path.write_text("""schema: epic-plan/v1
plan_id: T-TEST
level: standard
summary:
  step_count_floor: 2
  requirement_count: 2
requirements:
  - id: FR-001
    text: First requirement
  - id: FR-002
    text: Second requirement
""")

    reqs = parse_plan_requirements(plan_yaml_path)
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


def test_yaml_primary_pass(tmp_path: Path):
    """cp2: fixture: plan.yaml FR-001; decompose fr_ids: [FR-001] -> CRITICAL=0, PASS."""
    plan_yaml_path = tmp_path / "plan.yaml"
    plan_yaml_path.write_text("""schema: epic-plan/v1
plan_id: T-TEST
level: standard
summary:
  step_count_floor: 1
  requirement_count: 1
requirements:
  - id: FR-001
    text: First requirement
""")

    reqs = parse_plan_requirements(plan_yaml_path)
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


def test_md_fallback_deprecated(tmp_path: Path):
    """Post-purge: markdown files return empty requirements list (md fallback purged)."""
    plan_md_path = tmp_path / "plan.md"
    plan_md_path.write_text("""# Plan Test
| ID | Desc |
| FR-001 | First requirement |
| FR-002 | Second requirement |
""")

    reqs = parse_plan_requirements(plan_md_path)
    assert reqs == []


def test_cli_v2_plan_yaml_primary(tmp_path: Path, monkeypatch, capsys):
    """CLI validate-traceability primary resolution from layout v2 plan.yaml."""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan" / "T-TEST-CLI"
    yaml_dir = mb_dir / "yaml"
    steps_dir = yaml_dir / "steps"
    steps_dir.mkdir(parents=True)

    (yaml_dir / "plan.yaml").write_text("""schema: epic-plan/v1
plan_id: T-TEST-CLI
level: standard
summary:
  step_count_floor: 1
  requirement_count: 1
requirements:
  - id: FR-001
    text: CLI requirement 1
""")

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
