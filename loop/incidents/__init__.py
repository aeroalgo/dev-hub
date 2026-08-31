"""loop.incidents package export."""

from __future__ import annotations

from loop.incidents.metrics import (
    MetricsRecord,
    increment_counter,
    load_metrics,
)
from loop.incidents.schema import (
    SCHEMA_LOOP_INCIDENT,
    IncidentRecord,
    IncidentStatus,
    compute_incident_id,
)
from loop.incidents.store import (
    CorruptIncidentError,
    append_incident,
    list_open_incidents,
    parse_incidents_jsonl,
    resolve_incident,
)
from loop.incidents.trace import (
    SCHEMA_LOOP_SESSION_TRACE,
    append_trace,
    is_trace_enabled,
    read_session_trace_tail,
)

__all__ = [
    "SCHEMA_LOOP_INCIDENT",
    "IncidentRecord",
    "IncidentStatus",
    "compute_incident_id",
    "CorruptIncidentError",
    "append_incident",
    "list_open_incidents",
    "parse_incidents_jsonl",
    "resolve_incident",
    "SCHEMA_LOOP_SESSION_TRACE",
    "append_trace",
    "is_trace_enabled",
    "read_session_trace_tail",
    "MetricsRecord",
    "increment_counter",
    "load_metrics",
]
