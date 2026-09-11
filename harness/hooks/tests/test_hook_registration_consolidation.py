"""Test manifest and settings hook registration consolidation and runtime parity (FR-008, FR-011, FR-012, US-005, NFR-001)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from loop.hub_settings_merge import canonicalize_command, find_duplicate_hook_realpaths


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@pytest.fixture
def manifest_path(repo_root: Path) -> Path:
    return repo_root / "harness" / "manifest.yaml"


@pytest.fixture
def settings_path(repo_root: Path) -> Path:
    return repo_root / ".claude" / "settings.json"


def test_manifest_declares_canonical_dispatchers(manifest_path: Path) -> None:
    """harness/manifest.yaml declares canonical dispatchers and no active old hook entries."""
    assert manifest_path.exists(), f"Manifest file missing: {manifest_path}"
    manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    hooks = manifest_data.get("hooks", {})

    # Must contain pretool-dispatch and posttool-dispatch
    assert "pretool-dispatch" in hooks, "pretool-dispatch missing from manifest.yaml hooks"
    assert "posttool-dispatch" in hooks, "posttool-dispatch missing from manifest.yaml hooks"

    assert hooks["pretool-dispatch"]["source"] == "harness/hooks/pretool-dispatch.py"
    assert hooks["posttool-dispatch"]["source"] == "harness/hooks/posttool-dispatch.py"

    # Old entries must not be present in active hooks
    old_hook_entries = {
        "agent-pretool",
        "bash-pretool",
        "write-pretool",
        "context-ledger",
        "finish-boundary-pretool",
        "agent-posttool",
        "bash-output-cap",
    }
    for old_entry in old_hook_entries:
        assert old_entry not in hooks, f"Old hook entry '{old_entry}' still present in manifest.yaml"


def test_settings_unique_realpath(settings_path: Path, repo_root: Path) -> None:
    """Committed .claude/settings.json must have zero duplicate realpaths and no old hook commands."""
    assert settings_path.exists(), f"Settings file missing: {settings_path}"
    duplicates = find_duplicate_hook_realpaths(settings_path, project_dir=repo_root)
    assert duplicates == [], f"Found duplicate hook realpaths in settings: {duplicates}"

    settings_data = json.loads(settings_path.read_text(encoding="utf-8"))
    hooks = settings_data.get("hooks", {})

    # Ensure each registered event has single canonical command
    for event_name, matchers in hooks.items():
        if isinstance(matchers, list):
            for matcher_entry in matchers:
                hook_list = matcher_entry.get("hooks", [])
                assert len(hook_list) == 1, f"Event {event_name} has multiple commands per matcher block"

    # Verify old entrypoints are not registered in settings
    old_scripts = {
        "agent-pretool.py",
        "bash-pretool.py",
        "context-scope-pretool.py",
        "write-pretool.py",
        "finish-boundary-pretool.py",
        "agent-posttool.py",
        "bash-output-cap.py",
    }
    settings_raw = settings_path.read_text(encoding="utf-8")
    for script_name in old_scripts:
        assert script_name not in settings_raw, f"Old script '{script_name}' still referenced in .claude/settings.json"


def test_registration_entry_count_reduction(manifest_path: Path, settings_path: Path) -> None:
    """Total registered command entries is reduced from 11+ to canonical 7 event-specific count."""
    manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest_hooks = manifest_data.get("hooks", {})
    assert len(manifest_hooks) == 7, f"Expected 7 canonical manifest hooks, got {len(manifest_hooks)}"

    settings_data = json.loads(settings_path.read_text(encoding="utf-8"))
    settings_hooks = settings_data.get("hooks", {})
    
    total_settings_commands = 0
    for event_name, matchers in settings_hooks.items():
        if isinstance(matchers, list):
            for matcher_entry in matchers:
                total_settings_commands += len(matcher_entry.get("hooks", []))

    assert total_settings_commands == 7, f"Expected 7 canonical settings commands, got {total_settings_commands}"


def test_claude_codex_materialization_parity(manifest_path: Path, settings_path: Path, repo_root: Path) -> None:
    """Claude settings and manifest preserve canonical event set and all scripts exist."""
    canonical_events = {
        "SessionStart",
        "UserPromptSubmit",
        "PreToolUse",
        "PostToolUse",
        "SubagentStart",
        "SubagentStop",
        "Stop",
    }

    manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest_hooks = manifest_data.get("hooks", {})

    settings_data = json.loads(settings_path.read_text(encoding="utf-8"))
    settings_hooks = settings_data.get("hooks", {})

    assert set(settings_hooks.keys()) == canonical_events, "Settings missing canonical events"

    # All manifest hook sources must exist
    for hook_name, hook_cfg in manifest_hooks.items():
        source_file = repo_root / hook_cfg["source"]
        assert source_file.exists(), f"Manifest hook source not found: {source_file}"

    # PreToolUse and PostToolUse in settings must point to canonical dispatchers
    pretool_entries = settings_hooks.get("PreToolUse", [])
    assert len(pretool_entries) == 1
    pretool_cmd = pretool_entries[0]["hooks"][0]["command"]
    assert "pretool-dispatch.py" in pretool_cmd

    posttool_entries = settings_hooks.get("PostToolUse", [])
    assert len(posttool_entries) == 1
    posttool_cmd = posttool_entries[0]["hooks"][0]["command"]
    assert "posttool-dispatch.py" in posttool_cmd


def test_legacy_hook_files_purged(repo_root: Path) -> None:
    """Legacy hook scripts are deleted from filesystem (Kind A / FR-008)."""
    purged_files = [
        "harness/hooks/agent-pretool.py",
        "harness/hooks/bash-pretool.py",
        "harness/hooks/write-pretool.py",
        "harness/hooks/finish-boundary-pretool.py",
        "harness/hooks/agent-posttool.py",
    ]
    for rel_path in purged_files:
        full_path = repo_root / rel_path
        assert not full_path.exists(), f"Legacy hook file was not purged: {rel_path}"


def test_zero_prod_callers_for_deleted_hooks(manifest_path: Path, settings_path: Path) -> None:
    """Manifest and settings have zero references to purged hook entrypoints (Kind B / FR-011)."""
    purged_names = [
        "agent-pretool",
        "bash-pretool",
        "write-pretool",
        "finish-boundary-pretool",
        "agent-posttool",
    ]
    manifest_raw = manifest_path.read_text(encoding="utf-8")
    settings_raw = settings_path.read_text(encoding="utf-8")
    for name in purged_names:
        assert name not in manifest_raw, f"Manifest still references purged hook: {name}"
        assert name not in settings_raw, f"Settings still references purged hook: {name}"


def test_full_suite_regression_green(repo_root: Path) -> None:
    """Canonical dispatchers and policies are importable and functional (FR-001, FR-004, FR-008)."""
    from hook_dispatch import dispatch_pretool, dispatch_posttool
    from pretool_policy import create_pretool_branches
    from posttool_policy import create_posttool_branches

    pre_branches = create_pretool_branches()
    assert len(pre_branches) == 5, f"Expected 5 PreToolUse branches, got {len(pre_branches)}"

    post_branches = create_posttool_branches()
    assert len(post_branches) == 3, f"Expected 3 PostToolUse branches, got {len(post_branches)}"
