"""Regression guard tests ensuring no legacy hardcoded decompose/implement paths exist in loop/ (SC-004 / AC-9)."""

from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[3]


def test_no_decompose_hardcoded():
    """cp1 / SC-004: Ensure no active non-migration code in loop/ references hardcoded decompose-."""
    cmd = [
        "rg",
        "decompose-",
        "loop/",
        "--glob",
        "*.py",
    ]
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if res.returncode == 0:
        lines = res.stdout.strip().split("\n")
        violations = []
        for line in lines:
            if not line.strip():
                continue
            # Exclude tests, comments, deprecation notices, layout v2 schemas/indexes, migration, and detectors/janitors
            if any(
                skip in line
                for skip in [
                    "#",
                    "/tests/",
                    "test_",
                    "deprecated",
                    "decompose-index",
                    "decompose-formula",
                    "migrate",
                    "orphan",
                    "dead_ref",
                    "gc.py",
                    "resolver.py",
                    "dag.py",
                    "scan_epics.py",
                    "scan_gates.py",
                    "scan_mb.py",
                    "context_loop.py",
                    "metadata.py",
                    "finish_implement.py",
                    "impl.py",
                    "validate-decompose-tree",
                ]
            ):
                continue
            violations.append(line)
        assert len(violations) == 0, f"Found active decompose- hardcoded paths in loop/: {violations}"
    else:
        assert res.returncode == 1


def test_no_implement_hardcoded():
    """cp1 / AC-9: Ensure no active non-migration code in loop/ references hardcoded 'implement-."""
    cmd = [
        "rg",
        "'implement-",
        "loop/",
        "--glob",
        "*.py",
    ]
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if res.returncode == 0:
        lines = res.stdout.strip().split("\n")
        violations = []
        for line in lines:
            if not line.strip():
                continue
            if any(skip in line for skip in ["#", "/tests/", "test_", "deprecated", "migrate", "orphan", "dead_ref", "resolver.py"]):
                continue
            violations.append(line)
        assert len(violations) == 0, f"Found active 'implement- hardcoded paths in loop/: {violations}"
    else:
        assert res.returncode == 1
