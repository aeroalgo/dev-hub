"""Tests for epic_resolve.py tool-gate check CLI."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_cli_fail(tmp_path: Path) -> None:
    """CLI tool-gate check exit 1 when target output file is missing."""
    # Create project.yaml selecting video pack
    (tmp_path / "project.yaml").write_text("workflow_pack: video-production\n", encoding="utf-8")

    cmd = [
        sys.executable,
        str(ROOT / "harness/hooks/epic_resolve.py"),
        "tool-gate",
        "check",
        "--gate",
        "render",
        "--cwd",
        str(tmp_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert data["ok"] is False
    assert data["gate_id"] == "render"
    assert "render_output_missing" in data["diagnostic_codes"]


def test_cli_tool_gate_fail(tmp_path: Path) -> None:
    test_cli_fail(tmp_path)


def test_cli_pass(tmp_path: Path) -> None:
    """CLI tool-gate check exit 0 when target output fixture is present."""
    (tmp_path / "project.yaml").write_text("workflow_pack: video-production\n", encoding="utf-8")
    out_file = tmp_path / "outputs" / "final.mp4"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(b"dummy mp4 fixture payload")

    cmd = [
        sys.executable,
        str(ROOT / "harness/hooks/epic_resolve.py"),
        "tool-gate",
        "check",
        "--gate",
        "render",
        "--cwd",
        str(tmp_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["ok"] is True
    assert data["gate_id"] == "render"
    assert data["diagnostic_codes"] == []


def test_cli_tool_gate_pass(tmp_path: Path) -> None:
    test_cli_pass(tmp_path)

