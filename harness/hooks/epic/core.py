#!/usr/bin/env python3
"""Epic helpers: activeContext cursor + runtime state + index mark.

Finish-integrity: runner may auto-rollback implement ``completed``→``in_progress``
when index is still open (``mark_index_missing``). Index status is mutated only by
agent/CLI ``mark-index-status`` / ``finalize-step`` (never auto-mark by runner).
Context-first loop: loop/context_loop.py. This module is not an IPC/FSM.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logger = logging.getLogger(__name__)

_LOOP_HANDOFF_SCHEMA = "loop-handoff/v1"
_LOOP_HANDOFF_SCHEMA_LINE = f"schema: {_LOOP_HANDOFF_SCHEMA}"

from .convergence import run_convergence_checks
INDEX_IMPLEMENT_CONFLICT = "index_implement_conflict"
MARK_INDEX_MISSING = "mark_index_missing"
FINISH_INTEGRITY_DECOMPOSE_MISSING = "finish_integrity_decompose_missing"
FINISH_INTEGRITY_DIAGNOSTIC_CODES = frozenset(
    {
        INDEX_IMPLEMENT_CONFLICT,
        MARK_INDEX_MISSING,
        FINISH_INTEGRITY_DECOMPOSE_MISSING,
    }
)

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows has no POSIX flock
    fcntl = None

from epic_index import index_yaml_path, load_index_yaml
from _lib import gate_identity
from epic_events import (  # noqa: E402
    build_event,
    event_revision_key,
    event_stream_digest,
    read_event_log_result,
    revision_key,
)
from epic_paths import (  # noqa: E402
    _coerce_epic_shard_path,
    _normalize_mb_path,
    active_context_path,
    canonical_epic_id_for_decompose,
    epic_id_from_decompose_path,
    find_decompose_index_path,
    is_reserved_role_epic_id,
    role_from_decompose_path,
    state_path,
)
from epic_index import (  # noqa: E402
    dump_index_yaml,
    extract_implement_hub_href,
    find_next_step,
    index_yaml_path,
    load_index_yaml,
    md_queue_drift_from_yaml,
    mirror_status_to_md,
    parse_steps_from_md,
    rebuild_md_queue_from_yaml,
    set_step_status_in_doc,
    steps_from_doc,
    sync_yaml_from_md,
)
from epic_portfolio import sync_portfolio_after_step  # noqa: E402

_STEP_STATUS_WORDS = ("pending", "active", "completed", "done", "blocked")


def atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    with tmp.open("r+") as handle:
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


_CHECKPOINT_SCHEMA = "loop-checkpoint/v1"
_CHECKPOINT_STAGES = frozenset(
    {
        "prepared",
        "dispatched",
        "interrupted",
        "evidence_recorded",
        "handoff_validated",
        "blocked",
        "committed",
    }
)
_CHECKPOINT_STATUSES = frozenset({"active", "interrupted", "need_human", "committed"})
_CHECKPOINT_ACTIONS = frozenset({"invoke", "resume", "reconcile", "halt", "advance", "none"})
_CHECKPOINT_RESUME_POLICIES = frozenset({"same_step", "manual", "next_step", "halt"})
_CHECKPOINT_MAX_REASON = 512
_CHECKPOINT_MAX_METADATA = 8


def checkpoint_path(cwd: str | Path) -> Path:
    from epic_paths import epic_dir

    return epic_dir(cwd) / "checkpoint.json"


def checkpoint_lock_path(cwd: str | Path) -> Path:
    return checkpoint_path(cwd).with_suffix(".lock")


def clear_runner_checkpoint(cwd: str | Path) -> dict[str, Any]:
    """Unconditionally drop runner checkpoint (+ lock). Safe after arm/AC rewrite.

    Always unlinks paths even when load_checkpoint() fails validation — a stale
    file must not survive to prepare as checkpoint_projection_conflict.
    """
    path = checkpoint_path(cwd)
    lock = checkpoint_lock_path(cwd)
    errors: list[str] = []
    cleared = False
    for target in (path, lock):
        try:
            if target.exists():
                target.unlink()
                cleared = True
            else:
                target.unlink(missing_ok=True)
        except PermissionError as exc:
            errors.append(f"{target}: permission denied ({exc})")
        except OSError as exc:
            errors.append(f"{target}: {exc}")
    if errors:
        return {
            "ok": False,
            "cleared": cleared,
            "path": str(path),
            "errors": errors,
            "diagnostic_code": "checkpoint_clear_failed",
        }
    return {"ok": True, "cleared": cleared or not path.exists(), "path": str(path)}


def _checkpoint_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    if fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    return handle


def _checkpoint_unlock(handle: Any) -> None:
    if fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    handle.close()


def _checkpoint_scalar(value: Any, *, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()[:256]


def _checkpoint_identity(value: Any) -> dict[str, str]:
    source = value if isinstance(value, dict) else {}
    return {
        key: _checkpoint_scalar(source.get(key))
        for key in ("pipeline", "epic", "role", "step", "action")
        if _checkpoint_scalar(source.get(key))
    }


def _checkpoint_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {}
    for key, item in list(value.items())[:_CHECKPOINT_MAX_METADATA]:
        if not isinstance(key, str) or not re.match(r"^[A-Za-z0-9_.-]{1,64}$", key):
            continue
        if isinstance(item, (str, int, float, bool)) or item is None:
            result[key] = str(item)[:256] if isinstance(item, str) else item
    return result


def validate_checkpoint(record: Any) -> tuple[bool, str | None]:
    if not isinstance(record, dict) or record.get("schema") != _CHECKPOINT_SCHEMA:
        return False, "checkpoint_schema_invalid"
    if not isinstance(record.get("checkpoint_seq"), int) or record["checkpoint_seq"] < 1:
        return False, "checkpoint_seq_invalid"
    required = ("checkpoint_id", "session_id", "step_id", "phase", "stage", "status", "next_action", "resume_policy")
    if any(not _checkpoint_scalar(record.get(key)) for key in required):
        return False, "checkpoint_field_missing"
    if record["stage"] not in _CHECKPOINT_STAGES:
        return False, "checkpoint_stage_invalid"
    if record["status"] not in _CHECKPOINT_STATUSES:
        return False, "checkpoint_status_invalid"
    if record["next_action"] not in _CHECKPOINT_ACTIONS:
        return False, "checkpoint_action_invalid"
    if record["resume_policy"] not in _CHECKPOINT_RESUME_POLICIES:
        return False, "checkpoint_resume_policy_invalid"
    if not isinstance(record.get("identity"), dict):
        return False, "checkpoint_identity_invalid"
    if not _checkpoint_scalar(record.get("phase_epoch")):
        return False, "checkpoint_epoch_invalid"
    if any(not isinstance(record.get(key), (str, type(None))) for key in ("projection_hash", "context_fingerprint", "index_fingerprint")):
        return False, "checkpoint_fingerprint_invalid"
    return True, None


def _checkpoint_record(
    *,
    sequence: int,
    checkpoint_id: str,
    session_id: str,
    runner_id: str | None,
    identity: dict[str, Any] | None,
    step_id: str,
    phase: str,
    phase_epoch: int,
    projection_hash: str | None,
    stage: str,
    status: str,
    next_action: str,
    resume_policy: str,
    context_fingerprint: str | None = None,
    index_fingerprint: str | None = None,
    retry_count: int = 0,
    degraded_count: int = 0,
    session_boundary: bool | None = None,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = {
        "schema": _CHECKPOINT_SCHEMA,
        "checkpoint_seq": sequence,
        "checkpoint_id": _checkpoint_scalar(checkpoint_id),
        "session_id": _checkpoint_scalar(session_id),
        "runner_id": _checkpoint_scalar(runner_id),
        "identity": _checkpoint_identity(identity),
        "step_id": _checkpoint_scalar(step_id),
        "phase": _checkpoint_scalar(phase),
        "phase_epoch": _checkpoint_scalar(phase_epoch),
        "projection_hash": _checkpoint_scalar(projection_hash) or None,
        "stage": stage,
        "status": status,
        "next_action": next_action,
        "resume_policy": resume_policy,
        "context_fingerprint": _checkpoint_scalar(context_fingerprint) or None,
        "index_fingerprint": _checkpoint_scalar(index_fingerprint) or None,
        "retry_count": max(0, int(retry_count)),
        "degraded_count": max(0, int(degraded_count)),
        "session_boundary": bool(session_boundary) if session_boundary is not None else None,
        "reason": _checkpoint_scalar(reason)[:_CHECKPOINT_MAX_REASON] or None,
        "metadata": _checkpoint_metadata(metadata),
        "updated_at": utc_now(),
    }
    valid, error = validate_checkpoint(record)
    if not valid:
        raise ValueError(error)
    return record


def load_checkpoint(cwd: str | Path) -> dict[str, Any] | None:
    path = checkpoint_path(cwd)
    if not path.is_file():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return None
    valid, _ = validate_checkpoint(record)
    return record if valid else None


def commit_checkpoint(
    cwd: str | Path,
    *,
    checkpoint_id: str,
    session_id: str,
    runner_id: str | None = None,
    identity: dict[str, Any] | None = None,
    step_id: str,
    phase: str,
    phase_epoch: int = 0,
    projection_hash: str | None = None,
    stage: str,
    status: str,
    next_action: str,
    resume_policy: str,
    context_fingerprint: str | None = None,
    index_fingerprint: str | None = None,
    retry_count: int = 0,
    degraded_count: int = 0,
    session_boundary: bool | None = None,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist one runner-owned checkpoint; repeated identity/evidence is idempotent."""
    if stage not in _CHECKPOINT_STAGES or status not in _CHECKPOINT_STATUSES:
        raise ValueError("checkpoint lifecycle value invalid")
    lock = _checkpoint_lock(checkpoint_lock_path(cwd))
    try:
        previous = load_checkpoint(cwd)
        if previous and previous.get("checkpoint_id") == checkpoint_id:
            comparable = dict(previous)
            comparable.pop("updated_at", None)
            candidate = _checkpoint_record(
                sequence=int(previous["checkpoint_seq"]), checkpoint_id=checkpoint_id,
                session_id=session_id, runner_id=runner_id, identity=identity,
                step_id=step_id, phase=phase, phase_epoch=phase_epoch,
                projection_hash=projection_hash, stage=stage, status=status,
                next_action=next_action, resume_policy=resume_policy,
                context_fingerprint=context_fingerprint, index_fingerprint=index_fingerprint,
                retry_count=retry_count, degraded_count=degraded_count,
                session_boundary=session_boundary, reason=reason,
                metadata=metadata,
            )
            candidate.pop("updated_at", None)
            if candidate == comparable:
                return previous
        sequence = int(previous.get("checkpoint_seq", 0)) + 1 if previous else 1
        record = _checkpoint_record(
            sequence=sequence, checkpoint_id=checkpoint_id, session_id=session_id,
            runner_id=runner_id, identity=identity, step_id=step_id, phase=phase,
            phase_epoch=phase_epoch, projection_hash=projection_hash, stage=stage,
            status=status, next_action=next_action, resume_policy=resume_policy,
            context_fingerprint=context_fingerprint, index_fingerprint=index_fingerprint,
            retry_count=retry_count, degraded_count=degraded_count,
            session_boundary=session_boundary, reason=reason,
            metadata=metadata,
        )
        atomic_write_text(checkpoint_path(cwd), json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return record
    finally:
        _checkpoint_unlock(lock)


def checkpoint_lifecycle(cwd: str | Path, stage: str, **kwargs: Any) -> dict[str, Any]:
    """Commit a named lifecycle boundary without allowing arbitrary stage values."""
    return commit_checkpoint(cwd, stage=stage, **kwargs)


def resolve_checkpoint_resume(
    cwd: str | Path,
    *,
    projection_hash: str | None = None,
    index_fingerprint: str | None = None,
    context_fingerprint: str | None = None,
    identity: dict[str, Any] | None = None,
    validated_resume: bool = False,
) -> dict[str, Any]:
    checkpoint = load_checkpoint(cwd)
    if checkpoint is None:
        return {"ok": True, "decision": "fresh", "checkpoint": None}
    if checkpoint["status"] == "need_human":
        if not validated_resume:
            return {"ok": False, "decision": "need_human", "code": "checkpoint_blocked", "checkpoint": checkpoint}
    expected = _checkpoint_identity(identity)
    actual = checkpoint.get("identity") or {}
    if expected and any(actual.get(key) != value for key, value in expected.items()):
        conflicting_keys = {key for key, value in expected.items() if actual.get(key) != value}
        # resume_policy=next_step + stage=committed means we intentionally advanced
        # to a new step; step mismatch in identity is expected and must not halt.
        if checkpoint.get("resume_policy") == "next_step" and checkpoint.get("stage") == "committed":
            # step may differ after advance; fields absent in the stored identity
            # (e.g. role omitted when projection was unresolved) are not conflicts.
            material = {
                key
                for key in conflicting_keys
                if key != "step" and actual.get(key) is not None
            }
            if material:
                return {"ok": False, "decision": "halt", "code": "checkpoint_identity_conflict", "checkpoint": checkpoint}
        elif conflicting_keys <= {"step"}:
            # A committed same-step checkpoint must not hide a real step mismatch;
            # only an active/stale prepare checkpoint is disposable.
            if checkpoint.get("stage") == "committed":
                return {"ok": False, "decision": "halt", "code": "checkpoint_identity_conflict", "checkpoint": checkpoint}
            checkpoint_path(cwd).unlink(missing_ok=True)
            checkpoint_lock_path(cwd).unlink(missing_ok=True)
            return {
                "ok": True,
                "decision": "fresh",
                "checkpoint": None,
                "cleared_stale_step_checkpoint": True,
                "previous_step": actual.get("step") or checkpoint.get("step_id"),
                "expected_step": expected.get("step"),
            }
        else:
            # Safe-resume: if every conflicting field is simply absent (None) in the stored
            # identity (written before arm populated pipeline/step) but step_id matches,
            # the checkpoint is still valid for this step — don't halt.
            absent_in_actual = all(actual.get(key) is None for key in conflicting_keys)
            step_matches = checkpoint.get("step_id") == expected.get("step")
            if not (absent_in_actual and step_matches):
                return {"ok": False, "decision": "halt", "code": "checkpoint_identity_conflict", "checkpoint": checkpoint}
    for key, value in (("projection_hash", projection_hash), ("index_fingerprint", index_fingerprint), ("context_fingerprint", context_fingerprint)):
        if value and checkpoint.get(key) and value != checkpoint.get(key):
            return {"ok": False, "decision": "halt", "code": "checkpoint_index_conflict" if key == "index_fingerprint" else "checkpoint_projection_conflict", "checkpoint": checkpoint}
    if checkpoint["stage"] == "committed" and checkpoint["resume_policy"] == "next_step":
        decision = "advance"
    else:
        decision = "resume"
    return {"ok": True, "decision": decision, "step_id": checkpoint["step_id"], "next_action": checkpoint["next_action"], "checkpoint": checkpoint}


def checkpoint_resume(cwd: str | Path, *, validated: bool = False, **kwargs: Any) -> dict[str, Any]:
    return resolve_checkpoint_resume(cwd, validated_resume=validated, **kwargs)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_state() -> dict[str, Any]:
    from loop.schemas.state import EpicState
    return EpicState().model_dump()


def increment_drift_counter(cwd: str | Path, name: str) -> None:
    st = load_epic_state(cwd)
    drift = st.get("drift_counters")
    if not isinstance(drift, dict):
        drift = {}
    drift[name] = int(drift.get(name) or 0) + 1
    st["drift_counters"] = drift
    save_epic_state(cwd, st)


def load_epic_state(cwd: str | Path) -> dict[str, Any]:
    p = state_path(cwd)
    st = default_state()
    if not p.is_file():
        return st
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return st
        from loop.schemas.state import EpicState
        try:
            validated = EpicState.model_validate(data).model_dump()
            return validated
        except Exception:
            return st
    except (OSError, TypeError, ValueError):
        return st


def _state_diagnostics(cwd: str | Path) -> list[str]:
    p = state_path(cwd)
    if not p.is_file():
        return ["state_rebuilt"]
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return ["state_schema_invalid"]
    if not isinstance(data, dict):
        return ["state_schema_invalid"]
    from loop.schemas.state import EpicState
    try:
        EpicState.model_validate(data)
    except Exception:
        return ["state_schema_invalid"]
    if data.get("state_schema_version") != "loop-state/v2" and data.get("schema_version") != "loop-state/v2":
        return ["state_migrated"]
    return []


def _runtime_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "active",
        "status",
        "started_at",
        "updated_at",
        "halt_reason",
        "model",
        "last_verify_verdict",
        "last_verify_at",
        "pending_fingerprint_before",
        "load_now_before",
        "context_degraded",
        "degraded_count",
        "degraded_fingerprint",
        "retry_count",
        "resume_dirty",
    )
    return {key: state.get(key) for key in keys if key in state}


