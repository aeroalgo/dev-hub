"""finish_handoff, finish_qa, and finish_bugfix implementation."""

import hashlib
from pathlib import Path
from harness.hooks.epic.core import (
    atomic_write_text,
    epic_id_from_decompose_path,
    gate_evidence_matches,
    handoff_post_implement_phase,
    latest_audit_artifact_for_reference,
    latest_bugfix_artifact_for_reference,
    latest_qa_any_artifact_for_reference,
    load_epic_state,
    read_active_context,
    reconcile_epic_events,
    save_epic_state,
    sync_cursor_from_index,
    utc_now,
    validate_qa_finish_handoff,
    write_last_finish_tool,
)
from loop.mb_finish.render import render_active_context
from loop.mb_finish.schemas import HandoffBody, LoadNowItem, LoopHandoffMeta, MbFinishRequest, MbFinishResult


def finish_handoff(
    meta: LoopHandoffMeta,
    load_now: list[LoadNowItem],
    handoff_body: HandoffBody,
    cwd: str | Path = ".",
) -> MbFinishResult:
    """Low-level escape hatch to render and write activeContext without finalizing step."""
    cwd_p = Path(cwd)
    act_path = cwd_p / "memory-bank" / "activeContext.md"

    try:
        backup = read_active_context(cwd_p)
    except OSError:
        backup = ""

    try:
        rendered = render_active_context(
            meta=meta,
            load_now=load_now,
            done=[],
            handoff=handoff_body,
        )
    except ValueError as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["rendered_shape_invalid"],
            shape_errors=[str(exc)],
        )
    except Exception as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["render_failed"],
            shape_errors=[str(exc)],
        )

    try:
        atomic_write_text(act_path, rendered)
    except Exception as exc:
        if backup:
            try:
                atomic_write_text(act_path, backup)
            except Exception:
                pass
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["active_context_write_failed"],
            shape_errors=[str(exc)],
        )

    gate = handoff_post_implement_phase(rendered)
    if gate:
        st = load_epic_state(cwd_p)
        st["armed_step"] = gate
        st["phase"] = gate
        st["active"] = True
        st["status"] = "armed"
        st["halt_reason"] = None
        save_epic_state(cwd_p, st)

    return MbFinishResult(
        ok=True,
        active_context=rendered,
    )


def finish_qa(req: MbFinishRequest) -> MbFinishResult:
    """Orchestrate QA phase finish atomically."""
    cwd = Path(req.cwd).resolve()
    act_path = cwd / "memory-bank" / "activeContext.md"

    # Load epic state to resolve epic_id and role
    state = load_epic_state(cwd)
    epic_id = state.get("armed_epic") or ""
    role = (state.get("armed_role") or "BACK").upper()
    role_dir = role.lower()

    if not epic_id:
        decompose = state.get("armed_decompose") or ""
        if decompose:
            epic_id = epic_id_from_decompose_path(decompose)

    qa_art = latest_qa_any_artifact_for_reference(cwd, role_dir, epic_id=epic_id)
    if not qa_art or not qa_art.is_file():
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["qa_artifact_missing"],
            shape_errors=["QA artifact missing or invalid"],
        )

    try:
        qa_rel = qa_art.relative_to(cwd).as_posix()
    except ValueError:
        qa_rel = str(qa_art)
    qa_link = qa_rel.removeprefix("memory-bank/")

    load_now = [
        LoadNowItem(path=qa_rel, description="QA pass artifact"),
    ]

    meta = LoopHandoffMeta(
        role=role,
        mode="REFLECT",
        epic_id=epic_id or None,
    )
    handoff_body = HandoffBody(
        mode="REFLECT",
        next_hint=req.done_summary or "reflection",
        epic_id=epic_id or None,
    )

    try:
        rendered = render_active_context(
            meta=meta,
            load_now=load_now,
            done=[],
            handoff=handoff_body,
        )
    except ValueError as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["rendered_shape_invalid"],
            shape_errors=[str(exc)],
        )
    except Exception as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["render_failed"],
            shape_errors=[str(exc)],
        )

    valid_qa, err_msg = validate_qa_finish_handoff(cwd, rendered, role_dir=role_dir, epic_id=epic_id)
    if not valid_qa:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["qa_validation_failed"],
            shape_errors=[err_msg or "QA validation failed"],
        )

    try:
        backup = read_active_context(cwd)
    except OSError:
        backup = ""

    try:
        atomic_write_text(act_path, rendered)
    except Exception as exc:
        if backup:
            try:
                atomic_write_text(act_path, backup)
            except Exception:
                pass
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["active_context_write_failed"],
            shape_errors=[str(exc)],
        )

    role_dir = role.lower()
    if role_dir == "integ":
        role_dir = "integration"
    if epic_id:
        reconcile_epic_events(cwd, role_dir, epic_id)

    sync_cursor_from_index(cwd)

    st = load_epic_state(cwd)
    st["armed_step"] = "REFLECT"
    st["phase"] = "REFLECT"
    st["active"] = True
    st["status"] = "armed"
    st["halt_reason"] = None
    save_epic_state(cwd, st)

    fp_data = f"qa:{utc_now()}"
    fp = hashlib.sha256(fp_data.encode("utf-8")).hexdigest()
    write_last_finish_tool(cwd, "mb-finish qa", fp)

    return MbFinishResult(
        ok=True,
        active_context=rendered,
    )


