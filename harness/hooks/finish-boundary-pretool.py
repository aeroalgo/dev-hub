#!/usr/bin/env python3
"""PreToolUse barrier after a successful mb-finish in the current phase run.

Claude Code parity: deny every follow-up tool in the same phase_run after
``mb-finish`` / automatic gate finish succeeds, so the parent must stop the
turn. Codex PreToolUse uses the same ``permissionDecision: deny`` envelope.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (  # noqa: E402
    bash_project_boundary_deny_reason,
    emit,
    is_epic_loop_env,
    project_boundary_deny_reason,
    product_cwd,
    read_stdin,
)


def _load_epic_state(cwd: Path) -> dict:
    try:
        from epic.core import load_epic_state

        state = load_epic_state(cwd)
        return state if isinstance(state, dict) else {}
    except (ImportError, OSError, TypeError, ValueError):
        pass
    try:
        from epic_lib import load_epic_state

        state = load_epic_state(cwd)
        return state if isinstance(state, dict) else {}
    except (ImportError, OSError, TypeError, ValueError):
        return {}


def finish_boundary_reason(cwd: str | Path) -> str | None:
    state = _load_epic_state(product_cwd(cwd))
    finish = state.get("last_finish_tool")
    if not isinstance(finish, dict):
        return None
    name = str(finish.get("name") or "")
    current_run = str(state.get("phase_run_id") or "").strip()
    finish_run = str(finish.get("phase_run_id") or "").strip()
    if not name.startswith("mb-finish ") or not current_run or current_run != finish_run:
        return None
    return (
        f"finish_boundary: {name} успешно завершён в текущем phase_run_id; "
        "немедленно останови текущий turn. Следующий runner-эпизод продолжит работу."
    )


def project_boundary_reason(data: dict, cwd: Path) -> str | None:
    tool_name = str(data.get("tool_name") or data.get("tool") or "")
    tool_input = data.get("tool_input") or {}
    if tool_name in {"Bash", "bash", "shell", "shell_command", "local_shell", "exec_command"}:
        return bash_project_boundary_deny_reason(cwd, tool_input.get("command") or "")
    if tool_name not in {"Read", "Edit", "Write", "NotebookEdit", "Glob", "Grep", "apply_patch"}:
        return None
    raw_path = (
        tool_input.get("file_path")
        or tool_input.get("notebook_path")
        or tool_input.get("path")
    )
    return project_boundary_deny_reason(cwd, raw_path, operation=tool_name.lower())


def _emit_deny(reason: str) -> None:
    """Claude/Codex PreToolUse deny — same envelope (Codex enforces permissionDecision)."""
    print(f"finish-boundary DENY: {reason}", file=sys.stderr)
    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
                "additionalContext": (
                    "finish-boundary DENY: mb-finish уже успешен. "
                    "Не вызывай другие tools; заверши текущий turn."
                ),
            }
        }
    )


def main() -> None:
    data = read_stdin()
    cwd = product_cwd(data.get("cwd") or "")
    if not is_epic_loop_env():
        boundary = project_boundary_reason(data, cwd)
        if boundary:
            emit(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": boundary,
                        "additionalContext": "project-boundary DENY: доступ вне project root запрещён.",
                    }
                }
            )
        return
    boundary = project_boundary_reason(data, cwd)
    if boundary:
        _emit_deny(boundary)
        return
    reason = finish_boundary_reason(cwd)
    if not reason:
        return
    _emit_deny(reason)


if __name__ == "__main__":
    main()
