from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from loop.kernel.lifecycle import SubagentLifecycle, load_payload, paths_from_payload
from loop_guard import continue_event, hooks_enabled


def main() -> None:
    if not hooks_enabled():
        return
    payload = load_payload()
    try:
        context = SubagentLifecycle(paths_from_payload(payload)).start_context(payload)
    except Exception as exc:
        print(json.dumps({"continue": False, "reason": f"subagent_start_failed:{exc}"}, ensure_ascii=False))
        raise SystemExit(2)
    if not context:
        continue_event()
        return
    print(
        json.dumps(
            {
                "continue": True,
                "hookSpecificOutput": {
                    "hookEventName": "SubagentStart",
                    "additionalContext": context,
                },
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