def finish_bugfix(req: MbFinishRequest) -> MbFinishResult:
    """Orchestrate Bugfix phase finish atomically."""
    cwd = Path(req.cwd).resolve()
    act_path = cwd / "memory-bank" / "activeContext.md"

    state = load_epic_state(cwd)
    epic_id = state.get("armed_epic") or ""
    role = (state.get("armed_role") or "BACK").upper()
    role_dir = role.lower()
    if role_dir == "integ":
        role_dir = "integration"

    if not epic_id:
        decompose = state.get("armed_decompose") or ""
        if decompose:
            epic_id = epic_id_from_decompose_path(decompose)

    if not epic_id:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["bugfix_epic_missing"],
            shape_errors=["Bugfix finish requires armed epic_id"],
        )

    bugfix_art = latest_bugfix_artifact_for_reference(
        cwd, role_dir, epic_id=epic_id
    )
    if not bugfix_art or not bugfix_art.is_file():
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["bugfix_artifact_missing"],
            shape_errors=[
                f"Bugfix artifact missing: memory-bank/{role_dir}/bugfix/"
                f"{epic_id}/bugfix-*.md"
            ],
        )

    try:
        bugfix_rel = bugfix_art.relative_to(cwd).as_posix()
    except ValueError:
        bugfix_rel = str(bugfix_art)

    load_now = [
        LoadNowItem(path=bugfix_rel, description="Bugfix artifact"),
    ]

    meta = LoopHandoffMeta(
        role=role,
        mode="QA",
        epic_id=epic_id or None,
        step_id=req.step_id or None,
    )
    handoff_body = HandoffBody(
        mode="QA",
        next_hint=req.done_summary or "verify bugfix via QA",
        epic_id=epic_id or None,
        step_id=req.step_id or None,
    )

    try:
        rendered = render_active_context(
            meta=meta,
            load_now=load_now,
            done=[],
            handoff=handoff_body,
        )
    except ValueError as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["rendered_shape_invalid"],
            shape_errors=[str(exc)],
        )
    except Exception as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["render_failed"],
            shape_errors=[str(exc)],
        )

    try:
        backup = read_active_context(cwd)
    except OSError:
        backup = ""

    try:
        atomic_write_text(act_path, rendered)
    except Exception as exc:
        if backup:
            try:
                atomic_write_text(act_path, backup)
            except Exception:
                pass
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["active_context_write_failed"],
            shape_errors=[str(exc)],
        )

    reconcile_epic_events(cwd, role_dir, epic_id)

    st = load_epic_state(cwd)
    st["armed_step"] = "QA"
    st["phase"] = "QA"
    st["active"] = True
    st["status"] = "armed"
    st["halt_reason"] = None
    save_epic_state(cwd, st)

    sync_cursor_from_index(cwd)

    fp_data = f"bugfix:{utc_now()}"
    fp = hashlib.sha256(fp_data.encode("utf-8")).hexdigest()
    write_last_finish_tool(cwd, "mb-finish bugfix", fp)

    return MbFinishResult(
        ok=True,
        active_context=rendered,
    )


