"""Pre-IMPLEMENT ANALYZE gate — shared by roadmap_queue and board scan."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

COMPLETED_STATUSES = frozenset({"completed", "done"})


def _load_yaml(path: Path) -> dict[str, Any] | None:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return None
    return payload if isinstance(payload, dict) else None


def latest_analyze_paths(project: Path, role: str, epic_id: str) -> list[Path]:
    directories = [
        project / "memory-bank" / role / "analyze" / epic_id,
        project / "memory-bank" / role / "analyze",
    ]
    paths: list[Path] = []
    for directory in directories:
        if not directory.is_dir():
            continue
        paths.extend(directory.glob("analyze-*.yaml"))
    return sorted(paths, reverse=True)


def latest_analyze(project: Path, role: str, epic_id: str) -> dict[str, Any] | None:
    for path in latest_analyze_paths(project, role, epic_id):
        payload = _load_yaml(path)
        if payload:
            return payload
    return None


def latest_analyze_with_path(
    project: Path, role: str, epic_id: str
) -> tuple[Path | None, dict[str, Any] | None]:
    for path in latest_analyze_paths(project, role, epic_id):
        payload = _load_yaml(path)
        if payload:
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


def any_completed_step(steps: list[dict[str, Any]]) -> bool:
    return any(
        isinstance(step, dict) and step.get("status") in COMPLETED_STATUSES
        for step in steps
    )


def analyze_required_before_implement(
    root: Path,
    role: str,
    epic_id: str,
    steps: list[dict[str, Any]],
    *,
    index_path: Path | None = None,
) -> dict[str, Any]:
    """True when decompose exists, zero completed sNN, analyze missing/stale/failing."""
    if any_completed_step(steps):
        return {"required": False, "reason": "implement_in_progress"}

    analyze_path, payload = latest_analyze_with_path(root, role, epic_id)
    if payload is None:
        return {"required": True, "reason": "analyze_missing", "analyze_path": None}

    crit = critical_count(payload)
    if crit > 0:
        return {
            "required": True,
            "reason": "critical_findings",
            "critical_count": crit,
            "analyze_path": analyze_path.as_posix() if analyze_path else None,
        }

    if (
        index_path
        and analyze_path
        and index_path.is_file()
        and analyze_path.is_file()
    ):
        if index_path.stat().st_mtime > analyze_path.stat().st_mtime:
            return {
                "required": True,
                "reason": "analyze_stale",
                "analyze_path": analyze_path.as_posix(),
            }

    return {
        "required": False,
        "reason": "analyze_pass",
        "analyze_path": analyze_path.as_posix() if analyze_path else None,
    }
