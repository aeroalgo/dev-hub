"""Runtime-neutral session evidence extracted from provider logs."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable


@dataclass(frozen=True)
class SessionEvent:
    """Content-free normalized event shared by all runtime adapters."""

    runtime: str
    event_type: str
    sequence: int
    session_id: str = ""
    status: str | None = None
    tool: str | None = None
    item_type: str | None = None
    explicit_finish: bool = False
    metadata: dict[str, Any] | None = None


SCHEMA_SESSION_EVENTS = "loop-session-events/v1"


_FINISH_RE = re.compile(r"(?i)(?:^|\b)(?:FINISH|TASK_COMPLETE|TASK_COMPLETED)(?:\b|$)")


def _text_flags(value: Any) -> tuple[bool, bool]:
    if not isinstance(value, str):
        return False, False
    return bool(_FINISH_RE.search(value)), bool(re.search(r"(?i)\baborted\b", value))


def _bounded_text_flags(value: Any) -> tuple[bool, bool]:
    if isinstance(value, str):
        return _text_flags(value[:8192])
    if isinstance(value, dict):
        finish = aborted = False
        for key, item in value.items():
            if str(key).lower() in {"text", "message", "content", "result", "aggregated_output"}:
                f, a = _bounded_text_flags(item)
                finish = finish or f
                aborted = aborted or a
        return finish, aborted
    if isinstance(value, list):
        finish = aborted = False
        for item in value[:32]:
            f, a = _bounded_text_flags(item)
            finish = finish or f
            aborted = aborted or a
        return finish, aborted
    return False, False


def _marker_session_id(line: str) -> str:
    match = re.search(r"\bsession=([^\s]+)", line)
    return match.group(1) if match else ""


def _event_type(runtime: str, raw_type: str, item_type: str | None, obj: dict[str, Any]) -> str:
    normalized = raw_type.lower().replace("-", "_").replace(".", "_")
    item = (item_type or "").lower()
    if normalized in {"session_start", "session_end", "heartbeat", "result", "error"}:
        return normalized
    if normalized in {"turn_completed", "turn_complete"}:
        return "turn_end"
    if normalized in {"assistant", "assistant_message", "message"}:
        return "assistant_message"
    if normalized in {"user", "reasoning"}:
        return normalized
    if normalized in {"item_started", "tool_started"}:
        return "tool_start" if item not in {"agent_message", "reasoning"} else item
    if normalized in {"item_completed", "tool_completed"}:
        if item == "agent_message":
            return "assistant_message"
        if item == "reasoning":
            return "reasoning"
        if item == "error":
            return "error"
        return "tool_end"
    if normalized in {"stream_event", "content_block_start", "content_block_delta"}:
        return "stream"
    if item == "command_execution":
        return "tool_event"
    if runtime == "dsh" and normalized == "session_end":
        return "session_end"
    return "runtime_event"


def parse_session_events(raw_log: str, runtime: str) -> list[SessionEvent]:
    """Normalize JSONL and wrapper markers without retaining provider content."""
    events: list[SessionEvent] = []
    session_id = ""
    sequence = 0

    def add(event_type: str, *, obj: dict[str, Any] | None = None, status: str | None = None,
            tool: str | None = None, item_type: str | None = None, explicit_finish: bool = False,
            metadata: dict[str, Any] | None = None, event_session: str = "") -> None:
        nonlocal sequence, session_id
        if event_session:
            session_id = event_session
        events.append(SessionEvent(
            runtime=runtime,
            event_type=event_type,
            sequence=sequence,
            session_id=session_id,
            status=status,
            tool=tool,
            item_type=item_type,
            explicit_finish=explicit_finish,
            metadata=metadata or {},
        ))
        sequence += 1

    for line in (raw_log or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("SESSION_START"):
            session_id = _marker_session_id(stripped) or session_id
            add("session_start", event_session=session_id)
            continue
        if stripped.startswith("SESSION_END"):
            session_id = _marker_session_id(stripped) or session_id
            match = re.search(r"\bexit_code=(-?\d+)", stripped)
            add("session_end", status=match.group(1) if match else None, event_session=session_id)
            continue
        if stripped.startswith("SESSION_COLLAB_WAIT_TIMEOUT"):
            add(
                "error",
                metadata={"diagnostic": "native_collaboration_wait_timeout"},
            )
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            finish, aborted = _text_flags(stripped)
            if finish or aborted:
                add(
                    "runtime_text",
                    explicit_finish=finish,
                    metadata={"aborted_marker": aborted} if aborted else {},
                )
            continue
        if not isinstance(obj, dict):
            continue
        raw_type = str(obj.get("type") or obj.get("event_type") or "runtime_event")
        nested = obj.get("event") if isinstance(obj.get("event"), dict) else None
        source = nested or obj
        item = source.get("item") if isinstance(source.get("item"), dict) else None
        if item is None and source is not obj:
            item = source
        item_type = str(item.get("type")) if item and item.get("type") else None
        target = item or source
        finish, aborted = _bounded_text_flags(target)
        status_value = target.get("status") or source.get("status") or obj.get("status")
        status = str(status_value) if status_value is not None else None
        tool_value = target.get("tool") or target.get("name")
        tool = str(tool_value) if isinstance(tool_value, str) else None
        event_type = _event_type(runtime, raw_type, item_type, obj)
        add(
            event_type,
            obj=obj,
            status=status,
            tool=tool,
            item_type=item_type,
            explicit_finish=finish,
            metadata={"aborted_marker": aborted} if aborted else {},
        )
    return events


def summarize_session_events(events: Iterable[SessionEvent], exit_code: int | None = None) -> dict[str, Any]:
    """Build a bounded progress projection suitable for state and incident records."""
    materialized = list(events)
    counts: dict[str, int] = {}
    for event in materialized:
        counts[event.event_type] = counts.get(event.event_type, 0) + 1
    # FINISH is a terminal signal only when it comes from model/runtime output.
    # A command's aggregated_output may contain the word FINISH while the
    # command itself failed; treating that as completion is a false positive.
    explicit_finish = any(
        event.explicit_finish
        and event.event_type in {"assistant_message", "runtime_text", "result"}
        for event in materialized
    )
    has_error = any(event.event_type == "error" for event in materialized)
    has_progress = any(event.event_type in {"tool_start", "tool_end", "tool_event", "assistant_message", "write", "result"} for event in materialized)
    has_session_start = any(event.event_type == "session_start" for event in materialized)
    has_session_end = any(event.event_type == "session_end" for event in materialized)
    process_failed = exit_code not in (0, None)
    if process_failed:
        # Provider output may contain a planned FINISH before the wrapper is
        # killed.  A failed process is never semantic completion.
        semantic_status = "error" if has_error else "incomplete"
        task_complete = False
    elif explicit_finish:
        semantic_status = "complete"
        task_complete: bool | None = True
    elif has_error:
        semantic_status = "error"
        task_complete = False
    elif has_progress or materialized:
        semantic_status = "incomplete"
        task_complete = False
    else:
        semantic_status = "unknown"
        task_complete = None
    return {
        "event_counts": counts,
        "event_count": len(materialized),
        "has_progress": has_progress,
        "explicit_finish": explicit_finish,
        "semantic_status": semantic_status,
        "task_complete": task_complete,
        "has_session_start": has_session_start,
        "has_session_end": has_session_end,
        "process_exit_code": exit_code,
        "last_event": materialized[-1].event_type if materialized else None,
    }


def append_session_events(
    epic_dir: str | Path,
    events: Iterable[SessionEvent],
    *,
    session_id: str = "",
    step_id: str = "",
    epic_id: str = "",
    role: str = "",
    phase: str = "",
    outcome: str | None = None,
) -> Path | None:
    """Append normalized provider events to the runtime-neutral evidence stream."""
    materialized = list(events)
    if not materialized:
        return None
    target_dir = Path(epic_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "session-events.jsonl"
    with target.open("a", encoding="utf-8") as stream:
        for event in materialized[-2000:]:
            stream.write(json.dumps({
                "schema": SCHEMA_SESSION_EVENTS,
                "runtime": event.runtime,
                "session_id": session_id or event.session_id,
                "step_id": step_id,
                "epic_id": epic_id,
                "role": role,
                "phase": phase,
                "sequence": event.sequence,
                "event_type": event.event_type,
                "status": event.status,
                "tool": event.tool,
                "item_type": event.item_type,
                "explicit_finish": event.explicit_finish,
                "outcome": outcome,
                "metadata": event.metadata or {},
            }, ensure_ascii=False) + "\n")
    return target
