from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from loop_guard import active_context_write_denied, allow, hooks_enabled
from loop.kernel.boundary import BoundaryService, is_read_payload, is_write_payload, provider_from_payload, render_read
from loop.kernel.store import CursorStore, LoopPaths


def _paths(payload: dict[str, object]) -> LoopPaths:
    return LoopPaths.for_project(payload.get("cwd") or payload.get("project"))


def _cursor(paths: LoopPaths):
    return CursorStore(paths).read()


def main() -> None:
    if not hooks_enabled():
        return
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError, ValueError):
        print('{"permission":"deny","reason":"invalid_hook_payload"}')
        return
    if not isinstance(payload, dict):
        print('{"permission":"deny","reason":"invalid_hook_payload"}')
        return
    if active_context_write_denied(payload):
        print('{"permission":"deny","reason":"activeContext_owned_by_loop"}')
        return
    try:
        paths = _paths(payload)
        cursor = _cursor(paths)
        if cursor is not None and is_read_payload(payload):
            decision = BoundaryService(paths).read(payload, cursor)
            if not decision.allowed:
                print(json.dumps(render_read(decision, provider_from_payload(payload)), ensure_ascii=False))
                return
        elif cursor is not None and is_write_payload(payload):
            result = BoundaryService(paths).change(payload, cursor, stage="pre")
            if not result["ok"]:
                print(json.dumps({"permission": "deny", "reason": result["reason"], "paths": result["rejected"]}, ensure_ascii=False))
                return
    except Exception as exc:
        print(json.dumps({"permission": "deny", "reason": "boundary_error", "message": str(exc)}, ensure_ascii=False))
        return
    allow()


if __name__ == "__main__":
    main()
