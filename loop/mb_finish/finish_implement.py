"""finish_implement_step orchestration logic."""

import hashlib
from pathlib import Path
from typing import Any

from harness.hooks.epic.core import (
    _decompose_index_path,
    _verify_pass_ready_for_step,
    atomic_write_text,
    epic_id_from_decompose_path,
    finalize_step,
    read_active_context,
    utc_now,
    validate_finish_integrity,
    write_last_finish_tool,
)
from loop.mb_finish.render import render_active_context
from loop.mb_finish.schemas import (
    HandoffBody,
    LoadNowItem,
    LoopHandoffMeta,
    MbFinishRequest,
    MbFinishResult,
)


def _find_decompose_index(cwd: Path) -> Path | None:
    """Find active decompose index in memory-bank."""
    for role_dir in ("back", "front", "integration"):
        plan_dir = cwd / "memory-bank" / role_dir / "plan"
        if not plan_dir.exists():
            continue
        for item in plan_dir.glob("decompose-*"):
            idx_yaml = item / "index.yaml"
            if idx_yaml.exists():
                return item / "index.md"
            idx_md = item / "index.md"
            if idx_md.exists():
                return idx_md
    return None


def finish_implement_step(req: MbFinishRequest) -> MbFinishResult:
    """Orchestrate implement step finish atomically with rollback support."""
    cwd = Path(req.cwd).resolve()
    step_id = req.step_id.strip().lower()

    # Find decompose index path
    idx_path = _find_decompose_index(cwd)

    # 1. validate_finish_integrity(cwd, step_id)
    integrity = validate_finish_integrity(
        cwd=cwd,
        decompose=idx_path,
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

    role_str = "BACK"
    mode_str = req.phase.upper()
    epic_id = "unknown"
    if idx_path:
        epic_id = epic_id_from_decompose_path(str(idx_path)) or epic_id

    meta = LoopHandoffMeta(
        role=role_str,
        mode=mode_str,
        epic_id=epic_id,
        step_id=step_id,
    )

    load_now = [
        LoadNowItem(
            path=f"back/plan/decompose-{epic_id}/{step_id}.yaml",
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
    act_path = cwd / "memory-bank" / "activeContext.md"
    try:
        atomic_write_text(act_path, rendered)
    except Exception as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["active_context_write_failed"],
            shape_errors=[str(exc)],
        )

    # 7. finalize_step(cwd, step_id, done_summary)
    fin_res = finalize_step(
        cwd=cwd,
        decompose=idx_path,
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
    write_last_finish_tool(cwd, "mb-finish implement", fp)

    return MbFinishResult(
        ok=True,
        active_context=rendered,
    )
