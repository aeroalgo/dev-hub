#!/usr/bin/env python3
"""Traceability parsers and report data structures (T-HUB-024)."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any
import yaml


class ReqID(str):
    """Requirement ID string wrapper (FR-###, SC-###, US-###)."""
    pass


@dataclass
class ShardTrace:
    step_id: str
    plan_refs: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)


@dataclass
class Evidence:
    step_id: str
    status: str = "pending"
    files: list[str] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)


@dataclass
class Finding:
    id: str
    severity: str
    message: str
    shard: str = ""


@dataclass
class TraceReport:
    epic_id: str
    requirements: list[str] = field(default_factory=list)
    shards: dict[str, ShardTrace] = field(default_factory=dict)
    evidence: dict[str, Evidence] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    coverage_pct: float = 0.0
    critical_count: int = 0
    high_count: int = 0


def parse_plan_requirements(plan_md_path: Path) -> list[str]:
    """Extract requirement IDs (FR-###, SC-###, US-###) from plan.md.

    Robust to missing file or missing requirements table/sections (returns []).
    """
    if not plan_md_path.exists() or not plan_md_path.is_file():
        return []

    try:
        content = plan_md_path.read_text(encoding="utf-8")
    except Exception:
        return []

    # Matches FR-001, SC-001, US-001 etc.
    raw_matches = re.findall(r"\b((?:FR|SC|US)-\d{3,4})\b", content)

    requirements: list[str] = []
    seen: set[str] = set()
    for req in raw_matches:
        if req not in seen:
            seen.add(req)
            requirements.append(ReqID(req))

    return requirements


