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


_ALWAYS_INJECT = {
    "verify",
    "verify-implement",
    "verify-bugfix",
    "verify-qa",
    "verify-decompose",
    "analyze-verify",
    "reviewer",
    "gate-repair",
}
_AGENT_TYPE_FIELDS = ("agent_type", "subagent_type", "type")
PRESET_BY_AGENT = {
    "verify": "preset.verify",
    "verify-implement": "preset.verify",
    "verify-bugfix": "preset.verify",
    "verify-qa": "preset.reviewer",
    "verify-decompose": "preset.verify",
    "analyze-verify": "preset.verify",
    "reviewer": "preset.reviewer",
    "explorer": "preset.explorer",
    "gate-repair": "preset.repair",
}


def _resolve_agent_type(data: dict[str, object]) -> str | None:
    for field in _AGENT_TYPE_FIELDS:
        raw = data.get(field)
        if isinstance(raw, str) and raw.strip():
            return normalize_type(raw.strip().lower())
    return None


def main() -> None:
    data = read_stdin()
    agent_type = _resolve_agent_type(data)
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
                "additionalContext": (
                    f"agent_type={agent_type} preset={PRESET_BY_AGENT.get(agent_type, '')}\n"
                    f"{contract}\n{HARD_RULE}"
                ),
            }
        }
    )


if __name__ == "__main__":
    main()
