"""Tests for Janitor scan entry point."""

from __future__ import annotations

from pathlib import Path

from loop.janitor.scan import scan
from loop.janitor.schema import JANITOR_REPORT_SCHEMA, JanitorReport


def test_scan_returns_schema(tmp_path: Path):
    report = scan(tmp_path)
    assert isinstance(report, JanitorReport)
    assert report.schema == JANITOR_REPORT_SCHEMA
    assert report.cwd == str(tmp_path.resolve())
    assert report.findings == []
    assert report.summary.total_findings == 0