def finish_decompose(
    req: MbFinishRequest,
) -> MbFinishResult:
    """Orchestrate DECOMPOSE phase finish atomically with Transition Engine delegation."""
    cwd = Path(req.cwd).resolve()
    act_path = cwd / "memory-bank" / "activeContext.md"

    state = load_epic_state(cwd)
    epic_id = state.get("armed_epic") or ""
    role = (state.get("armed_role") or "BACK").upper()
    decompose_rel = state.get("armed_decompose") or ""

    if not epic_id and decompose_rel:
        epic_id = epic_id_from_decompose_path(decompose_rel)

    if not decompose_rel:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["decompose_artifact_missing"],
            shape_errors=["Decompose artifact path missing from epic state"],
        )

    # Validate decompose tree
    from harness.hooks.epic_yaml import validate_decompose_tree
    tree_errors = validate_decompose_tree(cwd, decompose_rel)
    if tree_errors:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["decompose_tree_invalid"],
            shape_errors=tree_errors,
        )

    load_now = [
        LoadNowItem(path=decompose_rel, description="Decompose index"),
    ]

    meta = LoopHandoffMeta(
        role=role,
        mode="ANALYZE",
        epic_id=epic_id or None,
        step_id=req.step_id or None,
    )
    handoff_body = HandoffBody(
        mode="ANALYZE",
        next_hint=req.done_summary or "run analyze phase",
        epic_id=epic_id or None,
        step_id=req.step_id or None,
    )

    try:
        rendered = render_active_context(
            meta=meta,
            load_now=load_now,
            done=[],
            handoff=handoff_body,
        )
    except ValueError as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["rendered_shape_invalid"],
            shape_errors=[str(exc)],
        )
    except Exception as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["render_failed"],
            shape_errors=[str(exc)],
        )

    backup = None
    if act_path.exists():
        try:
            backup = act_path.read_text(encoding="utf-8")
        except Exception:
            backup = None

    try:
        atomic_write_text(act_path, rendered)
    except Exception as exc:
        if backup:
            try:
                atomic_write_text(act_path, backup)
            except Exception:
                pass
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["active_context_write_failed"],
            shape_errors=[str(exc)],
        )

    from loop.epic_transition import promote_if_ready
    promote_if_ready(cwd, epic_id, role)

    sync_cursor_from_index(cwd)

    fp_data = f"decompose:{utc_now()}"
    fp = hashlib.sha256(fp_data.encode("utf-8")).hexdigest()
    write_last_finish_tool(cwd, "mb-finish decompose", fp)

    return MbFinishResult(
        ok=True,
        active_context=rendered,
    )


def finish_plan(
    req: MbFinishRequest,
) -> MbFinishResult:
    """Orchestrate PLAN phase finish atomically with Transition Engine delegation."""
    cwd = Path(req.cwd).resolve()
    act_path = cwd / "memory-bank" / "activeContext.md"

    state = load_epic_state(cwd)
    epic_id = state.get("armed_epic") or ""
    role = (state.get("armed_role") or "BACK").upper()
    plan_rel = state.get("armed_plan") or ""

    if not plan_rel and epic_id:
        role_dir = role.lower()
        cand = cwd / "memory-bank" / role_dir / "plan" / f"plan-{epic_id}.md"
        if cand.exists():
            plan_rel = str(cand.relative_to(cwd))

    if not plan_rel or not (cwd / plan_rel).exists():
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["plan_artifact_missing"],
            shape_errors=["Plan artifact missing"],
        )

    load_now = [
        LoadNowItem(path=plan_rel, description="Plan document"),
    ]

    meta = LoopHandoffMeta(
        role=role,
        mode="DECOMPOSE",
        epic_id=epic_id or None,
        step_id=req.step_id or None,
    )
    handoff_body = HandoffBody(
        mode="DECOMPOSE",
        next_hint=req.done_summary or "decompose plan into steps",
        epic_id=epic_id or None,
        step_id=req.step_id or None,
    )

    try:
        rendered = render_active_context(
            meta=meta,
            load_now=load_now,
            done=[],
            handoff=handoff_body,
        )
    except ValueError as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["rendered_shape_invalid"],
            shape_errors=[str(exc)],
        )
    except Exception as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["render_failed"],
            shape_errors=[str(exc)],
        )

    backup = None
    if act_path.exists():
        try:
            backup = act_path.read_text(encoding="utf-8")
        except Exception:
            backup = None

    try:
        atomic_write_text(act_path, rendered)
    except Exception as exc:
        if backup:
            try:
                atomic_write_text(act_path, backup)
            except Exception:
                pass
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["active_context_write_failed"],
            shape_errors=[str(exc)],
        )

    from loop.epic_transition import promote_if_ready
    promote_if_ready(cwd, epic_id, role)

    sync_cursor_from_index(cwd)

    fp_data = f"plan:{utc_now()}"
    fp = hashlib.sha256(fp_data.encode("utf-8")).hexdigest()
    write_last_finish_tool(cwd, "mb-finish plan", fp)

    return MbFinishResult(
        ok=True,
        active_context=rendered,
    )


