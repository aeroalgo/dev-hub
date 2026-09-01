"""Tests for JanitorReport schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from loop.janitor.schema import JANITOR_REPORT_SCHEMA, JanitorFinding, JanitorReport, JanitorSummary


def test_janitor_schema_instantiation():
    report = JanitorReport(
        cwd="/tmp/test",
        generated_at="2026-08-31T00:00:00Z",
        findings=[],
    )
    assert report.schema == JANITOR_REPORT_SCHEMA
    assert report.cwd == "/tmp/test"
    assert report.generated_at == "2026-08-31T00:00:00Z"
    assert report.findings == []
    assert report.summary.total_findings == 0


def test_janitor_schema_invalid_version():
    with pytest.raises(ValidationError):
        JanitorReport(
            schema="invalid-v1",  # type: ignore
            cwd="/tmp/test",
            generated_at="2026-08-31T00:00:00Z",
        )


def test_janitor_finding_creation():
    finding = JanitorFinding(
        category="stale_shard",
        description="Found stale shard",
        target_path="memory-bank/stale.yaml",
    )
    assert finding.category == "stale_shard"
    assert finding.description == "Found stale shard"
    assert finding.target_path == "memory-bank/stale.yaml"
    assert finding.actionable is True
