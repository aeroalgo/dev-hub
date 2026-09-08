"""Runtime-neutral structural gate for decompose-backed phase transitions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable


def missing_decompose_shards(
    index_path: str | Path,
    steps: Iterable[dict[str, Any]],
) -> list[str]:
    """Return index entries whose referenced decompose shard is absent.

    Layout v2 stores shards under ``yaml/steps`` while legacy indexes store
    them beside the index.  The index reference is authoritative in both
    layouts; status or an analyze artifact cannot substitute for the file.
    """
    index = Path(index_path)
    parent = index.parent
    steps_dir = parent / "steps"
    missing: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        step_id = str(step.get("id") or step.get("step_id") or "?").strip()
        href = str(step.get("file") or "").strip()
        if not href:
            # Legacy indexes may carry only queue/status fields.  Their
            # compatibility path has no shard reference to resolve here;
            # v2 indexes are checked by validate-decompose-tree at FINISH.
            continue

        filename = Path(href).name
        candidates = [steps_dir / filename, parent / filename, parent / href]
        if not any(candidate.is_file() for candidate in candidates):
            missing.append(f"{step_id}: {href}")
    return missing


def decompose_shards_diagnostic(
    index_path: str | Path,
    steps: Iterable[dict[str, Any]],
) -> str | None:
    """Render a bounded diagnostic for the structural decompose gate."""
    missing = missing_decompose_shards(index_path, steps)
    if not missing:
        return None
    return "missing decompose shards: " + ", ".join(missing[:20])
