from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from loop.kernel.boundary import BoundaryService, is_write_payload
from loop.kernel.store import CursorStore, LoopPaths
from loop_guard import continue_event, hooks_enabled


def main() -> None:
    if not hooks_enabled():
        return
    try:
        payload = json.load(sys.stdin)
        if isinstance(payload, dict) and is_write_payload(payload):
            paths = LoopPaths.for_project(payload.get("cwd") or payload.get("project"))
            cursor = CursorStore(paths).read()
            if cursor is not None:
                result = BoundaryService(paths).change(payload, cursor, stage="post")
                if not result["ok"]:
                    print(json.dumps({"continue": False, "reason": result["reason"], "paths": result["rejected"]}, ensure_ascii=False))
                    raise SystemExit(2)
    except Exception as exc:
        print(json.dumps({"continue": False, "reason": f"boundary_error:{exc}"}, ensure_ascii=False))
        raise SystemExit(2)
    continue_event()


if __name__ == "__main__":
    main()
