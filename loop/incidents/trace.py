"""loop-session-trace/v1 — session trace JSONL writer and reader."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_LOOP_SESSION_TRACE = "loop-session-trace/v1"


def is_trace_enabled() -> bool:
    """Check if session tracing is enabled via EPIC_INCIDENT_TRACE env var (default: True)."""
    val = os.getenv("EPIC_INCIDENT_TRACE", "1").strip().lower()
    return val not in ("0", "false", "no", "off")


def append_trace(
    epic_dir: Path | str,
    phase: str,
    *,
    session_id: str = "",
    step_id: str = "",
    epic_id: str = "",
    action: str = "",
    detail: dict[str, Any] | None = None,
    decide: str | None = None,
    ts: str | None = None,
) -> dict[str, Any] | None:
    """Append a session trace entry to epic_dir/session-trace.jsonl.

    Returns the entry dict if appended, or None if tracing is disabled.
    """
    if not is_trace_enabled():
        return None

    path = Path(epic_dir)
    path.mkdir(parents=True, exist_ok=True)
    trace_file = path / "session-trace.jsonl"

    if ts is None:
        ts = datetime.now(timezone.utc).isoformat()

    entry: dict[str, Any] = {
        "schema": SCHEMA_LOOP_SESSION_TRACE,
        "ts": ts,
        "session_id": session_id,
        "step_id": step_id,
        "epic_id": epic_id,
        "phase": phase,
        "action": action,
        "detail": detail or {},
        "decide": decide,
    }

    line = json.dumps(entry, ensure_ascii=False)
    with trace_file.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

    return entry


def read_session_trace_tail(epic_dir: Path | str, limit: int = 10) -> list[dict[str, Any]]:
    """Read the last `limit` trace entries from epic_dir/session-trace.jsonl."""
    trace_file = Path(epic_dir) / "session-trace.jsonl"
    if not trace_file.is_file():
        return []

    entries: list[dict[str, Any]] = []
    with trace_file.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                data = json.loads(line_str)
                if isinstance(data, dict):
                    entries.append(data)
            except json.JSONDecodeError:
                continue

    return entries[-limit:]
