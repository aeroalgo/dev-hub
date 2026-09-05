"""finish_implement_step orchestration logic."""

import hashlib
from pathlib import Path
from typing import Any

from harness.hooks._lib import ActiveContextLocked
from harness.hooks.epic.core import (
    _verify_pass_ready_for_step,
    atomic_write_text,
    epic_id_from_decompose_path,
    finalize_step,
    load_decompose_steps_fail_closed,
    load_epic_state,
    read_active_context,
    sync_cursor_from_index,
    utc_now,
    validate_finish_integrity,
    write_last_finish_tool,
)
from harness.hooks.epic_paths import find_decompose_index_path, role_from_decompose_path
from loop.mb_finish.render import render_active_context
from loop.mb_finish.schemas import (
    HandoffBody,
    LoadNowItem,
    LoopHandoffMeta,
    MbFinishRequest,
    MbFinishResult,
)
from loop.paths.pack_layout import resolve_mb_root


def _resolve_armed_decompose_index(cwd: Path) -> tuple[str | None, dict[str, Any]]:
    """Resolve armed decompose from loop epic state. Fail-closed when missing."""
    state = load_epic_state(cwd)
    decompose_rel = str(state.get("armed_decompose") or "").strip()
    if not decompose_rel:
        epic_id = str(state.get("armed_epic") or "").strip()
        role = str(state.get("armed_role") or state.get("role") or "back").strip()
        resolved = find_decompose_index_path(cwd, role, epic_id) if epic_id else None
        if resolved is not None and resolved.is_file():
            decompose_rel = resolved.relative_to(cwd).as_posix()
    if not decompose_rel:
        return None, state

    loaded = load_decompose_steps_fail_closed(cwd, decompose_rel)
    if not loaded.get("ok"):
        cand = Path(decompose_rel)
        if not cand.is_absolute():
            cand = cwd / cand
        parent = cand.parent if cand.is_file() else cand
        for name in ("index.yaml", "index.yml", "index.md", "decompose-index.yaml", "decompose-index.md"):
            alt = parent / name
            if alt.is_file():
                alt_rel = alt.relative_to(cwd).as_posix()
                loaded = load_decompose_steps_fail_closed(cwd, alt_rel)
                if loaded.get("ok"):
                    break

    if not loaded.get("ok"):
        return None, state
    index_ref = str(loaded.get("index") or decompose_rel).strip()
    from harness.hooks.epic_index import index_yaml_path

    index_path = Path(index_ref)
    if not index_path.is_absolute():
        index_path = cwd / index_path
    canonical_index = index_yaml_path(index_path)
    if canonical_index.is_file():
        index_ref = canonical_index.relative_to(cwd).as_posix()
    return index_ref or decompose_rel, state


def _resolve_work_shard_rel(cwd: Path, decompose_rel: str, step_id: str) -> str | None:
    """Resolve implement work shard path for step_id under armed decompose."""
    sid = step_id.strip().lower()
    loaded = load_decompose_steps_fail_closed(cwd, decompose_rel)
    if not loaded.get("ok"):
        return None
    idx_raw = loaded.get("index") or decompose_rel
    idx_path = Path(idx_raw)
    dec_dir = idx_path.parent if idx_path.is_file() else idx_path
    if not dec_dir.is_absolute():
        dec_dir = cwd / dec_dir
    if idx_path.name == "decompose-index.md" and idx_path.parent.name == "md":
        dec_dir = idx_path.parent.parent / "yaml" / "steps"
    elif idx_path.name in {"decompose-index.yaml", "decompose-index.yml"} and idx_path.parent.name == "yaml":
        dec_dir = idx_path.parent / "steps"
    for step in loaded.get("steps") or []:
        if str(step.get("id") or "").strip().lower() != sid:
            continue
        fname = str(step.get("file") or "").strip()
        if fname:
            shard = dec_dir / fname
            if shard.is_file():
                try:
                    return shard.relative_to(cwd).as_posix()
                except ValueError:
                    return str(shard)
    hits = sorted(dec_dir.glob(f"{sid}-*.yaml"))
    if hits:
        try:
            return hits[0].relative_to(cwd).as_posix()
        except ValueError:
            return str(hits[0])
    guess = dec_dir / f"{sid}.yaml"
    if guess.is_file():
        try:
            return guess.relative_to(cwd).as_posix()
        except ValueError:
            return str(guess)
    return None


