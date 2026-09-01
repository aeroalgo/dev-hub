"""Janitor report schema and read-only entropy audit entry point."""

from __future__ import annotations

from loop.janitor.schema import JANITOR_REPORT_SCHEMA, JanitorFinding, JanitorReport, JanitorSummary

__all__ = [
    "JANITOR_REPORT_SCHEMA",
    "JanitorFinding",
    "JanitorReport",
    "JanitorSummary",
    "scan",
]


def scan(cwd: str | None = None) -> JanitorReport:
    from loop.janitor.scan import scan as _scan
    return _scan(cwd=cwd)
