import copy
import json
import subprocess
import sys
from pathlib import Path
import pytest

from loop.runtime_materializers.hooks_json import CODEX_MIN_VERSION
from loop.runtime_materializers.parity import (
    REQUIRED_CODEX_EVENTS,
    REQUIRED_CODEX_AGENTS,
    check_codex_parity,
)


def test_required_codex_events_defined():
    assert len(REQUIRED_CODEX_EVENTS) >= 7
    expected_events = {"Stop", "SubagentStop", "PreToolUse", "PostToolUse", "UserPromptSubmit", "SessionStart", "SubagentStart"}
    assert expected_events <= REQUIRED_CODEX_EVENTS


def test_required_codex_agents_covers_claude():
    assert len(REQUIRED_CODEX_AGENTS) >= 7
    expected_agents = {"verify-implement", "gate-repair", "verify-bugfix", "verify-decompose", "verify-qa", "analyze-verify", "sunset-inventory"}
    assert expected_agents <= REQUIRED_CODEX_AGENTS


def test_codex_min_version_doctor():
    assert CODEX_MIN_VERSION == "0.152.0"
    parts = [int(p) for p in CODEX_MIN_VERSION.split(".")]
    assert len(parts) == 3
    assert parts[0] >= 0
    assert parts[1] >= 152


def test_check_codex_parity_missing_event(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    hooks_file = tmp_path / "hooks.json"
    actual_hooks = json.loads((repo_root / ".codex" / "hooks.json").read_text(encoding="utf-8"))

    modified_hooks = copy.deepcopy(actual_hooks)
    modified_hooks["hooks"].pop("Stop", None)
    hooks_file.write_text(json.dumps(modified_hooks), encoding="utf-8")

    issues = check_codex_parity(hooks_file)
    assert any("missing_required_event: Stop" in issue for issue in issues)


def test_check_codex_parity_full_set():
    repo_root = Path(__file__).resolve().parents[2]
    hooks_file = repo_root / ".codex" / "hooks.json"
    manifest_file = repo_root / "harness" / "manifest.yaml"

    issues = check_codex_parity(hooks_file, manifest_file)
    assert issues == []


def test_runtime_sync_cli_check_missing_event_fails(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    hooks_file = tmp_path / "hooks.json"
    actual_hooks = json.loads((repo_root / ".codex" / "hooks.json").read_text(encoding="utf-8"))

    modified_hooks = copy.deepcopy(actual_hooks)
    modified_hooks["hooks"].pop("Stop", None)
    hooks_file.write_text(json.dumps(modified_hooks), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "loop.cli.runtime_sync", "--check", "--hooks-json", str(hooks_file)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "missing_required_event: Stop" in proc.stdout or "missing_required_event: Stop" in proc.stderr


def test_runtime_sync_cli_check_full_set_succeeds():
    proc = subprocess.run(
        [sys.executable, "-m", "loop.cli.runtime_sync", "--check", "--runtime", "codex"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "No drift detected" in proc.stdout
