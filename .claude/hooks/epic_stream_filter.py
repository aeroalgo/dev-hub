#!/usr/bin/env python3
"""Print assistant text + tool activity from claude -p --output-format stream-json."""
from __future__ import annotations

import json
import sys
from pathlib import Path


_seen_tool_ids: set[str] = set()
_seen_text_via_delta = False
_last_usage_key: tuple[int, int, int] | None = None

_TOOL_CANONICAL = {
    "read": "Read",
    "bash": "Bash",
    "write": "Write",
    "edit": "Edit",
    "multiedit": "MultiEdit",
    "glob": "Glob",
    "grep": "Grep",
    "agent": "Agent",
    "task": "Task",
    "taskcreate": "TaskCreate",
    "todowrite": "TodoWrite",
    "todoread": "TodoRead",
    "skill": "Skill",
    "webfetch": "WebFetch",
    "websearch": "WebSearch",
}


def _write(text: str) -> None:
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
    except BrokenPipeError:
        sys.exit(0)


def _short_path(path: str) -> str:
    p = path.replace("\\", "/")
    if not p:
        return path

    candidate = Path(p)
    if not candidate.is_absolute():
        return candidate.as_posix()

    repo_root = Path(__file__).resolve().parents[2]
    try:
        return candidate.resolve().relative_to(repo_root).as_posix()
    except (OSError, ValueError):
        return candidate.name


def _canonical_tool_name(name: str) -> str:
    raw = (name or "?").strip()
    if not raw:
        return "?"
    return _TOOL_CANONICAL.get(raw.lower(), raw)


def _tool_input_ready(name: str, inp: dict) -> bool:
    """True when block has enough args to print a useful line (not empty {})."""
    if not isinstance(inp, dict) or not inp:
        return False
    key = (name or "").lower()
    if key == "read":
        return bool(inp.get("file_path") or inp.get("path"))
    if key == "bash":
        return bool((inp.get("command") or "").strip())
    if key in {"write", "edit", "multiedit"}:
        return bool(inp.get("file_path") or inp.get("path"))
    if key in {"agent", "task"}:
        return bool(
            inp.get("subagent_type")
            or inp.get("agent_type")
            or inp.get("description")
            or inp.get("prompt")
        )
    if key == "taskcreate":
        return bool(inp.get("subject"))
    return True


def _format_tool(block: dict) -> str:
    name = _canonical_tool_name(str(block.get("name") or "?"))
    inp = block.get("input") if isinstance(block.get("input"), dict) else {}
    key = name.lower()
    if key == "read":
        fp = inp.get("file_path") or inp.get("path") or ""
        if fp:
            return f"→ Read {_short_path(str(fp))}\n"
    if key == "bash":
        cmd = (inp.get("command") or "").replace("\n", " ").strip()
        if cmd:
            if len(cmd) > 140:
                cmd = cmd[:137] + "..."
            return f"→ Bash {cmd}\n"
    if key in {"write", "edit", "multiedit"}:
        fp = inp.get("file_path") or inp.get("path") or ""
        if fp:
            return f"→ {name} {_short_path(str(fp))}\n"
    if key in {"agent", "task"}:
        sub = inp.get("subagent_type") or inp.get("agent_type") or ""
        desc = (inp.get("description") or inp.get("prompt") or "")[:80]
        return f"→ {name} {sub} {desc}\n"
    if key == "taskcreate":
        subj = inp.get("subject") or ""
        return f"→ TaskCreate {subj}\n"
    return f"→ {name}\n"


def _emit_tool(block: dict) -> None:
    name = str(block.get("name") or "")
    inp = block.get("input") if isinstance(block.get("input"), dict) else {}
    if not _tool_input_ready(name, inp):
        return
    tid = block.get("id")
    if tid:
        if tid in _seen_tool_ids:
            return
        _seen_tool_ids.add(tid)
    _write(_format_tool(block))


def _emit_text(text: str) -> None:
    if text:
        _write(text)


def _emit_text_delta(text: str) -> None:
    global _seen_text_via_delta
    if text:
        _seen_text_via_delta = True
        _write(text)


def _emit_usage(usage: dict) -> None:
    """Surface message_delta usage — Gemini/omniroute often leaves assistant.usage at 0."""
    global _last_usage_key
    if not isinstance(usage, dict):
        return
    inp = usage.get("input_tokens")
    out = usage.get("output_tokens")
    if not isinstance(inp, int) or not isinstance(out, int):
        return
    if inp == 0 and out == 0:
        return
    cache = usage.get("cache_read_input_tokens")
    cache_i = cache if isinstance(cache, int) else 0
    key = (inp, out, cache_i)
    if key == _last_usage_key:
        return
    _last_usage_key = key
    if cache_i:
        _write(f"↻ tokens in={inp} out={out} cache_read={cache_i}\n")
    else:
        _write(f"↻ tokens in={inp} out={out}\n")


def reset_stream_state() -> None:
    """Test/helper: clear dedupe state between messages."""
    global _seen_text_via_delta, _last_usage_key
    _seen_tool_ids.clear()
    _seen_text_via_delta = False
    _last_usage_key = None


def emit_from_obj(obj: dict) -> None:
    global _seen_text_via_delta

    if obj.get("type") == "assistant":
        msg = obj.get("message") or {}
        for block in msg.get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                if not _seen_text_via_delta:
                    _emit_text(block.get("text") or "")
            elif block.get("type") == "tool_use":
                _emit_tool(block)
        usage = msg.get("usage")
        if isinstance(usage, dict):
            _emit_usage(usage)
        _seen_text_via_delta = False
        return

    if obj.get("type") == "stream_event":
        ev = obj.get("event") or {}
        et = ev.get("type")
        if et == "message_start":
            _seen_text_via_delta = False
        elif et == "content_block_start":
            cb = ev.get("content_block") or {}
            if cb.get("type") == "tool_use":
                _emit_tool(cb)
        elif et == "content_block_delta":
            delta = ev.get("delta") or {}
            if delta.get("type") == "text_delta":
                _emit_text_delta(delta.get("text") or "")
        elif et == "message_delta":
            usage = ev.get("usage")
            if isinstance(usage, dict):
                _emit_usage(usage)
        return

    if obj.get("type") == "content_block_delta":
        delta = obj.get("delta") or {}
        if delta.get("type") == "text_delta":
            _emit_text_delta(delta.get("text") or "")
        return

    if obj.get("type") == "message_delta":
        usage = obj.get("usage")
        if isinstance(usage, dict):
            _emit_usage(usage)
        if _seen_text_via_delta:
            return
        delta = obj.get("delta") or {}
        for block in delta.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text":
                _emit_text(block.get("text") or "")


def main() -> None:
    _write("--- epic stream (tools + text) ---\n")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            _write(line + "\n")
            continue
        emit_from_obj(obj)
    _write("\n--- epic stream end ---\n")


if __name__ == "__main__":
    main()