def parse_decompose_refs(decompose_dir: Path) -> dict[str, ShardTrace]:
    """Parse all sNN*.yaml shards in decompose_dir and extract plan_refs & out_of_scope.

    Robust to missing directory, invalid YAML, or missing keys.
    """
    result: dict[str, ShardTrace] = {}
    if not decompose_dir.exists() or not decompose_dir.is_dir():
        return result

    for shard_path in sorted(decompose_dir.glob("s*.yaml")):
        if shard_path.name == "index.yaml":
            continue
        try:
            with open(shard_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            data = {}

        if not isinstance(data, dict):
            data = {}

        step_id = str(data.get("step_id") or shard_path.stem.split("-")[0])

        plan_refs_raw = data.get("plan_refs")
        if plan_refs_raw is None and isinstance(data.get("context"), dict):
            plan_refs_raw = data.get("context", {}).get("plan_refs")
        if isinstance(plan_refs_raw, list):
            plan_refs = [str(x) for x in plan_refs_raw if x is not None]
        else:
            plan_refs = []

        out_of_scope_raw = data.get("out_of_scope")
        if isinstance(out_of_scope_raw, list):
            out_of_scope = [str(x) for x in out_of_scope_raw if x is not None]
        else:
            out_of_scope = []

        result[step_id] = ShardTrace(
            step_id=step_id,
            plan_refs=plan_refs,
            out_of_scope=out_of_scope,
        )

    return result


def parse_implement_evidence(implement_dir: Path) -> dict[str, Evidence]:
    """Parse all sNN*.yaml shards in implement_dir and extract status, files & tests.

    Robust to missing directory, invalid YAML, or missing keys.
    """
    result: dict[str, Evidence] = {}
    if not implement_dir.exists() or not implement_dir.is_dir():
        return result

    for shard_path in sorted(implement_dir.glob("s*.yaml")):
        if shard_path.name == "index.yaml":
            continue
        try:
            with open(shard_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            data = {}

        if not isinstance(data, dict):
            data = {}

        step_id = str(data.get("step_id") or shard_path.stem.split("-")[0])
        status = str(data.get("status") or "pending")

        files_raw = data.get("files")
        if isinstance(files_raw, list):
            files = [str(x) for x in files_raw if x is not None]
        else:
            files = []

        tests_raw = data.get("tests")
        if isinstance(tests_raw, list):
            tests = [str(x) for x in tests_raw if x is not None]
        else:
            tests = []

        result[step_id] = Evidence(
            step_id=step_id,
            status=status,
            files=files,
            tests=tests,
        )

    return result


def scan_ac_markers(tests_dir: Path | None) -> dict[str, list[str]]:
    """Scan python test files in tests_dir for @pytest.mark.ac("...") markers.

    Returns mapping: requirement_id (e.g. 'FR-001') -> list of test_file relative paths.
    """
    if tests_dir is None or not tests_dir.is_dir():
        return {}

    ac_map: dict[str, list[str]] = {}
    pattern = re.compile(r'@pytest\.mark\.ac\(\s*["\']([^"\']+)["\']\s*\)')

    for test_file in sorted(tests_dir.rglob("*.py")):
        if not test_file.is_file():
            continue
        try:
            content = test_file.read_text(encoding="utf-8")
        except OSError:
            continue

        matches = pattern.findall(content)
        rel_path = str(test_file)
        for req in matches:
            req_str = str(req).strip()
            if req_str not in ac_map:
                ac_map[req_str] = []
            if rel_path not in ac_map[req_str]:
                ac_map[req_str].append(rel_path)

    return ac_map


def enrich_with_ac(report: TraceReport, ac_map: dict[str, list[str]], strict: bool = False) -> None:
    """Enrich report findings with acceptance criteria marker coverage checks.

    If a plan requirement is missing from ac_map (or has no test files),
    add MEDIUM finding (or HIGH finding if strict=True).
    """
    if not ac_map and not strict:
        # If ac_map is empty because tests_dir was not passed or scanned empty,
        # but strict is False, we do not add findings for all requirements.
        return

    finding_idx = len(report.findings) + 1
    for req in report.requirements:
        if req not in ac_map or not ac_map[req]:
            severity = "HIGH" if strict else "MEDIUM"
            report.findings.append(
                Finding(
                    id=f"TR-{finding_idx:03d}",
                    severity=severity,
                    message=f"Requirement {req} has no pytest.mark.ac markers in test suite",
                )
            )
            finding_idx += 1

    report.critical_count = sum(1 for f in report.findings if f.severity == "CRITICAL")
    report.high_count = sum(1 for f in report.findings if f.severity == "HIGH")


_DEFER_CLAIM_RE = re.compile(
    r"\bdeferred\b|\bpartial\b|leave for later|follow[\s-]?up|если не нужно",
    re.IGNORECASE,
)
_FOLLOW_UP_ID_RE = re.compile(
    r"follow_up:\s*(T-[\w-]+)|(?<![\w-])(T-(?:HUB|FRONT|INTEG)-[\w-]+)",
    re.IGNORECASE,
)


def oos_has_valid_follow_up(text: str) -> bool:
    """True when out_of_scope line names a follow-up epic ID."""
    return bool(_FOLLOW_UP_ID_RE.search(text or ""))


def oos_is_invalid_deferral(text: str) -> bool:
    """Deferral/partial claim without follow_up epic ID → invalid escape hatch."""
    raw = text or ""
    if not _DEFER_CLAIM_RE.search(raw):
        return False
    return not oos_has_valid_follow_up(raw)


def oos_covers_requirement(text: str, req: str) -> bool:
    """Count OOS as coverage only if it mentions req and is not an invalid deferral."""
    if req not in (text or ""):
        return False
    if oos_is_invalid_deferral(text):
        return False
    return True


def run_checks(
    plan_reqs: list[str],
    decomp_refs: dict[str, ShardTrace],
    impl_ev: dict[str, Evidence],
    strict: bool = False,
) -> list[Finding]:
    """Run traceability rules on parsed requirements, decompose refs, and implement evidence.

    Rules:
    (a) FR/SC/US in plan without any sNN covering it in plan_refs or valid out_of_scope -> CRITICAL
    (b) sNN without plan_refs and not out_of_scope -> HIGH (or CRITICAL if strict)
    (c) completed implement without tests -> HIGH (or CRITICAL if strict)
    (d) coverage_pct < 80% -> MEDIUM
    (e) out_of_scope deferral/partial without follow_up:T-… epic ID -> CRITICAL (not coverage)
    """
    findings: list[Finding] = []
    finding_idx = 1

    covered_reqs: set[str] = set()

    # Check each requirement in plan
    for req in plan_reqs:
        is_covered = False
        for shard_id, shard in decomp_refs.items():
            # Check plan_refs
            for ref in shard.plan_refs:
                if req in ref:
                    is_covered = True
                    break
            if is_covered:
                break
            # Check out_of_scope (valid deferral with follow_up ID counts; bare deferred does not)
            for oos in shard.out_of_scope:
                if oos_covers_requirement(oos, req):
                    is_covered = True
                    break
            if is_covered:
                break

        if is_covered:
            covered_reqs.add(req)
        else:
            findings.append(
                Finding(
                    id=f"TR-{finding_idx:03d}",
                    severity="CRITICAL",
                    message=f"Requirement {req} has no coverage in decompose shards (plan_refs or out_of_scope)",
                )
            )
            finding_idx += 1

    # Check each shard in decompose
    for shard_id, shard in decomp_refs.items():
        if not shard.plan_refs and not shard.out_of_scope:
            severity = "CRITICAL" if strict else "HIGH"
            findings.append(
                Finding(
                    id=f"TR-{finding_idx:03d}",
                    severity=severity,
                    message=f"Shard {shard_id} has empty plan_refs and no out_of_scope references",
                    shard=shard_id,
                )
            )
            finding_idx += 1

        for oos in shard.out_of_scope:
            if oos_is_invalid_deferral(oos):
                findings.append(
                    Finding(
                        id=f"TR-{finding_idx:03d}",
                        severity="CRITICAL",
                        message=(
                            f"Shard {shard_id} out_of_scope deferral without follow_up epic ID "
                            f"in queue form (need `follow_up: T-…`): {oos[:120]}"
                        ),
                        shard=shard_id,
                    )
                )
                finding_idx += 1

    # Check implement evidence
    for shard_id, ev in impl_ev.items():
        if ev.status == "completed" and not ev.tests:
            severity = "CRITICAL" if strict else "HIGH"
            findings.append(
                Finding(
                    id=f"TR-{finding_idx:03d}",
                    severity=severity,
                    message=f"Completed implement shard {shard_id} has no tests evidence",
                    shard=shard_id,
                )
            )
            finding_idx += 1

    # Check overall coverage percentage
    if plan_reqs:
        pct = (len(covered_reqs) / len(plan_reqs)) * 100.0
        if pct < 80.0:
            findings.append(
                Finding(
                    id=f"TR-{finding_idx:03d}",
                    severity="MEDIUM",
                    message=f"Traceability coverage is {pct:.1f}% (below 80% threshold)",
                )
            )
            finding_idx += 1

    return findings


def build_report(
    epic_id: str,
    plan_reqs: list[str],
    decomp_refs: dict[str, ShardTrace],
    impl_ev: dict[str, Evidence],
    strict: bool = False,
    tests_dir: Path | None = None,
    ac_strict: bool = False,
) -> TraceReport:
    """Build a TraceReport object containing coverage metrics and findings."""
    findings = run_checks(plan_reqs, decomp_refs, impl_ev, strict=strict)

    covered_count = 0
    if plan_reqs:
        for req in plan_reqs:
            is_covered = False
            for shard in decomp_refs.values():
                if any(req in ref for ref in shard.plan_refs) or any(
                    oos_covers_requirement(oos, req) for oos in shard.out_of_scope
                ):
                    is_covered = True
                    break
            if is_covered:
                covered_count += 1
        coverage_pct = (covered_count / len(plan_reqs)) * 100.0
    else:
        coverage_pct = 100.0 if not findings else 0.0

    critical_count = sum(1 for f in findings if f.severity == "CRITICAL")
    high_count = sum(1 for f in findings if f.severity == "HIGH")

    report = TraceReport(
        epic_id=epic_id,
        requirements=plan_reqs,
        shards=decomp_refs,
        evidence=impl_ev,
        findings=findings,
        coverage_pct=coverage_pct,
        critical_count=critical_count,
        high_count=high_count,
    )

    if tests_dir is not None:
        ac_map = scan_ac_markers(tests_dir)
        enrich_with_ac(report, ac_map, strict=ac_strict)

    return report


def format_report(report: TraceReport, json_mode: bool = False) -> str:
    """Format TraceReport into JSON string or human-readable summary text."""
    if json_mode:
        matrix: list[dict[str, Any]] = []
        for req in report.requirements:
            covering_shards = [
                step_id
                for step_id, shard in report.shards.items()
                if any(req in ref for ref in shard.plan_refs)
                or any(oos_covers_requirement(oos, req) for oos in shard.out_of_scope)
            ]
            matrix.append(
                {
                    "req_id": req,
                    "covered": len(covering_shards) > 0,
                    "shards": covering_shards,
                }
            )

        data: dict[str, Any] = {
            "schema": "traceability-report/v1",
            "epic_id": report.epic_id,
            "coverage_pct": round(report.coverage_pct, 1),
            "critical_count": report.critical_count,
            "high_count": report.high_count,
            "requirements_count": len(report.requirements),
            "shards_count": len(report.shards),
            "matrix": matrix,
            "findings": [
                {
                    "id": f.id,
                    "severity": f.severity,
                    "message": f.message,
                    "shard": f.shard,
                }
                for f in report.findings
            ],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    lines: list[str] = [
        f"=== Traceability Report for {report.epic_id} ===",
        f"Coverage: {report.coverage_pct:.1f}% ({len(report.requirements)} requirements)",
        f"Critical Findings: {report.critical_count}",
        f"High Findings: {report.high_count}",
    ]

    if report.findings:
        lines.append("\nFindings:")
        for f in report.findings:
            shard_info = f" [{f.shard}]" if f.shard else ""
            lines.append(f"  - [{f.severity}]{shard_info} {f.id}: {f.message}")
    else:
        lines.append("\nNo traceability issues found.")

    return "\n".join(lines)

