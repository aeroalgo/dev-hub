import json
import subprocess
import pytest
from pathlib import Path


def test_cli_help():
    res = subprocess.run(
        ["python3", "harness/hooks/epic_resolve.py", "mb-load", "--help"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "session" in res.stdout


def test_cli_happy(tmp_path: Path):
    act_content = """---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-045-harness-workflow-session-load-api
step_id: s01
---

## load_now
1. [s01.yaml](memory-bank/back/plan/s01.yaml) — shard.

## Handoff BACK IMPLEMENT — s01
- **Эпик:** T-HUB-045
"""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "activeContext.md").write_text(act_content, encoding="utf-8")
    (mb_dir / "s01.yaml").write_text("step: s01", encoding="utf-8")

    res = subprocess.run(
        ["python3", "harness/hooks/epic_resolve.py", "mb-load", "session", "--cwd", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["ok"] is True
    assert len(data["files"]) == 1
    assert data["files"][0]["path"] == "memory-bank/back/plan/s01.yaml"


def test_cli_wrong_cwd(tmp_path: Path):
    # dev-hub root where activeContext.md does not exist or wrong project
    res = subprocess.run(
        ["python3", "harness/hooks/epic_resolve.py", "mb-load", "session", "--cwd", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 2
    data = json.loads(res.stdout)
    assert data["ok"] is False
    assert "missing_active_context" in data["diagnostic_codes"]


def test_cli_missing_file(tmp_path: Path):
    act_content = """---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-045
---

## load_now
1. [missing.yaml](memory-bank/back/plan/missing.yaml) — shard.

## Handoff BACK IMPLEMENT — s01
- **Эпик:** T-HUB-045
"""
    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "activeContext.md").write_text(act_content, encoding="utf-8")

    res = subprocess.run(
        ["python3", "harness/hooks/epic_resolve.py", "mb-load", "session", "--cwd", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    # If no files could be loaded, missing file policy returns ok:false exit 2
    assert res.returncode == 2
    data = json.loads(res.stdout)
    assert data["ok"] is False
    assert any("missing_file:" in d for d in data["diagnostic_codes"])
