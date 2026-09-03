"""Tests for loop.hub_settings_merge."""

import json
import pytest
from pathlib import Path
from loop.hub_settings_merge import merge_settings, merge_hooks


@pytest.fixture
def harness_settings_file(tmp_path: Path) -> Path:
    harness_path = tmp_path / "settings.harness.json"
    harness_data = {
        "$schema": "https://json.schemastore.org/claude-code-settings.json",
        "hooks": {
            "SessionStart": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 \"$CLAUDE_PROJECT_DIR/harness/hooks/session-start.py\"",
                            "timeout": 15,
                        }
                    ]
                }
            ],
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 \"$CLAUDE_PROJECT_DIR/harness/hooks/bash-pretool.py\"",
                            "timeout": 15,
                        }
                    ]
                }
            ]
        }
    }
    harness_path.write_text(json.dumps(harness_data, indent=2), encoding="utf-8")
    return harness_path


def test_merge_preserves_permissions(tmp_path: Path, harness_settings_file: Path):
    user_file = tmp_path / "settings.json"
    user_data = {
        "permissions": {
            "deny": ["Bash(rm -rf *)", "Bash(git push --force)"],
            "allow": ["Read", "Edit"]
        },
        "hooks": {
            "SessionStart": [
                {
                    "hooks": [
                        {"type": "command", "command": "echo user start"}
                    ]
                }
            ]
        }
    }
    user_file.write_text(json.dumps(user_data, indent=2), encoding="utf-8")

    changed = merge_settings(user_file, harness_settings_file, backup=True)
    assert changed is True

    result = json.loads(user_file.read_text(encoding="utf-8"))
    assert "permissions" in result
    assert result["permissions"]["deny"] == ["Bash(rm -rf *)", "Bash(git push --force)"]
    assert result["permissions"]["allow"] == ["Read", "Edit"]

    # Verify hooks merged
    session_start_hooks = result["hooks"]["SessionStart"]
    assert len(session_start_hooks) == 2
    assert "PreToolUse" in result["hooks"]


def test_merge_adds_hooks_idempotent(tmp_path: Path, harness_settings_file: Path):
    user_file = tmp_path / "settings.json"
    user_data = {
        "hooks": {
            "CustomEvent": [{"hooks": [{"type": "command", "command": "echo hello"}]}]
        }
    }
    user_file.write_text(json.dumps(user_data, indent=2), encoding="utf-8")

    # First merge
    changed1 = merge_settings(user_file, harness_settings_file, backup=True)
    assert changed1 is True

    content_after_first = user_file.read_text(encoding="utf-8")
    result1 = json.loads(content_after_first)
    assert "CustomEvent" in result1["hooks"]
    assert "SessionStart" in result1["hooks"]
    assert len(result1["hooks"]["SessionStart"]) == 1

    # Second merge (idempotent)
    changed2 = merge_settings(user_file, harness_settings_file, backup=True)
    assert changed2 is False
    assert user_file.read_text(encoding="utf-8") == content_after_first


def test_merge_creates_backup(tmp_path: Path, harness_settings_file: Path):
    user_file = tmp_path / "settings.json"
    original_content = json.dumps({"custom": "value", "permissions": {"deny": ["x"]}}, indent=2)
    user_file.write_text(original_content, encoding="utf-8")

    backup_file = tmp_path / "settings.json.hub-backup"
    assert not backup_file.exists()

    merge_settings(user_file, harness_settings_file, backup=True)

    assert backup_file.exists()
    assert backup_file.read_text(encoding="utf-8") == original_content


def test_merge_creates_file_if_missing(tmp_path: Path, harness_settings_file: Path):
    user_file = tmp_path / "subdir" / "settings.json"
    assert not user_file.exists()

    changed = merge_settings(user_file, harness_settings_file, backup=True)
    assert changed is True
    assert user_file.exists()

    result = json.loads(user_file.read_text(encoding="utf-8"))
    assert "hooks" in result
    assert "SessionStart" in result["hooks"]


def test_force_permissions_raises_not_implemented(tmp_path: Path, harness_settings_file: Path):
    user_file = tmp_path / "settings.json"
    user_file.write_text("{}", encoding="utf-8")

    with pytest.raises(NotImplementedError):
        merge_settings(user_file, harness_settings_file, force_permissions=True)


def test_unlink_restores_settings(tmp_path: Path):
    """settings backup restored on unlink."""
    import os
    import subprocess

    hub_dir = Path(__file__).resolve().parents[2]
    product_dir = tmp_path / "unlink_settings_product"
    product_dir.mkdir()

    claude_dir = product_dir / ".claude"
    claude_dir.mkdir()
    settings_file = claude_dir / "settings.json"
    original_settings = {"userKey": "originalValue", "permissions": {"deny": ["write"]}}
    settings_file.write_text(json.dumps(original_settings, indent=2), encoding="utf-8")

    env = dict(os.environ, DEV_HUB=str(hub_dir))
    hub_link_bin = hub_dir / "bin" / "hub-link"
    hub_unlink_bin = hub_dir / "bin" / "hub-unlink"

    # Link alongside (modifies settings.json and creates settings.json.hub-backup)
    res_link = subprocess.run([str(hub_link_bin), "--mode=alongside", str(product_dir)], env=env, capture_output=True, text=True)
    assert res_link.returncode == 0
    assert (claude_dir / "settings.json.hub-backup").exists()

    # Unlink alongside
    res_unlink = subprocess.run([str(hub_unlink_bin), "--mode=alongside", str(product_dir)], env=env, capture_output=True, text=True)
    assert res_unlink.returncode == 0

    assert not (claude_dir / "settings.json.hub-backup").exists()
    assert settings_file.exists()
    restored_data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert restored_data == original_settings

