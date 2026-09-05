"""Validate epic-audit/v2 — PLAN intent vs runtime (finish_audit gate)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from harness.hooks.epic.traceability import parse_plan_requirements
from harness.hooks.epic_paths import find_plan_md_path

_REQ_RE = re.compile(r"\b((?:FR|SC|US)-\d{3,4})\b")
_ALLOWED_STATUS = frozenset({"satisfied", "partial", "missing", "deferred"})
_ACTIONABLE_GAPS = frozenset(
    {"missing", "partial", "contradicts", "layout_dilution", "dilution"}
)
_COMPLETED = frozenset({"completed", "done"})
_PRESENCE_ONLY_RE = re.compile(
    r"(?i)(файл на диске|file on disk|файлы на диске|модуль есть|presence-only|(?:file|contract|module|directory) (?:exists|is present))"
)
_PYTEST_EVIDENCE_RE = re.compile(
    r"(?i)(pytest green|targeted suite|suite полностью|тесты зелён)"
)


def extract_plan_intent_ids(plan_path: Path) -> list[str]:
    """FR/SC/US from plan.md prose (SoT)."""
    reqs = list(parse_plan_requirements(plan_path))
    if reqs:
        return reqs
    if not plan_path.is_file():
        return []
    try:
        text = plan_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in _REQ_RE.finditer(text):
        rid = m.group(1)
        if rid not in seen:
            seen.add(rid)
            out.append(rid)
    return out


def _as_dict(data: Any) -> dict[str, Any] | None:
    return data if isinstance(data, dict) else None


def _norm_role(role_dir: str) -> str:
    value = str(role_dir or "back").strip().lower()
    if value == "integ":
        return "integration"
    return value or "back"


def _completed_step_ids(cwd: Path, role_norm: str, epic_id: str) -> list[str]:
    idx_path = (
        cwd
        / "memory-bank"
        / role_norm
        / "plan"
        / epic_id
        / "yaml"
        / "decompose-index.yaml"
    )
    if not idx_path.is_file():
        return []
    try:
        from harness.hooks.epic_index import load_index_yaml, steps_from_doc

        idx_doc = load_index_yaml(idx_path)
        steps = steps_from_doc(idx_doc or {})
    except (OSError, TypeError, ValueError, yaml.YAMLError):
        return []
    out: list[str] = []
    for step in steps:
        sid = str(step.get("id") or "").strip().lower()
        status = str(step.get("status") or "").strip().lower()
        if sid and status in _COMPLETED:
            out.append(sid)
    return out


def validate_audit_artifact(
    cwd: str | Path,
    *,
    role_dir: str,
    epic_id: str,
    audit_path: Path,
) -> list[str]:
    """Return shape/diagnostic errors; empty list = pass.

    HARD: epic-audit/v2 with plan_intent + plan_vs_runtime covering plan FR/SC/US.
    Rejects shallow v1 (status/PASS + empty not_implemented only).
    """
    errors: list[str] = []
    try:
        raw = audit_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        return [f"audit_artifact_unreadable:{exc}"]
    if not raw:
        return ["audit_artifact_empty"]

    try:
        data = yaml.safe_load(raw)
    except Exception as exc:
        return [f"audit_yaml_parse_failed:{exc}"]

    doc = _as_dict(data)
    if doc is None:
        return ["audit_yaml_not_mapping"]

    schema = str(doc.get("schema") or "").strip()
    if schema != "epic-audit/v2":
        errors.append(
            "audit_schema_not_v2:"
            f"need epic-audit/v2 (got {schema or 'missing'}); "
            "shallow v1 / status:PASS without plan_vs_runtime is forbidden"
        )
        return errors

    intent = _as_dict(doc.get("plan_intent"))
    if intent is None:
        errors.append("audit_plan_intent_missing")
    else:
        goal = str(intent.get("epic_goal") or "").strip()
        source = str(intent.get("source") or "").strip()
        if len(goal) < 16:
            errors.append(
                "audit_plan_intent_goal_missing:"
                "plan_intent.epic_goal must state epic goal from plan (≥16 chars)"
            )
        if not source:
            errors.append(
                "audit_plan_intent_source_missing:"
                "plan_intent.source must cite plan section (e.g. plan.md#WHAT)"
            )

    checked = _as_dict(doc.get("intent_checked"))
    if checked is None:
        errors.append("audit_intent_checked_missing")

    pvr = doc.get("plan_vs_runtime")
    if not isinstance(pvr, list) or not pvr:
        errors.append(
            "audit_plan_vs_runtime_missing:"
            "plan_vs_runtime[] required — each plan FR/US/SC/layout vs behavior evidence"
        )
        pvr = []

    covered_refs: set[str] = set()
    for i, row in enumerate(pvr):
        if not isinstance(row, dict):
            errors.append(f"audit_plan_vs_runtime[{i}]_not_mapping")
            continue
        ref = str(row.get("source_ref") or "").strip()
        status = str(row.get("status") or "").strip().lower()
        evidence = str(row.get("evidence") or "").strip()
        if not ref:
            errors.append(f"audit_plan_vs_runtime[{i}]_source_ref_missing")
        else:
            covered_refs.add(ref)
            for m in _REQ_RE.finditer(ref):
                covered_refs.add(m.group(1))
        if status not in _ALLOWED_STATUS:
            errors.append(
                f"audit_plan_vs_runtime[{i}]_status_invalid:"
                f"need one of {sorted(_ALLOWED_STATUS)}"
            )
        if len(evidence) < 8:
            errors.append(
                f"audit_plan_vs_runtime[{i}]_evidence_missing:"
                "behavior evidence required (not presence-only / sNN completed)"
            )
        if status == "satisfied" and _PRESENCE_ONLY_RE.search(evidence):
            errors.append(
                f"audit_plan_vs_runtime[{i}]_presence_only:"
                "satisfied FORBIDDEN on «файл есть» / file on disk"
            )
        if status == "satisfied" and _PYTEST_EVIDENCE_RE.search(evidence):
            errors.append(
                f"audit_plan_vs_runtime[{i}]_pytest_evidence:"
                "pytest/suite is not PLAN↔runtime evidence"
            )
        if status == "deferred" and not str(row.get("remaining_work") or row.get("follow_up") or "").strip():
            errors.append(
                f"audit_plan_vs_runtime[{i}]_deferred_without_follow_up"
            )

    if "findings" not in doc or not isinstance(doc.get("findings"), list):
        errors.append("audit_findings_missing")

    if "converged" not in doc or not isinstance(doc.get("converged"), bool):
        errors.append("audit_converged_missing")

    parity = doc.get("architecture_parity")
    if "architecture_parity" not in doc or not isinstance(parity, list):
        errors.append("audit_architecture_parity_missing")
        parity = []
    for i, row in enumerate(parity):
        if not isinstance(row, dict):
            continue
        ev = str(row.get("evidence") or "").strip()
        st = str(row.get("status") or "").strip().lower()
        if st in {"present", "satisfied"} and _PRESENCE_ONLY_RE.search(ev):
            errors.append(
                f"audit_architecture_parity[{i}]_presence_only:"
                "status present FORBIDDEN on «файл на диске» without behavior"
            )

    sunset = doc.get("sunset_inventory_scan")
    if not isinstance(sunset, dict):
        errors.append(
            "audit_sunset_inventory_scan_missing:"
            "brownfield scan block required (or plan_ref: n/a with empty rows)"
        )

    cwd_p = Path(cwd)
    role_norm = _norm_role(role_dir)
    implemented = doc.get("implemented")
    if isinstance(implemented, list):
        from harness.hooks.epic_yaml import resolve_implement_path

        for i, row in enumerate(implemented):
            if not isinstance(row, dict):
                continue
            step_id = str(row.get("step_id") or "").strip()
            impl_file = str(row.get("implement_file") or "").strip()
            if not impl_file:
                errors.append(f"audit_implemented[{i}]_implement_file_missing")
                continue
            impl_path = cwd_p / impl_file
            if not impl_path.is_file():
                errors.append(
                    f"audit_implemented[{i}]_implement_file_missing_on_disk:"
                    f"{impl_file}"
                )
                continue
            if "/plan/" in impl_file.replace("\\", "/") and impl_file.endswith(".md"):
                errors.append(
                    f"audit_implemented[{i}]_plan_md_not_implement:"
                    f"{impl_file}"
                )
            if step_id:
                resolved = resolve_implement_path(
                    cwd_p, role_norm, epic_id, step_id
                )
                resolved_p = cwd_p / resolved
                if resolved_p.is_file() and impl_path.resolve() != resolved_p.resolve():
                    errors.append(
                        f"audit_implemented[{i}]_not_implement_shard:"
                        f"got {impl_file}; expected {resolved}"
                    )

    completed_ids = _completed_step_ids(cwd_p, role_norm, epic_id)
    if completed_ids:
        covered_steps: set[str] = set()
        if isinstance(implemented, list):
            for row in implemented:
                if isinstance(row, dict):
                    sid = str(row.get("step_id") or "").strip().lower()
                    if sid:
                        covered_steps.add(sid)
        matrix = doc.get("step_matrix")
        if isinstance(matrix, list):
            for row in matrix:
                if isinstance(row, dict):
                    sid = str(row.get("step_id") or "").strip().lower()
                    if sid:
                        covered_steps.add(sid)
        missing_steps = [sid for sid in completed_ids if sid not in covered_steps]
        if missing_steps:
            preview = ", ".join(missing_steps[:12])
            errors.append(
                "audit_completed_steps_uncovered:"
                f"implemented[]/step_matrix must cover completed sNN: {preview}"
            )

    plan_path = find_plan_md_path(cwd, role_norm, epic_id)
    if plan_path is None or not plan_path.is_file():
        errors.append(
            f"audit_plan_missing:no plan.md for epic {epic_id!r} "
            "(AUDIT must inventory intent from plan)"
        )
    else:
        from harness.hooks.epic.audit_contract import validate_contract
        errors.extend(validate_contract(doc, cwd_p, plan_path))
        plan_ids = extract_plan_intent_ids(plan_path)
        if not plan_ids:
            errors.append(
                "audit_plan_ids_empty:"
                f"no FR/SC/US found in {plan_path.as_posix()}"
            )
        else:
            uncovered = [rid for rid in plan_ids if rid not in covered_refs]
            if uncovered:
                preview = ", ".join(uncovered[:12])
                more = f" (+{len(uncovered) - 12})" if len(uncovered) > 12 else ""
                errors.append(
                    "audit_plan_fr_uncovered:"
                    f"plan_vs_runtime must cover every plan id; missing: {preview}{more}"
                )
            if isinstance(checked, dict):
                fr_total = checked.get("fr_total")
                fr_plan = sum(1 for r in plan_ids if r.startswith("FR-"))
                if isinstance(fr_total, int) and fr_plan and fr_total < fr_plan:
                    errors.append(
                        "audit_intent_checked_fr_total_low:"
                        f"intent_checked.fr_total={fr_total} < plan FR count={fr_plan}"
                    )

    if doc.get("converged") is True:
        findings = doc.get("findings") if isinstance(doc.get("findings"), list) else []
        for f in findings:
            if not isinstance(f, dict):
                continue
            gap = str(f.get("gap_type") or "").strip().lower()
            if gap in _ACTIONABLE_GAPS:
                errors.append(
                    "audit_converged_with_actionable_findings:"
                    f"gap_type={gap} id={f.get('id')}"
                )
        for i, row in enumerate(pvr):
            if not isinstance(row, dict):
                continue
            status = str(row.get("status") or "").strip().lower()
            if status in {"missing", "partial"}:
                errors.append(
                    f"audit_converged_with_open_plan_vs_runtime[{i}]:status={status}"
                )

    return errors
