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


def _last_collab_verdict_events(
    events: list[CollabVerdictEvent],
) -> list[CollabVerdictEvent]:
    """Keep only the last verdict per record-agent key (mid-session retries superseded)."""
    from loop.mb_finish.verify_hint import record_agent_key

    last: dict[str, CollabVerdictEvent] = {}
    order: list[str] = []
    for event in events:
        key = record_agent_key(event.agent_type)
        if key not in last:
            order.append(key)
        last[key] = event
    return [last[key] for key in order]


def _mb_finish_committed(cwd: str | Path) -> bool:
    """True when live auto-finish / mb-finish already closed the gate (Claude: stop)."""
    try:
        from epic_lib import load_epic_state

        st = load_epic_state(cwd) or {}
    except Exception:
        return False
    finish = st.get("last_finish_tool")
    if not isinstance(finish, dict):
        return False
    name = str(finish.get("name") or "")
    if not name.startswith("mb-finish "):
        return False
    finish_run = str(finish.get("phase_run_id") or "").strip()
    current_run = str(st.get("phase_run_id") or "").strip()
    if finish_run and current_run and finish_run != current_run:
        return False
    return True


def _live_agent_gate_covers_event(
    cwd: str | Path,
    session_id: str,
    event: CollabVerdictEvent,
) -> bool:
    """Claude parity: live SubagentLifecycle/SubagentStop is SoT.

    Skip post-session gap-fill when live already recorded this agent and either
    matches the log's last verdict or already holds PASS (supersedes older FAIL).
    Allow gap-fill only when live has FAIL/none but the log's last event is PASS
    (stream filter died before the final child).
    """
    if not session_id:
        return False
    try:
        from harness.hooks._lib import load_state
        from loop.mb_finish.verify_hint import record_agent_key

        state = load_state(session_id, str(cwd))
        key = record_agent_key(event.agent_type)
        done = bool(state.get(f"{key}_done"))
        live_v = str(state.get(f"{key}_verdict") or "").upper()
        if key == "verify" and not done and state.get("verify_done"):
            done = True
            live_v = str(state.get("verify_verdict") or "").upper()
        if not done:
            return False
        event_v = str(event.verdict or "").upper()
        return live_v == event_v or live_v == "PASS"
    except Exception:
        return False


def mirror_codex_collab_verdicts_from_log(
    cwd: str | Path,
    log_path: str | Path,
    *,
    session_id: str | None = None,
) -> list[dict[str, Any]]:
    """Gap-fill collab VERDICTs when live Codex lifecycle missed a child.

    Claude Code: native SubagentStop only; ``post_session`` is a no-op.
    Codex: live ``SubagentLifecycle`` in the stream filter is the same SoT.
    This fallback must not replay mid-session FAIL hints after a live PASS /
    committed mb-finish — only fill agents whose gate was never recorded live.
    """
    path = Path(log_path)
    if not path.is_file():
        return []

    if _mb_finish_committed(cwd):
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
    for event in _last_collab_verdict_events(list(iter_codex_collab_verdicts(log_text))):
        if _live_agent_gate_covers_event(cwd, sid, event):
            continue
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
