"""Plan-derived AUDIT coverage and convergence invariants (no test execution)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def plan_contract(text: str) -> tuple[set[str], set[str], bool]:
    """Stable refs: AC+:N, AC-:N, NFR-NNN, layout:path and constitution:L<N>."""
    refs: set[str] = set(re.findall(r"\bNFR-\d{3,4}\b", text))
    paths: set[str] = set()
    section = ""
    ac = ""
    ac_count = 0
    sunset_lines: list[str] = []
    sunset = False
    for line in text.splitlines():
        if line.startswith("#"):
            title = line.lstrip("# ").strip().replace("−", "-")
            if line.startswith("## "):
                sunset = bool(re.search(r"sunset|replacement", title, re.I))
            if sunset:
                sunset_lines.append(line)
            section = title
            ac = "AC+" if re.search(r"\bAC\+", title) else "AC-" if re.search(r"\bAC-", title) else ""
            ac_count = 0
            continue
        if sunset:
            sunset_lines.append(line)
        if ac and re.match(r"\s*(?:\d+[.)]|[-*])\s+", line):
            ac_count += 1
            refs.add(f"{ac}:{ac_count}")
        if re.search(r"files|target layout|target tree|layout|файлы|структура", section, re.I):
            # Explicit table / bullet paths, excluding prose/example fragments.
            for candidate in re.findall(r"`([^`]+)`", line):
                if ("/" in candidate or re.search(r"\.[a-z]{1,5}$", candidate)) and not re.search(r"\s|[<>]", candidate):
                    paths.add(candidate.rstrip("/"))
    refs.update(f"layout:{p}" for p in paths)
    body = "\n".join(sunset_lines)
    brownfield = bool(body.strip()) and not re.search(r"\bn/a\b|greenfield", body, re.I)
    return refs, paths, brownfield


def _path_exists(cwd: Path, path: str) -> bool:
    if not path or Path(path).is_absolute() or ".." in Path(path).parts:
        return False
    if any(c in path for c in "*?["):
        return any(cwd.glob(path))
    return (cwd / path).exists()


def validate_contract(doc: dict[str, Any], cwd: Path, plan_path: Path) -> list[str]:
    errors: list[str] = []
    refs, paths, brownfield = plan_contract(plan_path.read_text(encoding="utf-8"))
    constitution = cwd / "memory-bank/constitution.md"
    if constitution.is_file():
        for n, line in enumerate(constitution.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\bMUST\b|\bHARD\b|\bFORBIDDEN\b", line):
                refs.add(f"constitution:L{n}")
        if (doc.get("intent_checked") or {}).get("constitution_checked") is not True:
            errors.append("audit_constitution_unchecked")
    pvr = [r for r in doc.get("plan_vs_runtime", []) if isinstance(r, dict)]
    covered = {str(r.get("source_ref", "")) for r in pvr}
    # Open missing intents may be represented by actionable findings.
    findings = [f for f in doc.get("findings", []) if isinstance(f, dict)]
    finding_refs = {str(f.get("source_ref", "")) for f in findings}
    for ref in sorted(refs - covered - finding_refs):
        errors.append(f"audit_intent_uncovered:{ref}")
    parity = [r for r in doc.get("architecture_parity", []) if isinstance(r, dict)]
    mapped = {str(r.get("layout_path", "")).rstrip("/") for r in parity}
    for path in sorted(paths - mapped):
        errors.append(f"audit_layout_uncovered:{path}")
    converged = doc.get("converged") is True
    for row in parity:
        path = str(row.get("layout_path", ""))
        status = row.get("status")
        if status not in {"present", "satisfied", "missing", "partial", "deferred"}:
            errors.append(f"audit_architecture_status_invalid:{path}")
        if converged and status in {"missing", "partial"}:
            errors.append(f"audit_architecture_open:{path}")
        if status in {"present", "satisfied"} and not _path_exists(cwd, path):
            errors.append(f"audit_architecture_path_missing:{path}")
        if status == "deferred":
            follow = str(row.get("follow_up") or "").strip()
            queues = list((cwd / "memory-bank").glob("*/roadmap/*queue.y*ml"))
            if not follow or not any(follow in p.read_text(encoding="utf-8") for p in queues):
                errors.append(f"audit_layout_follow_up_unqueued:{path}")
        if not str(row.get("evidence") or "").strip():
            errors.append(f"audit_architecture_evidence_missing:{path}")
    scan = doc.get("sunset_inventory_scan")
    scan = scan if isinstance(scan, dict) else {}
    rows = scan.get("rows")
    na = str(scan.get("plan_ref") or "").lower().startswith("n/a")
    if not scan.get("scanned_at") or not isinstance(rows, list) or not scan.get("plan_ref") or (brownfield and (na or not rows)):
        errors.append("audit_scan_incomplete")
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or any(not row.get(k) for k in ("symbol", "kind", "command", "result")):
            errors.append("audit_scan_row_incomplete")
        elif row["result"] not in {"pass", "fail"} or (converged and (row["result"] != "pass" or row.get("prod_callers"))):
            errors.append("audit_scan_failed")
    for field in ("legacy_surfaces_remaining", "fallback_remaining", "instruction_remaining"):
        if not isinstance(doc.get(field), list):
            errors.append(f"audit_leftovers_missing:{field}")
        elif converged and doc[field]:
            errors.append(f"audit_converged_with_leftovers:{field}")
    if converged and doc.get("purge_step_present") is not True and (brownfield or not na):
        errors.append("audit_purge_missing")
    for finding in findings:
        for field in ("id", "gap_type", "severity", "source_ref", "evidence", "remaining_work"):
            if not finding.get(field):
                errors.append(f"audit_finding_field_missing:{field}")
        if finding.get("severity") not in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
            errors.append("audit_finding_severity_invalid")
    return errors
