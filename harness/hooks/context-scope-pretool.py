#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import emit, is_epic_loop_env, product_cwd, read_stdin
from context_scope import ScopeResolver
from epic_lib import extract_load_now, read_active_context


READ_TOOLS = {"Read", "read", "ReadFile", "read_file", "View", "view", "cat"}
SEARCH_TOOLS = {"Glob", "glob", "Grep", "grep"}
PATH_KEYS = ("file_path", "path", "notebook_path", "file", "filename")


def _tool_input(data: dict) -> dict:
    for key in ("tool_input", "arguments", "args", "input"):
        value = data.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _path_for(data: dict, tool_name: str) -> str:
    tool_input = _tool_input(data)
    for key in PATH_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if tool_name in SEARCH_TOOLS:
        pattern = tool_input.get("pattern")
        if isinstance(pattern, str) and pattern.strip() and not any(ch in pattern for ch in "*?["):
            return pattern.strip()
    return "."


def _line_bounds(data: dict) -> tuple[int | None, int | None]:
    tool_input = _tool_input(data)
    try:
        if tool_input.get("offset") is not None and tool_input.get("limit") is not None:
            start = int(tool_input["offset"])
            return start, start + int(tool_input["limit"]) - 1
        start = int(tool_input["start_line"]) if tool_input.get("start_line") is not None else None
        end = int(tool_input["end_line"]) if tool_input.get("end_line") is not None else None
        return start, end
    except (TypeError, ValueError):
        return None, None


def _current_resolver(cwd: Path) -> ScopeResolver | None:
    active_path = cwd / "memory-bank" / "activeContext.md"
    text = read_active_context(cwd)
    load_now = extract_load_now(text)
    shard = next(
        (
            cwd / path
            for path in load_now
            if "/yaml/steps/" in path.replace("\\", "/")
            and Path(path).name != "decompose-index.yaml"
        ),
        None,
    )
    if not active_path.is_file() or shard is None or not shard.is_file():
        return None
    return ScopeResolver(project_root=cwd, shard_path=shard, load_now=load_now)


def main() -> None:
    data = read_stdin()
    if not is_epic_loop_env():
        return
    raw_name = str(data.get("tool_name") or data.get("tool") or data.get("name") or "")
    if raw_name not in READ_TOOLS and raw_name not in SEARCH_TOOLS:
        return

    cwd = product_cwd(data.get("cwd") or "")
    resolver = _current_resolver(cwd)
    if resolver is None:
        reason = "context_scope_denied: current IMPLEMENT shard is missing or unreadable"
    else:
        path = _path_for(data, raw_name)
        start_line, end_line = _line_bounds(data)
        if raw_name in READ_TOOLS:
            allowed, _code, details = resolver.evaluate_read_scope(
                path,
                mode="IMPLEMENT",
                start_line=start_line,
                end_line=end_line,
                graphify_evidence=data.get("graphify_evidence"),
                exception_reason=data.get("exception_reason"),
            )
        else:
            allowed, _code, details = resolver.evaluate_search(
                f"rg __scope__ {path}",
                cwd=cwd,
                graphify_evidence=data.get("graphify_evidence"),
                exception_reason=data.get("exception_reason"),
            )
        if allowed:
            return
        reason = str(details.get("diagnostic") or "context scope denied")

    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
                "additionalContext": f"context-scope DENY: {reason}",
            }
        }
    )


if __name__ == "__main__":
    main()
