#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "harness" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from loop_guard import hooks_enabled  # noqa: E402


def _deny(message: str) -> None:
    print(
        json.dumps(
            {
                "permission": "deny",
                "user_message": message,
                "agent_message": "Cursor hook не смог безопасно проверить операцию; запись запрещена.",
            }
        )
    )
    raise SystemExit(2)


def main() -> None:
    if not hooks_enabled():
        print(json.dumps({"permission": "allow"}))
        return
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError, ValueError):
        _deny("Некорректный JSON в запросе Cursor hook.")
    if not isinstance(payload, dict):
        _deny("Некорректный формат запроса Cursor hook.")
    tool = str(payload.get("tool_name") or payload.get("tool") or "")
    if tool and tool not in {"Write", "Edit", "TabWrite", "NotebookEdit"}:
        print(json.dumps({"permission": "allow"}))
        return
    inp = payload.get("tool_input") or payload
    file_path = (
        inp.get("file_path")
        or inp.get("path")
        or payload.get("file_path")
        or payload.get("path")
        or ""
    )
    if file_path and Path(str(file_path)).name.lower() != "activecontext.md":
        print(json.dumps({"permission": "allow"}))
        return
    reason = "Live loop owns memory-bank/activeContext.md."
    print(
        json.dumps(
            {
                "permission": "deny",
                "user_message": reason,
                "agent_message": (
                    "Live loop owns memory-bank/activeContext.md. "
                    "Write plan.md and queue.yaml only; do not overwrite the cursor."
                ),
            }
        )
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
