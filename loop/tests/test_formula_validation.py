"""Tests for formula validation and exit codes (s05)."""

import subprocess
import sys
from pathlib import Path
import pytest
from loop.schemas.formula import load_formula, DecomposeFormula


def test_valid_formula_exit0(tmp_path: Path):
    """Valid formula loads cleanly."""
    f_path = tmp_path / "valid.yaml"
    f_path.write_text(
        """
schema: decompose-formula/v1
id: test-valid
description: A valid formula
default_level: L2
steps:
  - title: step1
    goal_template: "Goal for {epic_id}"
""",
        encoding="utf-8",
    )
    formula = load_formula(f_path)
    assert isinstance(formula, DecomposeFormula)
    assert formula.id == "test-valid"


def test_broken_yaml_exit2(tmp_path: Path):
    """formula-render with invalid YAML returns exit code 2."""
    f_path = tmp_path / "invalid.yaml"
    f_path.write_text("id: [broken yaml: : :", encoding="utf-8")

    cmd = [
        sys.executable,
        ".claude/hooks/epic_resolve.py",
        "formula-render",
        "--formula",
        str(f_path),
        "--epic-id",
        "T-TEST-001",
        "--slug",
        "test",
        "--dry-run",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 2
    assert "formula error:" in res.stderr


def test_missing_field_exit2(tmp_path: Path):
    """formula-render with missing required schema fields returns exit code 2."""
    f_path = tmp_path / "missing_fields.yaml"
    # Missing required 'id' and 'description'
    f_path.write_text(
        """
schema: decompose-formula/v1
steps: []
""",
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        ".claude/hooks/epic_resolve.py",
        "formula-render",
        "--formula",
        str(f_path),
        "--epic-id",
        "T-TEST-001",
        "--slug",
        "test",
        "--dry-run",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 2
    assert "formula error:" in res.stderr


def test_list_broken_formula_exit2(tmp_path: Path):
    """formula-list with broken formula in dir returns exit code 2."""
    f_path = tmp_path / "broken.yaml"
    f_path.write_text("id: [broken yaml: : :", encoding="utf-8")

    cmd = [
        sys.executable,
        ".claude/hooks/epic_resolve.py",
        "formula-list",
        "--formulas-dir",
        str(tmp_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 2
    assert "formula error:" in res.stderr
