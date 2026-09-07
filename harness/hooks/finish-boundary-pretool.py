#!/usr/bin/env python3
"""PreToolUse barrier after a successful mb-finish in the current phase run."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (  # noqa: E402
    emit,
    is_epic_loop_env,
    product_cwd,
    read_stdin,
)


def _load_epic_state(cwd: Path) -> dict:
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


def main() -> None:
    data = read_stdin()
    if not is_epic_loop_env():
        return
    cwd = product_cwd(data.get("cwd") or "")
    reason = finish_boundary_reason(cwd)
    if not reason:
        return
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


if __name__ == "__main__":
    main()
