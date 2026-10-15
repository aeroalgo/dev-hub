from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .index import Queue, Step, normalize_role


def needs_creative_open(value: object) -> bool:
    """Open gate: starts with yes and has neither closed nor ✅."""
    text = str(value or "").strip().lower()
    return text.startswith("yes") and "closed" not in text and "✅" not in text


def effective_runner_phase(*, role: object, next_phase: object, needs_creative: object) -> str:
    """Map step next_phase + needs_creative to a kernel runner phase.

    Port of harness.hooks.epic.core.effective_phase, without role prefix:
    kernel cursor.phase is CREATIVE / IMPLEMENT, not "FRONT CREATIVE".
    """
    role_name = str(role or "").upper() or "BACK"
    if needs_creative_open(needs_creative):
        return "CREATIVE"
    phase = str(next_phase or f"{role_name} IMPLEMENT")
    if (
        needs_creative is not None
        and str(needs_creative).strip()
        and re.search(r"\bCREATIVE\b", phase.upper())
    ):
        return "IMPLEMENT"
    if re.search(r"\bCREATIVE\b", phase.upper()):
        return "CREATIVE"
    return "IMPLEMENT"


def step_shard_path(project: Path, queue: Queue, step: Step) -> Path | None:
    if not step.shard:
        return None
    raw = Path(str(step.shard))
    candidates = (
        queue.path.parent / "steps" / raw.name,
        queue.path.parent / raw,
        project / raw if not raw.is_absolute() else raw,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def load_step_needs_creative(project: Path, queue: Queue, step: Step) -> object:
    shard = step_shard_path(project, queue, step)
    if shard is None:
        return None
    try:
        doc = yaml.safe_load(shard.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError):
        return None
    return doc.get("needs_creative") if isinstance(doc, dict) else None


def load_step_next_phase(project: Path, queue: Queue, step: Step) -> object:
    shard = step_shard_path(project, queue, step)
    if shard is None:
        return None
    try:
        doc = yaml.safe_load(shard.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError):
        return None
    return doc.get("next_phase") if isinstance(doc, dict) else None


def creative_artifact_paths(project: Path, role: str, epic_id: str) -> list[Path]:
    role_dir = normalize_role(role)
    root = project / "memory-bank" / role_dir / "creative"
    if not root.is_dir():
        return []
    scoped = root / epic_id
    hits: list[Path] = []
    if scoped.is_dir():
        hits.extend(sorted(scoped.glob("creative-*.md")))
    task_token = epic_id.split("-", 1)[0] if epic_id else ""
    for path in sorted(root.glob("creative-*.md")):
        name = path.name
        if epic_id and epic_id in name:
            hits.append(path)
            continue
        if task_token and task_token in name:
            hits.append(path)
            continue
        try:
            head = path.read_text(encoding="utf-8", errors="replace")[:800]
        except OSError:
            continue
        if epic_id and epic_id in head:
            hits.append(path)
        elif task_token and task_token in head:
            hits.append(path)
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in hits:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def creative_finish_ready(
    project: Path,
    queue: Queue,
    step: Step,
) -> tuple[bool, str]:
    """CREATIVE finish requires artifact + closed needs_creative on the same step."""
    needs = load_step_needs_creative(project, queue, step)
    if needs_creative_open(needs):
        return False, "creative_gate_still_open"
    if needs is None or not str(needs).strip():
        next_phase = load_step_next_phase(project, queue, step)
        if next_phase and re.search(r"\bCREATIVE\b", str(next_phase).upper()):
            return False, "creative_gate_still_open"
    arts = creative_artifact_paths(project, queue.role, queue.epic_id)
    if not arts:
        return False, "creative_artifact_missing"
    return True, "creative_ready"


def resolve_creative_step(project: Path, queue: Queue) -> Step | None:
    for step in queue.pending:
        needs = load_step_needs_creative(project, queue, step)
        next_phase = load_step_next_phase(project, queue, step)
        phase = effective_runner_phase(
            role=queue.role,
            next_phase=next_phase,
            needs_creative=needs,
        )
        if phase == "CREATIVE":
            return step
    return None


def phase_for_pending_step(project: Path, queue: Queue, step: Step) -> tuple[str, str]:
    needs = load_step_needs_creative(project, queue, step)
    next_phase = load_step_next_phase(project, queue, step)
    phase = effective_runner_phase(
        role=queue.role,
        next_phase=next_phase,
        needs_creative=needs,
    )
    if phase == "CREATIVE":
        return "CREATIVE", f"open creative gate for {step.step_id}"
    return "IMPLEMENT", f"pending step {step.step_id}"
