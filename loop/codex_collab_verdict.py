"""Mirror gate verdicts from Codex ``exec --json`` collab spawn/wait events into epic state."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from loop.runtime_adapters.agent_contract import get_agent_contract_adapter
from loop.runtime_adapters.subagent_lifecycle import (
    SubagentCompletion,
    _already_processed,
)
from loop.schemas.gate_verdict import GateVerdictRecord

_AT_AGENT_RE = re.compile(r"@([\w-]+)")
_GATE_REPAIR_HINT_RE = re.compile(r"(?i)gate-repair|@gate-repair")
_AGENT_TYPE_RE = re.compile(r"(?im)^\s*(?:agent_type|subagent_type)\s*[:=]\s*([a-z0-9_-]+)")


@dataclass(frozen=True)
class CollabVerdictEvent:
    agent_type: str
    verdict: str
    message: str
    tool_use_id: str | None
    thread_id: str | None = None
    spawn_tool_use_id: str | None = None


def _normalize_agent_type(raw: str | None) -> str | None:
    if not raw:
        return None
    token = raw.strip().lower()
    aliases = {
        "verify": "verify-implement",
        "reviewer": "verify-qa",
        "explore": "explorer",
    }
    return aliases.get(token, token)


def _parse_gate_verdict_fence(message: str) -> GateVerdictRecord | None:
    return get_agent_contract_adapter("codex").parse_gate_verdict(message)


def _infer_agent_type(
    prompt: str | None,
    message: str,
    *,
    fence: GateVerdictRecord | None = None,
) -> str | None:
    if fence and fence.agent_id:
        agent = _normalize_agent_type(fence.agent_id)
        if agent:
            return agent
    if prompt:
        match = _AGENT_TYPE_RE.search(prompt)
        if match:
            agent = _normalize_agent_type(match.group(1))
            if agent:
                return agent
        for match in _AT_AGENT_RE.finditer(prompt):
            agent = _normalize_agent_type(match.group(1))
            if agent:
                return agent
        if _GATE_REPAIR_HINT_RE.search(prompt):
            return "gate-repair"
    return None


def iter_codex_collab_verdicts(log_text: str) -> Iterator[CollabVerdictEvent]:
    """Yield verify/gate verdicts recorded in Codex JSONL session logs."""
    pending_threads: dict[str, tuple[str, str | None]] = {}
    for line in log_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        item = obj.get("item")
        if not isinstance(item, dict):
            continue

        item_type = item.get("type")
        if item_type != "collab_tool_call":
            continue

        from loop.runtime_adapters.codex_collaboration import normalize_collaboration_item

        item = normalize_collaboration_item(item)

        tool = item.get("tool")
        prompt = str(item.get("prompt") or "")
        agent_hint = _infer_agent_type(prompt, "")

        if tool == "spawn_agent":
            for thread_id in item.get("receiver_thread_ids") or []:
                if isinstance(thread_id, str) and thread_id.strip():
                    pending_threads[thread_id.strip()] = (
                        agent_hint or "",
                        str(item.get("id") or "").strip() or None,
                    )
            continue

        if tool != "wait":
            continue

        states = item.get("agents_states")
        if not isinstance(states, dict):
            continue

        for thread_id, state in states.items():
            if not isinstance(state, dict):
                continue
            message = str(state.get("message") or "")
            if str(state.get("status") or "").lower() != "completed":
                continue
            fence = _parse_gate_verdict_fence(message)
            if fence is None:
                continue
            observed = pending_threads.get(str(thread_id))
            if not observed:
                continue
            agent_type, spawn_tool_use_id = observed
            agent_type = agent_type or _infer_agent_type(prompt, message, fence=fence)
            if not agent_type:
                continue
            yield CollabVerdictEvent(
                agent_type=agent_type,
                verdict=str(fence.verdict).upper(),
                message=message,
                tool_use_id=str(item.get("id") or "").strip() or None,
                thread_id=str(thread_id),
                spawn_tool_use_id=spawn_tool_use_id,
            )


def _invoke_subagent_start(
    *,
    cwd: str | Path,
    session_id: str,
    agent_type: str,
    prompt: str,
    tool_use_id: str | None,
    thread_id: str | None,
) -> int:
    hub_root = Path(__file__).resolve().parents[1]
    script = hub_root / "harness" / "hooks" / "subagent-start.py"
    payload = {
        "agent_type": agent_type,
        "prompt": prompt,
        "cwd": str(cwd),
        "session_id": session_id,
        "runtime_id": "codex",
        "tool_use_id": tool_use_id or "",
        "thread_id": thread_id or "",
    }
    env = os.environ.copy()
    env["PYTHONPATH"] = str(hub_root)
    env["EPIC_LOOP"] = "1"
    env["EPIC_RUNTIME"] = "codex"
    proc = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc.returncode


def _invoke_subagent_stop(
    *,
    cwd: str | Path,
    session_id: str,
    agent_type: str,
    message: str,
    tool_use_id: str | None,
    verdict: str,
) -> int:
    hub_root = Path(__file__).resolve().parents[1]
    script = hub_root / "harness" / "hooks" / "subagent-stop.py"
    payload = {
        "agent_type": agent_type,
        "cwd": str(cwd),
        "session_id": session_id,
        "tool_use_id": tool_use_id or "",
        "last_assistant_message": message,
        "verdict": verdict,
    }
    env = os.environ.copy()
    env["PYTHONPATH"] = str(hub_root)
    proc = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc.returncode


def mirror_codex_collab_verdicts_from_log(
    cwd: str | Path,
    log_path: str | Path,
    *,
    session_id: str | None = None,
) -> list[dict[str, Any]]:
    """Parse a Codex session log and mirror collab subagent VERDICTs via subagent-stop."""
    path = Path(log_path)
    if not path.is_file():
        return []

    log_text = path.read_text(encoding="utf-8", errors="replace")
    sid = (session_id or "").strip()
    if not sid:
        try:
            from epic_lib import load_epic_state

            st = load_epic_state(cwd)
            sid = str(st.get("session_id") or "").strip()
        except Exception:
            sid = ""

    results: list[dict[str, Any]] = []
    for event in iter_codex_collab_verdicts(log_text):
        completion = SubagentCompletion(
            agent_type=event.agent_type,
            message=event.message,
            verdict=event.verdict,
            tool_use_id=event.tool_use_id,
            thread_id=event.thread_id,
            spawn_tool_use_id=event.spawn_tool_use_id,
        )
        if _already_processed(cwd, sid, completion):
            continue
        start_rc = _invoke_subagent_start(
            cwd=cwd,
            session_id=sid,
            agent_type=event.agent_type,
            prompt=f"agent_type={event.agent_type}\n{event.thread_id or ''}",
            tool_use_id=event.spawn_tool_use_id,
            thread_id=event.thread_id,
        )
        if start_rc != 0:
            results.append(
                {
                    "agent_type": event.agent_type,
                    "verdict": event.verdict,
                    "exit_code": start_rc,
                    "tool_use_id": event.tool_use_id,
                    "error": "subagent_start_denied",
                }
            )
            continue
        rc = _invoke_subagent_stop(
            cwd=cwd,
            session_id=sid,
            agent_type=event.agent_type,
            message=event.message,
            tool_use_id=event.tool_use_id,
            verdict=event.verdict,
        )
        results.append(
            {
                "agent_type": event.agent_type,
                "verdict": event.verdict,
                "exit_code": rc,
                "tool_use_id": event.tool_use_id,
            }
        )
    return results
