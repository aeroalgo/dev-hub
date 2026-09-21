from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Iterable

import yaml

from .index import index_path as canonical_index_path, normalize_role


_COMPLETED_STATUSES = frozenset({"completed", "done"})
_STEP_REF_RE = re.compile(r"^[sera]\d{2}$", re.IGNORECASE)


def _load_yaml(path: Path) -> dict[str, Any] | None:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return None
    return payload if isinstance(payload, dict) else None


def index_content_fingerprint(path: Path) -> str | None:
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None
    return f"sha256:{digest}"


def latest_analyze_paths(project: Path, role: str, epic_id: str) -> list[Path]:
    root = project / "memory-bank" / normalize_role(role) / "analyze" / epic_id
    return sorted(root.glob("analyze-*.yaml"), reverse=True) if root.is_dir() else []


def latest_analyze_with_path(project: Path, role: str, epic_id: str) -> tuple[Path | None, dict[str, Any] | None]:
    for path in latest_analyze_paths(project, role, epic_id):
        payload = _load_yaml(path)
        if payload is not None:
            return path, payload
    return None, None


def critical_count(payload: dict[str, Any]) -> int:
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        return 0
    try:
        return int(metrics.get("critical_count", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _valid_critical_count(payload: dict[str, Any]) -> tuple[bool, int]:
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict) or "critical_count" not in metrics:
        return False, 0
    value = metrics.get("critical_count")
    if isinstance(value, bool):
        return False, 0
    try:
        return True, int(value)
    except (TypeError, ValueError):
        return False, 0


def _step_refs(payload: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for finding in payload.get("findings") or []:
        if not isinstance(finding, dict):
            continue
        value = str(finding.get("step_ref") or "").strip()
        for token in value.split(","):
            token = token.strip().lower()
            if _STEP_REF_RE.fullmatch(token):
                refs.add(token)
    for coverage in payload.get("coverage") or []:
        if not isinstance(coverage, dict):
            continue
        for step_id in coverage.get("step_ids") or []:
            token = str(step_id).strip().lower()
            if _STEP_REF_RE.fullmatch(token):
                refs.add(token)
    return refs


def analyze_index_structurally_aligned(payload: dict[str, Any], steps: Iterable[dict[str, Any]]) -> bool:
    step_ids = {
        str(step.get("id") or step.get("step_id") or "").strip().lower()
        for step in steps
        if isinstance(step, dict)
    }
    return _step_refs(payload) <= step_ids


def analyze_required_before_implement(
    project: Path,
    role: str,
    epic_id: str,
    steps: Iterable[dict[str, Any]],
    *,
    index_path_override: Path | None = None,
    index_path: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    step_rows = [step for step in steps if isinstance(step, dict)]
    if not force and any(str(step.get("status") or "").strip().lower() in _COMPLETED_STATUSES for step in step_rows):
        return {"required": False, "reason": "implement_in_progress"}

    analyze_path, payload = latest_analyze_with_path(project, role, epic_id)
    if payload is None:
        return {"required": True, "reason": "analyze_missing", "analyze_path": None}
    if payload.get("schema") != "epic-analyze/v1":
        return {
            "required": True,
            "reason": "analyze_schema_invalid",
            "analyze_path": str(analyze_path) if analyze_path else None,
        }

    metrics_valid, count = _valid_critical_count(payload)
    if not metrics_valid:
        return {
            "required": True,
            "reason": "analyze_invalid_metrics",
            "analyze_path": str(analyze_path) if analyze_path else None,
        }
    if count > 0:
        return {
            "required": True,
            "reason": "critical_findings",
            "critical_count": count,
            "analyze_path": str(analyze_path) if analyze_path else None,
        }

    canonical_index = index_path_override or index_path or canonical_index_path(project, role, epic_id)
    stored_fingerprint = str(payload.get("index_fingerprint") or "").strip()
    current_fingerprint = index_content_fingerprint(canonical_index)
    if stored_fingerprint and current_fingerprint and stored_fingerprint != current_fingerprint:
        return {
            "required": True,
            "reason": "analyze_stale",
            "analyze_path": str(analyze_path) if analyze_path else None,
        }

    status = str(payload.get("status") or "").strip().lower()
    if status and status not in {"complete", "completed", "done"}:
        return {
            "required": True,
            "reason": "analyze_incomplete",
            "analyze_path": str(analyze_path) if analyze_path else None,
        }

    if not analyze_index_structurally_aligned(payload, step_rows):
        return {
            "required": True,
            "reason": "analyze_stale",
            "analyze_path": str(analyze_path) if analyze_path else None,
        }

    return {
        "required": False,
        "reason": "analyze_pass",
        "analyze_path": str(analyze_path) if analyze_path else None,
        "critical_count": count,
    }


__all__ = [
    "analyze_index_structurally_aligned",
    "analyze_required_before_implement",
    "critical_count",
    "index_content_fingerprint",
    "latest_analyze_paths",
    "latest_analyze_with_path",
]
