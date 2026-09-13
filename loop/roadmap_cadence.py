"""Roadmap cadence state machine and SoT storage (load/save/fail-closed)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from loop.schemas.roadmap_cadence import (
    CADENCE_PHASES,
    SCHEMA_ROADMAP_CADENCE,
    CadencePhase,
    ReplanEvidence,
    ReplanGap,
    ReplanOutcome,
    ReplanOutcomeRecord,
    ReplanSkipRecord,
    ResyncEvidence,
    RoadmapCadenceState,
)

if not hasattr(RoadmapCadenceState, "completed_feature_count"):
    RoadmapCadenceState.completed_feature_count = property(  # type: ignore[attr-defined]
        lambda self: self.counter,
        lambda self, v: setattr(self, "counter", v),
    )

HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
if str(HOOKS) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(HOOKS))

try:
    from epic import atomic_write_text
except ImportError:
    from harness.hooks.epic.core import atomic_write_text  # type: ignore[no-redef]

DEFAULT_CADENCE_REL = "memory-bank/back/roadmap/cadence.yaml"


def canon_cadence_path(cwd: str | Path | None = None) -> Path:
    """Return canonical absolute path to cadence.yaml."""
    return Path(cwd or ".").resolve() / DEFAULT_CADENCE_REL


def load_cadence(
    cwd: str | Path | None = None,
    path: str | Path | None = None,
) -> RoadmapCadenceState:
    """Load and validate roadmap cadence SoT. Fail-closed on missing, corrupt, or invalid state."""
    target = Path(path) if path is not None else canon_cadence_path(cwd)
    if not target.is_file():
        raise FileNotFoundError(f"cadence SoT file not found: {target}")
    raw_text = target.read_text(encoding="utf-8")
    try:
        parsed = yaml.safe_load(raw_text)
    except Exception as exc:
        raise ValueError(f"corrupt cadence YAML in {target}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise TypeError(
            f"corrupt cadence YAML in {target}: expected mapping, got {type(parsed).__name__}"
        )
    return RoadmapCadenceState.model_validate(parsed)


def save_cadence(
    state: RoadmapCadenceState | dict[str, Any],
    cwd: str | Path | None = None,
    path: str | Path | None = None,
) -> Path:
    """Validate and atomically save roadmap cadence state to YAML."""
    if isinstance(state, dict):
        model = RoadmapCadenceState.model_validate(state)
    elif isinstance(state, RoadmapCadenceState):
        model = state
    else:
        raise TypeError(
            f"expected RoadmapCadenceState or dict, got {type(state).__name__}"
        )
    target = Path(path) if path is not None else canon_cadence_path(cwd)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = model.model_dump(by_alias=True)
    body = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    atomic_write_text(target, body)
    return target


def _resolve_cwd_and_epic(
    arg1: str | Path | None,
    arg2: str | Path | None,
    cwd: str | Path | None,
    path: str | Path | None,
    epic_id: str | None,
) -> tuple[str | Path | None, str | Path | None, str | None]:
    resolved_cwd = cwd
    resolved_path = path
    resolved_epic_id = epic_id

    if arg1 is not None:
        if isinstance(arg1, Path):
            resolved_cwd = arg1
            if arg2 is not None:
                resolved_epic_id = str(arg2)
        elif arg2 is not None:
            if isinstance(arg2, Path) or (
                isinstance(arg2, str)
                and (Path(arg2).is_dir() or "/" in arg2 or "\\" in arg2)
            ):
                resolved_cwd = arg2
                resolved_epic_id = str(arg1)
            elif (
                "/" in str(arg1)
                or "\\" in str(arg1)
                or Path(str(arg1)).is_dir()
            ):
                resolved_cwd = arg1
                resolved_epic_id = str(arg2)
            else:
                resolved_epic_id = str(arg1)
                resolved_cwd = arg2
        else:
            if "/" in str(arg1) or "\\" in str(arg1) or (
                resolved_epic_id is not None and resolved_cwd is None
            ):
                resolved_cwd = arg1
            elif resolved_epic_id is None and not (
                isinstance(arg1, Path) or Path(str(arg1)).is_dir()
            ):
                resolved_epic_id = str(arg1)
            elif resolved_cwd is None:
                resolved_cwd = arg1

    return resolved_cwd, resolved_path, resolved_epic_id


def on_feature_done(
    arg1: str | Path | None = None,
    arg2: str | Path | None = None,
    *,
    epic_id: str | None = None,
    cwd: str | Path | None = None,
    path: str | Path | None = None,
) -> RoadmapCadenceState:
    """Record a completed feature and trigger the next cadence phase."""
    resolved_cwd, resolved_path, resolved_epic = _resolve_cwd_and_epic(
        arg1, arg2, cwd, path, epic_id
    )
    state = load_cadence(cwd=resolved_cwd, path=resolved_path)
    if state.phase != "idle":
        return state
    if resolved_epic and resolved_epic in state.pair_ids:
        return state
    if state.counter == 0:
        state.pair_ids = []
    state.counter += 1
    if resolved_epic:
        state.pair_ids.append(resolved_epic)
    if state.counter >= state.every_n:
        state.phase = "replan"
        state.pair_ids = state.pair_ids[-state.every_n :]
        state.replan_outcomes = {}
    save_cadence(state, cwd=resolved_cwd, path=resolved_path)
    return state


def on_non_feature_done(
    arg1: str | Path | None = None,
    arg2: str | Path | None = None,
    *,
    epic_id: str | None = None,
    cwd: str | Path | None = None,
    path: str | Path | None = None,
) -> RoadmapCadenceState:
    """Return cadence state unchanged for a non-feature completion."""
    resolved_cwd, resolved_path, _ = _resolve_cwd_and_epic(
        arg1, arg2, cwd, path, epic_id
    )
    return load_cadence(cwd=resolved_cwd, path=resolved_path)


def is_critical_gap(gap: Any) -> bool:
    """Check if a gap item represents a critical gap (not cosmetic)."""
    if isinstance(gap, dict):
        sev = str(gap.get("severity", "")).lower()
        if sev in ("critical", "high", "blocker"):
            return True
        if sev in ("cosmetic", "low", "minor", "trivial") or gap.get("cosmetic") is True:
            return False
        desc = str(gap.get("description", gap.get("text", gap.get("gap", "")))).lower()
        if "cosmetic" in desc or "trivial" in desc:
            return False
        return True
    elif isinstance(gap, ReplanGap):
        if gap.severity.lower() in ("critical", "high", "blocker"):
            return True
        if gap.severity.lower() in ("cosmetic", "low", "minor", "trivial") or "cosmetic" in gap.description.lower():
            return False
        return True
    elif isinstance(gap, str):
        gl = gap.lower()
        if "cosmetic" in gl or "trivial" in gl:
            return False
        return True
    elif hasattr(gap, "severity"):
        sev = str(getattr(gap, "severity", "")).lower()
        if sev in ("cosmetic", "low", "minor", "trivial"):
            return False
        return True
    return True


def filter_critical_gaps(gaps: list[Any]) -> list[Any]:
    """Filter a list of gaps to return only critical gaps (cosmetics omitted)."""
    if not gaps:
        return []
    return [g for g in gaps if is_critical_gap(g)]


def advance_replan(
    arg1: str | Path | None = None,
    arg2: str | Path | None = None,
    arg3: str | None = None,
    arg4: str | None = None,
    arg5: Any = None,
    *,
    epic_id: str | None = None,
    outcome: str | None = None,
    evidence: ReplanEvidence | dict[str, Any] | str | None = None,
    reason: str | None = None,
    cwd: str | Path | None = None,
    path: str | Path | None = None,
) -> RoadmapCadenceState:
    """Advance a single epic in the replan phase of the cadence block.

    Records the outcome (complete or skip) with structured evidence.
    Transitions phase to 'refactor' only once all pair_ids have been advanced.
    """
    resolved_cwd = cwd
    resolved_path = path
    resolved_epic = epic_id
    resolved_outcome = outcome
    resolved_evidence = evidence
    resolved_reason = reason

    if arg1 is not None and arg2 is not None and arg3 is not None and arg4 is not None:
        resolved_cwd = arg1
        resolved_path = arg2
        resolved_epic = str(arg3)
        resolved_outcome = str(arg4)
        if arg5 is not None:
            resolved_evidence = arg5
    elif arg1 is not None and arg2 is not None and arg3 is not None:
        if isinstance(arg1, Path) or (
            isinstance(arg1, str)
            and (Path(arg1).is_dir() or "/" in arg1 or "\\" in arg1 or arg1 == ".")
        ):
            resolved_cwd = arg1
            resolved_epic = str(arg2)
            resolved_outcome = str(arg3)
            if arg4 is not None:
                resolved_evidence = arg4
        else:
            resolved_epic = str(arg1)
            resolved_outcome = str(arg2)
            resolved_evidence = arg3
    elif arg1 is not None and arg2 is not None:
        if isinstance(arg1, Path) or (
            isinstance(arg1, str)
            and (Path(arg1).is_dir() or "/" in arg1 or "\\" in arg1 or arg1 == ".")
        ):
            resolved_cwd = arg1
            resolved_epic = str(arg2)
        else:
            resolved_epic = str(arg1)
            resolved_outcome = str(arg2)
    elif arg1 is not None:
        if isinstance(arg1, Path) or (
            isinstance(arg1, str)
            and (Path(arg1).is_dir() or "/" in arg1 or "\\" in arg1 or arg1 == ".")
        ):
            resolved_cwd = arg1
        else:
            resolved_epic = str(arg1)

    if cwd is not None:
        resolved_cwd = cwd
    if path is not None:
        resolved_path = path
    if epic_id is not None:
        resolved_epic = epic_id
    if outcome is not None:
        resolved_outcome = outcome
    if evidence is not None:
        resolved_evidence = evidence
    if reason is not None:
        resolved_reason = reason

    state = load_cadence(cwd=resolved_cwd, path=resolved_path)
    if state.phase != "replan":
        raise ValueError(
            f"cannot advance replan: current cadence phase is {state.phase!r}, expected 'replan'"
        )

    if not resolved_epic:
        raise ValueError("epic_id is required for advance_replan")

    if resolved_epic not in state.pair_ids:
        raise ValueError(
            f"epic {resolved_epic!r} not in cadence pair_ids: {state.pair_ids}"
        )

    if resolved_epic in state.replan_outcomes:
        existing = state.replan_outcomes[resolved_epic]
        raise ValueError(
            f"cannot advance replan: epic {resolved_epic!r} already has terminal replan outcome {existing.outcome!r}"
        )

    normalized_outcome = str(resolved_outcome or "").strip().lower()
    if normalized_outcome in ("completed", "done"):
        normalized_outcome = "complete"
    elif normalized_outcome in ("skipped",):
        normalized_outcome = "skip"

    if normalized_outcome not in ("complete", "skip"):
        raise ValueError(
            f"invalid replan outcome: {resolved_outcome!r}, expected 'complete' or 'skip'"
        )

    if isinstance(resolved_evidence, str):
        evidence_obj: ReplanEvidence | None = ReplanEvidence(
            reason=resolved_evidence, notes=resolved_evidence
        )
    elif isinstance(resolved_evidence, dict):
        evidence_obj = ReplanEvidence.model_validate(resolved_evidence)
    elif isinstance(resolved_evidence, ReplanEvidence):
        evidence_obj = resolved_evidence
    elif resolved_evidence is None:
        evidence_obj = None
    else:
        evidence_obj = ReplanEvidence(details={"raw": str(resolved_evidence)})

    if resolved_reason:
        if evidence_obj is None:
            evidence_obj = ReplanEvidence(reason=resolved_reason)
        elif not evidence_obj.reason:
            evidence_obj.reason = resolved_reason

    if normalized_outcome == "skip":
        has_reason = bool(
            resolved_reason
            or (evidence_obj and (evidence_obj.reason or evidence_obj.notes))
        )
        has_gaps = bool(
            evidence_obj
            and (
                evidence_obj.critical_gaps
                or evidence_obj.cosmetic_gaps
                or evidence_obj.gaps
                or evidence_obj.details
            )
        )
        if not has_reason and not has_gaps:
            raise ValueError(
                f"missing evidence for replan skip on epic {resolved_epic!r}: structured evidence or reason is required"
            )

    if normalized_outcome == "complete":
        if evidence_obj is not None:
            has_cosmetic_only = False
            if evidence_obj.cosmetic_gaps and not evidence_obj.critical_gaps:
                if not evidence_obj.gaps:
                    has_cosmetic_only = True
                else:
                    filtered = filter_critical_gaps(evidence_obj.gaps)
                    if not filtered:
                        has_cosmetic_only = True
            elif evidence_obj.gaps:
                filtered = filter_critical_gaps(evidence_obj.gaps)
                if not filtered and not evidence_obj.critical_gaps:
                    has_cosmetic_only = True

            if has_cosmetic_only:
                raise ValueError(
                    f"cannot mark replan complete for epic {resolved_epic!r}: only cosmetic gaps provided; "
                    "cosmetic gaps do not create replan work (critical-only filter)"
                )

    effective_reason = (
        resolved_reason
        or (evidence_obj.reason if evidence_obj else "")
        or ""
    )
    record = ReplanOutcomeRecord(
        epic_id=resolved_epic,
        outcome=normalized_outcome,  # type: ignore[arg-type]
        reason=effective_reason,
        evidence=evidence_obj,
    )
    state.replan_outcomes[resolved_epic] = record

    all_done = bool(state.pair_ids) and all(
        pid in state.replan_outcomes for pid in state.pair_ids
    )
    if all_done:
        state.phase = "refactor"

    save_cadence(state, cwd=resolved_cwd, path=resolved_path)
    return state




def start_refactor_phase(
    arg1: str | Path | None = None,
    arg2: Any = None,
    arg3: Any = None,
    *,
    epic_spec: dict[str, Any] | str | None = None,
    cwd: str | Path | None = None,
    path: str | Path | None = None,
    role: str | None = None,
    queue_rel: str | None = None,
) -> dict[str, Any]:
    """Start the refactor phase by inserting a refactor epic (kind: refactor) into queue.yaml.

    Fails closed if the current cadence phase is not 'refactor' (e.g. if still in 'replan' or 'idle').
    """
    resolved_cwd = cwd
    resolved_path = path
    resolved_epic_spec = epic_spec

    if arg1 is not None:
        if isinstance(arg1, Path) or (
            isinstance(arg1, str)
            and (Path(arg1).is_dir() or "/" in arg1 or arg1 in (".", ""))
        ):
            resolved_cwd = arg1
            if arg2 is not None:
                if isinstance(arg2, dict) or (isinstance(arg2, str) and "/" not in arg2 and not arg2.endswith(".yaml")):
                    resolved_epic_spec = arg2
                    if arg3 is not None:
                        resolved_path = arg3
                else:
                    resolved_path = arg2
                    if arg3 is not None:
                        resolved_epic_spec = arg3
        elif isinstance(arg1, dict):
            resolved_epic_spec = arg1
            if arg2 is not None:
                resolved_cwd = arg2
        else:
            resolved_epic_spec = str(arg1)
            if arg2 is not None:
                resolved_cwd = arg2

    if cwd is not None:
        resolved_cwd = cwd
    if path is not None:
        resolved_path = path
    if epic_spec is not None:
        resolved_epic_spec = epic_spec

    state = load_cadence(cwd=resolved_cwd, path=resolved_path)
    if state.phase != "refactor":
        raise ValueError(
            f"cannot start refactor phase: current cadence phase is {state.phase!r}, expected 'refactor'"
        )

    if resolved_epic_spec is None:
        raise ValueError("epic_spec is required for start_refactor_phase")

    from loop.roadmap_queue import upsert_refactor_epic
    return upsert_refactor_epic(
        cwd=resolved_cwd or ".",
        epic_spec=resolved_epic_spec,
        role=role,
        queue_rel=queue_rel,
        cadence_state=state,
    )


def record_refactor_noop(
    arg1: str | Path | None = None,
    arg2: str | Path | None = None,
    arg3: str | None = None,
    arg4: Any = None,
    *,
    reason: str | None = None,
    evidence: Any = None,
    cwd: str | Path | None = None,
    path: str | Path | None = None,
) -> RoadmapCadenceState:
    """Record that refactor phase had no work (noop) and transition phase to 'resync'.

    Fails closed if the current cadence phase is not 'refactor'.
    Does not increment the feature counter.
    """
    resolved_cwd = cwd
    resolved_path = path
    resolved_reason = reason
    resolved_evidence = evidence

    if arg1 is not None:
        if isinstance(arg1, Path) or (
            isinstance(arg1, str)
            and (Path(arg1).is_dir() or "/" in arg1 or arg1 in (".", ""))
        ):
            resolved_cwd = arg1
            if arg2 is not None:
                if isinstance(arg2, Path) or (
                    isinstance(arg2, str)
                    and ("/" in arg2 or arg2.endswith(".yaml"))
                ):
                    resolved_path = arg2
                    resolved_reason = str(arg3) if arg3 is not None else None
                    resolved_evidence = arg4
                else:
                    resolved_reason = str(arg2)
                    resolved_evidence = arg3
        else:
            resolved_reason = str(arg1)
            resolved_evidence = arg2

    if cwd is not None:
        resolved_cwd = cwd
    if path is not None:
        resolved_path = path
    if reason is not None:
        resolved_reason = reason
    if evidence is not None:
        resolved_evidence = evidence

    state = load_cadence(cwd=resolved_cwd, path=resolved_path)
    if state.phase != "refactor":
        raise ValueError(
            f"cannot record refactor noop: current cadence phase is {state.phase!r}, expected 'refactor'"
        )

    state.phase = "resync"
    save_cadence(state, cwd=resolved_cwd, path=resolved_path)
    return state


def on_refactor_done(
    arg1: str | Path | None = None,
    arg2: str | Path | None = None,
    *,
    epic_id: str | None = None,
    cwd: str | Path | None = None,
    path: str | Path | None = None,
) -> RoadmapCadenceState:
    """Record completion of a refactor epic and transition phase to 'resync'.

    Does not increment the feature counter.
    """
    resolved_cwd, resolved_path, _ = _resolve_cwd_and_epic(
        arg1, arg2, cwd, path, epic_id
    )
    state = load_cadence(cwd=resolved_cwd, path=resolved_path)
    if state.phase == "refactor":
        state.phase = "resync"
        save_cadence(state, cwd=resolved_cwd, path=resolved_path)
    return state


def on_resync_done(
    arg1: str | Path | None = None,
    arg2: str | Path | None = None,
    *,
    epic_id: str | None = None,
    cwd: str | Path | None = None,
    path: str | Path | None = None,
) -> RoadmapCadenceState:
    """Record completion of cadence resync, resetting phase to 'idle' and feature count to 0."""
    resolved_cwd, resolved_path, _ = _resolve_cwd_and_epic(
        arg1, arg2, cwd, path, epic_id
    )
    state = load_cadence(cwd=resolved_cwd, path=resolved_path)
    state.phase = "idle"
    state.counter = 0
    state.pair_ids = []
    state.replan_outcomes = {}
    save_cadence(state, cwd=resolved_cwd, path=resolved_path)
    return state


reset_cadence_idle = on_resync_done


def record_resync_evidence(
    arg1: str | Path | None = None,
    arg2: Any = None,
    arg3: Any = None,
    *,
    evidence: ResyncEvidence | dict[str, Any] | None = None,
    high_count: int | None = None,
    resync_action: str | None = None,
    stale_epics: list[str] | None = None,
    timestamp: str | None = None,
    cwd: str | Path | None = None,
    path: str | Path | None = None,
) -> RoadmapCadenceState:
    """Record structured resync evidence on the cadence SoT.

    Fails closed if the current cadence phase is not 'resync'.
    """
    resolved_cwd = cwd
    resolved_path = path
    resolved_evidence = evidence
    resolved_high_count = high_count
    resolved_resync_action = resync_action
    resolved_stale_epics = stale_epics
    resolved_timestamp = timestamp

    if arg1 is not None:
        if isinstance(arg1, (Path, str)) and (
            Path(arg1).is_dir()
            or "/" in str(arg1)
            or "\\" in str(arg1)
            or str(arg1) in (".", "")
        ):
            resolved_cwd = arg1
            if arg2 is not None:
                if isinstance(arg2, (Path, str)) and (
                    str(arg2).endswith(".yaml") or "/" in str(arg2)
                ):
                    resolved_path = arg2
                    if arg3 is not None:
                        resolved_evidence = arg3
                else:
                    resolved_evidence = arg2
        elif isinstance(arg1, (dict, ResyncEvidence)):
            resolved_evidence = arg1
            if arg2 is not None:
                resolved_cwd = arg2

    if cwd is not None:
        resolved_cwd = cwd
    if path is not None:
        resolved_path = path
    if evidence is not None:
        resolved_evidence = evidence
    if high_count is not None:
        resolved_high_count = high_count
    if resync_action is not None:
        resolved_resync_action = resync_action
    if stale_epics is not None:
        resolved_stale_epics = stale_epics
    if timestamp is not None:
        resolved_timestamp = timestamp

    state = load_cadence(cwd=resolved_cwd, path=resolved_path)
    if state.phase != "resync":
        raise ValueError(
            f"cannot record resync evidence: current cadence phase is {state.phase!r}, expected 'resync'"
        )

    if isinstance(resolved_evidence, ResyncEvidence):
        evidence_obj = resolved_evidence
        if resolved_high_count is not None:
            evidence_obj.high_count = resolved_high_count
        if resolved_resync_action is not None:
            evidence_obj.resync_action = resolved_resync_action
        if resolved_stale_epics is not None:
            evidence_obj.stale_epics = list(resolved_stale_epics)
        if resolved_timestamp is not None:
            evidence_obj.timestamp = resolved_timestamp
    elif isinstance(resolved_evidence, dict):
        raw_dict = dict(resolved_evidence)
        if resolved_high_count is not None:
            raw_dict["high_count"] = resolved_high_count
        if resolved_resync_action is not None:
            raw_dict["resync_action"] = resolved_resync_action
        if resolved_stale_epics is not None:
            raw_dict["stale_epics"] = list(resolved_stale_epics)
        if resolved_timestamp is not None:
            raw_dict["timestamp"] = resolved_timestamp
        evidence_obj = ResyncEvidence.model_validate(raw_dict)
    else:
        calc_high = 0 if resolved_high_count is None else resolved_high_count
        calc_action = resolved_resync_action or ("reconciled" if calc_high == 0 else "drift_detected")
        evidence_obj = ResyncEvidence(
            high_count=calc_high,
            resync_action=calc_action,
            stale_epics=list(resolved_stale_epics or []),
            timestamp=resolved_timestamp,
        )

    if not evidence_obj.timestamp:
        try:
            from epic.core import utc_now
            evidence_obj.timestamp = utc_now()
        except Exception:
            from datetime import datetime, timezone
            evidence_obj.timestamp = datetime.now(timezone.utc).isoformat()

    state.resync_evidence = evidence_obj
    save_cadence(state, cwd=resolved_cwd, path=resolved_path)
    return state


def run_cadence_resync(
    arg1: str | Path | None = None,
    arg2: str | Path | None = None,
    *,
    cwd: str | Path | None = None,
    path: str | Path | None = None,
    queue_rel: str = "memory-bank/back/roadmap/queue.yaml",
) -> tuple[RoadmapCadenceState, dict[str, Any]]:
    """Run queue reconcile and persist structured summary on cadence SoT.

    Fails closed if the current cadence phase is not 'resync'.
    Returns (RoadmapCadenceState, reconcile_report_dict).
    """
    resolved_cwd, resolved_path, _ = _resolve_cwd_and_epic(
        arg1, arg2, cwd, path, None
    )
    root = Path(resolved_cwd or ".").resolve()
    state = load_cadence(cwd=root, path=resolved_path)
    if state.phase != "resync":
        raise ValueError(
            f"cannot run cadence resync: current cadence phase is {state.phase!r}, expected 'resync'"
        )

    try:
        from harness.hooks.epic.reconcile import reconcile_queue_epics
    except ImportError:
        try:
            from epic.reconcile import reconcile_queue_epics
        except ImportError:
            from reconcile import reconcile_queue_epics  # type: ignore

    report = reconcile_queue_epics(root, queue_rel=queue_rel)
    high_count = report.get("high_count", 0)
    if high_count == 0 and "findings_by_severity" in report:
        high_count = report["findings_by_severity"].get("high", 0)
    if high_count == 0 and "reports" in report:
        high_count = sum(r.get("high_count", 0) for r in report.get("reports", []))

    stale_epics: list[str] = []
    for r in report.get("reports", []):
        if r.get("high_count", 0) > 0:
            eid = r.get("epic_id")
            if eid and eid not in stale_epics:
                stale_epics.append(eid)

    action = "reconciled" if high_count == 0 else "drift_detected"
    try:
        from epic.core import utc_now
        ts = utc_now()
    except Exception:
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()

    evidence = ResyncEvidence(
        high_count=high_count,
        resync_action=action,
        stale_epics=stale_epics,
        timestamp=ts,
        details={
            "findings_total": report.get("findings_total", 0),
            "reports_count": len(report.get("reports", [])),
            "errors": report.get("errors", []),
        },
    )
    state.resync_evidence = evidence
    state.resync_summary = {
        "high_count": high_count,
        "findings_total": report.get("findings_total", 0),
        "stale_epics": stale_epics,
        "timestamp": ts,
    }
    save_cadence(state, cwd=root, path=resolved_path)
    return state, report


execute_cadence_resync = run_cadence_resync


def mark_plan_stale(
    arg1: str | Path | None = None,
    arg2: str | Path | None = None,
    *,
    epic_id: str | None = None,
    reason: str | None = None,
    cwd: str | Path | None = None,
    path: str | Path | None = None,
    role: str = "back",
) -> Path:
    """Mark a plan HOW/status as stale due to drift during cadence resync.

    Updates plan status and/or appends a stale notice to plan.md without
    mutating prompt §Epic.
    """
    resolved_cwd = cwd
    resolved_path = path
    resolved_epic = epic_id
    resolved_reason = reason

    if arg1 is not None and arg2 is not None:
        if isinstance(arg1, (Path, str)) and (
            Path(arg1).is_dir()
            or "/" in str(arg1)
            or "\\" in str(arg1)
            or str(arg1) in (".", "")
        ):
            resolved_cwd = arg1
            if str(arg2).endswith(".md"):
                resolved_path = arg2
            else:
                resolved_epic = str(arg2)
        elif str(arg1).endswith(".md"):
            resolved_path = arg1
            resolved_reason = str(arg2)
        else:
            resolved_epic = str(arg1)
            resolved_reason = str(arg2)
    elif arg1 is not None:
        if str(arg1).endswith(".md"):
            resolved_path = arg1
        elif isinstance(arg1, (Path, str)) and (
            Path(arg1).is_dir()
            or "/" in str(arg1)
            or "\\" in str(arg1)
            or str(arg1) in (".", "")
        ):
            resolved_cwd = arg1
        else:
            resolved_epic = str(arg1)

    if cwd is not None:
        resolved_cwd = cwd
    if path is not None:
        resolved_path = path
    if epic_id is not None:
        resolved_epic = epic_id
    if reason is not None:
        resolved_reason = reason

    root = Path(resolved_cwd or ".").resolve()
    target_plan_path: Path | None = None

    if resolved_path is not None:
        p = Path(resolved_path)
        target_plan_path = p if p.is_absolute() else root / p
    elif resolved_epic:
        try:
            from harness.hooks.epic_paths import find_plan_md_path
            target_plan_path = find_plan_md_path(root, role, resolved_epic)
        except Exception:
            try:
                from epic_paths import find_plan_md_path
                target_plan_path = find_plan_md_path(root, role, resolved_epic)
            except Exception:
                pass

        if target_plan_path is None or not target_plan_path.is_file():
            # Fallback direct search
            plan_dir = root / "memory-bank" / role / "plan"
            if plan_dir.is_dir():
                for cand in plan_dir.glob(f"*{resolved_epic}*/md/plan.md"):
                    if cand.is_file():
                        target_plan_path = cand
                        break
                if target_plan_path is None:
                    for cand in plan_dir.glob(f"plan-*{resolved_epic}*.md"):
                        if cand.is_file():
                            target_plan_path = cand
                            break

    if target_plan_path is None or not target_plan_path.is_file():
        raise FileNotFoundError(
            f"plan not found for epic {resolved_epic!r} (path: {resolved_path!r}) in {root}"
        )

    content = target_plan_path.read_text(encoding="utf-8")
    import re

    # Replace status if present
    status_suffix = f" (resync: {resolved_reason})" if resolved_reason else ""
    if re.search(r"\*\*(?:Статус|Status):\*\*", content):
        content = re.sub(
            r"(\*\*(?:Статус|Status):\*\*\s*)([^\r\n]+)",
            f"\\g<1>stale{status_suffix}",
            content,
            count=1,
        )
    elif re.search(r"(?m)^status:\s*", content):
        content = re.sub(
            r"(?m)^(status:\s*)([^\r\n]+)",
            f"\\g<1>stale{status_suffix}",
            content,
            count=1,
        )

    # Add or update STALE resync notice banner
    notice_text = (
        f"> **STALE (cadence resync):** {resolved_reason}\n"
        if resolved_reason
        else "> **STALE (cadence resync):** Plan HOW invalidated due to drift during cadence resync.\n"
    )
    if "> **STALE (cadence resync):**" not in content:
        lines = content.splitlines(keepends=True)
        inserted = False
        for idx, line in enumerate(lines):
            if line.startswith("# "):
                lines.insert(idx + 1, "\n" + notice_text)
                inserted = True
                break
        if inserted:
            content = "".join(lines)
        else:
            content = notice_text + "\n" + content

    atomic_write_text(target_plan_path, content)
    return target_plan_path


__all__ = [
    "CADENCE_PHASES",
    "DEFAULT_CADENCE_REL",
    "SCHEMA_ROADMAP_CADENCE",
    "CadencePhase",
    "ReplanEvidence",
    "ReplanGap",
    "ReplanOutcome",
    "ReplanOutcomeRecord",
    "ReplanSkipRecord",
    "ResyncEvidence",
    "RoadmapCadenceState",
    "advance_replan",
    "canon_cadence_path",
    "execute_cadence_resync",
    "filter_critical_gaps",
    "is_critical_gap",
    "load_cadence",
    "mark_plan_stale",
    "on_feature_done",
    "on_non_feature_done",
    "on_refactor_done",
    "on_resync_done",
    "record_refactor_noop",
    "record_resync_evidence",
    "reset_cadence_idle",
    "run_cadence_resync",
    "save_cadence",
    "start_refactor_phase",
]
