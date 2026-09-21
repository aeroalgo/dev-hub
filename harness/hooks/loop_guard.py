from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping


def is_loop_process(env: Mapping[str, str] | None = None) -> bool:
    values = env or os.environ
    return values.get("LOOP_ACTIVE") == "1" and values.get("EPIC_LOOP") == "1"


def hooks_enabled(env: Mapping[str, str] | None = None) -> bool:
    values = env or os.environ
    return is_loop_process(values) and values.get("LOOP_WORKFLOW_HOOKS", "loop").lower() == "loop"


def payload_path(payload: Mapping[str, Any]) -> str:
    tool_input = payload.get("tool_input")
    nested = tool_input if isinstance(tool_input, Mapping) else payload
    return str(
        nested.get("file_path")
        or nested.get("path")
        or payload.get("file_path")
        or payload.get("path")
        or ""
    )


def active_context_write_denied(payload: Mapping[str, Any]) -> bool:
    path = payload_path(payload)
    return bool(path and Path(path).name.lower() == "activecontext.md")


def allow() -> None:
    print('{"permission":"allow"}')


def continue_event() -> None:
    print('{"continue":true}')


__all__ = [
    "active_context_write_denied",
    "allow",
    "continue_event",
    "hooks_enabled",
    "is_loop_process",
    "payload_path",
]
