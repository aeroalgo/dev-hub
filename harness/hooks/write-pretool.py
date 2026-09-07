#!/usr/bin/env python3
"""PreToolUse Write/Edit — deny chat overwrite of live-loop activeContext, enforce provider parity, derived_identity, fail-closed invalidation.
Handles Write/Edit/NotebookEdit and Read/read invalidation boundaries across actors.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (  # noqa: E402
    active_context_write_deny_reason,
    gate_state_write_deny_reason,
    recorded_artifact_write_deny_reason,
    emit,
    product_cwd,
    read_stdin,
)
from context_ledger_adapters import (
    WRITE_TOOL_ALIASES,
    evaluate_write_payload,
)


def main() -> None:
    data = read_stdin()
    tool_name = str(data.get("tool_name") or data.get("tool") or data.get("name") or "")
    if tool_name not in WRITE_TOOL_ALIASES:
        return

    tool_input = data.get("tool_input") or data.get("arguments") or data.get("args") or {}
    file_path = (
        tool_input.get("file_path")
        or tool_input.get("path")
        or tool_input.get("notebook_path")
        or ""
    )
    contents = tool_input.get("contents") or tool_input.get("content") or tool_input.get("new_string") or ""
    cwd = product_cwd(data.get("cwd"))
    reason = gate_state_write_deny_reason(cwd, file_path)
    if not reason:
        reason = active_context_write_deny_reason(cwd, file_path, contents)
    if not reason:
        reason = recorded_artifact_write_deny_reason(cwd, file_path)
    if not reason:
        # Context ledger invalidation for write boundary across actors
        ok, r_code, resp = evaluate_write_payload(data, provider="claude", cwd=cwd)
        if not ok:
            emit(resp)
            return
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
