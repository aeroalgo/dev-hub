"""Read-only entropy audit scan entry point for Janitor."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from loop.janitor.detectors import DETECTORS
from loop.janitor.schema import JanitorFinding, JanitorReport, JanitorSummary


def scan(cwd: str | Path | None = None) -> JanitorReport:
    """Run read-only entropy audit scan across target directory."""
    target_path = Path(cwd).resolve() if cwd else Path.cwd().resolve()
    findings: list[JanitorFinding] = []

    for detector in DETECTORS:
        try:
            res = detector(target_path)
            findings.extend(res)
        except Exception:
            pass

    cat_counts: dict[str, int] = {}
    for f in findings:
        cat_counts[f.category] = cat_counts.get(f.category, 0) + 1

    summary = JanitorSummary(
        total_findings=len(findings),
        categories_count=cat_counts,
    )

    return JanitorReport(
        cwd=str(target_path),
        generated_at=datetime.now(timezone.utc).isoformat(),
        findings=findings,
        summary=summary,
    )
