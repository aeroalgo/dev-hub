"""EpicNextAction resolver — single source of truth for epic next command.

Provides resolve_epic_next_action to evaluate an epic's state across plan, decompose,
analyze, clarify, and post-implement lifecycle phases.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

_LOOP = Path(__file__).resolve().parents[1]
if str(_LOOP) not in sys.path:
    sys.path.insert(0, str(_LOOP))

_HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))

from epic import reduce_epic_lifecycle
from analyze_gate import critical_count as _critical_count
from analyze_gate import latest_analyze as _latest_analyze

from .plan_next import parse_plan_next, validate_plan_next

_COMPLETED_STATUSES = frozenset({"completed", "done"})
_POST_PHASES = frozenset({"AUDIT", "QA", "BUGFIX"})


@dataclass(frozen=True, slots=True)
class EpicNextAction:
    """Next action for an epic determined by project state or plan-next override."""

    epic_id: str
    role: str
    next_command: str
    phase: str
    next_step_id: str | None = None
    plan_rel: str | None = None
    decompose_rel: str | None = None
    reason_code: str | None = None
    diagnostic: str | None = None


def resolve_epic_next_action(
    project: Path | str,
    role: str,
    epic_id: str,
    *,
    require_plan: bool = True,
) -> EpicNextAction:
    """Resolve the next command and phase for an epic.

    Checks override block (plan-next/v1) first. If absent or valid, evaluates:
      1. Plan exists? No (and require_plan) -> PLAN
      2. Decompose exists? No -> DECOMPOSE
      3. Pre-implement matrix:
         - Analyze needed? -> ANALYZE
         - Clarify needed? -> CLARIFY
         - Pending steps? -> IMPLEMENT (next_step_id)
      4. Post-implement lifecycle -> AUDIT / QA / BUGFIX / DONE
    """
    project_path = Path(project).resolve()
    plan = _plan_path(project_path, role, epic_id)
    canonical_id = _epic_id_from_plan_path(plan) or epic_id
    decompose = _find_decompose(project_path, role, canonical_id)

    plan_rel = _relative(plan, project_path)
    decompose_rel = _relative(decompose, project_path)

    payload = _load_decompose(decompose) if decompose else {}
    steps = payload.get("steps", []) if isinstance(payload, dict) else []
    first_pending = next(
        (s for s in steps if isinstance(s, dict) and s.get("status") not in _COMPLETED_STATUSES),
        None,
    ) if decompose else None

    artifacts = {
        "plan_exists": plan is not None,
        "decompose_exists": decompose is not None,
        "pending_steps": first_pending is not None,
        "has_pending_steps": first_pending is not None,
    }

    # Check override
    if plan is not None:
        override = parse_plan_next(plan)
        if override is not None:
            err = validate_plan_next(override, artifacts)
            if err:
                return EpicNextAction(
                    epic_id=canonical_id,
                    role=role,
                    next_command=override.next_command,
                    phase=_phase_from_command(override.next_command),
                    plan_rel=plan_rel,
                    decompose_rel=decompose_rel,
                    reason_code="override_conflict",
                    diagnostic=err,
                )
            # Valid override
            phase = _phase_from_command(override.next_command)
            return EpicNextAction(
                epic_id=canonical_id,
                role=role,
                next_command=override.next_command,
                phase=phase,
                plan_rel=plan_rel,
                decompose_rel=decompose_rel,
                reason_code="override_valid",
            )

    # 1. Plan check
    if plan is None and require_plan:
        cmd = f"{role.upper()} PLAN {canonical_id}"
        return EpicNextAction(
            epic_id=canonical_id,
            role=role,
            next_command=cmd,
            phase="PLAN",
            plan_rel=None,
            decompose_rel=None,
            reason_code="plan_missing",
        )

    # 2. Decompose check
    if decompose is None:
        cmd = f"{role.upper()} DECOMPOSE {canonical_id}"
        return EpicNextAction(
            epic_id=canonical_id,
            role=role,
            next_command=cmd,
            phase="DECOMPOSE",
            plan_rel=plan_rel,
            decompose_rel=None,
            reason_code="decompose_missing",
        )

    # 3. Pre-implement matrix
    statuses = [s.get("status") for s in steps if isinstance(s, dict)]
    has_completed = any(st in _COMPLETED_STATUSES for st in statuses)

    if not has_completed and plan is not None:
        analyze = _latest_analyze(project_path, role, canonical_id)
        if analyze is None:
            cmd = f"{role.upper()} ANALYZE {canonical_id}"
            return EpicNextAction(
                epic_id=canonical_id,
                role=role,
                next_command=cmd,
                phase="ANALYZE",
                plan_rel=plan_rel,
                decompose_rel=decompose_rel,
                reason_code="stale_analyze_pending",
            )
        if _critical_count(analyze) > 0:
            cmd = f"{role.upper()} ANALYZE {canonical_id}"
            return EpicNextAction(
                epic_id=canonical_id,
                role=role,
                next_command=cmd,
                phase="ANALYZE",
                plan_rel=plan_rel,
                decompose_rel=decompose_rel,
                reason_code="analyze_required",
            )

    if _has_unresolved_critical(plan, project_path, role, canonical_id):
        cmd = f"{role.upper()} CLARIFY {canonical_id}"
        return EpicNextAction(
            epic_id=canonical_id,
            role=role,
            next_command=cmd,
            phase="CLARIFY",
            plan_rel=plan_rel,
            decompose_rel=decompose_rel,
            reason_code="clarify_required",
        )

    # Check pending steps in decompose
    if first_pending:
        step_id = str(first_pending.get("step_id", ""))
        cmd = f"{role.upper()} IMPLEMENT {step_id}"
        return EpicNextAction(
            epic_id=canonical_id,
            role=role,
            next_command=cmd,
            phase="IMPLEMENT",
            next_step_id=step_id,
            plan_rel=plan_rel,
            decompose_rel=decompose_rel,
            reason_code="implement_pending",
        )

    # 4. Post-implement lifecycle
    return _resolve_post_implement(project_path, role, canonical_id, plan_rel, decompose_rel)


def _resolve_post_implement(
    project: Path,
    role: str,
    epic_id: str,
    plan_rel: str | None,
    decompose_rel: str | None,
) -> EpicNextAction:
    lifecycle = reduce_epic_lifecycle(project, role, epic_id)
    phase = str(lifecycle.get("phase", "")).upper()
    reason_code = str(lifecycle.get("reason_code", ""))

    if phase == "DONE":
        cmd = f"{role.upper()} DONE {epic_id}"
        return EpicNextAction(
            epic_id=epic_id,
            role=role,
            next_command=cmd,
            phase="DONE",
            plan_rel=plan_rel,
            decompose_rel=decompose_rel,
            reason_code="epic_done",
        )

    gate_phase = "BUGFIX" if reason_code == "qa_failed" else phase
    cmd = f"{role.upper()} {gate_phase} {epic_id}"
    return EpicNextAction(
        epic_id=epic_id,
        role=role,
        next_command=cmd,
        phase=gate_phase,
        plan_rel=plan_rel,
        decompose_rel=decompose_rel,
        reason_code=reason_code,
    )


def _epic_done(project: Path | str, role: str, epic_id: str) -> bool:
    """Return True if epic post-implement lifecycle is complete (no pending post-impl gates)."""
    lifecycle = reduce_epic_lifecycle(Path(project), role, epic_id)
    phase = str(lifecycle.get("phase", "")).upper()
    return phase == "DONE"


def _phase_from_command(command: str) -> str:
    parts = command.strip().split()
    if len(parts) >= 2:
        return parts[1].upper()
    return parts[0].upper()


def _plan_path(project: Path, role: str, epic_id: str) -> Path | None:
    plan_dir = project / "memory-bank" / role / "plan"
    candidates = [plan_dir / f"plan-{epic_id}.md"]
    candidates.extend(sorted(plan_dir.glob(f"plan-{epic_id}-*.md")))
    return next((path for path in candidates if path.is_file()), None)


def _epic_id_from_plan_path(plan: Path | None) -> str | None:
    if plan is None or not plan.is_file():
        return None
    stem = plan.stem
    if stem.startswith("plan-"):
        return stem[len("plan-") :]
    return stem or None


def _find_decompose(project: Path, role: str, epic_id: str) -> Path | None:
    import sys
    from pathlib import Path as _Path

    hooks = _Path(__file__).resolve().parents[2] / ".claude" / "hooks"
    if str(hooks) not in sys.path:
        sys.path.insert(0, str(hooks))
    from epic_paths import find_decompose_index_path

    return find_decompose_index_path(project, role, epic_id)


def _relative(path: Path | None, root: Path) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _load_decompose(path: Path) -> dict:
    if path.suffix == ".md":
        from epic_index import parse_steps_from_md
        try:
            steps = parse_steps_from_md(path.read_text(encoding="utf-8"))
            return {"steps": steps}
        except (OSError, UnicodeError):
            return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, UnicodeError, yaml.YAMLError):
        return {}


def _has_unresolved_critical(
    plan: Path | None,
    project: Path,
    role: str,
    epic_id: str,
) -> bool:
    if plan is None:
        return False
    try:
        text = plan.read_text(encoding="utf-8")
    except OSError:
        return False
    lines = [line.strip() for line in text.splitlines()]
    if any(line.startswith("- [ ] CRITICAL:") or line.startswith("* [ ] CRITICAL:") for line in lines):
        return True

    clarify_dir = project / "memory-bank" / role / "plan" / f"clarify-{epic_id}"
    if not clarify_dir.is_dir():
        return False
    results = sorted(clarify_dir.glob("clarify-*.yaml"))
    if not results:
        return False
    try:
        payload = yaml.safe_load(results[-1].read_text(encoding="utf-8"))
        if isinstance(payload, dict) and payload.get("status") == "resolved":
            return False
    except (OSError, UnicodeError, yaml.YAMLError):
        pass
    return True
