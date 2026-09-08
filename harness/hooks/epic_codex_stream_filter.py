#!/usr/bin/env python3
"""Compact terminal view for `codex exec --json` (loop headless)."""
from __future__ import annotations

import json
import re
import shlex
import sys

_SKIP_ERROR_SUBSTRINGS = (
    "Skill descriptions were shortened",
)
_SHELL_COMMAND_RE = re.compile(r"^(?:/usr)?/bin/(?:ba)?sh\s+-lc\s+(.+)$")
_pending_commands: dict[str, str] = {}


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


def _display_command(command: str) -> str:
    raw = " ".join((command or "").split())
    match = _SHELL_COMMAND_RE.match(raw)
    if match:
        try:
            parts = shlex.split(match.group(1))
        except ValueError:
            parts = []
        if parts:
            raw = " ".join(parts)
    if len(raw) > 160:
        raw = raw[:157] + "..."
    return raw


def reset_stream_state() -> None:
    _pending_commands.clear()


def emit_from_obj(obj: dict) -> None:
    event_type = obj.get("type")
    if event_type == "item.started":
        item = obj.get("item") if isinstance(obj.get("item"), dict) else {}
        if item.get("type") == "command_execution":
            command = (item.get("command") or "").strip()
            if command:
                item_id = str(item.get("id") or "")
                display = _display_command(command)
                if item_id:
                    _pending_commands[item_id] = display
                _write(f"→ Bash {display}\n")
        return

    if event_type != "item.completed":
        return

    item = obj.get("item") if isinstance(obj.get("item"), dict) else {}
    item_type = item.get("type")

    if item_type == "command_execution":
        if item.get("status") != "completed":
            return
        exit_code = item.get("exit_code")
        if exit_code not in (None, 0):
            item_id = str(item.get("id") or "")
            display = _pending_commands.get(item_id) or _display_command(
                str(item.get("command") or "")
            )
            _write(f"✗ Bash {display} (exit={exit_code})\n")
        item_id = str(item.get("id") or "")
        if item_id:
            _pending_commands.pop(item_id, None)
        return

    if item_type == "agent_message":
        text = _agent_text(str(item.get("text") or ""))
        if text:
            _write(text + "\n")
        return

    if item_type == "error":
        message = str(item.get("message") or "").strip()
        if message and not _skip_error(message):
            _write(f"✗ error: {message}\n")


def main() -> None:
    reset_stream_state()
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


if __name__ == "__main__":
    main()
