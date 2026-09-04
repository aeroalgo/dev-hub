#!/usr/bin/env python3
"""PreToolUse Bash — deny runner-owned epic/program_resolve CLI inside EPIC_LOOP."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (  # noqa: E402
    bash_active_context_write_deny_reason,
    emit,
    is_epic_loop_env,
    product_cwd,
    read_stdin,
    runner_cli_deny_reason,
)


def main() -> None:
    data = read_stdin()
    if data.get("tool_name") != "Bash":
        return

    tool_input = data.get("tool_input") or {}
    cmd = tool_input.get("command") or ""
    cwd = product_cwd(data.get("cwd"))
    reason = bash_active_context_write_deny_reason(cwd, cmd)
    if not reason and is_epic_loop_env():
        reason = runner_cli_deny_reason(cmd)
    if not reason:
        return

    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
                "additionalContext": (
                    "bash-pretool DENY: runner CLI. "
                    f"{reason}"
                ),
            }
        }
    )


if __name__ == "__main__":
    main()
