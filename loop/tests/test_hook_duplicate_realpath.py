"""Test for detecting duplicate hook command realpaths in settings (FR-001, FR-002, US-001, US-004, TM-001, TM-002)."""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
import pytest
from loop.hub_settings_merge import canonicalize_command, find_duplicate_hook_realpaths, check_settings_unique_realpaths


def test_hook_duplicate_realpath_fixture_fails(tmp_path: Path) -> None:
    """Dual commands resolving to the same realpath must fail with hook_duplicate_realpath."""
    # Create target script in harness/hooks
    project_dir = tmp_path
    harness_hooks = project_dir / "harness" / "hooks"
    claude_hooks = project_dir / ".claude" / "hooks"
    harness_hooks.mkdir(parents=True)
    claude_hooks.mkdir(parents=True)

    target_script = harness_hooks / "session-start.py"
    target_script.write_text("# session start\n")

    symlink_script = claude_hooks / "session-start.py"
    symlink_script.symlink_to(target_script)

    dual_settings = {
        "hooks": {
            "SessionStart": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/session-start.py\"",
                        }
                    ]
                },
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 \"$CLAUDE_PROJECT_DIR/harness/hooks/session-start.py\"",
                        }
                    ]
                },
            ]
        }
    }

    settings_file = project_dir / ".claude" / "settings.json"
    settings_file.write_text(json.dumps(dual_settings, indent=2))

    with pytest.raises(ValueError) as exc_info:
        check_settings_unique_realpaths(settings_file, project_dir=project_dir)
    assert "hook_duplicate_realpath" in str(exc_info.value)


def test_committed_settings_unique_realpath_all_events() -> None:
    """Committed .claude/settings.json must have unique realpath per (event, matcher)."""
    project_dir = Path(__file__).resolve().parent.parent.parent
    settings_file = project_dir / ".claude" / "settings.json"
    assert settings_file.exists(), f"Settings file not found: {settings_file}"

    duplicates = find_duplicate_hook_realpaths(settings_file, project_dir=project_dir)
    assert duplicates == [], f"Found duplicate hook realpaths in committed settings: {duplicates}"