def finish_analyze(
    req: MbFinishRequest,
) -> MbFinishResult:
    """Orchestrate ANALYZE phase finish atomically."""
    cwd = Path(req.cwd).resolve()
    act_path = cwd / "memory-bank" / "activeContext.md"

    state = load_epic_state(cwd)
    epic_id = state.get("armed_epic") or ""
    role = (state.get("armed_role") or "BACK").upper()
    decompose_rel = state.get("armed_decompose") or ""

    if not epic_id and decompose_rel:
        epic_id = epic_id_from_decompose_path(decompose_rel)

    evidence = state.get("last_verify_evidence")
    matched, diagnostic = gate_evidence_matches(cwd, evidence) if evidence else (False, "gate_evidence_missing")
    if not matched:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["gate_evidence_missing"],
            shape_errors=[f"Gate evidence invalid or missing: {diagnostic}"],
        )

    load_now = []
    if decompose_rel:
        load_now.append(LoadNowItem(path=decompose_rel, description="Decompose index"))

    meta = LoopHandoffMeta(
        role=role,
        mode="IMPLEMENT",
        epic_id=epic_id or None,
        step_id=req.step_id or None,
    )
    handoff_body = HandoffBody(
        mode="IMPLEMENT",
        next_hint=req.done_summary or "implement first step",
        epic_id=epic_id or None,
        step_id=req.step_id or None,
    )

    try:
        rendered = render_active_context(
            meta=meta,
            load_now=load_now,
            done=[],
            handoff=handoff_body,
        )
    except ValueError as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["rendered_shape_invalid"],
            shape_errors=[str(exc)],
        )
    except Exception as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["render_failed"],
            shape_errors=[str(exc)],
        )

    backup = None
    if act_path.exists():
        try:
            backup = act_path.read_text(encoding="utf-8")
        except Exception:
            backup = None

    try:
        atomic_write_text(act_path, rendered)
    except Exception as exc:
        if backup:
            try:
                atomic_write_text(act_path, backup)
            except Exception:
                pass
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["active_context_write_failed"],
            shape_errors=[str(exc)],
        )

    from loop.epic_transition import promote_if_ready
    promote_if_ready(cwd, epic_id, role)

    sync_cursor_from_index(cwd)

    fp_data = f"analyze:{utc_now()}"
    fp = hashlib.sha256(fp_data.encode("utf-8")).hexdigest()
    write_last_finish_tool(cwd, "mb-finish analyze", fp)

    return MbFinishResult(
        ok=True,
        active_context=rendered,
    )


