"""Detector for dead plan_refs pointing to non-existent files or plan files."""

from __future__ import annotations

from pathlib import Path
import sys
import yaml

_HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from epic.traceability import parse_plan_requirements
from loop.janitor.schema import JanitorFinding


def detect_dead_plan_ref(cwd: Path) -> list[JanitorFinding]:
    """Check plan_refs in decompose shard files to verify referenced plan files or reqs exist."""
    findings: list[JanitorFinding] = []
    mb = cwd / "memory-bank"
    if not mb.is_dir():
        return findings

    for shard_file in mb.glob("**/decompose-*/*s[0-9][0-9]*.yaml"):
        if shard_file.name == "index.yaml":
            continue

        try:
            data = yaml.safe_load(shard_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        if not isinstance(data, dict):
            continue

        plan_refs = data.get("plan_refs", [])
        if not isinstance(plan_refs, list):
            continue

        plan_id = data.get("plan_id")
        role = data.get("role") or "back"
        plan_file = mb / role / "plan" / f"plan-{plan_id}.md"

        # Check if plan_refs contain explicit file references or check plan file
        for ref in plan_refs:
            if not isinstance(ref, str):
                continue
            # If ref mentions a file path (.md, .py, etc.) check existence
            parts = ref.split()
            for part in parts:
                cleaned = part.strip("`'\",:()")
                if (cleaned.startswith("memory-bank/") or cleaned.startswith("loop/") or cleaned.startswith(".claude/")) and ("/" in cleaned):
                    target = cwd / cleaned
                    if not target.exists():
                        rel_shard = shard_file.relative_to(cwd)
                        findings.append(
                            JanitorFinding(
                                category="dead_plan_ref",
                                description=f"Shard '{shard_file.name}' plan_ref targets non-existent path '{cleaned}'",
                                target_path=str(rel_shard),
                                actionable=True,
                                metadata={
                                    "shard": str(rel_shard),
                                    "ref": ref,
                                    "missing_path": cleaned,
                                },
                            )
                        )

        if plan_id and not plan_file.is_file():
            rel_shard = shard_file.relative_to(cwd)
            findings.append(
                JanitorFinding(
                    category="dead_plan_ref",
                    description=f"Shard '{shard_file.name}' references plan_id '{plan_id}' but '{plan_file}' does not exist",
                    target_path=str(rel_shard),
                    actionable=True,
                    metadata={
                        "shard": str(rel_shard),
                        "plan_id": plan_id,
                        "missing_plan": str(plan_file.relative_to(cwd) if plan_file.is_relative_to(cwd) else plan_file),
                    },
                )
            )

    return findings