def save_epic_state(cwd: str | Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    projection = state.get("projection") if isinstance(state.get("projection"), dict) else {}
    state["state_schema_version"] = "loop-state/v2"
    state["schema_version"] = "loop-state/v2"
    state["runtime"] = _runtime_snapshot(state)
    state["dag"] = {
        "pipeline_id": state.get("dag_pipeline") or state.get("pipeline_id"),
        "cursor": state.get("dag_cursor") or state.get("fanout_cursor"),
        "done": sorted({str(item) for item in state.get("dag_done") or []}),
    }
    state["gate_snapshot"] = projection.get("gates") or gates_from_phase(state.get("phase"))
    state["diagnostic_codes"] = sorted(
        set(state.get("diagnostic_codes") or [])
        | set(projection.get("diagnostic_codes") or [])
    )
    atomic_write_text(
        state_path(cwd),
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
    )


def write_last_finish_tool(
    cwd: str | Path,
    name: str,
    fingerprint: str | None = None,
    *,
    finished_step: str | None = None,
    armed_after_finish: str | None = None,
) -> bool:
    """Write last_finish_tool record into epic state."""
    st = load_epic_state(cwd)
    ts = utc_now()
    if not fingerprint:
        step_val = finished_step or st.get("armed_step") or name
        raw_fp = f"{step_val}:{ts}"
        fingerprint = hashlib.sha256(raw_fp.encode("utf-8")).hexdigest()
    st["last_finish_tool"] = {
        "name": str(name),
        "at": ts,
        "fingerprint": str(fingerprint),
    }
    if finished_step is not None:
        st["last_finished_step"] = str(finished_step)
        finished_epic = str(st.get("armed_epic") or "").strip()
        st["last_finished_epic"] = finished_epic or None
    if armed_after_finish is not None:
        st["armed_after_finish"] = str(armed_after_finish)
    save_epic_state(cwd, st)
    return True


def _needs_creative_open(value: object) -> bool:
    text = str(value or "").strip().lower()
    return text.startswith("yes") and "closed" not in text and "✅" not in text


def effective_phase(
    *, role: object, next_phase: object, needs_creative: object
) -> str:
    """Return the runner phase after applying the step's creative gate."""
    role_name = str(role or "").upper() or "BACK"
    if _needs_creative_open(needs_creative):
        return f"{role_name} CREATIVE"
    phase = str(next_phase or f"{role_name} IMPLEMENT")
    if (
        needs_creative is not None
        and str(needs_creative).strip()
        and re.search(r"\bCREATIVE\b", phase.upper())
    ):
        return f"{role_name} IMPLEMENT"
    return phase


def gates_from_phase(phase: object) -> dict[str, Any]:
    """Translate a runner-derived phase into spawn-gate requirements."""
    from loop.epic_transition import load_phase_registry

    default_gates = {"mode": None, "need_verify": False, "need_reviewer": False}
    reg = load_phase_registry()
    val = str(phase or "").upper().strip()

    matched_phase = None
    phases = reg.get("phases", {})
    if val in phases:
        matched_phase = val
    else:
        for p in phases:
            if re.search(r"\b" + re.escape(p) + r"\b", val):
                matched_phase = p
                break

    if not matched_phase or matched_phase in reg.get("terminal_phases", []):
        return default_gates

    row = phases.get(matched_phase, {})
    return dict(row.get("finish_gates_dict", default_gates))


def _step_needs_creative(cwd: Path, idx: Path | None, step: dict[str, str]) -> object:
    if idx is None:
        return None
    shard = _resolve_href(
        _decompose_step_shards_dir(idx),
        step.get("shard_href") or step.get("file") or "",
        cwd,
    )
    if not shard:
        return None
    try:
        doc = yaml.safe_load((cwd / shard).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    return doc.get("needs_creative") if isinstance(doc, dict) else None


def _projection_digest(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _index_fingerprint(cwd: Path, index: Path | None) -> str | None:
    if index is None:
        return None
    source = index
    yaml_path = index_yaml_path(index)
    if yaml_path.is_file():
        source = yaml_path
    try:
        return f"sha256:{hashlib.sha256(source.read_bytes()).hexdigest()}"
    except OSError:
        return None


def _event_evidence(
    cwd: Path, role_dir: str | None, epic_id: str | None
) -> tuple[str, int | None, list[str]]:
    if not role_dir or not epic_id:
        return "sha256:" + hashlib.sha256(b"").hexdigest(), None, []
    result = read_event_log_result(
        _event_log_path(cwd, role_dir, epic_id),
        expected_epic_id=epic_id,
        cwd=cwd,
    )
    last_seq = result.events[-1].get("seq") if result.events else None
    codes = sorted({item.code for item in result.diagnostics})
    return f"sha256:{event_stream_digest(result)}", last_seq, codes


def rebuild_epic_projection(cwd: str | Path) -> dict[str, Any]:
    """Rebuild the runner-owned projection from events and the decompose queue."""
    cwd_p = Path(cwd)
    diagnostics = _state_diagnostics(cwd_p)
    state = load_epic_state(cwd_p)
    if diagnostics == ["state_rebuilt"] and not state:
        diagnostics = []
    diagnostics = sorted(set(diagnostics) | set(state.get("diagnostic_codes") or []))
    info = discover_epic_for_pipeline(cwd_p)
    if info is None:
        logger.warning(
            "epic identity unavailable while rebuilding projection "
            "(code=identity_unresolved)"
        )
    if state.get("armed_epic") and state.get("armed_decompose"):
        decompose = str(state["armed_decompose"])
        armed_epic = str(state["armed_epic"])
        if is_reserved_role_epic_id(armed_epic) or is_reserved_role_epic_id(
            epic_id_from_decompose_path(decompose)
        ):
            diagnostics = sorted(set(diagnostics) | {"armed_role_slug"})
            logger.warning(
                "rebuild ignores reserved-role arm epic=%r decompose=%r",
                armed_epic,
                decompose,
            )
        else:
            role_from_path = role_from_decompose_path(decompose)
            role = (role_from_path or str(state.get("role") or "BACK")).upper()
            role_dir = {"BACK": "back", "FRONT": "front", "INTEG": "integration"}.get(
                role, "back"
            )
            info = {
                **(info or {}),
                "epic_id": armed_epic,
                "decompose": decompose,
                "role_dir": role_dir,
                "role": role,
            }
    previous = state.get("projection") if isinstance(state.get("projection"), dict) else {}
    projection: dict[str, Any] = {
        "schema_version": "loop-projection/v2",
        "pipeline_id": state.get("pipeline_id") or state.get("dag_pipeline"),
        "epic_id": None,
        "role": None,
        "phase": None,
        "epic": None,
        "next_step": None,
        "next_step_status": None,
        "expected_artifact": None,
        "index_fingerprint": None,
        "last_event_seq": None,
        "event_digest": "sha256:" + hashlib.sha256(b"").hexdigest(),
        "diagnostic_codes": diagnostics.copy(),
        "dag_node_id": state.get("dag_node_id") or state.get("fanout_cursor"),
        "dag_nodes": [],
        "source": "event-log+decompose-index",
        "session_id": state.get("session_id"),
        "generated_at": utc_now(),
    }

    if info:
        epic_id = str(info.get("epic_id") or "") or None
        role = str(info.get("role") or "").upper() or None
        role_dir = str(info.get("role_dir") or "") or None
        decompose = str(info.get("decompose") or "")
        idx, steps, _source = _load_decompose_steps(cwd_p, decompose)
        step = find_next_decompose_step_from_queue(steps)
        phase = ""
        next_step = None
        next_status = None
        armed_phase = str(state.get("armed_step") or state.get("phase") or "").upper()
        if armed_phase in {"ANALYZE", "CLARIFY", "CREATIVE", "PLAN", "DECOMPOSE"}:
            phase = armed_phase
            if armed_phase == "ANALYZE" and epic_id and role_dir and idx is not None:
                from analyze_gate import analyze_required_before_implement

                gate = analyze_required_before_implement(
                    cwd_p,
                    role_dir,
                    epic_id,
                    steps,
                    index_path=idx,
                )
                if not gate.get("required") and step:
                    phase = effective_phase(
                        role=role,
                        next_phase=step.get("next_phase"),
                        needs_creative=_step_needs_creative(cwd_p, idx, step),
                    )
            if step:
                next_step = step.get("step_id")
                next_status = step.get("status")
        elif step:
            phase = effective_phase(
                role=role,
                next_phase=step.get("next_phase"),
                needs_creative=_step_needs_creative(cwd_p, idx, step),
            )
            next_step = step.get("step_id")
            next_status = step.get("status")
        elif epic_id and role_dir:
            lifecycle = reduce_epic_lifecycle(cwd_p, role_dir, epic_id)
            phase = str(lifecycle.get("phase") or "QA")
            _reason_code = lifecycle.get("reason_code") or ""
            if phase == "QA" and _reason_code == "qa_failed":
                phase = "BUGFIX"
            _qa, _reflection = (
                find_qa_pass_artifact(cwd_p, role_dir, epic_id),
                None,
            )

        expected = None
        phase_upper = phase.upper()
        if "QA" in phase_upper:
            expected = f"memory-bank/{role_dir}/qa/{epic_id}/qa-*.yaml"
        elif "AUDIT" in phase_upper:
            expected = f"memory-bank/{role_dir}/audit/{epic_id}/audit-*.yaml"
        elif "IMPLEMENT" in phase_upper and next_step:
            expected = f"decompose step {next_step} artifact"
        event_digest, last_seq, event_diagnostics = _event_evidence(
            cwd_p, role_dir, epic_id
        )
        projection["diagnostic_codes"] = sorted(
            set(projection["diagnostic_codes"]) | set(event_diagnostics)
        )
        projection.update(
            {
                "epic_id": epic_id,
                "role": role,
                "phase": phase or None,
                "epic": epic_id,
                "next_step": next_step,
                "next_step_status": next_status,
                "expected_artifact": expected,
                "index_fingerprint": _index_fingerprint(cwd_p, idx),
                "last_event_seq": last_seq,
                "event_digest": event_digest,
                "diagnostic_codes": projection["diagnostic_codes"],
                "gates": gates_from_phase(phase),
            }
        )
    else:
        armed_epic = str(state.get("armed_epic") or "").strip()
        armed_step = str(state.get("armed_step") or "").strip().upper()
        if armed_epic:
            phase = armed_step or None
            projection.update(
                {
                    "epic_id": armed_epic,
                    "epic": armed_epic,
                    "role": state.get("role"),
                    "phase": phase,
                    "next_step": phase
                    if phase
                    in {"DECOMPOSE", "AUDIT", "QA", "BUGFIX"}
                    else state.get("armed_step"),
                    "gates": gates_from_phase(phase),
                }
            )
        else:
            projection["gates"] = gates_from_phase(None)

    identity = {
        key: projection[key]
        for key in (
            "schema_version",
            "pipeline_id",
            "epic_id",
            "role",
            "index_fingerprint",
            "next_step",
            "next_step_status",
            "last_event_seq",
            "event_digest",
            "phase",
            "expected_artifact",
            "dag_node_id",
            "dag_nodes",
            "diagnostic_codes",
        )
    }
    projection_hash = _projection_digest(identity)
    previous_hash = previous.get("projection_hash")
    previous_generation = previous.get("projection_generation", 0)
    try:
        generation = int(previous_generation)
    except (TypeError, ValueError):
        generation = 0
    if previous_hash != projection_hash:
        generation += 1
    phase_epoch = _projection_digest(
        {"projection_hash": projection_hash, "projection_generation": generation}
    )
    if not projection.get("next_step"):
        armed_step = str(state.get("armed_step") or "").strip()
        if armed_step and re.match(r"^[sera]\d+", armed_step, re.I):
            projection["next_step"] = armed_step
            if not projection.get("next_step_status"):
                projection["next_step_status"] = "active"
    projection.update(
        {
            "projection_hash": projection_hash,
            "projection_generation": generation,
            "phase_epoch": phase_epoch,
            "step": projection["next_step"],
        }
    )

    phase_u = str(projection.get("phase") or "").upper()
    # Keep armed_step aligned with projection: terminal DONE must not keep stale AUDIT/QA.
    if phase_u == "DONE":
        state["armed_step"] = None
    elif phase_u in {"AUDIT", "QA", "BUGFIX"} and not projection.get("next_step"):
        armed = str(state.get("armed_step") or "").strip()
        if armed.upper() != phase_u:
            # Stale sNN/eNN or previous post-implement phase → sync to current phase name.
            if (not armed) or armed.upper() in {
                "AUDIT", "QA", "BUGFIX", "DONE", "REFLECT"
            } or re.match(r"^[se]\d+", armed, re.I):
                state["armed_step"] = phase_u
    state.update(
        {
            "phase": projection["phase"],
            "epic": projection["epic"],
            "role": projection.get("role") or state.get("role"),
            "next_step": projection["next_step"],
            "expected_artifact": projection["expected_artifact"],
            "projection_hash": projection_hash,
            "phase_epoch": phase_epoch,
            "projection": projection,
            "state_migrated": "state_migrated" in diagnostics,
            "state_rebuilt": "state_rebuilt" in diagnostics,
        }
    )
    save_epic_state(cwd_p, state)
    return state


_EVENT_LOG_LIMIT = 20
_EVENT_ARCHIVE_NAME = "archive-rollover.jsonl"


def _event_log_path(cwd: str | Path, role_dir: str, epic_id: str) -> Path:
    cwd_p = Path(cwd)
    live = cwd_p / "memory-bank" / role_dir / "events" / epic_id / "events.jsonl"
    if live.is_file():
        return live
    archived = (
        cwd_p / "memory-bank" / "archive" / role_dir / "events" / epic_id / "events.jsonl"
    )
    if archived.is_file():
        return archived
    return live


def _role_mb_roots(cwd: Path, role_dir: str, *, epic_id: str | None = None, kind: str | None = None) -> list[Path]:
    """Live role tree first; archive only when live epic shard is missing."""
    live = cwd / "memory-bank" / role_dir
    archived = cwd / "memory-bank" / "archive" / role_dir
    if epic_id and kind:
        live_shard = live / kind / epic_id
        if live_shard.is_dir():
            return [live]
        arch_shard = archived / kind / epic_id
        if arch_shard.is_dir():
            return [archived]
        return [live]
    roots = [live]
    if archived.is_dir():
        roots.append(archived)
    return roots


def _read_event_log(path: Path) -> list[dict[str, Any]]:
    result = read_event_log_result(path, expected_epic_id=path.parent.name, cwd=path.parents[4])
    if result.diagnostics:
        return []
    return list(result.events)


def _artifact_sha256(artifact: Path) -> str:
    try:
        return hashlib.sha256(artifact.read_bytes()).hexdigest()
    except OSError:
        return hashlib.sha256(artifact.as_posix().encode("utf-8")).hexdigest()


def _next_event_seq(events: list[dict[str, Any]]) -> int:
    return max((event.get("seq", 0) for event in events if isinstance(event.get("seq"), int)), default=0) + 1


def _append_event(
    cwd: str | Path,
    role_dir: str,
    epic_id: str,
    kind: str,
    artifact: Path,
) -> bool:
    if not artifact.is_file():
        return False
    path = _event_log_path(cwd, role_dir, epic_id)
    lock_path = path.with_name("events.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = lock_path.open("a+", encoding="utf-8")
    try:
        if fcntl is not None:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        cwd_p = Path(cwd)
        history = read_event_log_result(
            path, expected_epic_id=epic_id, cwd=cwd_p, include_archives=True
        )
        if history.diagnostics:
            return False
        historical = list(history.events)
        live_stream = read_event_log_result(
            path, expected_epic_id=epic_id, cwd=cwd_p, include_archives=False
        )
        if live_stream.diagnostics:
            return False
        live_events = list(live_stream.events)
        try:
            artifact_rel = artifact.relative_to(cwd_p).as_posix()
        except ValueError:
            artifact_rel = artifact.as_posix()
        artifact_hash = _artifact_sha256(artifact)
        previous_hash = next(
            (
                existing.get("artifact_sha256")
                for existing in reversed(historical)
                if existing.get("kind") == kind
                and existing.get("artifact") == artifact_rel
                and existing.get("artifact_sha256") != artifact_hash
            ),
            None,
        )
        metadata = (
            {"previous_artifact_sha256": previous_hash}
            if previous_hash is not None
            else None
        )
        event = build_event(
            epic_id=epic_id,
            kind=kind,
            artifact=artifact_rel,
            artifact_sha256=artifact_hash,
            seq=_next_event_seq(historical),
            timestamp=utc_now(),
            metadata=metadata,
        )
        if any(
            event_revision_key(existing) == revision_key(event)
            for existing in historical
        ):
            return False
        live_events.append(event)
        if len(live_events) > _EVENT_LOG_LIMIT:
            overflow = live_events[:-_EVENT_LOG_LIMIT]
            archive = path.with_name(_EVENT_ARCHIVE_NAME)
            with archive.open("a", encoding="utf-8") as fh:
                for item in overflow:
                    fh.write(json.dumps(item, ensure_ascii=False) + "\n")
            live_events = live_events[-_EVENT_LOG_LIMIT:]
        atomic_write_text(
            path,
            "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in live_events),
        )
        return True
    finally:
        if fcntl is not None:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()


def _matching_reflection_artifacts(
    cwd: Path, role_dir: str, epic_id: str
) -> list[Path]:
    directory = cwd / "memory-bank" / role_dir / "reflection"
    if not directory.is_dir():
        return []
    task = _task_id_from_epic(epic_id)
    result: list[Path] = []
    for path in sorted(directory.glob("reflection-*.md"), key=lambda item: item.name):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        owner_epics = set(re.findall(r"(?im)^\*\*Эпик:\*\*\s*([^\s]+)", text[:800]))
        owner_epics.update(re.findall(r"(?im)^epic_id:\s*([^\s]+)", text[:800]))
        if owner_epics:
            if epic_id in owner_epics:
                result.append(path)
            continue
        if epic_id in path.name or (task and task in path.name):
            result.append(path)
            continue
        if epic_id in text[:800] or (task and task in text[:800]):
            result.append(path)
    return result


def _reflection_ownership_ambiguous(
    cwd: Path, role_dir: str, epic_id: str
) -> bool:
    matches = _matching_reflection_artifacts(cwd, role_dir, epic_id)
    if len(matches) > 1:
        return True
    if len(matches) != 1:
        return False
    path = matches[0]
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:800]
    except OSError:
        return False
    owner_epics = set(re.findall(r"(?im)^\*\*Эпик:\*\*\s*([^\s]+)", text))
    owner_epics.update(re.findall(r"(?im)^epic_id:\s*([^\s]+)", text))
    if owner_epics:
        return False
    task = _task_id_from_epic(epic_id)
    ids = set(re.findall(r"T-\d+", text))
    return bool(task and task in ids and len(ids) > 1)


def _declared_artifacts(cwd: Path, role_dir: str, epic_id: str) -> list[tuple[str, Path]]:
    """Return artifacts in append order: decompose → implement → audit → bugfix → qa → reflection.

    QA must come after audit/bugfix so a single reconcile pass that rewrites
    evidence and the QA verdict does not emit ``bugfix_done`` after ``qa_pass``.
    """
    records: list[tuple[str, Path]] = []
    for root in _role_mb_roots(cwd, role_dir, epic_id=epic_id, kind="plan"):
        decomp_dir = root / "plan" / f"decompose-{epic_id}"
        if decomp_dir.is_dir():
            for path in sorted(
                decomp_dir.glob("s*.yaml"),
                key=lambda item: str(item),
            ):
                records.append(("decompose_step_done", path))
    for root in _role_mb_roots(cwd, role_dir, epic_id=epic_id, kind="implement"):
        impl_dir = root / "implement" / f"implement-{epic_id}"
        if impl_dir.is_dir():
            for path in sorted(
                impl_dir.glob("s*.yaml"),
                key=lambda item: str(item),
            ):
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                if re.search(r"(?m)^status:\s*completed\s*$", text):
                    records.append(("implement_done", path))
    for root in _role_mb_roots(cwd, role_dir, epic_id=epic_id, kind="audit"):
        audit_dir = root / "audit" / epic_id
        for path in sorted(
            audit_dir.glob("audit-*.yaml"),
            key=lambda item: str(item),
        ) if audit_dir.is_dir() else ():
            records.append(("audit_done", path))
    for root in _role_mb_roots(cwd, role_dir, epic_id=epic_id, kind="bugfix"):
        bugfix_dir = root / "bugfix" / epic_id
        for path in sorted(
            bugfix_dir.glob("bugfix-*.md"),
            key=lambda item: str(item),
        ) if bugfix_dir.is_dir() else ():
            records.append(("bugfix_done", path))
    for root in _role_mb_roots(cwd, role_dir, epic_id=epic_id, kind="qa"):
        qa_dir = root / "qa" / epic_id
        for path in sorted(
            qa_dir.glob("qa-*.yaml"),
            key=lambda item: str(item),
        ) if qa_dir.is_dir() else ():
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            verdict = re.search(r"(?m)^verdict:\s*(pass|fail|blocked)\s*$", text)
            if verdict:
                v = verdict.group(1)
                records.append((f"qa_{'fail' if v == 'blocked' else v}", path))
    return records


def reconcile_epic_events(
    cwd: str | Path, role_dir: str, epic_id: str
) -> list[dict[str, Any]]:
    cwd_p = Path(cwd)
    records = _declared_artifacts(cwd_p, role_dir, epic_id)
    event_path = _event_log_path(cwd_p, role_dir, epic_id)
    known = {revision_key(event) for event in _read_event_log(event_path)}
    known_sha = {
        (str(event.get("kind") or ""), str(event.get("artifact_sha256") or ""))
        for event in _read_event_log(event_path)
        if event.get("artifact_sha256")
    }
    for kind, artifact in records:
        try:
            artifact_rel = artifact.relative_to(cwd_p).as_posix()
        except ValueError:
            artifact_rel = artifact.as_posix()
        artifact_hash = _artifact_sha256(artifact)
        candidate = build_event(
            epic_id=epic_id,
            kind=kind,
            artifact=artifact_rel,
            artifact_sha256=artifact_hash,
            seq=1,
            timestamp=utc_now(),
        )
        if revision_key(candidate) in known:
            continue
        # Same kind+bytes already recorded under another path (ARCHIVE move).
        if (kind, artifact_hash) in known_sha:
            continue
        if _append_event(cwd_p, role_dir, epic_id, kind, artifact):
            known.add(revision_key(candidate))
            known_sha.add((kind, artifact_hash))
    return _read_event_log(event_path)


def reconcile_current_epic_events(cwd: str | Path) -> list[dict[str, Any]]:
    info = discover_epic_for_pipeline(cwd)
    if info is None:
        logger.warning(
            "epic identity unavailable while reconciling events "
            "(code=identity_unresolved)"
        )
        return []
    return reconcile_epic_events(cwd, info["role_dir"], info["epic_id"])


def halt_epic(cwd: str | Path, reason: str) -> dict[str, Any]:
    st = load_epic_state(cwd)
    st["active"] = False
    st["status"] = "halted"
    st["halt_reason"] = reason
    save_epic_state(cwd, st)
    return st


def read_active_context(cwd: str | Path) -> str:
    p = active_context_path(cwd)
    if not p.is_file():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


def extract_handoff_block(text: str) -> str:
    m = re.search(r"(?im)^##\s*Handoff\b.*$", text)
    if not m:
        return ""
    start = m.start()
    rest = text[m.end() :]
    nxt = re.search(r"(?im)^##\s+", rest)
    end = m.end() + (nxt.start() if nxt else len(rest))
    return text[start:end].strip()


_HANDOFF_PHASE_HEADING_RE = re.compile(
    r"(?im)^##\s*Handoff\s+(?:BACK|FRONT|INTEG(?:RATION)?)\s+"
    r"(AUDIT|QA|REFLECT|BUGFIX|DECOMPOSE)\b"
)
_HANDOFF_MODE_LINE_RE = re.compile(
    r"(?im)(?:Режим/шаг|Mode/step):\s*`(?:BACK|FRONT|INTEG(?:RATION)?)\s+"
    r"(AUDIT|QA|REFLECT|BUGFIX|DECOMPOSE)`"
)
_HANDOFF_NEXT_PHASE_RE = re.compile(
    r"(?im)(?:Дальше|Next):\s*.*`(?:BACK|FRONT|INTEG(?:RATION)?)\s+"
    r"(AUDIT|QA|REFLECT|BUGFIX)`"
)


def handoff_post_implement_phase(text: str) -> str | None:
    """Parse explicit post-implement / decompose phase from Handoff (SoT over events)."""
    from loop.schemas.active_context import handoff_gate_phase_from_text

    return handoff_gate_phase_from_text(text)


def _reflection_stale_vs_qa_pass(
    cwd: Path,
    latest_qa: dict[str, Any],
    last_reflection: dict[str, Any],
) -> bool:
    """True when reflection artifact predates the current QA pass artifact."""
    qa_art = str(latest_qa.get("artifact") or "").strip()
    refl_art = str(last_reflection.get("artifact") or "").strip()
    if not qa_art or not refl_art:
        return False
    qa_path = cwd / qa_art
    refl_path = cwd / refl_art
    if not qa_path.is_file() or not refl_path.is_file():
        return False
    return refl_path.stat().st_mtime < qa_path.stat().st_mtime


def extract_load_now(text: str) -> list[str]:
    m = re.search(r"(?im)^##\s*load_now\s*$", text)
    if not m:
        return []
    rest = text[m.end() :]
    nxt = re.search(r"(?im)^##\s+", rest)
    body = rest[: nxt.start()] if nxt else rest
    paths: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        p = _coerce_epic_shard_path(_normalize_mb_path(raw))
        if not p or p in seen:
            return
        seen.add(p)
        paths.append(p)

    for line in body.splitlines():
        for pm in re.finditer(
            r"`((?:memory-bank|apps|tests|migrations|back|front|integration)/[^`]+)`",
            line,
        ):
            add(pm.group(1))
        for pm in re.finditer(
            r"\(((?:memory-bank/)?(?:back|front|integration)/[^)\s]+)\)",
            line,
        ):
            add(pm.group(1))
        stripped = line.strip()
        if stripped.startswith("- "):
            raw = stripped[2:].strip()
            if "#" in raw:
                raw = raw.split("#", 1)[0].strip()
            if raw.startswith(
                ("memory-bank/", "back/", "front/", "integration/")
            ):
                add(raw)
    return paths


def fingerprint_context(text: str) -> str:
    handoff = extract_handoff_block(text)
    load = "\n".join(extract_load_now(text))
    raw = f"{handoff}\n---\n{load}".strip()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def validate_active_context_shape(text: str) -> list[str]:
    """Return stable shape codes while keeping messages machine-readable."""
    value = text or ""
    if not value.strip():
        return ["missing_load_now", "missing_handoff"]

    errors: list[str] = []
    try:
        from loop.schemas.active_context import validate_handoff_frontmatter

        _fm, fm_errors = validate_handoff_frontmatter(value)
        errors.extend(fm_errors)
    except Exception:
        pass
    handoffs = re.findall(r"(?im)^##\s*Handoff\b", value)
    dones = re.findall(r"(?im)^##\s*done\b", value)
    load_now = re.findall(r"(?im)^##\s*load_now\b", value)
    if not load_now:
        errors.append("missing_load_now")
    elif len(load_now) > 1:
        errors.append("multiple_load_now")
    if not handoffs:
        errors.append("missing_handoff")
    elif len(handoffs) > 1:
        errors.append("multiple_handoff")
    if len(dones) > 1:
        errors.append("multiple_done")

    load_match = re.search(r"(?im)^##\s*load_now\s*$", value)
    if load_match:
        rest = value[load_match.end() :]
        next_section = re.search(r"(?im)^##\s+", rest)
        load_body = rest[: next_section.start()] if next_section else rest
        load_paths = re.findall(
            r"(?:`|\()((?:memory-bank/)?(?:back|front|integration)/[^)`\s]+)",
            load_body,
        )
        if re.search(r"(?im)\b(?:completed|done|status\s*:\s*(?:completed|done))\b", load_body):
            errors.append("completed_in_load_now")
        seen_implement = False
        for path in load_paths:
            if "/implement/" in path:
                seen_implement = True
            elif seen_implement and "/plan/" in path:
                errors.append("plan_loaded_after_implement")
                break

    marker_start = re.compile(
        r"^\s*(?:[-*]\s*)?(?:\*\*)?`?(?:EPIC_DONE|BLOCKED|NEED_HUMAN)`?"
    )
    marker_line = re.compile(
        r"^\s*(?:[-*]\s*)?(?:\*\*)?`?(?:EPIC_DONE|BLOCKED|NEED_HUMAN)`?"
        r"(?:\*\*)?(?::.*)?\s*$"
    )
    for line in value.splitlines():
        if (
            re.search(r"(?i)\b(?:EPIC_DONE|BLOCKED|NEED_HUMAN)\b", line)
            and marker_start.match(line)
            and not marker_line.match(line)
        ):
            errors.append("malformed_marker")
            break
    errors = list(dict.fromkeys(errors))
    return errors


def session_start_payload(cwd: str | Path, source: str | None = None) -> dict[str, Any] | None:
    import os

    if str(os.environ.get("EPIC_LOOP", "")).lower() not in {"1", "true", "yes"}:
        return None
    st = load_epic_state(cwd)
    if not st.get("active") or st.get("status") != "running":
        return None
    ctx = (
        f"source={source or '?'}\n"
        "Один шаг → FINISH (Handoff в activeContext) → stop.\n"
        "Режим/шаг — по activeContext + load_now.\n"
        "Не вызывай /clear."
    )
    try:
        from loop.mb_load.session import load_session

        res = load_session(cwd)
        if res.ok:
            fp = res.fingerprint or ""
            file_paths = [f.path for f in res.files]
            total_size = sum(len(f.content or "") for f in res.files)

            lines = [f"\nFingerprint: {fp}", "Bundle files: " + ", ".join(file_paths)]
            if total_size <= 16 * 1024:
                for f in res.files:
                    if f.content:
                        lines.append(f"\n--- {f.path} ---\n{f.content}")
            ctx += "\n".join(lines)
        else:
            diag = ", ".join(res.diagnostic_codes or res.shape_errors or ["load_session_failed"])
            ctx += f"\nWarning: bundle load failed ({diag})"
    except Exception as exc:
        ctx += f"\nWarning: load_session exception ({exc})"

    return {
        "additionalContext": ctx,
        "sessionTitle": "epic:context",
    }


def verify_pass_step_blockers(cwd: str | Path) -> list[str]:
    """Structural blockers that forbid accepting VERDICT: PASS for the armed step.

    Used to demote a false PASS when checkpoints are still pending or gaps are blocked.
    Parent must fix the step — not treat incomplete work as a successful gate.
    """
    st = load_epic_state(cwd)
    if not st.get("active"):
        return []
    step_id = str(st.get("armed_step") or "").strip()
    decompose = st.get("armed_decompose")
    if not step_id or not decompose:
        return []
    if not re.match(r"^[sera]\d{2}$", step_id.lower()):
        return []
    idx = _decompose_index_path(cwd, str(decompose))
    if idx is None:
        return [f"decompose_index_missing: {decompose}"]
    path, err = _resolve_implement_shard(
        cwd, idx=idx, step_id=step_id, implement=None
    )
    if err or path is None:
        return [err or "implement shard not found"]
    try:
        import epic_yaml as ey

        doc = ey.load_implement(path)
    except Exception as exc:
        return [f"implement_load_failed: {exc}"]
    blockers: list[str] = []
    if not ey.all_checkpoints_done(doc.checkpoints):
        pending = [cp.id for cp in doc.checkpoints if cp.status != "done"]
        blockers.append(
            f"checkpoints not done: {', '.join(pending) or '(unknown)'}"
        )
    gaps = doc.gaps
    if isinstance(gaps, dict) and str(gaps.get("status", "")).lower() == "blocked":
        blockers.append("gaps.status=blocked")
    elif isinstance(gaps, str) and gaps.strip().lower() == "blocked":
        blockers.append("gaps=blocked")
    return blockers


def coerce_verify_verdict(
    cwd: str | Path,
    verdict: str | None,
    *,
    evidence: dict[str, Any] | None = None,
) -> tuple[str | None, list[str]]:
    """Return (effective_verdict, demote_blockers). PASS→FAIL when step incomplete."""
    if not verdict:
        return None, []
    raw = str(verdict).upper()
    if raw != "PASS":
        return raw, []
    blockers = verify_pass_step_blockers(cwd)
    if blockers:
        return "FAIL", blockers
    return "PASS", []


def mirror_verify_verdict(
    cwd: str | Path,
    verdict: str | None,
    *,
    evidence: dict[str, Any] | None = None,
) -> None:
    if not verdict:
        return
    st = load_epic_state(cwd)
    if not st.get("active"):
        return
    effective, demote_blockers = coerce_verify_verdict(
        cwd, verdict, evidence=evidence
    )
    if not effective:
        return
    payload = dict(evidence or {})
    if demote_blockers:
        payload["demoted_from_pass"] = True
        payload["demote_blockers"] = demote_blockers
    st["last_verify_verdict"] = effective
    st["last_verify_at"] = utc_now()
    st["last_verify_evidence"] = payload
    save_epic_state(cwd, st)


def mirror_gate_verdict(
    cwd: str | Path,
    verdict: str | None,
    *,
    agent_id: str = "verify",
    evidence: dict[str, Any] | None = None,
) -> None:
    return mirror_verify_verdict(cwd, verdict, evidence=evidence)


def gate_evidence_matches(cwd: str | Path, evidence: object) -> tuple[bool, str]:
    """Match persisted verdict evidence against the current runner projection."""
    from _lib import gate_identity, match_gate_evidence

    state = load_epic_state(cwd)
    session_id = str(state.get("session_id") or "").strip()
    if not session_id:
        session_id = str(os.environ.get("EPIC_RUNNER_SESSION_ID") or "").strip()
        if not session_id and isinstance(evidence, dict):
            session_id = str(evidence.get("session_id") or "").strip()
        if session_id:
            state["session_id"] = session_id
            projection = state.get("projection")
            if isinstance(projection, dict):
                projection["session_id"] = session_id
            save_epic_state(cwd, state)
    return match_gate_evidence(evidence, gate_identity(state, session_id))



_INDEX_MD_NAME = "index.md"
_INDEX_YAML_NAMES = {"index.yaml", "index.yml"}


def _sibling_decompose_index_md(path: Path) -> Path | None:
    """Shard yaml/md in decompose-* dir → that dir's index.md. Else None."""
    parent = path.parent
    if not parent.name.startswith("decompose-"):
        return None
    cand = parent / _INDEX_MD_NAME
    return cand if cand.is_file() else None


def _decompose_index_path(cwd: str | Path, decompose: str | Path | None) -> Path | None:
    """Resolve human index.md (still used for hub links / mirror).

    Accepts index.md, index.yaml, a decompose-* directory, an epic id under
    memory-bank/*/plan/, or a step shard yaml sitting next to index.md.
    A shard must not be treated as the index itself (that desyncs yaml vs md).
    """
    if decompose is None or not isinstance(decompose, (str, Path)):
        return None
    if not decompose:
        return None
    root = Path(cwd)
    raw = str(decompose).replace("\\", "/")
    decompose = raw

    # Handle layout v2 decompose-index.yaml / decompose-index.md
    if raw.endswith("decompose-index.yaml"):
        md_cand = root / (raw[: -len("decompose-index.yaml")] + "decompose-index.md")
        if md_cand.is_file():
            return md_cand
        md_parent = root / raw[: -len("yaml/decompose-index.yaml")] / "md" / "decompose-index.md"
        if md_parent.is_file():
            return md_parent
        return root / raw

    if raw.endswith("decompose-index.md"):
        if (root / raw).is_file():
            return root / raw
        y_cand = root / (raw[: -len("decompose-index.md")] + "decompose-index.yaml")
        if y_cand.is_file():
            return y_cand
        y_parent = root / raw[: -len("md/decompose-index.md")] / "yaml" / "decompose-index.yaml"
        if y_parent.is_file():
            return y_parent
        return root / raw

    if raw.endswith("index.yaml"):
        raw = raw[: -len("index.yaml")] + "index.md"
        decompose = raw
    idx = root / decompose
    if idx.is_dir():
        if (idx / "md" / "decompose-index.md").is_file():
            return idx / "md" / "decompose-index.md"
        if (idx / "yaml" / "decompose-index.yaml").is_file():
            return idx / "yaml" / "decompose-index.yaml"
        idx = idx / _INDEX_MD_NAME
    elif idx.name in _INDEX_YAML_NAMES:
        idx = idx.with_name(_INDEX_MD_NAME)
    elif idx.is_file() and idx.name != _INDEX_MD_NAME:
        sibling = _sibling_decompose_index_md(idx)
        if sibling is not None:
            return sibling
        # v2 step in yaml/steps/
        if idx.parent.name == "steps" and idx.parent.parent.name == "yaml":
            v2_md = idx.parent.parent.parent / "md" / "decompose-index.md"
            if v2_md.is_file():
                return v2_md
            v2_yaml = idx.parent.parent / "decompose-index.yaml"
            if v2_yaml.is_file():
                return v2_yaml
        return None
    if idx.is_file():
        return idx
    # yaml-only tree: return md path even when md is absent (canon lives in yaml)
    if idx.name == _INDEX_MD_NAME and idx.with_name("index.yaml").is_file():
        return idx

    # If decompose is an epic path in v1 or v2 that is missing or relocated:
    for base in (
        root / "memory-bank" / "back" / "plan",
        root / "memory-bank" / "front" / "plan",
        root / "memory-bank" / "integration" / "plan",
    ):
        # check if it is an epic directory in v2
        cand_v2 = base / decompose / "md" / "decompose-index.md"
        if cand_v2.is_file():
            return cand_v2
        cand_v2_y = base / decompose / "yaml" / "decompose-index.yaml"
        if cand_v2_y.is_file():
            return cand_v2_y
        # if decompose is decompose-<epic_id> or decompose-<epic_id>/index.yaml, check migrated <epic_id>
        parts = Path(decompose).parts
        for p in parts:
            if p.startswith("decompose-"):
                epic_slug = p[len("decompose-"):]
                migrated_md = base / epic_slug / "md" / "decompose-index.md"
                if migrated_md.is_file():
                    return migrated_md
                migrated_y = base / epic_slug / "yaml" / "decompose-index.yaml"
                if migrated_y.is_file():
                    return migrated_y

    if str(decompose).endswith((".md", ".yaml", ".yml")):
        return None
    for base in (
        root / "memory-bank" / "back" / "plan",
        root / "memory-bank" / "front" / "plan",
        root / "memory-bank" / "integration" / "plan",
        root / "memory-bank" / "back" / "refactor" / "plan",
        root / "memory-bank" / "front" / "refactor" / "plan",
        root / "memory-bank" / "integration" / "refactor" / "plan",
        root / "memory-bank" / "back" / "security" / "plan",
        root / "memory-bank" / "front" / "security" / "plan",
        root / "memory-bank" / "integration" / "security" / "plan",
    ):
        cand = base / decompose / "index.md"
        if cand.is_file():
            return cand
    return None


def remap_decompose_to_archive(
    cwd: str | Path, decompose: str | Path | None
) -> str | None:
    """When live decompose index was moved to archive/, return archive rel path."""
    if decompose is None or not isinstance(decompose, (str, Path)):
        return None
    raw = str(decompose).replace("\\", "/")
    if "/archive/" in raw or raw.startswith("memory-bank/archive/"):
        return None
    parts = raw.split("/")
    if len(parts) < 4 or parts[0] != "memory-bank" or parts[1] == "archive":
        return None
    archived = "/".join(["memory-bank", "archive", *parts[1:]])
    idx = _decompose_index_path(cwd, archived)
    if idx is None:
        return None
    ypath = index_yaml_path(idx)
    if ypath.is_file():
        return archived
    return None


def decompose_index_yaml_exists(cwd: str | Path, decompose: str | Path | None) -> bool:
    if decompose is None or not isinstance(decompose, (str, Path)):
        return False
    idx = _decompose_index_path(cwd, decompose)
    if idx is None:
        return False
    return index_yaml_path(idx).is_file()


def complete_archived_armed_epic(cwd: str | Path) -> dict[str, Any] | None:
    """Disarm runtime when armed decompose only exists under memory-bank/archive/."""
    cwd_p = Path(cwd)
    state = load_epic_state(cwd_p)
    decompose = (state.get("armed_decompose") or "").strip()
    if not decompose:
        return None
    if decompose_index_yaml_exists(cwd_p, decompose):
        return None
    archived_rel = remap_decompose_to_archive(cwd_p, decompose)
    if not archived_rel:
        return None
    loaded = load_decompose_steps_fail_closed(cwd_p, archived_rel)
    if not loaded.get("ok"):
        return None
    steps = loaded.get("steps") or []
    if not steps:
        return None
    open_steps = [
        s.get("id")
        for s in steps
        if (s.get("status") or "").lower() not in {"completed", "done"}
    ]
    if open_steps:
        return None
    state["active"] = False
    state["status"] = "complete"
    state["halt_reason"] = None
    state["armed_epic"] = None
    state["armed_decompose"] = None
    state["armed_step"] = None
    state["pending_fingerprint_before"] = None
    state["load_now_before"] = []
    save_epic_state(cwd_p, state)
    return {
        "ok": True,
        "complete": True,
        "stop": "ARCHIVE_DONE",
        "reason": "ARCHIVE_DONE",
        "archived_decompose": archived_rel,
        "epic_id": epic_id_from_decompose_path(archived_rel),
    }


def _load_decompose_steps(
    cwd: str | Path, decompose: str | None
) -> tuple[Path | None, list[dict[str, str]], str]:
    """Return (md_path, steps, source) where source is 'yaml'|'md'."""
    idx = _decompose_index_path(cwd, decompose)
    if idx is None:
        return None, [], "missing"
    ypath = index_yaml_path(idx)
    if ypath.is_file():
        doc = load_index_yaml(ypath) or {}
        return idx, steps_from_doc(doc), "yaml"
    if not idx.is_file():
        return None, [], "missing"
    text = idx.read_text(encoding="utf-8", errors="replace")
    return idx, parse_steps_from_md(text), "md"


def _index_result(
    status: str,
    diagnostic_code: str,
    *,
    idx: Path | None = None,
    steps: list[dict[str, str]] | None = None,
    source: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": status == "resolved",
        "status": status,
        "diagnostic_code": diagnostic_code,
        "steps": steps or [],
        "source": source,
    }
    if idx is not None:
        result["index"] = str(idx)
    if message:
        result["message"] = message
    return result


def load_decompose_steps_fail_closed(
    cwd: str | Path, decompose: str | Path | None
) -> dict[str, Any]:
    """Load status-canon index.yaml; md is never a fail-closed gate."""
    if decompose is None or not isinstance(decompose, (str, Path)):
        error = f"invalid_arg: expected str/Path, got {type(decompose).__name__}"
        result = _index_result("invalid", "invalid_arg", message=error)
        result["error"] = error
        return result
    idx = _decompose_index_path(cwd, decompose)
    if idx is None:
        archived = remap_decompose_to_archive(cwd, decompose)
        if archived:
            decompose = archived
            idx = _decompose_index_path(cwd, decompose)
    if idx is None:
        return _index_result("not_found", "index_not_found", message=str(decompose or ""))

    ypath = index_yaml_path(idx)
    if ypath.is_file():
        try:
            doc = load_index_yaml(ypath)
        except (OSError, TypeError, ValueError, yaml.YAMLError) as exc:
            return _index_result("invalid", "index_invalid", idx=idx, message=str(exc))
        if not isinstance(doc, dict):
            return _index_result("invalid", "index_invalid", idx=idx)
        yaml_steps = steps_from_doc(doc)
        if not yaml_steps:
            return _index_result("invalid", "index_invalid", idx=idx, message="index has no steps")
        # index.yaml is sole SoT — do not fail-closed on human md drift.
        return _index_result("resolved", "index_loaded", idx=idx, steps=yaml_steps, source="yaml")

    if not idx.is_file():
        return _index_result("not_found", "index_not_found", message=str(decompose or ""))

    try:
        text = idx.read_text(encoding="utf-8", errors="replace")
        md_steps = parse_steps_from_md(text)
    except OSError as exc:
        return _index_result("invalid", "index_invalid", idx=idx, message=str(exc))
    ids = [s.get("id") for s in md_steps]
    if not md_steps or len(ids) != len(set(ids)):
        return _index_result("ambiguous", "index_ambiguous", idx=idx)
    return _index_result("resolved", "index_loaded", idx=idx, steps=md_steps, source="md")


def _row_status_from_body(body: str) -> str | None:
    words = "|".join(_STEP_STATUS_WORDS)
    status_cell = rf"\**\s*({words})\s*\**"
    found = re.findall(rf"\|\s*{status_cell}\s*\|", body, flags=re.I)
    if found:
        return found[-1].lower()
    m_end = re.search(rf"(?i)\|\s*{status_cell}\s*$", body.rstrip())
    return m_end.group(1).lower() if m_end else None


def _iter_index_step_rows(index_text: str):
    for m in re.finditer(
        r"(?im)^\|\s*\*\*([sera]\d{2})\*\*\s*\|(?P<body>.*)$",
        index_text,
    ):
        body = "|" + m.group("body")
        yield m.group(1).lower(), body, m.group("body")


def _index_plan_id(idx: Path) -> str:
    ypath = index_yaml_path(idx)
    if not ypath.is_file():
        return ""
    try:
        doc = load_index_yaml(ypath) or {}
    except Exception:
        return ""
    if not isinstance(doc, dict):
        return ""
    return str(doc.get("plan_id") or "").strip()


def _implement_yaml_completed(
    cwd: str | Path,
    role: str,
    epic_id: str,
    step_id: str,
    *,
    plan_id: str | None = None,
) -> bool:
    try:
        import epic_yaml as ey

        rel = ey.resolve_implement_path(
            cwd, role, epic_id, step_id.strip().lower(), plan_id=plan_id
        )
        return ey.implement_completed(cwd, rel)
    except Exception:
        return False


def _resolve_implement_shard(
    cwd: str | Path,
    *,
    idx: Path,
    step_id: str,
    implement: str | Path | None = None,
) -> tuple[Path | None, str | None]:
    cwd_p = Path(cwd)
    role, role_dir = _role_dir_from_index_path(idx, cwd_p)
    epic_id = epic_id_from_decompose_path(str(idx)) or ""
    if not role or not role_dir or not epic_id:
        return None, "failed to resolve role/epic for implement shard"
    try:
        import epic_yaml as ey

        if implement:
            rel = str(implement).strip().replace("\\", "/")
        else:
            rel = ey.resolve_implement_path(
                cwd_p,
                role_dir,
                epic_id,
                step_id.strip().lower(),
                plan_id=_index_plan_id(idx) or None,
            )
        path = cwd_p / rel
        if not path.is_file():
            return None, f"implement shard not found: {rel}"
        return path, None
    except Exception as exc:
        return None, f"failed to resolve implement shard: {exc}"


def _verify_pass_ready_for_step(cwd: str | Path, step_id: str) -> dict[str, Any]:
    state = load_epic_state(cwd)
    verdict = str(state.get("last_verify_verdict") or "").upper()
    evidence = state.get("last_verify_evidence")
    if verdict != "PASS":
        return {
            "ok": False,
            "error": "verify PASS required before finalize-step",
            "diagnostic": "verify_pass_missing",
            "verdict": verdict or None,
        }
    sid = step_id.strip().lower()
    if isinstance(evidence, dict):
        evidence_step = str(evidence.get("step") or "").strip().lower()
        if evidence_step and evidence_step != sid:
            return {
                "ok": False,
                "error": "verify PASS is stale or not bound to the current step",
                "diagnostic": "verdict_wrong_step",
                "verdict": verdict,
                "evidence": evidence,
            }
    matched, diagnostic = gate_evidence_matches(cwd, evidence)
    if matched:
        return {
            "ok": True,
            "diagnostic": diagnostic,
            "verdict": verdict,
            "evidence": evidence,
        }
    return {
        "ok": False,
        "error": "verify PASS is stale or not bound to the current step",
        "diagnostic": diagnostic,
        "verdict": verdict,
        "evidence": evidence if isinstance(evidence, dict) else None,
    }


def _implement_load_now_lines(
    *,
    shard_rel: str,
    yaml_rel: str,
    step_id: str,
    phase: str,
) -> list[str]:
    shard_link = shard_rel.removeprefix("memory-bank/")
    yaml_link = yaml_rel.removeprefix("memory-bank/")
    return [
        f"1. [{Path(shard_rel).name}]({shard_link}) — текущий work shard "
        f"({phase} {step_id}).",
        f"2. [{Path(yaml_rel).name}]({yaml_link}) — очередь/status (canon=yaml).",
    ]


def _try_advance_active_context(
    cwd: Path,
    idx: Path,
    doc: dict[str, Any],
    completed_status: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": True,
        "next_step": None,
        "activeContext_rewritten": False,
        "armed_step_updated": False,
    }
    if completed_status not in {"completed", "done"}:
        return result

    try:
        next_step = find_next_step(steps_from_doc(doc))
        if not next_step:
            return result
        step_id = str(next_step.get("id") or next_step.get("step_id") or "").strip()
        shard = _resolve_href(
            _decompose_step_shards_dir(idx),
            str(next_step.get("file") or ""),
            cwd,
        )
        if not step_id or not shard:
            raise FileNotFoundError(
                f"next step shard not found: {next_step.get('file')!r}"
            )

        yaml_path = index_yaml_path(idx)
        yaml_rel = yaml_path.relative_to(cwd).as_posix()
        phase = str(next_step.get("next_phase") or "BACK IMPLEMENT")
        epic_id = epic_id_from_decompose_path(yaml_rel) or "unknown"
        role_token, _role_dir = _role_dir_from_index_path(idx, cwd)
        shard_link = shard.removeprefix("memory-bank/")
        yaml_link = yaml_rel.removeprefix("memory-bank/")
        atomic_write_text(
            active_context_path(cwd),
            _render_loop_active_context(
                role=role_token or "BACK",
                mode=phase,
                epic_id=epic_id,
                step_id=step_id,
                load_now=[
                    (
                        shard_link,
                        f"текущий work shard ({phase} {step_id})",
                    ),
                    (
                        yaml_link,
                        "очередь/status (canon=yaml)",
                    ),
                ],
                custom_lines=[
                    f"- **Эпик:** {epic_id}.",
                    f"- **Режим/шаг:** следующий {phase} `{step_id}`.",
                    f"- **Сделано:** предыдущий шаг отмечен `{completed_status}`.",
                ],
                next_hint=f"продолжить с work shard `{shard}`",
            ),
        )
        result["next_step"] = step_id
        result["activeContext_rewritten"] = True

        # Stale prepare checkpoint still has old step → identity_conflict on next prepare.
        cp = load_checkpoint(cwd)
        if cp and (
            (cp.get("identity") or {}).get("step") != step_id
            or cp.get("step_id") != step_id
        ):
            checkpoint_path(cwd).unlink(missing_ok=True)
            checkpoint_lock_path(cwd).unlink(missing_ok=True)
            result["checkpoint_cleared"] = True

        state = load_epic_state(cwd)
        state["armed_step"] = step_id
        state["pending_fingerprint_before"] = None
        save_epic_state(cwd, state)
        result["armed_step_updated"] = True
    except Exception as exc:
        logger.warning("Failed to advance activeContext after mark-index: %s", exc)
        result["ok"] = False
        result["error"] = str(exc)
        result["activeContext_rewritten"] = False
    return result


def mark_index_step_status(
    cwd: str | Path,
    decompose: str | None,
    step_id: str,
    status: str,
    *,
    sync_checklist: bool = True,
) -> dict[str, Any]:
    """One write path: update index.yaml (canon) + mirror status into index.md.

    Agents must not edit status in md/yaml by hand — only this helper.
    """
    status_l = (status or "").strip().lower()
    if status_l not in set(_STEP_STATUS_WORDS):
        return {
            "ok": False,
            "error": f"status must be one of {_STEP_STATUS_WORDS}, got {status!r}",
        }
    sid = step_id.strip().lower()
    if not re.match(r"^[sera]\d{2}$", sid):
        return {"ok": False, "error": f"bad step_id: {step_id!r}"}
    if decompose is None or not isinstance(decompose, (str, Path)):
        return {
            "ok": False,
            "error": f"invalid_arg: expected str/Path, got {type(decompose).__name__}",
        }
    idx = _decompose_index_path(cwd, decompose)
    if idx is None:
        return {"ok": False, "error": f"missing decompose index: {decompose}"}

    cwd_p = Path(cwd)
    ypath = index_yaml_path(idx)
    if not ypath.is_file():
        if not idx.is_file():
            return {"ok": False, "error": f"missing decompose index: {decompose}"}
        boot = sync_yaml_from_md(idx, preserve_yaml_status=False)
        if not boot.get("ok"):
            return boot
    elif not idx.is_file():
        boot_md = rebuild_md_queue_from_yaml(idx)
        if not boot_md.get("ok"):
            return {
                "ok": False,
                "error": boot_md.get("error") or "failed to create index.md from yaml",
            }

    doc = load_index_yaml(ypath)
    if doc is None:
        return {"ok": False, "error": f"failed to load {ypath}"}
    if status_l in {"completed", "done"}:
        role, role_dir = _role_dir_from_index_path(idx, cwd_p)
        epic_id = epic_id_from_decompose_path(str(idx)) or ""
        plan_id = str(doc.get("plan_id") or "").strip()
        try:
            import epic_yaml as ey

            impl_rel = ey.resolve_implement_path(
                cwd_p, role_dir or role, epic_id, sid, plan_id=plan_id or None
            )
            impl_path = cwd_p / impl_rel
        except Exception:
            impl_rel = ""
            impl_path = None
        if impl_path is not None and impl_path.is_file():
            try:
                import epic_yaml as ey

                state = ey.implement_load_state(cwd_p, impl_rel)
            except Exception as exc:
                state = {"completed": False, "load_error": str(exc)}
            if state.get("load_error"):
                return {
                    "ok": False,
                    "error": (
                        f"refuse mark-index-status {status_l} for {sid}: "
                        f"implement yaml invalid — {state['load_error']}; "
                        "fix shard (validate-step) then use finalize-step"
                    ),
                    "diagnostic": INDEX_IMPLEMENT_CONFLICT,
                    "implement_path": impl_rel,
                    "step_id": sid,
                }
            if not state.get("completed"):
                return {
                    "ok": False,
                    "error": (
                        f"refuse mark-index-status {status_l} for {sid}: "
                        "implement yaml exists but is not completed — "
                        "use finalize-step after IMPLEMENT; "
                        "CREATIVE must not mark the step completed"
                    ),
                    "diagnostic": INDEX_IMPLEMENT_CONFLICT,
                    "implement_path": impl_rel,
                    "step_id": sid,
                }
    old_st = set_step_status_in_doc(doc, sid, status_l)
    if old_st is None:
        return {"ok": False, "error": f"step {sid} not found in {ypath.name}"}

    unchanged = old_st == status_l
    yaml_written = False
    if not unchanged:
        ypath.write_text(dump_index_yaml(doc), encoding="utf-8")
        yaml_written = True

    # yaml is SoT — md mirror is best-effort (rebuild queue if row missing).
    md_rebuilt = False
    mirror = mirror_status_to_md(
        idx, sid, status_l, sync_checklist=sync_checklist
    )
    if not mirror.get("ok"):
        rebuilt = rebuild_md_queue_from_yaml(idx)
        md_rebuilt = bool(rebuilt.get("ok"))
        if md_rebuilt:
            mirror = mirror_status_to_md(
                idx, sid, status_l, sync_checklist=sync_checklist
            )
            if not mirror.get("ok"):
                # Table already has statuses from yaml rebuild — treat as mirrored.
                mirror = {
                    "ok": True,
                    "mirrored": True,
                    "unchanged": False,
                    "checklist_updated": False,
                    "via": "rebuild_md_queue_from_yaml",
                }

    rel_y = (
        str(ypath.relative_to(cwd_p))
        if ypath.is_relative_to(cwd_p)
        else str(ypath)
    )
    rel_md = (
        str(idx.relative_to(cwd_p)) if idx.is_relative_to(cwd_p) else str(idx)
    )
    if not mirror.get("ok"):
        # Keep yaml; do not roll back. Runner continues on canon.
        advance = _try_advance_active_context(cwd_p, idx, doc, status_l)
        return {
            "ok": True,
            "path": rel_y,
            "md_path": rel_md,
            "step_id": sid,
            "status": status_l,
            "previous": old_st,
            "unchanged": unchanged,
            "checklist_updated": False,
            "canon": "index.yaml",
            "mirrored_md": False,
            "md_mirror_degraded": True,
            "md_error": mirror.get("error"),
            "md_rebuilt": md_rebuilt,
            "yaml_rolled_back": False,
            "next_step": advance.get("next_step"),
            "activeContext_rewritten": bool(advance.get("activeContext_rewritten")),
            "armed_step_updated": bool(advance.get("armed_step_updated")),
            "advance_diagnostic": advance,
        }

    advance = _try_advance_active_context(cwd_p, idx, doc, status_l)
    return {
        "ok": True,
        "path": rel_y,
        "md_path": rel_md,
        "step_id": sid,
        "status": status_l,
        "previous": old_st,
        "unchanged": unchanged and mirror.get("unchanged", False),
        "checklist_updated": bool(mirror.get("checklist_updated")),
        "canon": "index.yaml",
        "mirrored_md": True,
        "md_rebuilt": md_rebuilt,
        "next_step": advance.get("next_step"),
        "activeContext_rewritten": bool(advance.get("activeContext_rewritten")),
        "armed_step_updated": bool(advance.get("armed_step_updated")),
        "advance_diagnostic": advance,
    }


def repair_index_mirror(
    cwd: str | Path,
    decompose: str | Path | None,
) -> dict[str, Any]:
    """Diagnostic logger and counter for index mirror drift. Does not write md.

    Sunset: auto md-write purged in s16.
    """
    increment_drift_counter(cwd, "index_mirror_repair")
    logger.warning("repair_index_mirror called: diagnostic log only (auto-rewrite purged)")
    if decompose is None or not isinstance(decompose, (str, Path)):
        return {
            "ok": False,
            "error": f"invalid_arg: expected str/Path, got {type(decompose).__name__}",
        }
    idx = _decompose_index_path(cwd, decompose)
    if idx is None:
        archived = remap_decompose_to_archive(cwd, decompose)
        if archived:
            decompose = archived
            idx = _decompose_index_path(cwd, decompose)
    if idx is None:
        return {"ok": False, "error": f"missing decompose index: {decompose}"}
    ypath = index_yaml_path(idx)
    if not ypath.is_file():
        return {"ok": False, "error": f"missing {ypath}"}
    drift = md_queue_drift_from_yaml(idx)
    loaded = load_decompose_steps_fail_closed(cwd, str(ypath))
    cwd_p = Path(cwd)
    rel_md = str(idx.relative_to(cwd_p)) if idx.is_relative_to(cwd_p) else str(idx)
    rel_y = str(ypath.relative_to(cwd_p)) if ypath.is_relative_to(cwd_p) else str(ypath)
    return {
        "ok": bool(loaded.get("ok")),
        "canon": "index.yaml",
        "md_path": rel_md,
        "yaml_path": rel_y,
        "mirrored_steps": [],
        "md_rebuilt": False,
        "mode": "log_only",
        "drift": drift,
        "diagnostic_code": loaded.get("diagnostic_code"),
        "warning": "auto-rewrite purged (diagnostic log only)",
    }


def _step_id_from_active_context(text: str) -> str | None:
    """First sNN/eNN from load_now paths (agent work cursor)."""
    for raw in extract_load_now(text):
        m = re.search(r"(?:^|/)([sera]\d{2})-", raw.replace("\\", "/"))
        if m:
            return m.group(1).lower()
    return None


def _implement_files_on_disk(cwd: Path, files: list[Any]) -> tuple[bool, list[str]]:
    missing: list[str] = []
    for raw in files or []:
        rel = str(raw or "").strip()
        if not rel or rel.startswith(("http://", "https://")):
            continue
        if not (cwd / rel).is_file():
            missing.append(rel)
    return (not missing), missing


def sync_cursor_from_index(cwd: str | Path) -> dict[str, Any]:
    """Make activeContext + armed_step match index.yaml next pending (SoT).

    armed_step / AC are caches — never win over index.yaml for IMPLEMENT queue.
    Skips non-implement phases (DECOMPOSE/AUDIT/QA/REFLECT/DONE/…).
    """
    cwd_p = Path(cwd)
    state = load_epic_state(cwd_p)
    decompose = (state.get("armed_decompose") or "").strip()
    if not decompose:
        return {"ok": True, "synced": False, "reason": "no_decompose"}

    armed = str(state.get("armed_step") or "").strip()
    armed_u = armed.upper()
    if armed_u in {
        "DECOMPOSE",
        "ANALYZE",
        "CLARIFY",
        "AUDIT",
        "QA",
        "BUGFIX",
        "REFLECT",
        "DONE",
        "CREATIVE",
        "PLAN",
        "ARCHIVE",
    }:
        return {
            "ok": True,
            "synced": False,
            "reason": "non_implement_phase",
            "armed_step": armed,
        }

    loaded = load_decompose_steps_fail_closed(cwd_p, decompose)
    if not loaded.get("ok"):
        return {
            "ok": False,
            "synced": False,
            "reason": "index_load_failed",
            "diagnostic_code": loaded.get("diagnostic_code"),
        }
    steps = loaded.get("steps") or []
    idx_path = Path(loaded.get("index") or decompose)
    role_dir = "back"
    if "/front/" in decompose.replace("\\", "/"):
        role_dir = "front"
    elif "/integration/" in decompose.replace("\\", "/"):
        role_dir = "integration"
    epic_id = str(state.get("armed_epic") or "").strip()
    if not epic_id:
        epic_id = epic_id_from_decompose_path(decompose)
    if epic_id:
        from analyze_gate import analyze_required_before_implement
        from epic_index import index_yaml_path

        gate_index = index_yaml_path(idx_path)
        if not gate_index.is_file():
            gate_index = idx_path
        gate = analyze_required_before_implement(
            cwd_p, role_dir, epic_id, steps, index_path=gate_index
        )
        if gate.get("required"):
            from loop.epic_transition import arm_phase

            arm_decomp = decompose
            if arm_decomp.endswith(("/index.yaml", "/index.yml", "/index.md")):
                arm_decomp = str(Path(arm_decomp).parent).replace("\\", "/")
            arm_res = arm_phase(
                cwd_p,
                epic_id,
                "ANALYZE",
                role_dir,
                decompose_rel=arm_decomp,
            )
            if isinstance(arm_res, dict) and arm_res.get("ok"):
                return {
                    "ok": True,
                    "synced": True,
                    "reason": "analyze_gate_rearm",
                    "analyze_reason": gate.get("reason"),
                    "previous_armed": armed or None,
                    "step_id": "ANALYZE",
                    "armed_step": "ANALYZE",
                }
            return {
                "ok": True,
                "synced": False,
                "reason": "analyze_gate_pending",
                "analyze_reason": gate.get("reason"),
                "armed_step": armed or None,
            }
    next_step = find_next_step(steps)
    text = read_active_context(cwd_p)
    ac_step = _step_id_from_active_context(text)

    if next_step is None:
        text = read_active_context(cwd_p)
        handoff_phase = handoff_post_implement_phase(text)
        if handoff_phase in {"AUDIT", "QA", "BUGFIX"}:
            if not epic_id:
                epic_id = epic_id_from_decompose_path(decompose) or ""
            if epic_id:
                from loop.schemas.active_context import post_implement_phase_rank

                decision = reduce_epic_lifecycle(cwd_p, role_dir, epic_id)
                lifecycle_phase = str(decision.get("phase") or "QA").upper()
                handoff_rank = post_implement_phase_rank(handoff_phase)
                lifecycle_rank = post_implement_phase_rank(lifecycle_phase)
                if handoff_rank > lifecycle_rank:
                    return {
                        "ok": False,
                        "halt": True,
                        "synced": False,
                        "reason": (
                            f"Handoff указывает {handoff_phase}, lifecycle — "
                            f"{lifecycle_phase}; завершай фазу через "
                            f"mb-finish {lifecycle_phase.lower()} (не mb-finish handoff)"
                        ),
                        "diagnostic_code": "handoff_ahead_of_lifecycle",
                        "handoff_phase": handoff_phase,
                        "lifecycle_phase": lifecycle_phase,
                    }
                if handoff_rank == lifecycle_rank:
                    return {
                        "ok": True,
                        "synced": False,
                        "reason": "handoff_aligned",
                        "armed_step": handoff_phase,
                    }
        # Queue exhausted — arm may promote to AUDIT/QA/REFLECT/DONE.
        arm = arm_active_context_from_decompose(cwd_p, decompose)
        return {
            "ok": bool(arm.get("ok")),
            "synced": True,
            "mode": "queue_exhausted",
            "previous_armed": armed or None,
            "previous_ac": ac_step,
            "arm": arm,
            "complete": bool(arm.get("complete")),
            "step_id": arm.get("step_id") or arm.get("phase"),
        }

    next_id = str(next_step.get("id") or "").strip().lower()
    if armed == next_id and ac_step == next_id:
        return {
            "ok": True,
            "synced": False,
            "reason": "already_aligned",
            "step_id": next_id,
        }

    arm = arm_active_context_from_decompose(cwd_p, decompose)
    ok = bool(arm.get("ok")) and not arm.get("complete")
    if arm.get("complete"):
        ok = bool(arm.get("ok"))
    return {
        "ok": ok,
        "synced": ok,
        "mode": "rearm_from_index",
        "previous_armed": armed or None,
        "previous_ac": ac_step,
        "step_id": arm.get("step_id") or next_id,
        "arm": arm,
    }


def repair_fingerprint_stall(cwd: str | Path) -> dict[str, Any]:
    """Deterministic recovery when agent did the step but forgot Handoff/load_now.

    Uses index.yaml + implement shard + filesystem files. No LLM.
    Modes:
    - rearm: index already completed for the AC step → rewrite activeContext
    - mark_index: implement already completed → mark index + advance
    - finalize_evidence: implement ready (cps/files/done) → finalize without verify
    """
    cwd_p = Path(cwd)
    state = load_epic_state(cwd_p)
    decompose = (state.get("armed_decompose") or "").strip()
    if not decompose:
        identity = resolve_pipeline_identity(cwd_p)
        if identity.get("status") == "resolved":
            decompose = str(identity.get("decompose") or "")
    if not decompose:
        return {"ok": False, "repaired": False, "reason": "no_decompose"}

    loaded = load_decompose_steps_fail_closed(cwd_p, decompose)
    if not loaded.get("ok"):
        return {
            "ok": False,
            "repaired": False,
            "reason": "index_load_failed",
            "diagnostic_code": loaded.get("diagnostic_code"),
        }
    steps = loaded.get("steps") or []
    idx = Path(loaded["index"])
    text = read_active_context(cwd_p)
    step_id = _step_id_from_active_context(text) or str(
        state.get("armed_step") or ""
    ).strip().lower()
    if not step_id or not re.match(r"^[sera]\d{2}$", step_id):
        return {"ok": False, "repaired": False, "reason": "no_step_id"}

    cur = next((s for s in steps if str(s.get("id") or "") == step_id), None)
    if cur is None:
        return {
            "ok": False,
            "repaired": False,
            "reason": "step_not_in_index",
            "step_id": step_id,
        }

    st_status = str(cur.get("status") or "").lower()
    if st_status in {"completed", "done"}:
        arm = arm_active_context_from_decompose(cwd_p, str(idx))
        ok = bool(arm.get("ok")) and not arm.get("complete")
        if arm.get("complete"):
            # all steps done — arm may return complete; still a successful repair
            ok = bool(arm.get("ok"))
        if ok:
            st = load_epic_state(cwd_p)
            st["pending_fingerprint_before"] = None
            save_epic_state(cwd_p, st)
        return {
            "ok": ok,
            "repaired": ok,
            "mode": "rearm_completed_step",
            "step_id": step_id,
            "arm": arm,
        }

    implement_path, err = _resolve_implement_shard(
        cwd_p, idx=idx, step_id=step_id, implement=None
    )
    if err or implement_path is None or not implement_path.is_file():
        return {
            "ok": False,
            "repaired": False,
            "reason": "implement_missing",
            "step_id": step_id,
            "error": err,
        }

    try:
        import epic_yaml as ey

        doc = ey.load_implement(implement_path)
    except Exception as exc:
        return {
            "ok": False,
            "repaired": False,
            "reason": "implement_load_failed",
            "step_id": step_id,
            "error": str(exc),
        }

    files_ok, missing_files = _implement_files_on_disk(cwd_p, list(doc.files or []))
    ready_errors = ey.implement_ready_for_finalize_doc(doc)
    if doc.status == "completed":
        ready_errors = [
            e for e in ready_errors if e.startswith("checkpoints not done")
        ]

    if doc.status == "completed" and not any(
        e.startswith("checkpoints not done") for e in ready_errors
    ):
        marked = mark_index_step_status(
            cwd_p, str(idx), step_id, "completed", sync_checklist=True
        )
        ok = bool(marked.get("ok"))
        if ok:
            st = load_epic_state(cwd_p)
            st["pending_fingerprint_before"] = None
            save_epic_state(cwd_p, st)
        return {
            "ok": ok,
            "repaired": ok,
            "mode": "mark_index_after_implement_completed",
            "step_id": step_id,
            "mark": marked,
        }

    if ready_errors or not files_ok:
        return {
            "ok": False,
            "repaired": False,
            "reason": "insufficient_evidence",
            "step_id": step_id,
            "ready_errors": ready_errors,
            "missing_files": missing_files,
            "implement_status": doc.status,
        }

    # Strong evidence: finalize without verify (agent finished work, forgot Handoff).
    fin = finalize_step(
        cwd_p,
        str(idx),
        step_id,
        require_verify=False,
        sync_checklist=True,
    )
    ok = bool(fin.get("ok"))
    if ok:
        st = load_epic_state(cwd_p)
        st["pending_fingerprint_before"] = None
        save_epic_state(cwd_p, st)
    return {
        "ok": ok,
        "repaired": ok,
        "mode": "finalize_evidence",
        "step_id": step_id,
        "finalize": fin,
        "verify_skipped": True,
    }


def finalize_step(
    cwd: str | Path,
    decompose: str | Path | None,
    step_id: str,
    *,
    implement: str | Path | None = None,
    sync_checklist: bool = True,
    require_verify: bool = True,
) -> dict[str, Any]:
    """Atomically set implement status=completed + mark index completed.

    Agent leaves implement at in_progress (evidence + cp done). This API is the
    only writer of implement completed together with index. On index failure,
    implement is rolled back to in_progress so prepare never sees half-done.

    require_verify=False — только deterministic repair (fingerprint stall), когда
    implement shard + files на диске уже доказывают готовность шага.
    """
    sid = step_id.strip().lower()
    if not re.match(r"^[sera]\d{2}$", sid):
        return {"ok": False, "error": f"bad step_id: {step_id!r}"}
    idx = _decompose_index_path(cwd, decompose)
    if idx is None:
        return {"ok": False, "error": f"missing decompose index: {decompose}"}
    ypath = index_yaml_path(idx)
    if not idx.is_file() and not ypath.is_file():
        return {"ok": False, "error": f"missing decompose index: {decompose}"}
    implement_path, err = _resolve_implement_shard(
        cwd,
        idx=idx,
        step_id=sid,
        implement=implement,
    )
    if err:
        return {"ok": False, "error": err, "step_id": sid}
    if require_verify:
        verify = _verify_pass_ready_for_step(cwd, sid)
        if not verify.get("ok"):
            return {
                "ok": False,
                "error": str(verify.get("error") or "verify PASS required"),
                "diagnostic": verify.get("diagnostic"),
                "step_id": sid,
            }
    else:
        verify = {"ok": True, "diagnostic": "verify_skipped_evidence_repair"}
    try:
        import epic_yaml as ey

        rel = str(implement_path.relative_to(Path(cwd))).replace("\\", "/")
        doc = ey.load_implement(implement_path)
        if str(doc.step_id).strip().lower() != sid:
            return {
                "ok": False,
                "error": (
                    f"implement shard step_id mismatch: expected {sid}, "
                    f"got {doc.step_id!r}"
                ),
                "implement_path": rel,
                "step_id": sid,
            }
        ready_errors = ey.implement_ready_for_finalize_doc(doc)
        if doc.status == "completed":
            ready_errors = [
                e for e in ready_errors if e.startswith("checkpoints not done")
            ]
        if ready_errors:
            return {
                "ok": False,
                "error": "implement shard not ready for finalize",
                "errors": ready_errors,
                "implement_path": rel,
                "step_id": sid,
            }
        status_before = doc.status
        if status_before != "completed":
            set_res = ey.set_implement_status(implement_path, "completed")
            if not set_res.get("ok"):
                return {
                    "ok": False,
                    "error": str(set_res.get("error") or "failed to set completed"),
                    "implement_path": rel,
                    "step_id": sid,
                }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"failed to validate implement shard: {exc}",
            "step_id": sid,
        }
    marked = mark_index_step_status(
        cwd,
        str(idx),
        sid,
        "completed",
        sync_checklist=sync_checklist,
    )
    if not marked.get("ok"):
        try:
            import epic_yaml as ey

            rollback = ey.set_implement_status(implement_path, "in_progress")
        except Exception as exc:
            rollback = {"ok": False, "error": str(exc)}
        marked["implement_path"] = rel
        marked["implement_status_before"] = status_before
        marked["rolled_back_implement"] = bool(rollback.get("ok"))
        marked["rollback"] = rollback
        marked["diagnostic"] = "finalize_index_failed_rolled_back"
        return marked
    marked["finalized"] = True
    marked["implement_path"] = rel
    marked["implement_status_before"] = status_before
    marked["implement_completed_by_finalize"] = status_before != "completed"
    marked["verify_diagnostic"] = verify.get("diagnostic")
    st = load_epic_state(cwd)
    st["last_verify_verdict"] = None
    st["last_verify_at"] = None
    st["last_verify_evidence"] = None
    save_epic_state(cwd, st)
    cwd_p = Path(cwd)
    role, _role_dir = _role_dir_from_index_path(idx, cwd_p)
    epic_id = epic_id_from_decompose_path(
        str(idx.relative_to(cwd_p)) if idx.is_relative_to(cwd_p) else str(idx)
    ) or ""
    if epic_id:
        _append_event(cwd_p, _role_dir, epic_id, "implement_done", implement_path)
    loaded = load_decompose_steps_fail_closed(cwd_p, str(idx))
    pending = [
        s
        for s in (loaded.get("steps") or [])
        if str(s.get("status") or "").lower() not in {"completed", "done"}
    ]
    all_completed = bool(loaded.get("ok")) and not pending
    marked["portfolio"] = sync_portfolio_after_step(
        cwd_p,
        epic_id=epic_id,
        role=role,
        step_id=sid,
        artifact=rel,
        all_completed=all_completed,
    )
    if all_completed:
        marked["post_implement"] = arm_epic(cwd_p, epic_id, role=_role_dir)
    try:
        from loop.epic_transition import promote_if_ready

        promoted = promote_if_ready(cwd_p, epic_id, role)
        if isinstance(promoted, dict) and promoted.get("ok"):
            marked["promoted"] = promoted
    except Exception:
        pass
    try:
        from loop.git_discipline import maybe_atomic_commit

        step_title = ""
        for s in loaded.get("steps") or []:
            if str(s.get("id") or "").strip().lower() == sid:
                step_title = str(s.get("title") or "")
                break
        commit_res = maybe_atomic_commit(
            cwd=cwd_p,
            epic_id=epic_id,
            step_id=sid,
            title=step_title,
        )
        marked["atomic_commit"] = commit_res.model_dump()
    except Exception as exc:
        marked["atomic_commit"] = {
            "ok": False,
            "skipped": False,
            "error": str(exc),
        }
    marked["session_boundary"] = True
    try:
        current_chk = load_checkpoint(cwd_p)
        if current_chk:
            current_meta = dict(current_chk.get("metadata") or {})
            current_meta["session_boundary"] = True
            commit_checkpoint(
                cwd_p,
                checkpoint_id=current_chk.get("checkpoint_id") or f"finalize-{sid}",
                session_id=current_chk.get("session_id") or "finalize",
                runner_id=current_chk.get("runner_id"),
                identity=current_chk.get("identity"),
                step_id=sid,
                phase=current_chk.get("phase") or "IMPLEMENT",
                phase_epoch=current_chk.get("phase_epoch") or 1,
                projection_hash=current_chk.get("projection_hash"),
                stage=current_chk.get("stage") or "committed",
                status=current_chk.get("status") or "committed",
                next_action=current_chk.get("next_action") or "none",
                resume_policy=current_chk.get("resume_policy") or "next_step",
                context_fingerprint=current_chk.get("context_fingerprint"),
                index_fingerprint=current_chk.get("index_fingerprint"),
                retry_count=current_chk.get("retry_count", 0),
                degraded_count=current_chk.get("degraded_count", 0),
                session_boundary=True,
                reason=current_chk.get("reason"),
                metadata=current_meta,
            )
    except Exception:
        pass
    return marked


def repair_finish_desync(
    cwd: str | Path,
    decompose: str | Path | None,
) -> dict[str, Any]:
    """Roll implement completed → in_progress when index step is still open.

    Clears mark_index_missing half-done without auto-marking the index.
    """
    loaded = load_decompose_steps_fail_closed(cwd, decompose)
    if not loaded["ok"]:
        return {
            "ok": False,
            "repaired": [],
            "error": str(loaded.get("message") or loaded.get("error") or decompose),
        }
    idx = Path(loaded["index"])
    cwd_p = Path(cwd)
    epic_id = epic_id_from_decompose_path(str(idx)) or ""
    _role, role_dir = _role_dir_from_index_path(idx, cwd_p)
    repaired: list[str] = []
    details: list[dict[str, Any]] = []
    import epic_yaml as ey

    for step in loaded["steps"]:
        sid = str(step.get("id") or "").strip().lower()
        status = str(step.get("status") or "").lower()
        if not sid or status in {"completed", "done"}:
            continue
        plan_id = _index_plan_id(idx)
        if not _implement_yaml_completed(
            cwd_p, role_dir, epic_id, sid, plan_id=plan_id or None
        ):
            continue
        try:
            rel = ey.resolve_implement_path(
                cwd_p, role_dir, epic_id, sid, plan_id=plan_id or None
            )
            found = cwd_p / rel
        except Exception as exc:
            details.append({"step_id": sid, "ok": False, "error": str(exc)})
            continue
        if not found.is_file():
            details.append({"step_id": sid, "ok": False, "error": "implement missing"})
            continue
        res = ey.set_implement_status(found, "in_progress")
        details.append({"step_id": sid, **res, "path": str(found)})
        if res.get("ok") and res.get("changed"):
            repaired.append(sid)
        elif res.get("ok") and res.get("previous") == "completed":
            repaired.append(sid)
    return {
        "ok": True,
        "repaired": repaired,
        "details": details,
        "index": str(idx),
    }


def repair_false_index_completed(
    cwd: str | Path,
    decompose: str | Path | None,
) -> dict[str, Any]:
    """Roll index completed → pending when implement shard is not machine-completed.

    Clears hand-edited or premature index completed without a matching implement shard.
    """
    loaded = load_decompose_steps_fail_closed(cwd, decompose)
    if not loaded["ok"]:
        return {
            "ok": False,
            "repaired": [],
            "error": str(loaded.get("message") or loaded.get("error") or decompose),
        }
    idx = Path(loaded["index"])
    cwd_p = Path(cwd)
    epic_id = epic_id_from_decompose_path(str(idx)) or ""
    _role, role_dir = _role_dir_from_index_path(idx, cwd_p)
    plan_id = _index_plan_id(idx)
    import epic_yaml as ey

    repaired: list[str] = []
    details: list[dict[str, Any]] = []
    for step in loaded["steps"]:
        sid = str(step.get("id") or "").strip().lower()
        status = str(step.get("status") or "").lower()
        if not sid or status not in {"completed", "done"}:
            continue
        impl_rel = ""
        try:
            impl_rel = ey.resolve_implement_path(
                cwd_p, role_dir, epic_id, sid, plan_id=plan_id or None
            )
            state = ey.implement_load_state(cwd_p, impl_rel)
        except Exception as exc:
            state = {"completed": False, "load_error": str(exc)}
        if state.get("completed"):
            details.append(
                {"step_id": sid, "ok": True, "skipped": True, "reason": "implement completed"}
            )
            continue
        marked = mark_index_step_status(
            cwd_p, str(idx), sid, "pending", sync_checklist=False
        )
        entry: dict[str, Any] = {
            "step_id": sid,
            "implement_path": impl_rel or None,
            "load_error": state.get("load_error"),
            **marked,
        }
        details.append(entry)
        if marked.get("ok"):
            repaired.append(sid)
    return {
        "ok": True,
        "repaired": repaired,
        "details": details,
        "index": str(idx),
    }


def validate_finish_integrity_with_repair(
    cwd: str | Path,
    *,
    decompose: str | Path | None,
    step_id: str,
    require_verify_pass: bool,
) -> dict[str, Any]:
    """Detect finish desync; auto-rollback implement completed if index still open."""
    result = validate_finish_integrity(
        cwd,
        decompose=decompose,
        step_id=step_id,
        require_verify_pass=require_verify_pass,
    )
    codes = list(result.get("diagnostic_codes") or [])
    if result.get("ok"):
        return result
    if INDEX_IMPLEMENT_CONFLICT in codes:
        repair = repair_false_index_completed(cwd, decompose)
        result["repair"] = repair
        if repair.get("repaired"):
            repaired_result = validate_finish_integrity(
                cwd,
                decompose=decompose,
                step_id=step_id,
                require_verify_pass=require_verify_pass,
            )
            repaired_result["repaired_false_index"] = repair.get("repaired")
            repaired_result["repair"] = repair
            return repaired_result
        return result
    if MARK_INDEX_MISSING not in codes:
        return result
    repair = repair_finish_desync(cwd, decompose)
    if not repair.get("repaired"):
        result["repair"] = repair
        return result
    repaired_result = validate_finish_integrity(
        cwd,
        decompose=decompose,
        step_id=step_id,
        require_verify_pass=require_verify_pass,
    )
    repaired_result["repaired_desync"] = repair.get("repaired")
    repaired_result["repair"] = repair
    return repaired_result


def validate_index_vs_implement(cwd: str | Path, decompose: str | None) -> list[str]:
    errors: list[str] = []
    if decompose is None or not isinstance(decompose, (str, Path)):
        return [
            f"invalid_arg: expected str/Path, got {type(decompose).__name__}"
        ]
    idx, steps, _src = _load_decompose_steps(cwd, decompose)
    if idx is None or not steps:
        return errors
    epic_id = epic_id_from_decompose_path(decompose or "")
    if not epic_id:
        epic_id = epic_id_from_decompose_path(
            str(idx.relative_to(Path(cwd)))
            if idx.is_relative_to(Path(cwd))
            else str(idx)
        )
    if not epic_id:
        return errors
    role = "integ"
    dnorm = str(decompose or "").replace("\\", "/")
    if "/front/" in dnorm:
        role = "front"
    elif "/back/" in dnorm:
        role = "back"
    plan_id = _index_plan_id(idx)
    false_completed: list[str] = []
    load_errors: dict[str, str] = {}
    import epic_yaml as ey

    for s in steps:
        st = s.get("status") or ""
        if st not in {"completed", "done"}:
            continue
        sid = str(s["id"]).strip().lower()
        try:
            impl_rel = ey.resolve_implement_path(
                cwd, role, epic_id, sid, plan_id=plan_id or None
            )
            state = ey.implement_load_state(cwd, impl_rel)
        except Exception as exc:
            state = {"completed": False, "load_error": str(exc)}
        if state.get("completed"):
            continue
        false_completed.append(sid)
        if state.get("load_error"):
            load_errors[sid] = str(state["load_error"])
    if false_completed:
        parts: list[str] = []
        for sid in false_completed[:8]:
            if sid in load_errors:
                err = load_errors[sid]
                if len(err) > 160:
                    err = err[:157] + "..."
                parts.append(f"{sid} (implement invalid: {err})")
            else:
                parts.append(f"{sid} (implement not completed)")
        sample = ", ".join(parts)
        more = f" (+{len(false_completed) - 8})" if len(false_completed) - 8 > 0 else ""
        errors.append(
            "decompose index: status=completed без implement yaml completed: "
            f"{sample}{more} — use finalize-step per step; "
            "FORBIDDEN ручной index completed"
        )
    return errors


def resolve_armed_decompose_for_integrity(
    cwd: str | Path,
    *,
    armed_step: str,
    armed_decompose: str | None,
) -> str | None:
    """Return decompose rel for index integrity, or None when pre-implement has no index yet."""
    rel = (armed_decompose or "").strip() or None
    if not rel:
        return None
    step = str(armed_step or "").upper()
    if step == "DECOMPOSE" and not (Path(cwd) / rel).is_file():
        return None
    return rel


def validate_finish_integrity(
    cwd: str | Path,
    *,
    decompose: str | Path | None,
    step_id: str,
    require_verify_pass: bool,
) -> dict[str, Any]:
    """Return fail-closed, bidirectional index/implement finish diagnostics."""
    _ = require_verify_pass
    loaded = load_decompose_steps_fail_closed(cwd, decompose)
    if not loaded["ok"]:
        diag = str(loaded.get("diagnostic_code") or "")
        message = str(
            loaded.get("message")
            or loaded.get("error")
            or diag
            or decompose
            or ""
        )
        if diag in {"index_not_found", "not_found"} or loaded.get("status") == "not_found":
            codes = [FINISH_INTEGRITY_DECOMPOSE_MISSING]
        elif diag:
            codes = [diag]
        else:
            codes = [FINISH_INTEGRITY_DECOMPOSE_MISSING]
        return {
            "ok": False,
            "errors": [message],
            "diagnostic_codes": codes,
            "step_id": step_id,
        }

    idx = Path(loaded["index"])
    cwd_p = Path(cwd)
    epic_id = epic_id_from_decompose_path(str(idx)) or ""
    role, role_dir = _role_dir_from_index_path(idx, cwd_p)
    errors = validate_index_vs_implement(cwd_p, decompose)
    diagnostic_codes = (
        [INDEX_IMPLEMENT_CONFLICT] if errors else []
    )
    missing: list[str] = []
    for step in loaded["steps"]:
        status = str(step.get("status") or "").lower()
        if status in {"completed", "done"}:
            continue
        if _implement_yaml_completed(
            cwd_p,
            role_dir,
            epic_id,
            str(step.get("id") or ""),
            plan_id=_index_plan_id(idx) or None,
        ):
            missing.append(str(step["id"]))
    if missing:
        errors.append(
            "implement yaml completed but decompose index is not completed: "
            + ", ".join(missing[:8])
            + " — use mark-index-status per step"
        )
        diagnostic_codes.append(MARK_INDEX_MISSING)
    return {
        "ok": not errors,
        "errors": errors,
        "diagnostic_codes": diagnostic_codes,
        "step_id": step_id,
        "index": str(idx),
        "role": role,
    }


def _role_dir_from_index_path(idx: Path, cwd: Path) -> tuple[str, str]:
    """Return (ROLE_TOKEN, memory-bank role dir)."""
    try:
        rel = idx.relative_to(Path(cwd)).as_posix()
    except ValueError:
        rel = idx.as_posix()
    from epic_paths import role_from_decompose_path

    role = role_from_decompose_path(rel)
    role_dir = {"BACK": "back", "FRONT": "front", "INTEG": "integration"}.get(
        role, ""
    )
    return role or "", role_dir


def _task_id_from_epic(epic_id: str) -> str:
    """T-031-perf-log-decorator → T-031; T-HUB-040-xxx → T-HUB-040; demo → demo."""
    parts = (epic_id or "").split("-")
    if len(parts) >= 3 and parts[0].upper() == "T" and parts[2].isdigit():
        return f"{parts[0]}-{parts[1]}-{parts[2]}"
    if len(parts) >= 2 and parts[0].upper() == "T" and parts[1].isdigit():
        return f"T-{parts[1]}"
    return epic_id


def latest_qa_pass_artifact_for_reference(
    cwd: str | Path, role_dir: str = "back", epic_id: str = ""
) -> Path | None:
    """[REFERENCE ONLY] Latest QA pass artifact — NOT a completion test.

    Do not call in reducer as completion proof.
    """
    cwd_p = Path(cwd)
    hits: list[Path] = []
    for root in _role_mb_roots(cwd_p, role_dir, epic_id=epic_id, kind="qa"):
        d = root / "qa" / epic_id if epic_id else root / "qa"
        if not d.is_dir():
            continue
        glob_pattern = "qa-*.yaml" if epic_id else "**/qa-*.yaml"
        for p in sorted(d.glob(glob_pattern), reverse=True):
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if re.search(r"(?m)^verdict:\s*pass\s*$", text):
                hits.append(p)
        if hits:
            break
    return hits[0] if hits else None


def latest_audit_artifact_for_reference(
    cwd: str | Path, role_dir: str = "back", epic_id: str = ""
) -> Path | None:
    cwd_p = Path(cwd)
    hits: list[Path] = []
    for root in _role_mb_roots(cwd_p, role_dir, epic_id=epic_id, kind="audit"):
        d = root / "audit" / epic_id if epic_id else root / "audit"
        if not d.is_dir():
            continue
        glob_pattern = "audit-*.yaml" if epic_id else "**/audit-*.yaml"
        for p in sorted(d.glob(glob_pattern), reverse=True):
            hits.append(p)
        if hits:
            break
    return hits[0] if hits else None


def latest_qa_any_artifact_for_reference(
    cwd: str | Path, role_dir: str = "back", epic_id: str = ""
) -> Path | None:
    cwd_p = Path(cwd)
    hits: list[Path] = []
    for root in _role_mb_roots(cwd_p, role_dir, epic_id=epic_id, kind="qa"):
        d = root / "qa" / epic_id if epic_id else root / "qa"
        if not d.is_dir():
            continue
        glob_pattern = "qa-*.yaml" if epic_id else "**/qa-*.yaml"
        for p in sorted(d.glob(glob_pattern), reverse=True):
            hits.append(p)
        if hits:
            break
    return hits[0] if hits else None


def latest_bugfix_artifact_for_reference(
    cwd: str | Path, role_dir: str = "back", epic_id: str = ""
) -> Path | None:
    cwd_p = Path(cwd)
    hits: list[Path] = []
    for root in _role_mb_roots(cwd_p, role_dir, epic_id=epic_id, kind="bugfix"):
        d = root / "bugfix" / epic_id if epic_id else root / "bugfix"
        if not d.is_dir():
            continue
        glob_pattern = "bugfix-*.md" if epic_id else "**/bugfix-*.md"
        for p in sorted(d.glob(glob_pattern), reverse=True):
            hits.append(p)
        if hits:
            break
    return hits[0] if hits else None


find_qa_pass_artifact = latest_qa_pass_artifact_for_reference
latest_qa_artifact = latest_qa_any_artifact_for_reference


def parse_qa_verdict(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(r"(?m)^verdict:\s*(pass|fail|blocked)\s*$", text)
    return m.group(1).lower() if m else None


def lifecycle_arm_phase(phase: str, decision: dict[str, Any]) -> str:
    if phase == "QA" and decision.get("reason_code") == "qa_failed":
        return "BUGFIX"
    return phase


def validate_qa_finish_handoff(
    cwd: str | Path, body: str, role_dir: str = "back", epic_id: str = ""
) -> tuple[bool, str | None]:
    if not epic_id:
        m = re.search(r"(?m)^epic_id:\s*([^\s]+)", body)
        if m:
            epic_id = m.group(1).strip()
    qa = latest_qa_any_artifact_for_reference(cwd, role_dir, epic_id)
    if not qa:
        return False, "QA FINISH без qa-*.yaml — запиши epic-qa/v1 artifact"
    verdict = parse_qa_verdict(qa)
    if not verdict:
        return False, "qa-*.yaml без verdict: pass|fail|blocked"
    if verdict in {"blocked", "fail"}:
        if "REFLECT" in body.upper():
            return False, "QA FINISH: verdict blocked/fail — Handoff BACK BUGFIX, не REFLECT/DONE"
        if "BUGFIX" not in body.upper():
            return False, "QA FINISH: verdict blocked/fail — Handoff должен быть BACK BUGFIX"
    return True, None


_VERIFY_NO_VERDICT_LINE_RE = re.compile(
    r"(?im)(?:BLOCKED|NEED_HUMAN).*verify_no_verdict"
)


def _strip_verify_no_verdict_lines(text: str) -> str:
    lines = [
        line
        for line in (text or "").splitlines()
        if not _VERIFY_NO_VERDICT_LINE_RE.search(line)
    ]
    cleaned = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip() + "\n"


def _implement_queue_exhausted(cwd_p: Path, decompose: str) -> bool:
    loaded = load_decompose_steps_fail_closed(cwd_p, decompose)
    if not loaded.get("ok"):
        return False
    pending = [
        s
        for s in (loaded.get("steps") or [])
        if str(s.get("status") or "").lower() not in {"completed", "done"}
    ]
    return not pending


def clear_stale_verify_no_verdict_handoff(cwd: str | Path) -> dict[str, Any]:
    """Drop verify_no_verdict halt when implement queue is done and post-implement is next."""
    from loop.schemas.active_context import handoff_mode_from_text

    cwd_p = Path(cwd)
    ac = active_context_path(cwd_p)
    if not ac.is_file():
        return {"ok": True, "cleared": False}
    text = ac.read_text(encoding="utf-8", errors="replace")
    if not _VERIFY_NO_VERDICT_LINE_RE.search(text):
        return {"ok": True, "cleared": False}

    info = discover_epic_for_pipeline(cwd_p)
    if not info or not info.get("decompose"):
        return {"ok": True, "cleared": False}
    if not _implement_queue_exhausted(cwd_p, info["decompose"]):
        return {"ok": True, "cleared": False}

    phase, _, _ = post_implement_phase(cwd_p, info["role_dir"], info["epic_id"])
    handoff_mode = (handoff_mode_from_text(text) or "").upper()
    post_modes = {"AUDIT", "QA", "BUGFIX", "DONE"}
    if phase not in post_modes and handoff_mode not in post_modes:
        return {"ok": True, "cleared": False}

    cleaned = _strip_verify_no_verdict_lines(text)
    if cleaned == text:
        return {"ok": True, "cleared": False}
    atomic_write_text(ac, cleaned)
    st = load_epic_state(cwd_p)
    st["last_verify_verdict"] = None
    st["last_verify_at"] = None
    st["last_verify_evidence"] = None
    save_epic_state(cwd_p, st)
    return {
        "ok": True,
        "cleared": True,
        "phase": phase,
        "handoff_mode": handoff_mode or phase,
        "epic_id": info.get("epic_id"),
    }


def project_handoff_from_reducer(
    cwd: str | Path,
    *,
    allow_terminal_done_projection: bool = True,
) -> dict[str, Any]:
    cwd_p = Path(cwd)
    ac = cwd_p / "memory-bank" / "activeContext.md"
    if not ac.is_file():
        return {"ok": True, "projected": False}
    text = ac.read_text(encoding="utf-8", errors="replace")
    info = discover_epic_for_pipeline(cwd_p) or {}
    epic_id = info.get("epic_id") or ""
    role_dir = info.get("role_dir") or "back"

    if not epic_id:
        m_epic = re.search(r"decompose-([^/]+)/index\.yaml", text)
        if not m_epic:
            m_epic = re.search(r"Handoff\s+BACK\s+\w+\s*—\s*([^\n\s]+)", text)
        epic_id = m_epic.group(1) if m_epic else ""

    if not epic_id:
        return {"ok": True, "projected": False}

    if info.get("decompose") and not _implement_queue_exhausted(cwd_p, info["decompose"]):
        return {"ok": True, "projected": False}

    decision = reduce_epic_lifecycle(cwd_p, role_dir, epic_id)
    raw_phase = str(decision.get("phase") or "QA")
    phase = lifecycle_arm_phase(raw_phase, decision)
    reason_code = str(decision.get("reason_code") or "")
    role_u = str(info.get("role") or role_dir or "back").upper()
    if role_u == "INTEGRATION":
        role_u = "INTEG"

    projected = False
    if phase == "AUDIT" and (
        "mode: IMPLEMENT" in text
        or re.search(rf"(?im)^##\s*Handoff\s+{role_u}\s+IMPLEMENT\b", text)
    ):
        text_new = re.sub(
            rf"Handoff\s+{role_u}\s+IMPLEMENT", f"Handoff {role_u} AUDIT", text
        )
        text_new = re.sub(rf"`{role_u} IMPLEMENT`", f"`{role_u} AUDIT`", text_new)
        text_new = re.sub(r"mode:\s*IMPLEMENT", "mode: AUDIT", text_new)
        if _LOOP_HANDOFF_SCHEMA_LINE not in text_new:
            frontmatter = (
                f"---\n{_LOOP_HANDOFF_SCHEMA_LINE} # handoff\nrole: {role_u}\n"
                f"mode: {phase}\nepic_id: {epic_id}\nstep_id: {epic_id}\n---\n"
            )
            text_new = frontmatter + text_new
        text_new = _strip_verify_no_verdict_lines(text_new)
        ac.write_text(text_new, encoding="utf-8")
        projected = True
    elif phase == "BUGFIX" and (
        "mode: AUDIT" in text
        or "mode: QA" in text
        or re.search(r"(?im)^##\s*Handoff\s+BACK\s+(AUDIT|QA)\b", text)
    ):
        text_new = re.sub(r"Handoff\s+BACK\s+(AUDIT|QA)", "Handoff BACK BUGFIX", text)
        text_new = re.sub(r"`BACK (AUDIT|QA)`", "`BACK BUGFIX`", text_new)
        text_new = re.sub(r"mode:\s*(AUDIT|QA)", "mode: BUGFIX", text_new)
        if _LOOP_HANDOFF_SCHEMA_LINE not in text_new:
            frontmatter = (
                f"---\n{_LOOP_HANDOFF_SCHEMA_LINE} # handoff\nrole: BACK\n"
                f"mode: {phase}\nepic_id: {epic_id}\nstep: null\n---\n"
            )
            text_new = frontmatter + text_new
        ac.write_text(text_new, encoding="utf-8")
        projected = True
    elif phase == "QA" and (
        "mode: AUDIT" in text
        or re.search(r"(?im)^##\s*Handoff\s+BACK\s+AUDIT\b", text)
    ):
        text_new = re.sub(r"Handoff\s+BACK\s+AUDIT", "Handoff BACK QA", text)
        text_new = re.sub(r"`BACK AUDIT`", "`BACK QA`", text_new)
        text_new = re.sub(r"mode:\s*AUDIT", "mode: QA", text_new)
        if _LOOP_HANDOFF_SCHEMA_LINE not in text_new:
            frontmatter = (
                f"---\n{_LOOP_HANDOFF_SCHEMA_LINE} # handoff\nrole: BACK\n"
                f"mode: {phase}\nepic_id: {epic_id}\nstep: null\n---\n"
            )
            text_new = frontmatter + text_new
        ac.write_text(text_new, encoding="utf-8")
        projected = True
    elif (
        allow_terminal_done_projection
        and phase == "DONE"
        and ("REFLECT" in text or "mode: REFLECT" in text or "BUGFIX" in text or "mode: QA" in text)
    ):
        text_new = re.sub(r"Handoff\s+BACK\s+(REFLECT|BUGFIX|QA)", "Handoff BACK DONE", text)
        text_new = re.sub(r"`BACK (REFLECT|BUGFIX|QA)`", "`BACK DONE`", text_new)
        text_new = re.sub(r"mode:\s*(REFLECT|BUGFIX|QA)", "mode: DONE", text_new)
        ac.write_text(text_new, encoding="utf-8")
        projected = True

    return {
        "ok": True,
        "projected": projected,
        "phase": phase,
        "reason_code": reason_code,
    }


def repair_post_implement_handoff_drift(cwd: str | Path) -> dict[str, Any]:
    return project_handoff_from_reducer(cwd)


def find_reflection_artifact(cwd: str | Path, role_dir: str, epic_id: str) -> Path | None:
    """reflection-*.md matching epic_id or task id (T-031…)."""
    cwd_p = Path(cwd)
    d = cwd_p / "memory-bank" / role_dir / "reflection"
    if not d.is_dir():
        return None
    task = _task_id_from_epic(epic_id)
    for p in sorted(d.glob("reflection-*.md"), reverse=True):
        name = p.name
        if epic_id in name or (task and task in name):
            return p
        try:
            head = p.read_text(encoding="utf-8", errors="replace")[:800]
        except OSError:
            continue
        if epic_id in head or (task and task in head):
            return p
    return None


def reduce_epic_lifecycle(
    cwd: str | Path, role_dir: str, epic_id: str
) -> dict[str, Any]:
    """Return the current AUDIT → QA → BUGFIX → DONE lifecycle decision."""
    cwd_p = Path(cwd)
    event_path = _event_log_path(cwd_p, role_dir, epic_id)
    reconcile_epic_events(cwd_p, role_dir, epic_id)
    result = read_event_log_result(
        event_path,
        expected_epic_id=epic_id,
        cwd=cwd_p,
    )
    events = list(result.events)
    diagnostics = [
        {
            "code": item.code,
            "field": item.field,
            "message": item.message,
        }
        for item in result.diagnostics
    ]

    latest_event = events[-1] if events else None
    latest_qa: dict[str, Any] | None = None
    latest_audit: dict[str, Any] | None = None
    for event in events:
        if event.get("kind") in {"qa_pass", "qa_fail"}:
            latest_qa = event
        if event.get("kind") == "audit_done":
            latest_audit = event

    invalidator: dict[str, Any] | None = None
    if latest_qa is not None:
        qa_seq = int(latest_qa.get("seq", 0))
        for event in events:
            if (
                event.get("kind") == "bugfix_done"
                and int(event.get("seq", 0)) > qa_seq
            ):
                invalidator = event

    phase = "QA"
    reason_code = "qa_required"
    if diagnostics:
        reason_code = "event_stream_invalid"
    elif latest_qa is not None and latest_qa.get("kind") == "qa_fail":
        qa_seq = int(latest_qa.get("seq", 0))
        bugfix_after_fail = None
        for event in events:
            if (
                event.get("kind") == "bugfix_done"
                and int(event.get("seq", 0)) > qa_seq
            ):
                bugfix_after_fail = event
        if bugfix_after_fail is not None:
            phase = "QA"
            reason_code = "bugfix_reopens_qa"
        else:
            reason_code = "qa_failed"
    elif latest_qa is not None and latest_qa.get("kind") == "qa_pass":
        if invalidator is not None:
            phase = "QA"
            reason_code = "bugfix_reopens_qa"
        else:
            phase = "DONE"
            reason_code = "qa_passed"
    elif latest_audit is None:
        phase = "AUDIT"
        reason_code = "audit_required"

    if phase == "DONE":
        expected_artifact = None
    elif phase == "AUDIT":
        expected_artifact = (
            f"memory-bank/{role_dir}/audit/{epic_id}/audit-*.yaml"
        )
    else:
        expected_artifact = f"memory-bank/{role_dir}/qa/{epic_id}/qa-*.yaml"

    last_seq = latest_event.get("seq") if latest_event else None
    event_digest = f"sha256:{event_stream_digest(result)}"
    diagnostic_codes = sorted({item["code"] for item in diagnostics})
    identity = {
        "schema_version": "loop-projection/v1",
        "epic_id": epic_id,
        "role": role_dir.upper(),
        "phase": phase,
        "reason_code": reason_code,
        "last_seq": last_seq,
        "event_digest": event_digest,
        "expected_artifact": expected_artifact,
        "diagnostic_codes": diagnostic_codes,
    }
    projection_hash = _projection_digest(identity)
    epoch = max(
        (int(event.get("epoch", 0)) for event in events),
        default=0,
    )
    phase_epoch = _projection_digest(
        {
            "projection_hash": projection_hash,
            "phase": phase,
            "epoch": epoch,
        }
    )
    return {
        "phase": phase,
        "reason_code": reason_code,
        "last_event": latest_event,
        "last_seq": last_seq,
        "event_digest": event_digest,
        "expected_artifact": expected_artifact,
        "diagnostics": diagnostics,
        "projection_hash": projection_hash,
        "phase_epoch": phase_epoch,
        "epoch": epoch,
    }


def post_implement_phase(
    cwd: str | Path, role_dir: str, epic_id: str
) -> tuple[str, Path | None, Path | None]:
    """Reduce the ordered artifact events to AUDIT, QA, BUGFIX, or DONE."""
    decision = reduce_epic_lifecycle(cwd, role_dir, epic_id)
    phase = str(decision["phase"])
    qa = find_qa_pass_artifact(cwd, role_dir, epic_id)
    if phase == "DONE":
        return phase, qa, find_reflection_artifact(cwd, role_dir, epic_id)
    return phase, None, None


def resolve_pipeline_identity(cwd: str | Path) -> dict[str, Any]:
    """Resolve one explicit pipeline/epic/role/index identity fail-closed."""
    cwd_p = Path(cwd)
    st = load_epic_state(cwd_p)
    text = ""
    try:
        text = read_active_context(cwd_p)
    except OSError:
        pass

    # Trust armed_decompose from runtime state when present.
    # IMPLEMENT load_now lists index.yaml (canon), not index.md.
    state_decompose = (st.get("armed_decompose") or "").strip()
    idx_state = _decompose_index_path(cwd_p, state_decompose) if state_decompose else None
    if state_decompose and idx_state is not None and idx_state.is_file():
        candidates = {state_decompose.removeprefix("memory-bank/")}
    else:
        candidates = set(re.findall(
            r"(?:memory-bank/)?([A-Za-z0-9._-]+/plan/decompose-[A-Za-z0-9._-]+/index\.(?:yaml|md))",
            text,
        ))
        for m in re.finditer(
            r"(?:memory-bank/)?((?:back|front|integration)/plan/decompose-[A-Za-z0-9._-]+)/",
            text,
        ):
            rel_dir = m.group(1)
            y = rel_dir + "/index.yaml"
            candidates.add(y)
        if not candidates:
            m_epic = re.search(r"(?:qa|plan)/([A-Za-z0-9._-]+)/", text)
            if not m_epic:
                m_epic = re.search(r"Handoff\s+[A-Za-z]+\s+[^\n]*?—\s*([A-Za-z0-9._-]+)", text)
            if m_epic:
                epic_id = m_epic.group(1).strip()
                for p in cwd_p.glob(f"memory-bank/*/plan/decompose-{epic_id}/index.yaml"):
                    candidates.add(str(p.relative_to(cwd_p)).removeprefix("memory-bank/"))
        if not candidates:
            armed = (st.get("armed_epic") or "").strip()
            role_raw = str(st.get("role") or "back").lower()
            role_dir = (
                "integration"
                if role_raw in {"integ", "integration"}
                else role_raw
            )
            if armed and role_dir in {"back", "front", "integration"}:
                found = find_decompose_index_path(cwd_p, role_dir, armed)
                if found is not None:
                    try:
                        rel = found.relative_to(cwd_p).as_posix()
                    except ValueError:
                        rel = found.as_posix()
                    if not rel.startswith("memory-bank/"):
                        rel = "memory-bank/" + rel
                    candidates.add(rel.removeprefix("memory-bank/"))
    if len(candidates) > 1:
        # Collapse index.md + index.yaml of the same decompose folder into one canon.
        by_dir: dict[str, set[str]] = {}
        for cand in candidates:
            rel = cand.removeprefix("memory-bank/")
            parent = str(Path(rel).parent).replace("\\", "/")
            by_dir.setdefault(parent, set()).add(rel)
        collapsed: set[str] = set()
        for parent, rels in by_dir.items():
            yaml_rel = f"{parent}/index.yaml"
            if yaml_rel in rels or any(r.endswith("/index.yaml") for r in rels):
                collapsed.add(yaml_rel if yaml_rel in rels else next(
                    r for r in rels if r.endswith("/index.yaml")
                ))
            elif len(rels) == 1:
                collapsed.add(next(iter(rels)))
            else:
                collapsed.update(rels)
        candidates = collapsed
    if len(candidates) > 1:
        return _index_result("ambiguous", "identity_ambiguous", message=sorted(candidates).__repr__())
    if not candidates:
        return _index_result("not_found", "identity_not_found")

    decompose = "memory-bank/" + next(iter(candidates)).removeprefix("memory-bank/")
    idx = _decompose_index_path(cwd_p, decompose)
    if idx is None or (not idx.is_file() and not idx.with_name("index.yaml").is_file()):
        archived = None
        parts = decompose.split("/")
        # memory-bank/<role>/plan/decompose-… → memory-bank/archive/<role>/plan/decompose-…
        if (
            len(parts) >= 4
            and parts[0] == "memory-bank"
            and parts[1] != "archive"
        ):
            archived = "/".join(
                ["memory-bank", "archive", parts[1], *parts[2:]]
            )
            idx = _decompose_index_path(cwd_p, archived)
            if idx is not None and (idx.is_file() or idx.with_name("index.yaml").is_file()):
                decompose = archived
        if idx is None or (not idx.is_file() and not idx.with_name("index.yaml").is_file()):
            return _index_result("invalid", "identity_invalid", message=decompose)
    role, role_dir = _role_dir_from_index_path(idx, cwd_p)
    if role not in {"BACK", "FRONT", "INTEG"}:
        m_role = re.search(r"memory-bank/(?:archive/)?(back|front|integration)/", str(idx.as_posix()))
        if m_role:
            role_dir = m_role.group(1)
            role = {"back": "BACK", "front": "FRONT", "integration": "INTEG"}.get(role_dir, "")
    if role not in {"BACK", "FRONT", "INTEG"}:
        return _index_result("invalid", "identity_invalid", idx=idx, message=decompose)
    folder_epic_id = epic_id_from_decompose_path(decompose)
    epic_id = canonical_epic_id_for_decompose(decompose, index_path=idx)
    if is_reserved_role_epic_id(epic_id):
        return _index_result(
            "invalid",
            "identity_role_slug",
            idx=idx,
            message=decompose,
        )
    armed_epic = (st.get("armed_epic") or "").strip()
    if armed_epic and armed_epic != epic_id and armed_epic != folder_epic_id:
        return _index_result("ambiguous", "identity_conflict", idx=idx, message=f"armed_epic={armed_epic}")
    loaded = load_decompose_steps_fail_closed(cwd_p, decompose)
    if not loaded["ok"]:
        return loaded
    return {
        **loaded,
        "ok": True,
        "status": "resolved",
        "diagnostic_code": "identity_resolved",
        "epic_id": epic_id,
        "role": role,
        "role_dir": role_dir,
        "decompose": decompose,
    }


def discover_epic_for_pipeline(cwd: str | Path) -> dict[str, Any] | None:
    """Resolve epic_id / role / decompose path for post-implement gate."""
    identity = resolve_pipeline_identity(cwd)
    if identity["status"] != "resolved":
        return None
    return {
        key: identity[key]
        for key in ("epic_id", "role", "role_dir", "decompose")
    }


def epic_complete_allowed(cwd: str | Path) -> dict[str, Any]:
    """HARD gate: EPIC_DONE only after QA pass (AUDIT → QA → DONE).

    Legacy Handoff REFLECT is ignored (not blocking). Without QA pass the epic
    is NOT complete — never treat as DONE.
    """
    cwd_p = Path(cwd)
    project_handoff_from_reducer(cwd_p)
    handoff_phase = handoff_post_implement_phase(read_active_context(cwd_p))
    if handoff_phase in {"AUDIT", "BUGFIX"}:
        info = discover_epic_for_pipeline(cwd) or {}
        epic_id = info.get("epic_id") or (load_epic_state(cwd_p) or {}).get(
            "armed_epic"
        )
        return {
            "allowed": False,
            "phase": handoff_phase,
            "reason": (
                f"EPIC_DONE запрещён: Handoff требует {handoff_phase} "
                f"(события/артефакты не переопределяют Handoff)."
            ),
            **info,
            "epic_id": epic_id,
            "handoff_phase": handoff_phase,
        }
    info = discover_epic_for_pipeline(cwd)
    if not info:
        logger.warning(
            "EPIC_DONE halted: epic identity unavailable "
            "(code=identity_unresolved)"
        )
        return {
            "allowed": False,
            "phase": None,
            "reason": (
                "EPIC_DONE отклонён: не удалось определить эпик "
                "(нужны AUDIT + QA pass)"
            ),
        }
    phase, qa, refl = post_implement_phase(
        cwd, info["role_dir"], info["epic_id"]
    )
    if phase == "DONE":
        return {
            "allowed": True,
            "phase": "DONE",
            "reason": None,
            **info,
            "qa_path": qa,
            "reflection_path": refl,
        }
    need = post_implement_phase_need(phase)
    return {
        "allowed": False,
        "phase": phase,
        "reason": (
            f"EPIC_DONE запрещён для {info['epic_id']}: нет {need}. "
            f"Цепочка: {POST_IMPLEMENT_CHAIN}."
        ),
        **info,
        "qa_path": qa,
        "reflection_path": refl,
    }


POST_IMPLEMENT_CHAIN = "IMPLEMENT → AUDIT → QA → EPIC_DONE"
# Keep in sync with loop/context_loop.py STOP_EPIC_DONE_RE (standalone line only).
_EPIC_DONE_LINE_RE = re.compile(
    r"(?m)^\s*(?:[-*]\s*)?(?:\*\*)?`?EPIC_DONE`?(?:\*\*)?\s*$"
)
_POST_IMPLEMENT_NEED = {
    "AUDIT": "AUDIT (audit-*.yaml)",
    "QA": "QA pass",
    "BUGFIX": "BUGFIX (после qa_fail)",
}


def post_implement_phase_need(phase: str) -> str:
    key = str(phase or "").upper()
    return _POST_IMPLEMENT_NEED.get(key, f"фаза {phase} не терминальная")


def post_implement_handoff_violates_epic_done(phase: str, body: str) -> bool:
    """True when a non-DONE Handoff contains a standalone EPIC_DONE line."""
    if str(phase or "").upper() == "DONE":
        return False
    return bool(_EPIC_DONE_LINE_RE.search(body or ""))


def _render_loop_active_context(
    *,
    role: str,
    mode: str,
    epic_id: str,
    step_id: str | None,
    load_now: list[tuple[str, str]],
    custom_lines: list[str],
    next_hint: str | None = None,
    done: list[str] | None = None,
) -> str:
    """Sole writer path for arm/repair — always emits loop-handoff/v1 frontmatter."""
    from loop.mb_finish.render import render_active_context
    from loop.mb_finish.schemas import HandoffBody, LoadNowItem, LoopHandoffMeta
    from loop.schemas.active_context import normalize_gate_mode

    role_u = str(role or "BACK").upper()
    if role_u == "INTEGRATION":
        role_u = "INTEG"
    mode_u = normalize_gate_mode(mode, role_u) or str(mode or "").upper()
    meta = LoopHandoffMeta(
        role=role_u,
        mode=mode_u,
        epic_id=epic_id,
        step_id=step_id,
    )
    items = [
        LoadNowItem(path=path, description=desc.rstrip("."))
        for path, desc in load_now
    ]
    handoff = HandoffBody(
        mode=mode_u,
        step_id=step_id,
        epic_id=epic_id,
        next_hint=next_hint,
        custom_lines=custom_lines,
    )
    return render_active_context(meta, items, done or [], handoff)


def build_post_implement_active_context(
    *,
    role: str,
    role_dir: str,
    epic_id: str,
    tracker_rel: str,
    tracker_link: str,
    index_rel: str,
    hub_rel: str | None,
    phase: str,
    qa_path: Path | None,
    reflection_path: Path | None,
    cwd: Path,
) -> str:
    """Full Handoff for post-implement pipeline — not a one-line EPIC_DONE stub."""
    del role_dir, index_rel, hub_rel
    load_now: list[tuple[str, str]] = [
        (
            tracker_link,
            f"decompose index.yaml (implement queue исчерпана; эпик {epic_id})",
        ),
    ]
    if qa_path is not None and qa_path.is_file():
        try:
            qa_rel = qa_path.relative_to(cwd).as_posix()
        except ValueError:
            qa_rel = str(qa_path)
        qa_link = qa_rel.removeprefix("memory-bank/")
        load_now.append((qa_link, "QA pass artifact"))
    if reflection_path is not None and reflection_path.is_file():
        try:
            r_rel = reflection_path.relative_to(cwd).as_posix()
        except ValueError:
            r_rel = str(reflection_path)
        r_link = r_rel.removeprefix("memory-bank/")
        load_now.append((r_link, "reflection"))

    phase_u = str(phase or "").upper()
    role_u = str(role or "BACK").upper()
    if role_u == "INTEGRATION":
        role_u = "INTEG"

    if phase_u == "AUDIT":
        next_hint = (
            f"выполнить `{role_u} AUDIT` (gap-матрица + audit yaml); "
            f"пусто not_implemented[] → `{role_u} QA`. "
            f"НЕ ставить EPIC_DONE до QA pass"
        )
        custom_lines = [
            f"- **Эпик:** {epic_id} — все sNN/eNN в index completed/done.",
            f"- **Режим/шаг:** `{role_u} AUDIT`.",
            "- **Сделано:** implement queue исчерпана.",
            "- **ARCHIVE:** вне loop после EPIC_DONE (не в AUDIT/QA сессии).",
        ]
    elif phase_u == "QA":
        next_hint = (
            f"выполнить `{role_u} QA` (suite + reviewer); "
            f"после QA pass — EPIC_DONE. "
            f"НЕ ставить EPIC_DONE до QA pass"
        )
        custom_lines = [
            f"- **Эпик:** {epic_id} — все sNN/eNN в index completed/done.",
            f"- **Режим/шаг:** `{role_u} QA`.",
            "- **Сделано:** implement queue исчерпана.",
            "- **ARCHIVE:** вне loop после EPIC_DONE (не в QA сессии).",
        ]
    elif phase_u == "DONE":
        next_hint = None
        custom_lines = [
            "EPIC_DONE",
            f"- **Эпик:** {epic_id} — implement + AUDIT + QA pass завершены.",
            "- **Дальше:** stop на EPIC_DONE; при EPIC_CHAIN_ROADMAP=1 runner "
            "возьмёт следующий эпик из roadmap Queue.",
            "- **FORBIDDEN:** ARCHIVE NOW / VAN в loop-сессии.",
            "- **ARCHIVE:** только вручную вне loop после stop / исчерпания queue.",
        ]
    else:
        next_hint = (
            f"выполнить `{role_u} {phase_u}`. "
            f"НЕ ставить EPIC_DONE: фаза `{phase_u}` не терминальная "
            f"(канон: {POST_IMPLEMENT_CHAIN})"
        )
        custom_lines = [
            f"- **Эпик:** {epic_id} — implement queue исчерпана; фаза `{phase_u}`.",
            f"- **Режим/шаг:** `{role_u} {phase_u}`.",
        ]

    return _render_loop_active_context(
        role=role_u,
        mode=phase_u,
        epic_id=epic_id,
        step_id=None if phase_u == "DONE" else epic_id,
        load_now=load_now,
        custom_lines=custom_lines,
        next_hint=next_hint,
    )


def _decompose_step_shards_dir(idx: Path) -> Path:
    """Directory with sNN-*.yaml shards (v2: ``yaml/steps/``, v1: beside index)."""
    ypath = index_yaml_path(idx)
    if ypath.name in {"decompose-index.yaml", "decompose-index.yml"} and ypath.parent.name == "yaml":
        steps = ypath.parent / "steps"
        if steps.is_dir():
            return steps
        return ypath.parent
    if ypath.is_file():
        return ypath.parent
    return idx.parent if idx.suffix else idx


def _resolve_href(base_dir: Path, href: str, cwd: Path) -> str | None:
    href = (href or "").strip()
    if not href:
        return None
    if href.startswith("memory-bank/"):
        return href if (cwd / href).exists() else None
    cand = (base_dir / href).resolve()
    try:
        rel = cand.relative_to(Path(cwd).resolve()).as_posix()
    except ValueError:
        return None
    return rel if cand.exists() else None


def find_next_decompose_step(index_text: str) -> dict[str, str] | None:
    """[LEGACY FALLBACK] Parse next step from Markdown index (md-only path).

    Preferred: find_next_decompose_step_from_queue() when YAML index available.
    """
    step = find_next_step(parse_steps_from_md(index_text))
    if not step:
        return None
    return {
        "step_id": step["id"],
        "status": step["status"],
        "shard_href": step.get("file") or "",
        "next_phase": step.get("next_phase") or "",
        "title": step.get("title") or "",
    }


def find_next_decompose_step_from_queue(
    steps: list[dict[str, str]],
) -> dict[str, str] | None:
    step = find_next_step(steps)
    if not step:
        return None
    return {
        "step_id": step["id"],
        "status": step["status"],
        "shard_href": step.get("file") or "",
        "next_phase": step.get("next_phase") or "",
        "title": step.get("title") or "",
    }


def clear_reserved_role_arm(cwd: str | Path) -> dict[str, Any]:
    """Disarm state when armed_epic/decompose uses a role slug as epic_id."""
    cwd_p = Path(cwd)
    st = load_epic_state(cwd_p)
    epic = (st.get("armed_epic") or "").strip()
    decomp = (st.get("armed_decompose") or "").strip()
    if not is_reserved_role_epic_id(epic) and not is_reserved_role_epic_id(
        epic_id_from_decompose_path(decomp)
    ):
        return {"ok": True, "cleared": False}
    reason = (
        "NEED_HUMAN: armed_epic/decompose used role slug as epic_id "
        f"(armed_epic={epic!r}, decompose={decomp!r}). "
        "Re-arm with a real epic id (e.g. T-HUB-…). "
        "Forbidden slugs: back|front|integration|integ."
    )
    st["armed_epic"] = None
    st["armed_decompose"] = None
    st["armed_step"] = None
    st["active"] = False
    st["status"] = "halted"
    st["halt_reason"] = reason
    st["diagnostic_codes"] = sorted(
        set(st.get("diagnostic_codes") or []) | {"armed_role_slug"}
    )
    save_epic_state(cwd_p, st)
    logger.warning("cleared reserved-role arm: %s", reason)
    return {
        "ok": False,
        "cleared": True,
        "halt": True,
        "reason": reason,
        "diagnostic_code": "armed_role_slug",
    }


def arm_active_context_from_decompose(
    cwd: str | Path,
    decompose: str,
) -> dict[str, Any]:
    """Overwrite activeContext from decompose index — ignore prior epic cursor.

    Used when human launches ``./loop/loop.sh decompose-<epic> …`` so the model
    starts on the chosen epic's next pending/active step even if activeContext
    still points at another epic or carries BLOCKED/NEED_HUMAN from it.
    """
    from loop.epic_transition import _legacy_warn
    _legacy_warn("arm_active_context_from_decompose")

    if decompose is None or not isinstance(decompose, (str, Path)):
        return {
            "ok": False,
            "error": f"invalid_arg: expected str/Path, got {type(decompose).__name__}",
        }
    cwd_p = Path(cwd)
    idx = _decompose_index_path(cwd_p, decompose)
    ypath = index_yaml_path(idx) if idx is not None else None
    if idx is None or (
        not idx.is_file() and not (ypath is not None and ypath.is_file())
    ):
        return {
            "ok": False,
            "error": f"decompose index not found: {decompose!r}",
        }

    loaded = load_decompose_steps_fail_closed(cwd_p, str(idx))
    if not loaded["ok"]:
        return loaded
    steps = loaded["steps"]
    if not index_yaml_path(idx).is_file():
        steps = [
            {**item, "status": "completed" if item.get("status") == "done" else item.get("status")}
            for item in steps
        ]
    queue_src = loaded["source"]
    epic_id = epic_id_from_decompose_path(
        str(idx.relative_to(cwd_p)) if idx.is_relative_to(cwd_p) else str(idx)
    ) or epic_id_from_decompose_path(decompose)
    if is_reserved_role_epic_id(epic_id):
        return {
            "ok": False,
            "error": (
                f"epic_id must not be a role slug: {epic_id!r} "
                "(forbidden: back|front|integration|integ)"
            ),
            "diagnostic_code": "epic_id_reserved",
            "epic_id": epic_id,
        }
    role, role_dir = _role_dir_from_index_path(idx, cwd_p)
    index_rel = (
        str(idx.relative_to(cwd_p)).replace("\\", "/")
        if idx.is_relative_to(cwd_p)
        else str(idx)
    )
    ypath = index_yaml_path(idx)
    yaml_rel = (
        str(ypath.relative_to(cwd_p)).replace("\\", "/")
        if ypath.is_file() and ypath.is_relative_to(cwd_p)
        else (str(ypath) if ypath.is_file() else "")
    )
    tracker_rel = yaml_rel or index_rel
    tracker_link = tracker_rel.removeprefix("memory-bank/")

    step = find_next_decompose_step_from_queue(steps)
    if step is None:
        phase, qa_p, refl_p = post_implement_phase(cwd_p, role_dir, epic_id or "")
        body = build_post_implement_active_context(
            role=role,
            role_dir=role_dir,
            epic_id=epic_id or "unknown",
            tracker_rel=tracker_rel,
            tracker_link=tracker_link,
            index_rel=index_rel,
            hub_rel=None,
            phase=phase,
            qa_path=qa_p,
            reflection_path=refl_p,
            cwd=cwd_p,
        )
        if post_implement_handoff_violates_epic_done(phase, body):
            return {
                "ok": False,
                "error": (
                    f"invariant: post-implement Handoff for phase={phase} "
                    "must not contain EPIC_DONE"
                ),
                "phase": phase,
                "epic_id": epic_id,
            }
        atomic_write_text(active_context_path(cwd_p), body)
        cleared = clear_runner_checkpoint(cwd_p)
        if not cleared.get("ok"):
            return {
                "ok": False,
                "error": "failed to clear runner checkpoint after arm",
                "diagnostic_code": cleared.get("diagnostic_code"),
                "checkpoint_clear": cleared,
                "epic_id": epic_id,
                "phase": phase,
            }
        st = load_epic_state(cwd_p)
        st["armed_epic"] = epic_id
        st["armed_decompose"] = tracker_rel
        st["armed_step"] = None
        st["role"] = role
        st["pending_fingerprint_before"] = None
        if phase == "DONE":
            st["active"] = False
            st["status"] = "complete"
            st["halt_reason"] = None
            save_epic_state(cwd_p, st)
            return {
                "ok": True,
                "complete": True,
                "stop": "EPIC_DONE",
                "phase": phase,
                "epic_id": epic_id,
                "role": role,
                "index": tracker_rel,
                "queue_source": queue_src,
                "active_context": "memory-bank/activeContext.md",
            }
        st["active"] = True
        st["status"] = "armed"
        st["halt_reason"] = None
        st["armed_step"] = phase
        save_epic_state(cwd_p, st)
        return {
            "ok": True,
            "complete": False,
            "stop": None,
            "phase": phase,
            "epic_id": epic_id,
            "role": role,
            "step_id": phase,
            "status": "pending",
            "index": tracker_rel,
            "queue_source": queue_src,
            "active_context": "memory-bank/activeContext.md",
            "qa_path": str(qa_p.relative_to(cwd_p)) if qa_p else None,
        }

    shard_rel = _resolve_href(_decompose_step_shards_dir(idx), step["shard_href"], cwd_p)
    if not shard_rel:
        steps_dir = _decompose_step_shards_dir(idx)
        guess = steps_dir / f"{step['step_id']}.yaml"
        if not guess.is_file():
            hits = sorted(steps_dir.glob(f"{step['step_id']}-*.yaml"))
            guess = hits[0] if hits else guess
        if guess.is_file():
            shard_rel = guess.relative_to(cwd_p).as_posix()
        else:
            return {
                "ok": False,
                "error": (
                    f"work shard for {step['step_id']} not found under {steps_dir}"
                ),
                "step_id": step["step_id"],
            }

    phase = effective_phase(
        role=role,
        next_phase=step["next_phase"],
        needs_creative=_step_needs_creative(cwd_p, idx, step),
    )
    title = step["title"] or step["step_id"]
    yaml_for_load = (
        tracker_rel if tracker_rel.endswith(".yaml") else yaml_rel or tracker_rel
    )
    shard_link = shard_rel.removeprefix("memory-bank/")
    yaml_link = yaml_for_load.removeprefix("memory-bank/")
    done_items: list[str] = []
    completed = [s["id"] for s in steps if s.get("status") in {"completed", "done"}]
    if completed:
        done_items.append(
            f"{completed[0]}–{completed[-1]} completed в `{tracker_link}` "
            f"({len(completed)} шагов)"
        )

    body = _render_loop_active_context(
        role=role,
        mode=phase,
        epic_id=epic_id or "unknown",
        step_id=step["step_id"],
        load_now=[
            (
                shard_link,
                f"текущий work shard ({phase} {step['step_id']})",
            ),
            (
                yaml_link,
                "очередь/status (canon=yaml)",
            ),
        ],
        custom_lines=[
            f"- **Эпик:** {epic_id} ({role}); armed из `{tracker_link}` "
            f"(прошлый activeContext игнорирован).",
            f"- **Текущий шаг:** {step['step_id']} — {title} "
            f"(status={step['status']} в index.yaml).",
            f"- **Команда:** `{phase} @{step['step_id']}`",
        ],
        next_hint=(
            "выполнить atomic шаг → FINISH "
            "(seed-implement → flush cp → suite → evidence in_progress → "
            "validate-step → Handoff → @verify → finalize-step)"
        ),
        done=done_items,
    )
    atomic_write_text(active_context_path(cwd_p), body)

    # Arm always rewrites activeContext. Drop runner checkpoint unconditionally —
    # same-step re-arm still changes context_fingerprint and would halt prepare with
    # checkpoint_projection_conflict if a prior committed/prepared checkpoint remains.
    cleared = clear_runner_checkpoint(cwd_p)
    if not cleared.get("ok"):
        return {
            "ok": False,
            "error": "failed to clear runner checkpoint after arm",
            "diagnostic_code": cleared.get("diagnostic_code"),
            "checkpoint_clear": cleared,
            "epic_id": epic_id,
            "step_id": step["step_id"],
        }

    st = load_epic_state(cwd_p)
    st["active"] = True
    st["status"] = "armed"
    st["halt_reason"] = None
    st["armed_epic"] = epic_id
    st["armed_decompose"] = tracker_rel
    st["armed_step"] = step["step_id"]
    st["phase"] = phase
    st["role"] = role
    st["pending_fingerprint_before"] = None
    save_epic_state(cwd_p, st)

    return {
        "ok": True,
        "complete": False,
        "epic_id": epic_id,
        "role": role,
        "step_id": step["step_id"],
        "status": step["status"],
        "phase": phase,
        "work_shard": shard_rel,
        "index": tracker_rel,
        "index_md": index_rel,
        "queue_source": queue_src,
        "implement_hub": None,
        "active_context": "memory-bank/activeContext.md",
        "checkpoint_cleared": True,
    }


def arm_epic(
    cwd: str | Path,
    epic_id: str,
    *,
    role: str = "back",
    require_plan: bool = True,
) -> dict[str, Any]:
    """Arm activeContext for epic via resolver (pre-implement / implement / post-implement)."""
    cwd_p = Path(cwd)
    from board_sync.epic_resolver import resolve_epic_next_action
    from epic_transition import arm_phase

    action = resolve_epic_next_action(cwd_p, role, epic_id, require_plan=require_plan)
    phase = (action.phase or "").upper()
    if phase == "DONE":
        if action.decompose_rel:
            return arm_phase(cwd_p, epic_id, "IMPLEMENT", role, decompose_rel=action.decompose_rel)
        return {
            "ok": True,
            "complete": True,
            "stop": "EPIC_DONE",
            "phase": "DONE",
            "epic_id": epic_id,
            "role": role,
        }
    if phase in {"PLAN", "DECOMPOSE", "CLARIFY", "ANALYZE", "CREATIVE"}:
        return arm_phase(
            cwd_p,
            epic_id,
            phase,
            role,
            target_rel=action.plan_rel,
            decompose_rel=action.decompose_rel if phase == "ANALYZE" else None,
        )
    if phase == "IMPLEMENT":
        if not action.decompose_rel:
            return {
                "ok": False,
                "error": f"cannot arm epic {epic_id} in phase {phase} without decompose index",
            }
        if os.environ.get("EPIC_CONVERGENCE_CHECK") == "1":
            try:
                findings = run_convergence_checks(cwd_p, epic_id)
                for f in findings:
                    if str(f.severity).upper() in {"HIGH", "CRITICAL"}:
                        logger.warning(
                            f"[convergence] {f.severity} finding in epic {epic_id}: {f.category} - {f.message}"
                        )
            except Exception as exc:
                logger.warning(f"[convergence] check failed during arm_epic: {exc}")
        return arm_phase(cwd_p, epic_id, "IMPLEMENT", role, decompose_rel=action.decompose_rel)
    if phase in {"AUDIT", "QA", "BUGFIX"}:
        qa_p = find_qa_pass_artifact(cwd_p, role, epic_id)
        ref_p = find_reflection_artifact(cwd_p, role, epic_id)
        rel_idx = action.decompose_rel or f"memory-bank/{role}/plan/decompose-{epic_id}/index.yaml"
        rel_md = rel_idx.removesuffix(".yaml") + ".md" if rel_idx.endswith(".yaml") else rel_idx
        link = rel_idx.removeprefix("memory-bank/")
        hub_rel = f"memory-bank/hub/plan/plan-{epic_id}.md"
        role_u = {"back": "BACK", "front": "FRONT", "integration": "INTEG"}.get(
            str(role or "back").lower(), str(role or "BACK").upper()
        )
        body = build_post_implement_active_context(
            role=role_u,
            role_dir=f"memory-bank/{role}",
            epic_id=epic_id,
            tracker_rel=rel_idx,
            tracker_link=link,
            index_rel=rel_md,
            hub_rel=hub_rel if (cwd_p / hub_rel).is_file() else None,
            phase=phase,
            qa_path=qa_p if qa_p and qa_p.is_file() else None,
            reflection_path=ref_p if ref_p and ref_p.is_file() else None,
            cwd=cwd_p,
        )
        atomic_write_text(active_context_path(cwd_p), body)
        clear_runner_checkpoint(cwd_p)
        st = load_epic_state(cwd_p)
        st["active"] = True
        st["status"] = "armed"
        st["halt_reason"] = None
        st["armed_epic"] = epic_id
        st["armed_decompose"] = rel_idx
        st["armed_step"] = phase
        st["role"] = role_u
        st["pending_fingerprint_before"] = None
        save_epic_state(cwd_p, st)
        return {
            "ok": True,
            "complete": False,
            "phase": phase,
            "epic_id": epic_id,
            "role": role_u,
            "step_id": phase,
            "status": "pending",
            "index": rel_idx,
            "active_context": "memory-bank/activeContext.md",
            "qa_path": str(qa_p.relative_to(cwd_p)) if qa_p and qa_p.is_file() else None,
        }
    return {
        "ok": False,
        "error": f"unhandled phase {phase} for epic {epic_id}",
    }


def arm_pre_implement_context(
    cwd: str | Path,
    *,
    epic_id: str,
    role: str,
    phase: str,
    target_rel: str | None,
    decompose_rel: str | None = None,
) -> dict[str, Any]:
    """Arm activeContext for pre-implement phases (PLAN, DECOMPOSE, CLARIFY, ANALYZE)."""
    from loop.epic_transition import _legacy_warn
    _legacy_warn("arm_pre_implement_context")

    cwd_p = Path(cwd)
    role_key = str(role or "back").lower()
    from epic_paths import epic_id_from_plan_path, find_plan_md_path

    resolved_plan = find_plan_md_path(cwd_p, role_key, epic_id)
    if resolved_plan is not None:
        full_id = epic_id_from_plan_path(resolved_plan)
        if full_id:
            epic_id = full_id

    phase_u = str(phase or "").upper()
    role_u = str(role or "back").upper()
    if target_rel:
        pass
    elif resolved_plan is not None:
        try:
            target_rel = resolved_plan.relative_to(cwd_p).as_posix()
        except ValueError:
            target_rel = str(resolved_plan).replace("\\", "/")
    else:
        from loop.paths.epic_layout import EpicLayoutKind, resolve as layout_resolve

        target_rel = layout_resolve(
            role_key, epic_id, EpicLayoutKind.PLAN_MD, project_root=cwd_p
        ).relative_to(cwd_p).as_posix()
    link = target_rel.removeprefix("memory-bank/")
    next_cmd = f"{role_u} {phase_u}"
    load_now = (
        f"1. [{Path(target_rel).name}]({link}) — source plan/artifact for pre-implement phase {phase_u}.\n"
    )
    armed_decompose: str | None = None
    if phase_u == "ANALYZE" and decompose_rel:
        decomp_yaml = decompose_rel
        if decomp_yaml.endswith("index.md"):
            decomp_yaml = decomp_yaml[: -len("index.md")] + "index.yaml"
        decomp_link = decomp_yaml.removeprefix("memory-bank/")
        decomp_dir = Path(decompose_rel).parent.name
        load_now += (
            f"2. [`{decomp_dir}/index.yaml`]({decomp_link}) — decompose index for ANALYZE gate.\n"
        )
        armed_decompose = decomp_yaml
    elif phase_u == "DECOMPOSE":
        from epic_paths import find_decompose_index_path

        rule_dir = {
            "back": "back_developer",
            "front": "front_developer",
            "integration": "integration_developer",
        }.get(role_key, f"{role_key}_developer")
        idx = find_decompose_index_path(cwd_p, role_key, epic_id)
        if idx and idx.is_file():
            decomp_yaml = idx.relative_to(cwd_p).as_posix()
        else:
            decomp_yaml = f"memory-bank/{role_key}/plan/decompose-{epic_id}/index.yaml"
        decomp_link = decomp_yaml.removeprefix("memory-bank/")
        decomp_dir = Path(decomp_yaml).parent.name
        load_now += (
            f"2. `.cursor/templates/decompose/` — epic-step.yaml + index.md (канон sNN-<slug>.yaml).\n"
            f"3. `.cursor/rules/{rule_dir}/workflow-decompose.mdc` — §Maximal detail + §Replacement cleanup.\n"
            f"4. Target decompose: [`{decomp_dir}/index.yaml`]({decomp_link}) "
            f"(index.md + index.yaml + sNN-<slug>.yaml).\n"
        )
        armed_decompose = decomp_yaml if idx and idx.is_file() else None
    body = (
        f"---\n{_LOOP_HANDOFF_SCHEMA_LINE} # handoff\nrole: {role_u}\nmode: {phase_u}\nepic_id: {epic_id}\nstep_id: {phase_u}\n---\n\n"
        f"## load_now\n{load_now}\n"
        f"## Handoff {phase_u}\n"
        f"- # epic_id: {epic_id} — NOT short queue id\n"
        f"- **Эпик:** {epic_id} ({role_u}).\n"
        f"- **Режим/шаг:** `{next_cmd}`.\n"
        f"- **Дальше:** выполнить `{next_cmd}`.\n"
    )
    atomic_write_text(active_context_path(cwd_p), body)
    clear_runner_checkpoint(cwd_p)
    st = load_epic_state(cwd_p)
    st["active"] = True
    st["status"] = "armed"
    st["halt_reason"] = None
    st["armed_epic"] = epic_id
    st["armed_decompose"] = armed_decompose
    st["armed_step"] = phase_u
    st["role"] = role
    st["pending_fingerprint_before"] = None
    save_epic_state(cwd_p, st)
    return {
        "ok": True,
        "complete": False,
        "phase": phase_u,
        "epic_id": epic_id,
        "role": role,
        "step_id": phase_u,
        "target_rel": target_rel,
        "active_context": "memory-bank/activeContext.md",
    }
