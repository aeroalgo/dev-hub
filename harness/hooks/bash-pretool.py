#!/usr/bin/env python3
"""PreToolUse Bash — deny runner-owned epic/program_resolve CLI and out-of-scope search inside EPIC_LOOP."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (  # noqa: E402
    active_context_write_deny_reason,
    bash_active_context_write_deny_reason,
    bash_discard_dirty_deny_reason,
    bash_gate_state_write_deny_reason,
    emit,
    is_epic_loop_env,
    product_cwd,
    read_stdin,
    runner_cli_deny_reason,
)
from context_scope import ScopeResolver, is_search_command_line


def main() -> None:
    data = read_stdin()
    if data.get("tool_name") != "Bash":
        return

    tool_input = data.get("tool_input") or {}
    cmd = tool_input.get("command") or ""
    cwd = product_cwd(data.get("cwd"))
    reason = bash_gate_state_write_deny_reason(cmd)
    if not reason:
        reason = bash_active_context_write_deny_reason(cwd, cmd)
    if not reason and is_epic_loop_env():
        reason = bash_discard_dirty_deny_reason(cmd)
    if not reason and is_epic_loop_env():
        reason = runner_cli_deny_reason(cmd)

    # Check search scope enforcement inside EPIC_LOOP
    if not reason and is_epic_loop_env() and is_search_command_line(cmd):
        resolver = ScopeResolver(project_root=cwd)
        graphify_evidence = data.get("graphify_evidence") or tool_input.get("graphify_evidence")
        exception_reason = data.get("exception_reason") or tool_input.get("exception_reason")
        allowed, search_reason, details = resolver.evaluate_search(
            command=cmd,
            cwd=cwd,
            graphify_evidence=graphify_evidence,
            exception_reason=exception_reason,
        )
        if not allowed:
            diag = details.get("diagnostic", search_reason)
            reason = f"search_outside_scope_denied: {diag}"

    if not reason:
        return

    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
                "additionalContext": (
                    "bash-pretool DENY: "
                    f"{reason}"
                ),
            }
        }
    )


if __name__ == "__main__":
    main()
