"""Detector for stale index status where index.md status differs from index.yaml."""

from __future__ import annotations

from pathlib import Path
import sys

_HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from epic_index import index_yaml_path, load_index_yaml, parse_steps_from_md
from loop.janitor.schema import JanitorFinding


def detect_stale_index_status(cwd: Path) -> list[JanitorFinding]:
    """Compare step statuses in index.yaml vs index.md across memory-bank."""
    findings: list[JanitorFinding] = []
    mb = cwd / "memory-bank"
    if not mb.is_dir():
        return findings

    for index_yaml_file in mb.glob("**/index.yaml"):
        index_md_file = index_yaml_file.with_name("index.md")
        if not index_md_file.is_file():
            continue

        try:
            yaml_data = load_index_yaml(index_yaml_file)
            md_text = index_md_file.read_text(encoding="utf-8")
            md_steps = parse_steps_from_md(md_text)
        except Exception:
            continue

        yaml_steps_map = {
            s.get("id"): s.get("status")
            for s in yaml_data.get("steps", [])
            if isinstance(s, dict) and "id" in s
        }

        for md_step in md_steps:
            sid = md_step.get("id")
            md_st = md_step.get("status")
            yaml_st = yaml_steps_map.get(sid)

            if yaml_st and md_st != yaml_st:
                rel_path = index_md_file.relative_to(cwd)
                findings.append(
                    JanitorFinding(
                        category="stale_index_status",
                        description=f"Step '{sid}' status mismatch: index.md has '{md_st}' while index.yaml has '{yaml_st}'",
                        target_path=str(rel_path),
                        actionable=True,
                        metadata={
                            "step_id": sid,
                            "md_status": md_st,
                            "yaml_status": yaml_st,
                            "index_md": str(rel_path),
                        },
                    )
                )

    return findings
