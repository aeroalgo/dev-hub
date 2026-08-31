"""metrics.json rolling counters and rate metrics (schema loop-metrics/v1)."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# Supported counter metric names
VALID_COUNTERS = {
    "sessions_total",
    "tier0_attempts",
    "tier0_success",
    "tier0_fail",
    "incidents_opened",
    "incidents_escalated",
    "check_after_halt",
    "check_after_continue",
    "tier1_attempts_total",
    "tier1_resolved_total",
    "tier1_escalated_total",
}


def _is_metrics_enabled() -> bool:
    """Return True unless EPIC_INCIDENT_METRICS=0."""
    val = os.getenv("EPIC_INCIDENT_METRICS", "1").strip()
    return val != "0"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MetricEntry(BaseModel):
    timestamp: str
    counter: str
    amount: int = 1


class MetricsRecord(BaseModel):
    schema_version: str = Field(default="loop-metrics/v1", alias="schema")
    updated_at: str
    window_days: int = 7
    counters: dict[str, int] = Field(default_factory=lambda: {c: 0 for c in sorted(VALID_COUNTERS)})
    rates: dict[str, float] = Field(
        default_factory=lambda: {
            "tier0_success_rate": 0.0,
            "auto_continue_rate": 0.0,
            "tier1_success_rate": 0.0,
        }
    )
    entries: list[MetricEntry] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


def compute_rates(counters: dict[str, int]) -> dict[str, float]:
    """Compute tier0_success_rate and auto_continue_rate from counters."""
    tier0_attempts = counters.get("tier0_attempts", 0)
    tier0_success = counters.get("tier0_success", 0)
    if tier0_attempts > 0:
        tier0_success_rate = round(tier0_success / tier0_attempts, 4)
    else:
        tier0_success_rate = 0.0

    check_halt = counters.get("check_after_halt", 0)
    check_continue = counters.get("check_after_continue", 0)
    total_checks = check_halt + check_continue
    if total_checks > 0:
        auto_continue_rate = round(check_continue / total_checks, 4)
    else:
        auto_continue_rate = 0.0

    tier1_attempts = counters.get("tier1_attempts_total", 0)
    tier1_resolved = counters.get("tier1_resolved_total", 0)
    if tier1_attempts > 0:
        tier1_success_rate = round(tier1_resolved / tier1_attempts, 4)
    else:
        tier1_success_rate = 0.0

    return {
        "tier0_success_rate": tier0_success_rate,
        "auto_continue_rate": auto_continue_rate,
        "tier1_success_rate": tier1_success_rate,
    }


def load_metrics(epic_dir: Path | str) -> MetricsRecord:
    """Load metrics.json from epic_dir or return fresh metrics if missing/invalid."""
    epic_path = Path(epic_dir)
    metrics_path = epic_path / "metrics.json"

    if not metrics_path.is_file():
        now = _now_iso()
        rec = MetricsRecord(updated_at=now)
        rec.rates = compute_rates(rec.counters)
        return rec

    try:
        raw = json.loads(metrics_path.read_text(encoding="utf-8"))
        rec = MetricsRecord.model_validate(raw)
        return rec
    except Exception:
        # Fail-safe fallback to fresh record if corrupt
        now = _now_iso()
        rec = MetricsRecord(updated_at=now)
        rec.rates = compute_rates(rec.counters)
        return rec


def save_metrics_atomic(epic_dir: Path | str, metrics: MetricsRecord) -> None:
    """Atomic write metrics.json via temporary file rename."""
    epic_path = Path(epic_dir)
    epic_path.mkdir(parents=True, exist_ok=True)
    metrics_path = epic_path / "metrics.json"

    # Always ensure updated_at is refreshed before write
    metrics.updated_at = _now_iso()
    metrics.rates = compute_rates(metrics.counters)

    data_dict = metrics.model_dump(by_alias=True)
    content = json.dumps(data_dict, indent=2, ensure_ascii=False)

    with tempfile.NamedTemporaryFile("w", dir=epic_path, delete=False, encoding="utf-8") as tf:
        tf.write(content)
        temp_path = Path(tf.name)

    temp_path.replace(metrics_path)


def prune_metrics_entries(
    metrics: MetricsRecord,
    window_days: int = 7,
    now_dt: datetime | None = None,
) -> MetricsRecord:
    """Prune entries older than window_days and recompute counters & rates."""
    if now_dt is None:
        now_dt = datetime.now(timezone.utc)

    cutoff = now_dt - timedelta(days=window_days)
    new_entries: list[MetricEntry] = []

    for entry in metrics.entries:
        try:
            ts = datetime.fromisoformat(entry.timestamp)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                new_entries.append(entry)
        except Exception:
            # Skip unparseable timestamp
            continue

    new_counters = {c: 0 for c in sorted(VALID_COUNTERS)}
    for entry in new_entries:
        if entry.counter in new_counters:
            new_counters[entry.counter] += entry.amount

    metrics.entries = new_entries
    metrics.counters = new_counters
    metrics.window_days = window_days
    metrics.rates = compute_rates(new_counters)
    return metrics


def increment_counter(
    epic_dir: Path | str,
    name: str,
    amount: int = 1,
    window_days: int = 7,
    timestamp: str | None = None,
) -> MetricsRecord | None:
    """Increment counter by name, prune entries outside rolling window, and atomically update metrics.json."""
    if not _is_metrics_enabled():
        return None

    if name not in VALID_COUNTERS:
        raise ValueError(f"Unknown metric counter: {name!r}. Must be one of {sorted(VALID_COUNTERS)}")

    metrics = load_metrics(epic_dir)

    ts = timestamp or _now_iso()
    entry = MetricEntry(timestamp=ts, counter=name, amount=amount)
    metrics.entries.append(entry)

    metrics = prune_metrics_entries(metrics, window_days=window_days)
    save_metrics_atomic(epic_dir, metrics)
    return metrics
