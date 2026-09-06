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

from loop.schemas.gate_verdict import GateVerdictRecord, SCHEMA_LOOP_GATE_VERDICT
from loop.validate_boundary import validate_boundary

_JSON_FENCE_RE = re.compile(r"```json[^\n`]*\n(.*?)\n```", re.DOTALL)
_AT_AGENT_RE = re.compile(r"@([\w-]+)")
_GATE_REPAIR_HINT_RE = re.compile(r"(?i)gate-repair|@gate-repair")


@dataclass(frozen=True)
class CollabVerdictEvent:
    agent_type: str
    verdict: str
    message: str
    tool_use_id: str | None


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


def _extract_json_fence(text: str) -> dict[str, Any] | None:
    if not isinstance(text, str) or not text.strip():
        return None
    match = _JSON_FENCE_RE.search(text)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _parse_gate_verdict_fence(message: str) -> GateVerdictRecord | None:
    data = _extract_json_fence(message)
    if not data or not isinstance(data, dict):
        return None
    res = validate_boundary(SCHEMA_LOOP_GATE_VERDICT, data)
    if not res.valid:
        return None
    try:
        return GateVerdictRecord.model_validate(data)
    except Exception:
        return None


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
        for match in _AT_AGENT_RE.finditer(prompt):
            agent = _normalize_agent_type(match.group(1))
            if agent:
                return agent
        if _GATE_REPAIR_HINT_RE.search(prompt):
            return "gate-repair"
    return None


def iter_codex_collab_verdicts(log_text: str) -> Iterator[CollabVerdictEvent]:
    """Yield verify/gate verdicts recorded in Codex JSONL session logs."""
    pending_threads: dict[str, str] = {}
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

        tool = item.get("tool")
        prompt = str(item.get("prompt") or "")
        agent_hint = _infer_agent_type(prompt, "")

        if tool == "spawn_agent" and agent_hint:
            for thread_id in item.get("receiver_thread_ids") or []:
                if isinstance(thread_id, str) and thread_id.strip():
                    pending_threads[thread_id.strip()] = agent_hint
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
            fence = _parse_gate_verdict_fence(message)
            if fence is None:
                continue
            agent_type = pending_threads.get(str(thread_id)) or _infer_agent_type(
                prompt, message, fence=fence
            )
            if not agent_type:
                continue
            yield CollabVerdictEvent(
                agent_type=agent_type,
                verdict=str(fence.verdict).upper(),
                message=message,
                tool_use_id=str(item.get("id") or "").strip() or None,
            )


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
