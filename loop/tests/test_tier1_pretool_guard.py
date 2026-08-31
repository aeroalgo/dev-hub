"""Integration tests for .claude/hooks/tier1-pretool-guard.py."""

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent.parent / ".claude" / "hooks" / "tier1-pretool-guard.py"


def test_pretool_guard_skips_when_no_incident_session_env(tmp_path: Path) -> None:
    payload = {
        "tool": "Write",
        "tool_input": {"file_path": str(tmp_path / "forbidden.txt")},
    }
    env = dict(os.environ)
    env.pop("EPIC_INCIDENT_SESSION", None)

    res = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
    )
    assert res.returncode == 0


def test_pretool_guard_oob_blocked(tmp_path: Path) -> None:
    scope_file = tmp_path / "tier1_scope.json"
    scope_file.write_text(json.dumps({"allowlist": [str(tmp_path / "allowed.txt")]}), encoding="utf-8")

    payload = {
        "tool": "Write",
        "tool_input": {"file_path": str(tmp_path / "forbidden.txt")},
    }
    env = dict(os.environ)
    env["EPIC_INCIDENT_SESSION"] = "1"
    env["TIER1_SCOPE_FILE"] = str(scope_file)

    res = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
    )
    assert res.returncode == 2
    assert "BLOCKED" in res.stderr


def test_pretool_guard_in_scope_allowed(tmp_path: Path) -> None:
    allowed_dir = tmp_path / "allowed_dir"
    allowed_dir.mkdir()
    allowed_file = allowed_dir / "child.txt"

    scope_file = tmp_path / "tier1_scope.json"
    scope_file.write_text(json.dumps({"allowlist": [str(allowed_dir)]}), encoding="utf-8")

    payload = {
        "tool": "Write",
        "tool_input": {"file_path": str(allowed_file)},
    }
    env = dict(os.environ)
    env["EPIC_INCIDENT_SESSION"] = "1"
    env["TIER1_SCOPE_FILE"] = str(scope_file)

    res = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
    )
    assert res.returncode == 0
