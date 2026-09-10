#!/usr/bin/env python3
"""Compact terminal view for `codex exec --json` (loop headless)."""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loop.runtime_adapters.codex import CodexAdapter

_SKIP_ERROR_SUBSTRINGS = (
    "Skill descriptions were shortened",
)
_SHELL_COMMAND_RE = re.compile(r"^(?:/usr)?/bin/(?:ba)?sh\s+-lc\s+(.+)$")
_pending_commands: dict[str, str] = {}
_pending_children: set[str] = set()
_codex_adapter = CodexAdapter()
_lifecycle: object | None = None


def _collaboration_tool(item: dict) -> str:
    tool = str(item.get("tool") or "").strip()
    try:
        from loop.runtime_adapters.codex_collaboration import normalize_tool_identity

        _namespace, tool = normalize_tool_identity(tool, item.get("namespace"))
    except Exception:
        pass
    return str(tool or "unknown")


def _collaboration_label(item: dict) -> str:
    for key in ("agent_type", "subagent_type", "agent_name", "name"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    prompt = str(item.get("prompt") or "")
    try:
        from loop.runtime_adapters.subagent_lifecycle import infer_agent_type

        inferred = infer_agent_type(prompt)
        if inferred:
            return inferred
    except Exception:
        pass
    match = re.search(
        r"(?im)^\s*(?:agent_type|subagent_type)\s*[:=]\s*([a-z0-9_-]+)",
        prompt,
    )
    if match:
        return match.group(1).strip().lower()
    heading = re.search(r"(?im)^\s*#\s+([a-z][a-z0-9_-]{1,63})(?=\s|:|$)", prompt)
    return heading.group(1) if heading else "unknown"


def _display_child_message(message: str, *, limit: int = 4000) -> str | None:
    text = (message or "").strip()
    if not text:
        return None
    if len(text) > limit:
        text = text[:limit] + "…"
    return text


def _child_message(state: dict) -> str | None:
    for key in ("message", "output", "result", "last_message"):
        value = state.get(key)
        if isinstance(value, dict):
            value = value.get("text") or value.get("message")
        message = _display_child_message(str(value or ""))
        if message:
            return message
    return None


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
        # Keep a readable summary instead of dropping the whole turn — otherwise
        # verify/repair fences vanish from the console while the parent waits.
        prose = []
        in_fence = False
        for line in stripped.splitlines():
            if line.strip().startswith("```"):
                in_fence = not in_fence
                continue
            if not in_fence:
                prose.append(line)
        compact = "\n".join(prose).strip()
        return compact or None
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
    global _lifecycle
    _pending_commands.clear()
    _pending_children.clear()
    _lifecycle = _codex_adapter.subagent_lifecycle(
        os.environ.get("PROJECT_ROOT") or str(Path.cwd()),
        os.environ.get("EPIC_RUNNER_SESSION_ID") or "",
    )


def emit_from_obj(obj: dict) -> None:
    event_type = obj.get("type")
    if event_type == "item.started":
        item = obj.get("item") if isinstance(obj.get("item"), dict) else {}
        if item.get("type") == "collab_tool_call":
            tool = _collaboration_tool(item)
            if tool == "spawn_agent":
                _pending_children.update(
                    str(thread_id)
                    for thread_id in item.get("receiver_thread_ids") or []
                    if str(thread_id).strip()
                )
                _write(f"→ Subagent spawn type={_collaboration_label(item)}\n")
            elif tool == "wait":
                _pending_children.update(
                    str(thread_id)
                    for thread_id in item.get("receiver_thread_ids") or []
                    if str(thread_id).strip()
                )
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
        if _lifecycle is not None:
            try:
                actions = _lifecycle.process_item(
                    _codex_adapter.normalize_collaboration_item(item)
                )
                for action in actions or []:
                    stderr = str(getattr(action, "stderr", "") or "").strip()
                    if stderr:
                        for line in stderr.splitlines():
                            _write(f"{line}\n")
                    stop_rc = int(getattr(action, "stop_exit_code", 0) or 0)
                    if stop_rc != 0 and not stderr:
                        _write(
                            f"← Subagent hook fail agent={getattr(action, 'agent_type', '?')} "
                            f"rc={stop_rc}\n"
                        )
            except Exception as exc:
                # The display filter must never terminate the runtime stream;
                # record-session remains the bounded fallback processor.
                print(f"codex subagent lifecycle adapter error: {exc}", file=sys.stderr)
        tool = _collaboration_tool(item)
        _pending_children.update(
            str(thread_id)
            for thread_id in item.get("receiver_thread_ids") or []
            if str(thread_id).strip()
        )
        states = item.get("agents_states")
        states = states if isinstance(states, dict) else {}
        if not states:
            pending = ", ".join(sorted(_pending_children))
            suffix = f": {pending}" if pending else ""
            _write(
                f"← Subagent {tool} completed "
                f"(child output pending{suffix})\n"
            )
            return
        for thread_id, state in states.items():
            if not isinstance(state, dict):
                continue
            status = str(state.get("status") or "unknown")
            _write(f"← Subagent {thread_id} status={status}\n")
            message = _child_message(state)
            if message:
                _write(f"  {message}\n")
            if status.lower() in {"completed", "failed", "error", "closed"}:
                _pending_children.discard(str(thread_id))
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
