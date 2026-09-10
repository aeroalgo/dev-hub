from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "harness" / "hooks"
sys.path.insert(0, str(HOOKS))
sys.path.insert(0, str(ROOT))

from touch_ledger import (  # noqa: E402
    ensure_touch_ledger_identity,
    load_touch_ledger,
    record_touch,
    reset_touch_ledger,
    touched_paths,
    touch_ledger_path,
)
from _lib import bash_discard_dirty_deny_reason  # noqa: E402


def test_record_touch_and_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    monkeypatch.setenv("DEV_HUB", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    (project / "a.py").write_text("x\n", encoding="utf-8")

    reset_touch_ledger(project, epic_id="T-HUB-091-x", step_id="s02")
    record_touch(project, "a.py", operation="edit", epic_id="T-HUB-091-x", step_id="s02")
    record_touch(project, "a.py", operation="edit", epic_id="T-HUB-091-x", step_id="s02")
    record_touch(project, "b.py", operation="write", epic_id="T-HUB-091-x", step_id="s02")

    assert touched_paths(project) == ["a.py", "b.py"]
    data = load_touch_ledger(project)
    assert data["epic_id"] == "T-HUB-091-x"
    assert data["step_id"] == "s02"
    assert touch_ledger_path(project).is_file()


def test_identity_change_resets_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    monkeypatch.setenv("DEV_HUB", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    record_touch(project, "old.py", epic_id="T-HUB-080", step_id="s01")
    assert touched_paths(project) == ["old.py"]

    ensure_touch_ledger_identity(project, epic_id="T-HUB-091", step_id="s02")
    assert touched_paths(project) == []
    data = load_touch_ledger(project)
    assert data["epic_id"] == "T-HUB-091"
    assert data["step_id"] == "s02"


def test_bash_discard_dirty_deny_reason() -> None:
    assert bash_discard_dirty_deny_reason("git status") is None
    assert bash_discard_dirty_deny_reason("git restore --staged foo.py") is None
    assert bash_discard_dirty_deny_reason("git log -1") is None

    denied = [
        "git checkout -- harness/hooks/epic/core.py",
        "git checkout HEAD -- loop/gate_identity.py",
        "/bin/bash -lc 'git checkout -- a.py b.py'",
        "git restore loop/x.py",
        "git reset --hard",
        "git clean -fd",
        "echo hi && git restore --worktree foo.py",
    ]
    for cmd in denied:
        reason = bash_discard_dirty_deny_reason(cmd)
        assert reason and "git_discard_dirty_forbidden" in reason, cmd


def test_verify_implement_contract_mentions_touch_ledger() -> None:
    text = (ROOT / "harness" / "agents" / "verify-implement.md").read_text(encoding="utf-8")
    assert "touch-ledger" in text
    assert "git checkout --" in text
    assert "IGNORE" in text or "игнорир" in text.lower()


def test_agent_posttool_records_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    monkeypatch.setenv("DEV_HUB", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    target = project / "loop" / "x.py"
    target.parent.mkdir(parents=True)
    target.write_text("print(1)\n", encoding="utf-8")

    # Seed epic state identity for record_touch fallback
    from epic_paths import epic_dir

    epic = epic_dir(project)
    (epic / "state.json").write_text(
        json.dumps(
            {
                "armed_epic": "T-HUB-091-test",
                "armed_step": "s02",
                "phase_run_id": "abc",
            }
        ),
        encoding="utf-8",
    )

    import subprocess

    post = ROOT / "harness" / "hooks" / "agent-posttool.py"
    payload = {
        "tool_name": "Write",
        "cwd": str(project),
        "session_id": "sess-1",
        "tool_input": {
            "file_path": str(target),
            "content": "print(2)\n",
        },
    }
    proc = subprocess.run(
        [sys.executable, str(post)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(project),
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    paths = touched_paths(project)
    assert any(p.endswith("loop/x.py") for p in paths), paths
