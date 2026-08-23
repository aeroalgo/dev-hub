#!/usr/bin/env python3
"""SubagentStart — inject per-agent contract into child context."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (
    product_cwd,  # noqa: E402
    CONTRACTS,
    HARD_RULE,
    emit,
    load_state,
    normalize_type,
    read_stdin,
    workflow_state_active,
)


_ALWAYS_INJECT = {"verify", "reviewer"}


def main() -> None:
    data = read_stdin()
    agent_type = normalize_type(data.get("agent_type")) or data.get("agent_type")
    session_id = data.get("session_id") or ""
    cwd = str(product_cwd(data.get("cwd") or ""))
    contract = CONTRACTS.get(agent_type or "", "")
    if not contract:
        return
    # verify/reviewer always get their contract — regardless of workflow state
    if agent_type not in _ALWAYS_INJECT:
        st = load_state(session_id, cwd)
        if not workflow_state_active(st, cwd or None):
            return
    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "SubagentStart",
                "additionalContext": f"{contract}\n{HARD_RULE}",
            }
        }
    )


if __name__ == "__main__":
    main()
