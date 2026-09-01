"""Detector for duplicate epic/plan IDs across memory-bank."""

from __future__ import annotations

from pathlib import Path
import sys
import yaml

_HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from epic_index import index_yaml_path, load_index_yaml
from loop.janitor.schema import JanitorFinding


def detect_duplicate_epic_id(cwd: Path) -> list[JanitorFinding]:
    """Scan all plan files and decompose index files for duplicate epic/plan IDs."""
    findings: list[JanitorFinding] = []
    mb = cwd / "memory-bank"
    if not mb.is_dir():
        return findings

    seen_epics: dict[str, list[Path]] = {}

    for index_yaml_file in mb.glob("**/index.yaml"):
        try:
            data = load_index_yaml(index_yaml_file)
            epic_id = data.get("epic_id") or data.get("plan_id")
            if epic_id:
                seen_epics.setdefault(epic_id, []).append(index_yaml_file)
        except Exception:
            continue

    for epic_id, paths in seen_epics.items():
        if len(paths) > 1:
            for p in paths:
                rel_p = p.relative_to(cwd)
                other_paths = [str(o.relative_to(cwd)) for o in paths if o != p]
                findings.append(
                    JanitorFinding(
                        category="duplicate_epic_id",
                        description=f"Duplicate epic_id '{epic_id}' found in multiple index files: {other_paths}",
                        target_path=str(rel_p),
                        actionable=True,
                        metadata={
                            "epic_id": epic_id,
                            "conflicting_paths": [str(x.relative_to(cwd)) for x in paths],
                        },
                    )
                )

    return findings
