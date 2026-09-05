"""Pre-IMPLEMENT ANALYZE gate — shared by roadmap_queue and board scan."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import yaml

COMPLETED_STATUSES = frozenset({"completed", "done"})
_STEP_REF_RE = re.compile(r"^[sera]\d{2}$")


def _load_yaml(path: Path) -> dict[str, Any] | None:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return None
    return payload if isinstance(payload, dict) else None


def index_content_fingerprint(index_path: Path) -> str | None:
    try:
        digest = hashlib.sha256(index_path.read_bytes()).hexdigest()
    except OSError:
        return None
    return f"sha256:{digest}"


def canon_index_yaml_path(index_path: Path | None) -> Path | None:
    """Fingerprint/mtime SoT is index.yaml when present (md is mirror only)."""
    if index_path is None:
        return None
    path = Path(index_path)
    if path.is_dir():
        yaml_v2 = path / "yaml" / "decompose-index.yaml"
        if yaml_v2.is_file():
            return yaml_v2
        yaml = path / "index.yaml"
        return yaml if yaml.is_file() else path
    if path.name == "decompose-index.md" and path.parent.name == "md":
        yaml_v2 = path.parent.parent / "yaml" / "decompose-index.yaml"
        if yaml_v2.is_file():
            return yaml_v2
    if path.name in {"index.md", "index.yml"}:
        yaml = path.with_name("index.yaml")
        if yaml.is_file():
            return yaml
    return path


def latest_analyze_paths(project: Path, role: str, epic_id: str) -> list[Path]:
    import sys

    hooks = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
    if str(hooks) not in sys.path:
        sys.path.insert(0, str(hooks))
    from epic_paths import epic_lookup_ids

    paths: list[Path] = []
    seen: set[Path] = set()
    for lookup_id in epic_lookup_ids(epic_id):
        directories = [
            project / "memory-bank" / role / "analyze" / lookup_id,
        ]
        if lookup_id == epic_id:
            directories.append(project / "memory-bank" / role / "analyze")
        for directory in directories:
            if not directory.is_dir():
                continue
            for path in directory.glob("analyze-*.yaml"):
                if path not in seen:
                    seen.add(path)
                    paths.append(path)
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


def _step_refs_from_analyze(payload: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for finding in payload.get("findings") or []:
        if not isinstance(finding, dict):
            continue
        ref = str(finding.get("step_ref") or "").strip()
        if not ref or ref.lower() == "n/a":
            continue
        for part in ref.split(","):
            token = part.strip().lower()
            if _STEP_REF_RE.match(token):
                refs.add(token)
    for cov in payload.get("coverage") or []:
        if not isinstance(cov, dict):
            continue
        for sid in cov.get("step_ids") or []:
            token = str(sid).strip().lower()
            if _STEP_REF_RE.match(token):
                refs.add(token)
    return refs


def analyze_index_structurally_aligned(
    payload: dict[str, Any], steps: list[dict[str, Any]]
) -> bool:
    step_ids = {
        str(step.get("id") or "").strip().lower()
        for step in steps
        if isinstance(step, dict)
    }
    refs = _step_refs_from_analyze(payload)
    if not refs:
        return True
    return refs <= step_ids


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

    if analyze_path and analyze_path.is_file() and index_path is not None:
        fp_path = canon_index_yaml_path(Path(index_path))
        if fp_path is not None and fp_path.is_file():
            stored_fp = str(payload.get("index_fingerprint") or "").strip()
            current_fp = index_content_fingerprint(fp_path)
            if stored_fp and current_fp and stored_fp != current_fp:
                return {
                    "required": True,
                    "reason": "analyze_stale",
                    "analyze_path": analyze_path.as_posix(),
                }

            status = str(payload.get("status") or "").strip().lower()
            if status and status not in {"complete", "completed", "done"}:
                return {
                    "required": True,
                    "reason": "analyze_incomplete",
                    "analyze_path": analyze_path.as_posix(),
                }

            if not analyze_index_structurally_aligned(payload, steps):
                return {
                    "required": True,
                    "reason": "analyze_stale",
                    "analyze_path": analyze_path.as_posix(),
                }

            if (
                not stored_fp
                and fp_path.stat().st_mtime > analyze_path.stat().st_mtime
                and status not in {"complete", "completed", "done"}
            ):
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
