#!/usr/bin/env python3
"""PreToolUse Write/Edit — deny chat overwrite of live-loop activeContext."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (  # noqa: E402
    active_context_write_deny_reason,
    recorded_artifact_write_deny_reason,
    emit,
    product_cwd,
    read_stdin,
)


def main() -> None:
    data = read_stdin()
    tool_name = str(data.get("tool_name") or data.get("tool") or "")
    if tool_name not in {"Write", "Edit", "NotebookEdit"}:
        return

    tool_input = data.get("tool_input") or {}
    file_path = (
        tool_input.get("file_path")
        or tool_input.get("path")
        or tool_input.get("notebook_path")
        or ""
    )
    contents = tool_input.get("contents") or tool_input.get("content") or tool_input.get("new_string") or ""
    cwd = product_cwd(data.get("cwd"))
    reason = active_context_write_deny_reason(cwd, file_path, contents)
    if not reason:
        reason = recorded_artifact_write_deny_reason(cwd, file_path)
    if not reason:
        return

    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
                "additionalContext": (
                    "write-pretool DENY: live loop owns activeContext. "
                    f"{reason}"
                ),
            }
        }
    )


if __name__ == "__main__":
    main()