def finish_audit(
    req: MbFinishRequest,
) -> MbFinishResult:
    """Orchestrate AUDIT phase finish atomically."""
    cwd = Path(req.cwd).resolve()
    act_path = cwd / "memory-bank" / "activeContext.md"

    state = load_epic_state(cwd)
    epic_id = state.get("armed_epic") or ""
    role = (state.get("armed_role") or "BACK").upper()
    role_dir = role.lower()

    if not epic_id:
        decompose = state.get("armed_decompose") or ""
        if decompose:
            epic_id = epic_id_from_decompose_path(decompose)

    audit_art_path = latest_audit_artifact_for_reference(cwd, epic_id=epic_id)
    audit_art = Path(audit_art_path) if audit_art_path else None
    if not audit_art or not audit_art.is_file():
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["audit_artifact_missing"],
            shape_errors=["Audit artifact missing or invalid"],
        )

    try:
        content = audit_art.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError("empty file")
    except Exception as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["audit_artifact_invalid"],
            shape_errors=[f"Audit artifact invalid: {exc}"],
        )

    try:
        audit_rel = audit_art.relative_to(cwd).as_posix()
    except ValueError:
        audit_rel = str(audit_art)

    load_now = [
        LoadNowItem(path=audit_rel, description="Audit artifact"),
    ]

    meta = LoopHandoffMeta(
        role=role,
        mode="QA",
        epic_id=epic_id or None,
        step_id=req.step_id or None,
    )
    handoff_body = HandoffBody(
        mode="QA",
        next_hint=req.done_summary or "run qa phase",
        epic_id=epic_id or None,
        step_id=req.step_id or None,
    )

    try:
        rendered = render_active_context(
            meta=meta,
            load_now=load_now,
            done=[],
            handoff=handoff_body,
        )
    except ValueError as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["rendered_shape_invalid"],
            shape_errors=[str(exc)],
        )
    except Exception as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["render_failed"],
            shape_errors=[str(exc)],
        )

    backup = None
    if act_path.exists():
        try:
            backup = act_path.read_text(encoding="utf-8")
        except Exception:
            backup = None

    try:
        atomic_write_text(act_path, rendered)
    except Exception as exc:
        if backup:
            try:
                atomic_write_text(act_path, backup)
            except Exception:
                pass
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["active_context_write_failed"],
            shape_errors=[str(exc)],
        )

    from loop.epic_transition import promote_if_ready
    promote_if_ready(cwd, epic_id, role)

    sync_cursor_from_index(cwd)

    fp_data = f"audit:{utc_now()}"
    fp = hashlib.sha256(fp_data.encode("utf-8")).hexdigest()
    write_last_finish_tool(cwd, "mb-finish audit", fp)

    return MbFinishResult(
        ok=True,
        active_context=rendered,
    )


def finish_creative(
    req: MbFinishRequest,
) -> MbFinishResult:
    """Orchestrate CREATIVE phase finish atomically."""
    cwd = Path(req.cwd).resolve()
    act_path = cwd / "memory-bank" / "activeContext.md"

    state = load_epic_state(cwd)
    epic_id = state.get("armed_epic") or ""
    role = (state.get("armed_role") or "BACK").upper()
    role_dir = role.lower()
    decompose_rel = state.get("armed_decompose") or ""

    if not epic_id and decompose_rel:
        epic_id = epic_id_from_decompose_path(decompose_rel)

    # Validate creative artifact presence
    from harness.hooks.epic.core import _task_id_from_epic
    task_id = _task_id_from_epic(epic_id)
    creative_dir = cwd / "memory-bank" / role_dir / "creative"
    creative_art = None
    if creative_dir.is_dir():
        for p in sorted(creative_dir.glob("creative-*.md"), reverse=True):
            if not epic_id or (epic_id in p.name or (task_id and task_id in p.name)):
                creative_art = p
                break
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")[:800]
                if epic_id in txt or (task_id and task_id in txt):
                    creative_art = p
                    break
            except OSError:
                continue

    if not creative_art or not creative_art.is_file():
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["creative_artifact_missing"],
            shape_errors=["Creative artifact missing or invalid"],
        )

    try:
        creative_rel = creative_art.relative_to(cwd).as_posix()
    except ValueError:
        creative_rel = str(creative_art)

    load_now = [
        LoadNowItem(path=creative_rel, description="Creative artifact"),
    ]
    if decompose_rel:
        load_now.append(LoadNowItem(path=decompose_rel, description="Decompose index"))

    meta = LoopHandoffMeta(
        role=role,
        mode="IMPLEMENT",
        epic_id=epic_id or None,
        step_id=req.step_id or None,
    )
    handoff_body = HandoffBody(
        mode="IMPLEMENT",
        next_hint=req.done_summary or "implement first step",
        epic_id=epic_id or None,
        step_id=req.step_id or None,
    )

    try:
        rendered = render_active_context(
            meta=meta,
            load_now=load_now,
            done=[],
            handoff=handoff_body,
        )
    except ValueError as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["rendered_shape_invalid"],
            shape_errors=[str(exc)],
        )
    except Exception as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["render_failed"],
            shape_errors=[str(exc)],
        )

    backup = None
    if act_path.exists():
        try:
            backup = act_path.read_text(encoding="utf-8")
        except Exception:
            backup = None

    try:
        atomic_write_text(act_path, rendered)
    except Exception as exc:
        if backup:
            try:
                atomic_write_text(act_path, backup)
            except Exception:
                pass
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["active_context_write_failed"],
            shape_errors=[str(exc)],
        )

    from loop.epic_transition import promote_if_ready
    promote_if_ready(cwd, epic_id, role)

    sync_cursor_from_index(cwd)

    fp_data = f"creative:{utc_now()}"
    fp = hashlib.sha256(fp_data.encode("utf-8")).hexdigest()
    write_last_finish_tool(cwd, "mb-finish creative", fp)

    return MbFinishResult(
        ok=True,
        active_context=rendered,
    )


