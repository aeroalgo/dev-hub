#!/usr/bin/env python3
"""Compact terminal view for `codex exec --json` (loop headless)."""
from __future__ import annotations

import json
import sys

_SKIP_ERROR_SUBSTRINGS = (
    "Skill descriptions were shortened",
)


def _write(text: str) -> None:
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
    except BrokenPipeError:
        sys.exit(0)


def _skip_error(message: str) -> bool:
    return any(part in message for part in _SKIP_ERROR_SUBSTRINGS)


def _agent_text(text: str) -> str | None:
    stripped = (text or "").strip()
    if not stripped:
        return None
    if "```" in stripped:
        return None
    return stripped


def emit_from_obj(obj: dict) -> None:
    event_type = obj.get("type")
    if event_type == "item.started":
        item = obj.get("item") if isinstance(obj.get("item"), dict) else {}
        if item.get("type") == "command_execution":
            command = (item.get("command") or "").strip()
            if command:
                _write(f"exec\n{command}\n")
        return

    if event_type != "item.completed":
        return

    item = obj.get("item") if isinstance(obj.get("item"), dict) else {}
    item_type = item.get("type")

    if item_type == "command_execution":
        if item.get("status") != "completed":
            return
        exit_code = item.get("exit_code")
        if exit_code in (None, 0):
            _write(" succeeded\n")
        else:
            _write(f" failed (exit={exit_code})\n")
        return

    if item_type == "agent_message":
        text = _agent_text(str(item.get("text") or ""))
        if text:
            _write(text + "\n")
        return

    if item_type == "error":
        message = str(item.get("message") or "").strip()
        if message and not _skip_error(message):
            _write(f"error: {message}\n")


def main() -> None:
    _write("--- codex stream (commands + text) ---\n")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            emit_from_obj(obj)
    _write("\n--- codex stream end ---\n")


if __name__ == "__main__":
    main()
