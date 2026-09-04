"""Integration tests for validate-traceability via epic_resolve CLI and context_loop integration."""
import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.ac("AC-005")
def test_traceability_integration_exit0_on_clean_fixture(tmp_path: Path):
    """Test validate-traceability exit 0 and JSON report structure on a valid fixture."""
    epic_root = tmp_path / "memory-bank" / "back" / "plan" / "T-TEST-001"
    md_dir = epic_root / "md"
    yaml_dir = epic_root / "yaml"
    decomp_dir = yaml_dir / "steps"
    md_dir.mkdir(parents=True, exist_ok=True)
    decomp_dir.mkdir(parents=True, exist_ok=True)

    (md_dir / "plan.md").write_text(
        """# Plan T-TEST-001

## Requirements

US-001 Test Story
FR-001 Test FR
SC-001 Test SC
""",
        encoding="utf-8",
    )

    (yaml_dir / "decompose-index.yaml").write_text(
        """schema: epic-decompose-index/v1
plan_id: T-TEST-001
source_md: index.md
status_canon: index.yaml
steps:
- id: s01
  file: s01-test.yaml
  title: Test Step
  next_phase: BACK IMPLEMENT
  status: pending
""",
        encoding="utf-8",
    )

    (decomp_dir / "s01-test.yaml").write_text(
        """schema: epic-decompose/v1
role: back
step_id: s01
plan_id: T-TEST-001
title: Test Step
next_phase: BACK IMPLEMENT
needs_creative: "no"
goal: Goal
context:
  consumes: []
  produces: []
  plan_refs:
    - "plan-T-TEST-001 US-001"
    - "plan-T-TEST-001 FR-001"
    - "plan-T-TEST-001 SC-001"
  files: []
as_built: []
delta: []
deletes: []
out_of_scope: []
skills:
  code_surface: infra
  impl: []
checkpoints: []
verify: []
tdd: []
""",
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[2]
    cli_path = repo_root / ".claude" / "hooks" / "epic_resolve.py"

    cmd = [
        sys.executable,
        str(cli_path),
        "--cwd",
        str(tmp_path),
        "validate-traceability",
        "--epic",
        "T-TEST-001",
        "--json",
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"Expected exit 0, got {res.returncode}. Stderr: {res.stderr}, Stdout: {res.stdout}"

    report = json.loads(res.stdout)
    assert report["epic_id"] == "T-TEST-001"
    assert report["critical_count"] == 0
    assert report["coverage_pct"] == 100.0


@pytest.mark.ac("AC-005")
def test_traceability_integration_exit1_on_uncovered_req(tmp_path: Path):
    """Test validate-traceability exit 1 when requirements are uncovered."""
    epic_root = tmp_path / "memory-bank" / "back" / "plan" / "T-TEST-002"
    md_dir = epic_root / "md"
    yaml_dir = epic_root / "yaml"
    decomp_dir = yaml_dir / "steps"
    md_dir.mkdir(parents=True, exist_ok=True)
    decomp_dir.mkdir(parents=True, exist_ok=True)

    (md_dir / "plan.md").write_text(
        """# Plan T-TEST-002

## Requirements

US-001 Covered Story
US-002 Uncovered Story
""",
        encoding="utf-8",
    )

    (yaml_dir / "decompose-index.yaml").write_text(
        """schema: epic-decompose-index/v1
plan_id: T-TEST-002
source_md: index.md
status_canon: index.yaml
steps:
- id: s01
  file: s01-test.yaml
  title: Test Step
  next_phase: BACK IMPLEMENT
  status: pending
""",
        encoding="utf-8",
    )

    (decomp_dir / "s01-test.yaml").write_text(
        """schema: epic-decompose/v1
role: back
step_id: s01
plan_id: T-TEST-002
title: Test Step
next_phase: BACK IMPLEMENT
needs_creative: "no"
goal: Goal
context:
  consumes: []
  produces: []
  plan_refs:
    - "plan-T-TEST-002 US-001"
  files: []
as_built: []
delta: []
deletes: []
out_of_scope: []
skills:
  code_surface: infra
  impl: []
checkpoints: []
verify: []
tdd: []
""",
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[2]
    cli_path = repo_root / ".claude" / "hooks" / "epic_resolve.py"

    cmd = [
        sys.executable,
        str(cli_path),
        "--cwd",
        str(tmp_path),
        "validate-traceability",
        "--epic",
        "T-TEST-002",
        "--json",
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 1, f"Expected exit 1, got {res.returncode}. Stderr: {res.stderr}, Stdout: {res.stdout}"

    report = json.loads(res.stdout)
    assert report["epic_id"] == "T-TEST-002"
    assert report["critical_count"] == 1
    assert report["coverage_pct"] == 50.0
