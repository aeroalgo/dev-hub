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
    if payload.get("stop_hook_active"):
        return
    try:
        action = SubagentLifecycle(paths_from_payload(payload)).stop(payload)
    except Exception as exc:
        print(json.dumps({"continue": False, "reason": f"subagent_stop_failed:{exc}"}, ensure_ascii=False))
        raise SystemExit(2)
    print(json.dumps(action.as_hook_payload(), ensure_ascii=False))
    if action.exit_code:
        raise SystemExit(action.exit_code)


if __name__ == "__main__":
    main()
