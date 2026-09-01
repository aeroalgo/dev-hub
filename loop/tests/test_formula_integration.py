"""Integration tests for formula render, validation, and validate-decompose-tree (s06)."""

import json
import subprocess
import sys
from pathlib import Path
import pytest

from loop.formula_render import render_formula, list_formulas


def test_render_all_formulas_dry_run():
    """SC-001: Every formula ID from list_formulas() renders cleanly in dry-run mode via CLI."""
    formulas = list_formulas()
    assert len(formulas) >= 3, "Expected at least 3 bundled formulas"

    for formula in formulas:
        cmd = [
            sys.executable,
            ".claude/hooks/epic_resolve.py",
            "formula-render",
            "--formula",
            formula.id,
            "--epic-id",
            "T-TEST-001",
            "--slug",
            "integration-test",
            "--dry-run",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"Formula render dry-run failed for {formula.id}: {res.stderr}"
        assert "schema: epic-decompose-index/v1" in res.stdout
        assert "plan_id: T-TEST-001-integration-test" in res.stdout


def test_render_then_tree_valid(tmp_path: Path):
    """End-to-end integration: render formula to out-dir -> validate-decompose-tree returns ok: true."""
    target_dir = tmp_path / "decompose-T-TEST-002-render-tree"
    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. Render hooks-epic formula
    written_files = render_formula("hooks-epic", "T-TEST-002", "render-tree", out_dir=target_dir)
    assert len(written_files) >= 5
    assert (target_dir / "index.yaml").exists()

    # 2. Add minimal index.md with required coverage sections for tree validation
    index_md = """# Decompose Index

## Requirements Coverage
| Requirement | Step |

## Stages Coverage
| Stage | Step |

## Outcome Map
| Step | Outcome |

## Replacement Cleanup
n/a
"""
    (target_dir / "index.md").write_text(index_md, encoding="utf-8")

    # 3. Run validate-decompose-tree on the rendered index.yaml
    cmd = [
        sys.executable,
        ".claude/hooks/epic_resolve.py",
        "validate-decompose-tree",
        "--decompose",
        str(target_dir / "index.yaml"),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"validate-decompose-tree failed: {res.stderr}"
    data = json.loads(res.stdout)
    assert data.get("ok") is True
    assert len(data.get("errors", [])) == 0


def test_render_no_overwrite_guard_cli(tmp_path: Path):
    """CLI formula-render respects overwrite guard unless --force flag is set."""
    target_dir = tmp_path / "decompose-T-TEST-003-guard"
    target_dir.mkdir(parents=True, exist_ok=True)

    base_cmd = [
        sys.executable,
        ".claude/hooks/epic_resolve.py",
        "formula-render",
        "--formula",
        "hooks-epic",
        "--epic-id",
        "T-TEST-003",
        "--slug",
        "guard",
        "--out",
        str(target_dir),
    ]

    # Initial render: succeeds
    res1 = subprocess.run(base_cmd, capture_output=True, text=True)
    assert res1.returncode == 0

    # Re-render without force flag: fails (exit code 2 with error message)
    res2 = subprocess.run(base_cmd, capture_output=True, text=True)
    assert res2.returncode != 0
    assert "already exists" in res2.stderr or "already exists" in res2.stdout

    # Re-render with --force: succeeds
    res3 = subprocess.run(base_cmd + ["--force"], capture_output=True, text=True)
    assert res3.returncode == 0
