#!/usr/bin/env python3
"""Cross-artifact convergence engine (T-HUB-032 / FR-001 - FR-004).

Aggregates multi-source checks: traceability, spec reconcile, and stale handoff detection.
Read-only, deduplicated findings, schema-versioned report.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
import json
from pathlib import Path
from typing import Any

from .reconcile import resolve_epic_bundle, reconcile_epic
from .traceability import (
    parse_plan_requirements,
    parse_decompose_refs,
    parse_implement_evidence,
    scan_ac_markers,
    enrich_with_ac,
    run_checks as run_traceability_checks,
    TraceReport,
)
from harness.hooks.epic_paths import is_reserved_role_epic_id


@dataclass
class ConvergenceFinding:
    id: str
    category: str  # orphan_requirement | orphan_task | ac_gap | reconcile_overlap | stale_handoff
    severity: str  # CRITICAL | HIGH | MEDIUM | LOW
    message: str
    shard: str = ""
    path: str = ""

    @property
    def fingerprint(self) -> str:
        return f"{self.severity}:{self.category}:{self.message[:60]}"


@dataclass
class ConvergenceReport:
    plan_id: str
    schema: str = "convergence-report/v1"
    findings: list[ConvergenceFinding] = field(default_factory=list)
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    coverage_pct: float = 100.0


def _dedupe_findings(findings: list[ConvergenceFinding]) -> list[ConvergenceFinding]:
    seen: set[str] = set()
    deduped: list[ConvergenceFinding] = []
    for f in findings:
        fp = f.fingerprint
        if fp not in seen:
            seen.add(fp)
            deduped.append(f)
    return deduped


def _stale_handoff_check(cwd: Path, plan_id: str) -> list[ConvergenceFinding]:
    findings: list[ConvergenceFinding] = []
    active_ctx_path = cwd / "memory-bank" / "activeContext.md"
    if not active_ctx_path.is_file():
        return findings

    try:
        content = active_ctx_path.read_text(encoding="utf-8")
    except Exception:
        return findings

    if f"epic: {plan_id}" in content or f"plan_id: {plan_id}" in content or plan_id in content:
        if "BACK IMPLEMENT" in content or "FRONT IMPLEMENT" in content or "INTEG IMPLEMENT" in content:
            if "## Handoff" not in content and "Handoff BACK IMPLEMENT" not in content:
                findings.append(
                    ConvergenceFinding(
                        id=f"CF-STALE-001",
                        category="stale_handoff",
                        severity="HIGH",
                        message=f"activeContext.md references active IMPLEMENT phase for {plan_id} but missing Handoff block",
                        path="memory-bank/activeContext.md",
                    )
                )
    return findings


def run_convergence_checks(
    cwd: Path,
    plan_id: str,
    *,
    strict: bool = False,
    include_git_diff: bool = False,
) -> ConvergenceReport:
    """Run cross-artifact convergence checks without modifying any files (read-only)."""
    root = Path(cwd).resolve()
    all_findings: list[ConvergenceFinding] = []
    seq = 1

    bundle = resolve_epic_bundle(root, plan_id)

    # 1. Traceability checks (orphan_requirement, orphan_task, ac_gap)
    if bundle is not None:
        plan_reqs = parse_plan_requirements(bundle.plan_path)
        decomp_dir = bundle.decompose_index.parent
        decomp_refs = parse_decompose_refs(decomp_dir)
        impl_ev = parse_implement_evidence(bundle.implement_dir) if bundle.implement_dir else {}

        trace_report = TraceReport(
            epic_id=bundle.epic_id,
            requirements=plan_reqs,
            shards=decomp_refs,
            evidence=impl_ev,
        )

        trace_findings = run_traceability_checks(plan_reqs, decomp_refs, impl_ev, strict=strict)
        for tf in trace_findings:
            if tf.message.startswith("Requirement") and "coverage" in tf.message:
                category = "orphan_requirement"
            elif tf.message.startswith("Shard"):
                category = "orphan_task"
            elif "implement" in tf.message.lower() or "tests" in tf.message.lower():
                category = "ac_gap"
            elif "coverage" in tf.message.lower():
                category = "orphan_requirement"
            else:
                category = "orphan_requirement"

            all_findings.append(
                ConvergenceFinding(
                    id=f"CF-{seq:03d}",
                    category=category,
                    severity=tf.severity,
                    message=tf.message,
                    shard=tf.shard,
                )
            )
            seq += 1

        tests_dir = root / "tests"
        if not tests_dir.is_dir():
            tests_dir = root / "loop" / "tests"
        if tests_dir.is_dir():
            ac_map = scan_ac_markers(tests_dir)
            enrich_with_ac(trace_report, ac_map, strict=strict)
            for tf in trace_report.findings:
                all_findings.append(
                    ConvergenceFinding(
                        id=f"CF-{seq:03d}",
                        category="ac_gap",
                        severity=tf.severity,
                        message=tf.message,
                        shard=tf.shard,
                    )
                )
                seq += 1

        # 2. Reconcile overlap checks
        rec_res = reconcile_epic(root, bundle)
        rec_findings = rec_res.get("findings", [])
        for rf in rec_findings:
            all_findings.append(
                ConvergenceFinding(
                    id=f"CF-{seq:03d}",
                    category="reconcile_overlap",
                    severity=rf.get("severity", "MEDIUM"),
                    message=rf.get("message", ""),
                    shard=rf.get("step_id", ""),
                    path=rf.get("path", ""),
                )
            )
            seq += 1

    # 3. Stale handoff check
    stale_findings = _stale_handoff_check(root, plan_id)
    for sf in stale_findings:
        sf.id = f"CF-{seq:03d}"
        all_findings.append(sf)
        seq += 1

    deduped = _dedupe_findings(all_findings)

    crit_cnt = sum(1 for f in deduped if f.severity == "CRITICAL")
    high_cnt = sum(1 for f in deduped if f.severity == "HIGH")
    med_cnt = sum(1 for f in deduped if f.severity == "MEDIUM")
    low_cnt = sum(1 for f in deduped if f.severity == "LOW")

    return ConvergenceReport(
        plan_id=plan_id,
        schema="convergence-report/v1",
        findings=deduped,
        critical_count=crit_cnt,
        high_count=high_cnt,
        medium_count=med_cnt,
        low_count=low_cnt,
        coverage_pct=100.0 if not deduped else max(0.0, 100.0 - len(deduped) * 5.0),
    )


def format_json(report: ConvergenceReport) -> str:
    """Format ConvergenceReport as JSON string."""
    data = asdict(report)
    return json.dumps(data, ensure_ascii=False, indent=2)


def format_text(report: ConvergenceReport) -> str:
    """Format ConvergenceReport as human-readable text."""
    lines = [
        "==================================================",
        f"CONVERGENCE REPORT — Epic: {report.plan_id or 'ALL ACTIVE'}",
        f"Schema: {report.schema} | Coverage: {report.coverage_pct:.1f}%",
        "==================================================",
        f"Summary: CRITICAL: {report.critical_count} | HIGH: {report.high_count} | MEDIUM: {report.medium_count} | LOW: {report.low_count}",
        "--------------------------------------------------",
    ]
    if not report.findings:
        lines.append("No convergence findings detected.")
    else:
        for f in report.findings:
            loc = f" ({f.shard or f.path})" if (f.shard or f.path) else ""
            lines.append(f"[{f.severity}] [{f.category}] {f.id}: {f.message}{loc}")
    lines.append("==================================================")
    return "\n".join(lines)