def finish_implement_step(req: MbFinishRequest) -> MbFinishResult:
    """Orchestrate implement step finish atomically with rollback support."""
    cwd = Path(req.cwd).resolve()
    step_id = req.step_id.strip().lower()

    armed = load_epic_state(cwd)
    if str(armed.get("armed_step") or armed.get("phase") or "").upper() == "BUGFIX":
        return MbFinishResult(ok=False, diagnostic_codes=["bugfix_finish_required"], shape_errors=["Use mb-finish bugfix; do not finalize a completed implement step"])

    idx_ref, state = _resolve_armed_decompose_index(cwd)
    decompose_rel = str(state.get("armed_decompose") or idx_ref or "").strip()
    if not decompose_rel or not idx_ref:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["armed_decompose_missing"],
            shape_errors=[
                "armed_decompose missing or invalid in epic state; arm epic via loop prepare/arm"
            ],
        )
    role_str = (
        str(state.get("armed_role") or state.get("role") or "").strip().upper()
        or role_from_decompose_path(decompose_rel)
        or "BACK"
    )
    mode_str = req.phase.upper()
    epic_id = str(state.get("armed_epic") or "").strip()
    if not epic_id:
        epic_id = epic_id_from_decompose_path(decompose_rel) or "unknown"

    # 1. validate_finish_integrity(cwd, step_id)
    integrity = validate_finish_integrity(
        cwd=cwd,
        decompose=idx_ref,
        step_id=step_id,
        require_verify_pass=False,
    )
    if not integrity.get("ok"):
        codes = integrity.get("diagnostic_codes") or ["integrity_check_failed"]
        errors = integrity.get("errors") or []
        return MbFinishResult(
            ok=False,
            diagnostic_codes=codes,
            shape_errors=[str(e) for e in errors],
        )

    # 2. _verify_pass_ready_for_step(cwd, step_id)
    verify_res = _verify_pass_ready_for_step(cwd, step_id)
    if not verify_res.get("ok"):
        code = verify_res.get("diagnostic") or "verify_pass_required"
        err = verify_res.get("error") or "verify PASS required"
        return MbFinishResult(
            ok=False,
            diagnostic_codes=[code],
            shape_errors=[err],
        )

    # 3. Backup activeContext
    try:
        backup = read_active_context(cwd)
    except Exception as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["active_context_read_failed"],
            shape_errors=[str(exc)],
        )

    meta = LoopHandoffMeta(
        role=role_str,
        mode=mode_str,
        epic_id=epic_id,
        step_id=step_id,
    )

    shard_rel = _resolve_work_shard_rel(cwd, decompose_rel, step_id)
    load_now_path = shard_rel or decompose_rel
    load_now = [
        LoadNowItem(
            path=load_now_path,
            description=f"work shard ({role_str} {mode_str} {step_id})",
        )
    ]
    done_items = [req.done_summary] if req.done_summary else []
    handoff = HandoffBody(
        mode=mode_str,
        epic_id=epic_id,
        step_id=step_id,
        next_hint=f"продолжить работу по шагу {step_id}",
    )

    # 4 & 5. Render activeContext (raises ValueError if shape invalid)
    try:
        rendered = render_active_context(meta, load_now, done_items, handoff)
    except ValueError as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["shape_invalid"],
            shape_errors=[str(exc)],
        )
    except Exception as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["render_failed"],
            shape_errors=[str(exc)],
        )

    # 6. Write rendered to activeContext.md
    act_path = resolve_mb_root(cwd) / "activeContext.md"
    try:
        atomic_write_text(act_path, rendered)
    except ActiveContextLocked as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["runner_owns_active_context"],
            shape_errors=[str(exc)],
        )
    except Exception as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["active_context_write_failed"],
            shape_errors=[str(exc)],
        )

    # 7. finalize_step(cwd, step_id, done_summary)
    fin_res = finalize_step(
        cwd=cwd,
        decompose=idx_ref,
        step_id=step_id,
        require_verify=True,
    )

    # 8. On finalize failure: restore backup
    if not fin_res.get("ok"):
        try:
            atomic_write_text(act_path, backup)
        except Exception:
            pass
        err = fin_res.get("error") or "finalize step failed"
        diag = fin_res.get("diagnostic") or "finalize_failed"
        err_details = fin_res.get("errors") or [str(err)]
        return MbFinishResult(
            ok=False,
            diagnostic_codes=[diag],
            shape_errors=[str(e) for e in err_details],
        )

    fp_data = f"{step_id}:{utc_now()}"
    fp = hashlib.sha256(fp_data.encode("utf-8")).hexdigest()

    sync_cursor_from_index(cwd)
    try:
        active_context = read_active_context(cwd)
    except Exception:
        active_context = rendered

    st_after = load_epic_state(cwd)
    next_step = st_after.get("armed_step")
    next_phase = st_after.get("phase")
    epic_done = not st_after.get("active") and st_after.get("status") == "complete"

    write_last_finish_tool(
        cwd,
        "mb-finish implement",
        fp,
        finished_step=step_id,
        armed_after_finish=str(next_step) if next_step else None,
    )

    return MbFinishResult(
        ok=True,
        active_context=active_context,
        finished_step=step_id,
        next_step=next_step,
        next_phase=next_phase,
        epic_done=epic_done,
    )
