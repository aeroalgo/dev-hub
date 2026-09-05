#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "harness" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from _lib import active_context_write_deny_reason  # noqa: E402


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print(json.dumps({"permission": "allow"}))
        return
    if not isinstance(payload, dict):
        print(json.dumps({"permission": "allow"}))
        return
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
    contents = inp.get("contents") or inp.get("new_string") or payload.get("contents") or ""
    roots = payload.get("workspace_roots") or []
    cwd = Path(roots[0]).resolve() if roots else ROOT
    try:
        reason = active_context_write_deny_reason(
            cwd, file_path, contents, same_session=False
        )
    except Exception:
        print(json.dumps({"permission": "allow"}))
        return
    if not reason:
        print(json.dumps({"permission": "allow"}))
        return
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
