from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_workflow_pack_flag_in_help():
    cmd = [sys.executable, str(ROOT / "loop" / "context_loop.py"), "prepare", "--help"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "--workflow-pack" in res.stdout
    assert "Override WORKFLOW_PACK env var for this session" in res.stdout


def test_workflow_pack_flag_sets_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from loop.context_loop import main
    from loop.workflow.registry import resolve_workflow_pack

    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.delenv("WORKFLOW_PACK", raising=False)
    monkeypatch.delenv("EPIC_WORKFLOW_PACK", raising=False)

    ac = tmp_path / "memory-bank" / "activeContext.md"
    ac.parent.mkdir(parents=True, exist_ok=True)
    ac.write_text("## load_now\n", encoding="utf-8")

    # Run main prepare with --workflow-pack video-production
    try:
        main(["--cwd", str(tmp_path), "prepare", "--workflow-pack", "video-production"])
    except SystemExit:
        pass

    assert os.environ.get("WORKFLOW_PACK") == "video-production"

    resolved = resolve_workflow_pack(cwd=tmp_path, hub_root=ROOT)
    assert resolved.ok is True
    assert resolved.pack_id == "video-production"
