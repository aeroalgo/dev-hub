from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from .kernel.analyze import (
        analyze_index_structurally_aligned,
        analyze_required_before_implement,
        critical_count,
        index_content_fingerprint,
        latest_analyze_paths,
        latest_analyze_with_path,
    )
except ImportError:
    import sys

    root = str(Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)
    from loop.kernel.analyze import (
        analyze_index_structurally_aligned,
        analyze_required_before_implement,
        critical_count,
        index_content_fingerprint,
        latest_analyze_paths,
        latest_analyze_with_path,
    )


def canon_index_yaml_path(index_path: Path | None) -> Path | None:
    if index_path is None:
        return None
    path = Path(index_path)
    if path.is_dir():
        return path / "yaml" / "decompose-index.yaml"
    if path.suffix.lower() in {".md", ".markdown"}:
        return None
    return path if path.name in {"decompose-index.yaml", "decompose-index.yml"} else None


def any_completed_step(steps: list[dict[str, Any]]) -> bool:
    return any(
        isinstance(step, dict) and str(step.get("status") or "").lower() in {"completed", "done"}
        for step in steps
    )


def latest_analyze(project: Path, role: str, epic_id: str) -> dict[str, Any] | None:
    _, payload = latest_analyze_with_path(project, role, epic_id)
    return payload


__all__ = [
    "analyze_index_structurally_aligned",
    "analyze_required_before_implement",
    "any_completed_step",
    "canon_index_yaml_path",
    "critical_count",
    "index_content_fingerprint",
    "latest_analyze",
    "latest_analyze_paths",
    "latest_analyze_with_path",
]
