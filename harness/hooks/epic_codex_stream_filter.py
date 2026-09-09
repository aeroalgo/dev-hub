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


def _collaboration_tool(item: dict) -> str:
    tool = str(item.get("tool") or "").strip()
    try:
        from loop.runtime_adapters.codex_collaboration import normalize_tool_identity

        _namespace, tool = normalize_tool_identity(tool, item.get("namespace"))
    except Exception:
        pass
    return str(tool or "unknown")


def _collaboration_label(item: dict) -> str:
    prompt = str(item.get("prompt") or "")
    match = re.search(r"(?im)^\s*(?:role|agent_type|subagent_type)\s*[:=]\s*([^\n]+)", prompt)
    return match.group(1).strip() if match else "unknown"


def _display_child_message(message: str, *, limit: int = 4000) -> str | None:
    text = (message or "").strip()
    if not text:
        return None
    if len(text) > limit:
        text = text[:limit] + "…"
    return text


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
        if item.get("type") == "collab_tool_call":
            tool = _collaboration_tool(item)
            if tool == "spawn_agent":
                _write(f"→ Subagent spawn type={_collaboration_label(item)}\n")
            elif tool == "wait":
                count = len(item.get("receiver_thread_ids") or [])
                _write(f"→ Subagent wait children={count}\n")
            return
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

    if item_type == "collab_tool_call":
        tool = _collaboration_tool(item)
        states = item.get("agents_states")
        states = states if isinstance(states, dict) else {}
        if not states:
            _write(f"← Subagent {tool} completed (child output pending)\n")
            return
        for thread_id, state in states.items():
            if not isinstance(state, dict):
                continue
            status = str(state.get("status") or "unknown")
            _write(f"← Subagent {thread_id} status={status}\n")
            message = _display_child_message(str(state.get("message") or ""))
            if message:
                _write(f"  {message}\n")
        return

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
