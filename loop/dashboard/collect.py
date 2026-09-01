"""Dashboard collection module."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from loop.dashboard.schema import DashboardReport, EpisodeSummary, TaskRow
from loop.episodes.core import episodes_root, list_episodes
from loop.incidents.metrics import MetricsRecord, compute_rates, load_metrics
from loop.incidents.store import parse_incidents_jsonl
from loop.incidents.schema import IncidentRecord


def _parse_tasks_md_active_rows(cwd: Path) -> list[TaskRow]:
    tasks_path = cwd / "memory-bank" / "tasks.md"
    if not tasks_path.is_file():
        return []

    lines = tasks_path.read_text(encoding="utf-8").splitlines()
    in_active_section = False
    rows: list[TaskRow] = []

    for line in lines:
        line_strip = line.strip()
        if line_strip.startswith("## Active"):
            in_active_section = True
            continue
        elif line_strip.startswith("## ") and in_active_section:
            break

        if in_active_section and line_strip.startswith("|") and not line_strip.startswith("|---") and not line_strip.startswith("| Epic") and not re.match(r"^\|\s*:?-+:?\s*\|", line_strip):
            parts = [p.strip() for p in line_strip.split("|")[1:-1]]
            if len(parts) >= 4:
                epic_id = parts[0]
                role = parts[1] if len(parts) > 1 else ""
                phase = parts[2] if len(parts) > 2 else ""
                step = parts[3] if len(parts) > 3 else ""
                title = parts[4] if len(parts) > 4 else ""
                if epic_id and epic_id != "Epic" and not epic_id.startswith("-"):
                    rows.append(TaskRow(epic_id=epic_id, role=role, phase=phase, step=step, title=title))

    return rows


def _parse_iso_ts(ts_str: str) -> datetime | None:
    if not ts_str:
        return None
    try:
        # Handle ISO strings
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        return None


def collect(cwd: str | Path, days: int = 7) -> DashboardReport:
    """Aggregate dashboard metrics, open incidents, events by kind, last episodes, and active task progress."""
    root = Path(cwd).resolve()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    # 1. Load metrics
    mb_dir = root / "memory-bank"
    metrics_rec = load_metrics(mb_dir)
    # Ensure rates match compute_rates
    if metrics_rec.counters:
        metrics_rec.rates = compute_rates(metrics_rec.counters)

    # 2. Parse open incidents across all roles in memory-bank/
    open_incidents: list[IncidentRecord] = []
    if mb_dir.is_dir():
        for inc_file in mb_dir.glob("**/incidents.jsonl"):
            try:
                records = parse_incidents_jsonl(inc_file)
                for r in records:
                    if r.status == "open":
                        open_incidents.append(r)
            except Exception:
                pass

    # 3. Events by kind (in last days)
    events_by_kind: dict[str, int] = {}
    if mb_dir.is_dir():
        for evt_file in mb_dir.glob("**/events.jsonl"):
            if not evt_file.is_file():
                continue
            for line in evt_file.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    kind = data.get("kind")
                    ts_str = data.get("timestamp") or data.get("created_at") or data.get("ts")
                    if kind:
                        if ts_str:
                            ts = _parse_iso_ts(str(ts_str))
                            if ts and ts < cutoff:
                                continue
                        events_by_kind[str(kind)] = events_by_kind.get(str(kind), 0) + 1
                except Exception:
                    pass

    # 4. Last episodes (up to 20)
    last_episodes: list[EpisodeSummary] = []
    ep_root = episodes_root(root)
    if ep_root.is_dir():
        ep_ids = list_episodes(root)
        for ep_id in ep_ids[:20]:
            ep_dir = ep_root / ep_id
            manifest_file = ep_dir / "manifest.json"
            if manifest_file.is_file():
                try:
                    data = json.loads(manifest_file.read_text(encoding="utf-8"))
                    last_episodes.append(
                        EpisodeSummary(
                            episode_id=data.get("episode_id", ep_id),
                            started_at=data.get("started_at", ""),
                            ended_at=data.get("ended_at"),
                            epic_id=data.get("epic_id", ""),
                            role=data.get("role", ""),
                            armed_step=data.get("armed_step", ""),
                            decide=data.get("decide"),
                            halt_reason=data.get("halt_reason"),
                            incident_count=len(data.get("incident_ids") or []),
                        )
                    )
                except Exception:
                    pass

    # 5. Epic progress from tasks.md
    epic_progress = _parse_tasks_md_active_rows(root)

    return DashboardReport(
        schema_version="dashboard-report/v1",
        generated_at=now.isoformat(),
        cwd=str(root),
        days_window=days,
        metrics=metrics_rec,
        open_incidents=open_incidents,
        events_by_kind=events_by_kind,
        last_episodes=last_episodes,
        epic_progress=epic_progress,
    )