def finish_reflect(
    req: MbFinishRequest,
) -> MbFinishResult:
    """Orchestrate REFLECT phase finish atomically."""
    cwd = Path(req.cwd).resolve()
    act_path = cwd / "memory-bank" / "activeContext.md"

    state = load_epic_state(cwd)
    epic_id = state.get("armed_epic") or ""
    role = (state.get("armed_role") or "BACK").upper()
    role_dir = role.lower()
    decompose_rel = state.get("armed_decompose") or ""

    if not epic_id and decompose_rel:
        epic_id = epic_id_from_decompose_path(decompose_rel)

    from harness.hooks.epic.core import find_reflection_artifact
    refl_art = find_reflection_artifact(cwd, role_dir, epic_id)
    if not refl_art or not refl_art.is_file():
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["reflection_artifact_missing"],
            shape_errors=["Reflection artifact missing or invalid"],
        )

    try:
        refl_rel = refl_art.relative_to(cwd).as_posix()
    except ValueError:
        refl_rel = str(refl_art)

    load_now = [
        LoadNowItem(path=refl_rel, description="Reflection artifact"),
    ]

    meta = LoopHandoffMeta(
        role=role,
        mode="NEXT_CYCLE",
        epic_id=epic_id or None,
        step_id=req.step_id or None,
    )
    handoff_body = HandoffBody(
        mode="NEXT_CYCLE",
        next_hint=req.done_summary or "epic complete, select next work",
        epic_id=epic_id or None,
        step_id=req.step_id or None,
    )

    try:
        rendered = render_active_context(
            meta=meta,
            load_now=load_now,
            done=[],
            handoff=handoff_body,
        )
    except ValueError as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["rendered_shape_invalid"],
            shape_errors=[str(exc)],
        )
    except Exception as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["render_failed"],
            shape_errors=[str(exc)],
        )

    backup = None
    if act_path.exists():
        try:
            backup = act_path.read_text(encoding="utf-8")
        except Exception:
            backup = None

    try:
        atomic_write_text(act_path, rendered)
    except Exception as exc:
        if backup:
            try:
                atomic_write_text(act_path, backup)
            except Exception:
                pass
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["active_context_write_failed"],
            shape_errors=[str(exc)],
        )

    sync_cursor_from_index(cwd)

    fp_data = f"reflect:{utc_now()}"
    fp = hashlib.sha256(fp_data.encode("utf-8")).hexdigest()
    write_last_finish_tool(cwd, "mb-finish reflect", fp)

    return MbFinishResult(
        ok=True,
        active_context=rendered,
    )

