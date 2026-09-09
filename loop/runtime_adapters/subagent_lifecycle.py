"""Runtime-neutral lifecycle for managed gate subagents.

Claude Code calls this lifecycle through its native SubagentStart/SubagentStop
hooks.  Runtimes without those callbacks (currently Codex native
``multi_agent``) feed normalized spawn/wait items into the same object.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from loop.runtime_adapters.agent_contract import get_agent_contract_adapter


_AGENT_TYPE_RE = re.compile(
    r"(?im)^\s*(?:agent_type|subagent_type|role)\s*[:=]\s*([a-z0-9_-]+)"
)
_AT_AGENT_RE = re.compile(r"@([a-z][a-z0-9_-]+)", re.IGNORECASE)
_REVIEWER_ALIASES = {"reviewer", "verify-qa"}


@dataclass(frozen=True)
class SubagentCompletion:
    """A normalized completed managed child."""

    agent_type: str
    message: str
    verdict: str
    tool_use_id: str | None = None
    thread_id: str | None = None
    spawn_tool_use_id: str | None = None


@dataclass(frozen=True)
class LifecycleAction:
    """Result of applying one normalized child completion."""

    agent_type: str
    verdict: str
    start_exit_code: int
    stop_exit_code: int
    finish: dict[str, Any] | None = None
    stderr: str = ""


def normalize_agent_type(raw: str | None) -> str | None:
    token = str(raw or "").strip().lower()
    if not token:
        return None
    return {
        "verify": "verify-implement",
        "reviewer": "verify-qa",
        "explore": "explorer",
    }.get(token, token)


def infer_agent_type(
    prompt: str | None,
    message: str | None = None,
    *,
    fence: Any = None,
) -> str | None:
    """Infer the managed child only from transport metadata or valid evidence."""
    if fence is not None:
        agent = normalize_agent_type(getattr(fence, "agent_id", None))
        if agent:
            return agent
    text = f"{prompt or ''}\n{message or ''}"
    match = _AGENT_TYPE_RE.search(text)
    if match:
        return normalize_agent_type(match.group(1))
    for match in _AT_AGENT_RE.finditer(prompt or ""):
        agent = normalize_agent_type(match.group(1))
        if agent:
            return agent
    if re.search(r"(?i)\b(?:BACK\s+)?QA\b|review", prompt or ""):
        return "verify-qa"
    if re.search(r"(?i)gate-repair", prompt or ""):
        return "gate-repair"
    return None


def _hook_environment(runtime_id: str) -> dict[str, str]:
    env = os.environ.copy()
    env["EPIC_LOOP"] = "1"
    env["EPIC_RUNTIME"] = runtime_id
    env.setdefault("EPIC_RUNTIME_RESOLVED", runtime_id)
    return env


def _hook_path(name: str) -> Path:
    return Path(__file__).resolve().parents[2] / "harness" / "hooks" / name


def _run_hook(name: str, payload: dict[str, Any], *, cwd: str | Path, runtime_id: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(_hook_path(name))],
        input=json.dumps(payload, ensure_ascii=False),
        cwd=str(cwd),
        env=_hook_environment(runtime_id),
        capture_output=True,
        text=True,
        check=False,
    )
    stderr = result.stderr or ""
    # Never write hook diagnostics into a JSONL pipe; callers surface them
    # on the human-readable console stream instead.
    return result.returncode, stderr


def _record_agent_key(agent_type: str) -> str:
    return "reviewer" if agent_type in _REVIEWER_ALIASES else agent_type


def _already_processed(cwd: str | Path, session_id: str, completion: SubagentCompletion) -> bool:
    """Prevent the end-of-session fallback from replaying a live completion."""
    if not session_id or not completion.tool_use_id:
        return False
    try:
        from harness.hooks._lib import load_state, verdict_dedupe_key

        state = load_state(session_id, str(cwd))
        key = verdict_dedupe_key(
            session_id,
            _record_agent_key(completion.agent_type),
            tool_use_id=completion.tool_use_id,
            verdict=completion.verdict,
        )
        return key in (state.get("verdict_recorded_agents") or [])
    except Exception:
        return False


def auto_finish_after_gate(
    cwd: str | Path,
    *,
    agent_type: str,
    verdict: str,
    session_id: str,
) -> dict[str, Any] | None:
    """Finish QA after a valid reviewer PASS, using the canonical mb-finish.

    Implement/bugfix gates intentionally do not finish here: their parent must
    first persist the implement/bugfix artifact.  QA already has its artifact
    before the reviewer is spawned, so the reviewer completion is the canonical
    finish boundary.
    """
    if agent_type not in _REVIEWER_ALIASES or str(verdict).upper() != "PASS":
        return None

    try:
        from harness.hooks.epic.core import load_epic_state

        state = load_epic_state(cwd)
        phase = str(state.get("phase") or state.get("armed_step") or "").upper()
        if phase != "QA" or not state.get("active"):
            return None
        finish = state.get("last_finish_tool")
        if isinstance(finish, dict) and str(finish.get("name") or "").startswith("mb-finish qa"):
            return {"ok": True, "already_finished": True}

        from loop.mb_finish.impl import finish_qa
        from loop.mb_finish.schemas import MbFinishRequest

        result = finish_qa(
            MbFinishRequest(
                phase="QA",
                step_id="QA",
                done_summary="verify-qa PASS; QA finished by shared gate lifecycle",
                cwd=str(cwd),
            )
        )
        return result.model_dump()
    except Exception as exc:
        return {"ok": False, "diagnostic_codes": ["auto_qa_finish_failed"], "error": str(exc)}


class SubagentLifecycle:
    """Consume normalized collaboration items and invoke shared gate hooks."""

    def __init__(self, cwd: str | Path, session_id: str, runtime_id: str) -> None:
        self.cwd = str(cwd)
        self.session_id = str(session_id or "")
        self.runtime_id = runtime_id
        self._pending: dict[str, tuple[str, str | None]] = {}
        self._completed: set[str] = set()

    def _start_and_stop(self, completion: SubagentCompletion) -> LifecycleAction:
        start_payload = {
            "agent_type": completion.agent_type,
            "prompt": f"agent_type={completion.agent_type}",
            "cwd": self.cwd,
            "session_id": self.session_id,
            "runtime_id": self.runtime_id,
            "tool_use_id": completion.spawn_tool_use_id or completion.thread_id or "",
            "thread_id": completion.thread_id or "",
        }
        start_rc, start_err = _run_hook(
            "subagent-start.py", start_payload, cwd=self.cwd, runtime_id=self.runtime_id
        )
        if start_rc != 0:
            return LifecycleAction(
                completion.agent_type,
                completion.verdict,
                start_rc,
                start_rc,
                stderr=start_err,
            )

        stop_payload = {
            "agent_type": completion.agent_type,
            "cwd": self.cwd,
            "session_id": self.session_id,
            "runtime_id": self.runtime_id,
            "tool_use_id": completion.tool_use_id or "",
            "thread_id": completion.thread_id or "",
            "last_assistant_message": completion.message,
            "verdict": completion.verdict,
        }
        stop_rc, stop_err = _run_hook(
            "subagent-stop.py", stop_payload, cwd=self.cwd, runtime_id=self.runtime_id
        )
        finish = None
        if stop_rc == 0:
            finish = auto_finish_after_gate(
                self.cwd,
                agent_type=completion.agent_type,
                verdict=completion.verdict,
                session_id=self.session_id,
            )
        return LifecycleAction(
            completion.agent_type,
            completion.verdict,
            start_rc,
            stop_rc,
            finish,
            stderr=stop_err or start_err,
        )

    def process_item(self, item: dict[str, Any]) -> list[LifecycleAction]:
        """Process one adapter-normalized ``spawn_agent``/``wait`` item."""
        tool = str(item.get("tool") or "").strip()
        if tool == "spawn_agent":
            prompt = str(item.get("prompt") or "")
            hint = infer_agent_type(prompt)
            spawn_id = str(item.get("id") or "").strip() or None
            for thread_id in item.get("receiver_thread_ids") or []:
                thread = str(thread_id).strip()
                if thread:
                    self._pending[thread] = (hint or "", spawn_id)
            return []
        if tool != "wait":
            return []

        states = item.get("agents_states")
        if not isinstance(states, dict):
            return []
        actions: list[LifecycleAction] = []
        wait_id = str(item.get("id") or "").strip() or None
        for thread_id, state in states.items():
            if not isinstance(state, dict):
                continue
            if str(state.get("status") or "").lower() not in {"completed", "failed", "error", "closed"}:
                continue
            thread = str(thread_id).strip()
            message = str(state.get("message") or state.get("output") or state.get("result") or "")
            fence = get_agent_contract_adapter(self.runtime_id).parse_gate_verdict(message)
            if fence is None:
                continue
            pending = self._pending.get(thread, ("", None))
            agent_type = normalize_agent_type(pending[0]) or infer_agent_type(None, message, fence=fence)
            if not agent_type:
                continue
            completion = SubagentCompletion(
                agent_type=agent_type,
                message=message,
                verdict=str(fence.verdict).upper(),
                tool_use_id=wait_id,
                thread_id=thread,
                spawn_tool_use_id=pending[1],
            )
            dedupe = f"{thread}:{wait_id or ''}:{completion.verdict}"
            if dedupe in self._completed or _already_processed(self.cwd, self.session_id, completion):
                continue
            self._completed.add(dedupe)
            actions.append(self._start_and_stop(completion))
            self._pending.pop(thread, None)
        return actions

