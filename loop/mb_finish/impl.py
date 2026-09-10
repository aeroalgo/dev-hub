"""finish_handoff, finish_qa, and finish_bugfix implementation."""

import hashlib
import os
import re
from pathlib import Path
from harness.hooks._lib import ActiveContextLocked
from harness.hooks.epic.core import (
    _append_event,
    event_persisted,
    _verify_pass_ready_for_step,
    atomic_write_text,
    epic_id_from_decompose_path,
    extract_load_now,
    find_decompose_index_path,
    gate_evidence_matches,
    handoff_post_implement_phase,
    latest_audit_artifact_for_reference,
    latest_bugfix_artifact_for_reference,
    lifecycle_arm_phase,
    reduce_epic_lifecycle,
    latest_qa_any_artifact_for_reference,
    load_epic_state,
    parse_qa_verdict,
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
from loop.mb_finish.transaction import (
    FinishTxRecord,
    FinishTxState,
    commit_staged_files,
    recover_finish_transaction,
    rollback_staged_files,
    stage_file_in_tx,
    write_finish_tx,
)
from loop.paths.pack_layout import resolve_mb_root
from loop.schemas.state import QaAfterBugfix
from loop.qa_outcome import extract_changed_paths, suite_plan_after_changes


def finish_handoff(
    meta: LoopHandoffMeta,
    load_now: list[LoadNowItem],
    handoff_body: HandoffBody,
    cwd: str | Path = ".",
    recovery_token: str | None = None,
) -> MbFinishResult:
    """Internal finish_handoff requiring recovery_token matching active journal id.

    FR-007 / US-002: Tokenless calls return finish_handoff_forbidden.
    """
    from loop.mb_finish.transaction import read_finish_tx

    cwd_p = Path(cwd)
    tx = read_finish_tx(cwd_p)
    expected_token = tx.tx_id if tx else None

    if not recovery_token or recovery_token != expected_token:
        # Log incident / reject
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["finish_handoff_forbidden"],
            shape_errors=[
                "finish_handoff is internal only and requires a valid recovery_token matching the finish transaction journal"
            ],
        )

    act_path = resolve_mb_root(cwd_p) / "activeContext.md"
    state = load_epic_state(cwd_p)
    if str(state.get("armed_step") or state.get("phase") or "").upper() == "BUGFIX" and meta.mode.upper() != "BUGFIX":
        return MbFinishResult(ok=False, diagnostic_codes=["bugfix_finish_required"], shape_errors=["Use mb-finish bugfix with a bugfix artifact and verify-bugfix PASS"])

    # FR-003 / US-003 / SC-003: Escape hatch closed.
    # If latest QA verdict for the armed epic is fail or blocked, finish_handoff cannot write DONE/IMPLEMENT/ANALYZE/DECOMPOSE/PLAN/QA success.
    # BUGFIX mode is the only allowed transition.
    epic_for_qa = str(meta.epic_id or state.get("armed_epic") or "").strip()
    role_for_qa = str(meta.role or state.get("armed_role") or "back").strip().lower()
    if role_for_qa == "integ":
        role_for_qa = "integration"
    if epic_for_qa:
        latest_qa = latest_qa_any_artifact_for_reference(cwd_p, role_for_qa, epic_id=epic_for_qa)
        if latest_qa:
            v = parse_qa_verdict(latest_qa)
            if v in {"fail", "blocked"} and meta.mode.upper() != "BUGFIX":
                return MbFinishResult(
                    ok=False,
                    diagnostic_codes=["qa_fail_blocks_handoff"],
                    shape_errors=[
                        f"Latest QA artifact {latest_qa.name} has verdict '{v}'. Cannot finish handoff to '{meta.mode}'. Only BUGFIX is allowed."
                    ],
                )

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
    except ActiveContextLocked as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["runner_owns_active_context"],
            shape_errors=[str(exc)],
        )
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
    act_path = resolve_mb_root(cwd) / "activeContext.md"

    # Load epic state to resolve epic_id and role
    state = load_epic_state(cwd)
    if str(state.get("phase") or state.get("armed_step") or "").upper() == "BUGFIX":
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["bugfix_finish_required"],
            shape_errors=["QA cannot finish while BUGFIX is active; finish BUGFIX first, then start a new QA run"],
        )
    epic_id = state.get("armed_epic") or ""
    role = (state.get("armed_role") or "BACK").upper()
    role_dir = role.lower()
    if role_dir == "integ":
        role_dir = "integration"

    phase_run_id = (
        state.get("phase_run_id")
        or state.get("session_id")
        or os.environ.get("EPIC_RUNNER_SESSION_ID")
    )

    if not epic_id:
        decompose = state.get("armed_decompose") or ""
        if decompose:
            epic_id = epic_id_from_decompose_path(decompose)

    rerun = state.get("qa_after_bugfix")
    qa_art = latest_qa_any_artifact_for_reference(cwd, role_dir, epic_id=epic_id)
    if rerun is not None:
        rerun = QaAfterBugfix.model_validate(rerun)
        if rerun.epic_id == epic_id:
            if not phase_run_id or phase_run_id == rerun.phase_run_id:
                return MbFinishResult(
                    ok=False,
                    diagnostic_codes=["qa_new_session_required"],
                    shape_errors=["BUGFIX finished; stop this session and start a new QA run"],
                )
            qa_dir = resolve_mb_root(cwd) / role_dir / "qa" / epic_id
            candidates = [
                path for path in sorted(qa_dir.glob("*.yaml"), reverse=True)
                if path.name == "qa.yaml" or path.name.startswith("qa-")
            ]
            qa_art = next((
                path for path in candidates
                if path.relative_to(cwd).as_posix() not in rerun.existing_artifacts
            ), None)
            if qa_art is None:
                return MbFinishResult(
                    ok=False,
                    diagnostic_codes=["qa_new_artifact_required"],
                    shape_errors=["Write a new qa-*.yaml run artifact after BUGFIX; earlier artifacts cannot close QA"],
                )
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
    try:
        mb_root_name = resolve_mb_root(cwd).name
        qa_link = qa_rel.removeprefix(f"{mb_root_name}/").removeprefix("memory-bank/")
    except Exception:
        qa_link = qa_rel.removeprefix("memory-bank/")

    load_now = [
        LoadNowItem(path=qa_rel, description="QA pass artifact"),
    ]

    qa_verdict = parse_qa_verdict(qa_art)
    if qa_verdict is None:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["qa_verdict_missing"],
            shape_errors=["qa-*.yaml missing or invalid verdict (must be pass, fail, or blocked)"],
        )
    # A QA artifact is only a report.  Closing QA requires a fresh autonomous
    # verify-qa receipt for the current run.  Re-QA already had this check;
    # applying it to normal QA closes the path that previously forged qa_pass.
    reviewer_required = bool(state.get("active")) or (
        rerun is not None and rerun.epic_id == epic_id
    )
    if qa_verdict == "pass" and reviewer_required:
        reviewer = state.get("last_reviewer_evidence")
        matched, _ = gate_evidence_matches(cwd, reviewer)
        verifier_identity = (
            str(reviewer.get("verifier_identity") or reviewer.get("agent_id") or "").strip()
            if isinstance(reviewer, dict)
            else ""
        )
        if (
            state.get("last_reviewer_verdict") != "PASS"
            or state.get("reviewer_done") is not True
            or not phase_run_id
            or state.get("last_reviewer_phase_run_id") != phase_run_id
            or not isinstance(reviewer, dict)
            or str(reviewer.get("step") or "").upper() != "QA"
            or verifier_identity not in {"verify-qa", "reviewer"}
            or reviewer.get("authority") == "manual"
            or not matched
        ):
            return MbFinishResult(
                ok=False,
                diagnostic_codes=["qa_reviewer_required"],
                shape_errors=["The current QA run requires its own autonomous verify-qa PASS receipt before FINISH"],
            )
    if qa_verdict in {"fail", "blocked"}:
        next_mode = "BUGFIX"
        default_hint = "fix QA blockers via BUGFIX"
    else:
        next_mode = "DONE"
        default_hint = "EPIC_DONE"

    meta = LoopHandoffMeta(
        role=role,
        mode=next_mode,
        epic_id=epic_id or None,
    )
    from harness.hooks.context_telemetry import build_finish_receipt, format_telemetry_summary
    session_id = str(state.get("session_id") or os.environ.get("PROJECT_LOOP_SESSION_ID") or "").strip()
    receipt = None
    if session_id:
        receipt = build_finish_receipt(cwd, session_id, epic_id=epic_id)
        if receipt.status in ("corrupt", "non_green"):
            diag_code = receipt.aggregate.diagnostic_code or "telemetry_corrupt"
            return MbFinishResult(
                ok=False,
                diagnostic_codes=[diag_code],
                shape_errors=[f"Context telemetry is non-green: {receipt.diagnostics}"],
            )

    handoff_body = HandoffBody(
        mode=next_mode,
        next_hint=req.done_summary or default_hint,
        epic_id=epic_id or None,
        telemetry_summary=format_telemetry_summary(receipt) if receipt and receipt.status == "green" else None,
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

    valid_qa, err_msg = validate_qa_finish_handoff(cwd, rendered, role_dir=role_dir, epic_id=epic_id, qa_artifact=qa_art)
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

    # Transaction Journal: stage activeContext, commit and record states
    tx_id = f"tx-qa-{epic_id or 'none'}-{hashlib.sha256(utc_now().encode('utf-8')).hexdigest()[:8]}"
    act_rel = str(act_path.relative_to(cwd)) if act_path.is_relative_to(cwd) else "memory-bank/activeContext.md"

    staged_act = stage_file_in_tx(cwd, tx_id, act_rel, rendered)
    tx_rec = FinishTxRecord(
        tx_id=tx_id,
        epic_id=epic_id or "",
        step_id="QA",
        phase="BACK QA",
        state=FinishTxState.PREPARED,
        staged_files=[staged_act],
        recovery_token=tx_id,
    )
    write_finish_tx(cwd, tx_rec)

    try:
        commit_staged_files(cwd, [staged_act])
        tx_rec.state = FinishTxState.CONTEXT_WRITTEN
        write_finish_tx(cwd, tx_rec)
    except ActiveContextLocked as exc:
        rollback_staged_files(cwd, tx_rec.staged_files)
        tx_rec.state = FinishTxState.ROLLBACK_REQUIRED
        tx_rec.error = str(exc)
        write_finish_tx(cwd, tx_rec)
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["runner_owns_active_context"],
            shape_errors=[str(exc)],
        )
    except Exception as exc:
        rollback_staged_files(cwd, tx_rec.staged_files)
        tx_rec.state = FinishTxState.ROLLBACK_REQUIRED
        tx_rec.error = str(exc)
        write_finish_tx(cwd, tx_rec)
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["active_context_write_failed"],
            shape_errors=[str(exc)],
        )

    role_dir = role.lower()
    if role_dir == "integ":
        role_dir = "integration"
    if epic_id:
        qa_kind = "qa_fail" if qa_verdict in {"fail", "blocked"} else "qa_pass"
        event_written = _append_event(cwd, role_dir, epic_id, qa_kind, qa_art)
        if not event_written and not event_persisted(
            cwd, role_dir, epic_id, qa_kind, qa_art
        ):
            # The context has already been committed to the finish journal,
            # so restore it before returning.  A phase must never report DONE
            # while its durable reducer event is missing.
            rollback_staged_files(cwd, tx_rec.staged_files)
            tx_rec.state = FinishTxState.ROLLBACK_REQUIRED
            tx_rec.error = "qa lifecycle event was not persisted"
            write_finish_tx(cwd, tx_rec)
            return MbFinishResult(
                ok=False,
                diagnostic_codes=["qa_event_persist_failed"],
                shape_errors=[
                    "QA finish rolled back: qa_pass/qa_fail lifecycle event was not persisted"
                ],
            )
        reconcile_epic_events(cwd, role_dir, epic_id)

    sync_cursor_from_index(cwd)

    st = load_epic_state(cwd)
    st["armed_step"] = next_mode
    st["phase"] = next_mode
    st["active"] = next_mode != "DONE"
    st["status"] = "complete" if next_mode == "DONE" else "armed"
    st["halt_reason"] = None
    st["qa_after_bugfix"] = None
    from loop.qa_checklist_freeze import (
        REQA_CYCLE_MAX,
        bump_reqa_cycle,
        ensure_freeze,
        finish_qa_freeze_errors,
        freeze_from_qa_checks,
        load_freeze,
        persist_freeze,
        read_qa_artifact_lists,
        with_prior_blockers,
        with_verify_scope,
    )

    if next_mode == "DONE":
        persist_freeze(st, None)
    elif epic_id:
        checks, blockers, ac_plus, ac_minus, _art_sha, section_011 = read_qa_artifact_lists(qa_art)
        freeze_errors = finish_qa_freeze_errors(
            path=qa_art,
            freeze=load_freeze(st) or ensure_freeze(cwd, epic_id=epic_id, role=role, state=st),
            verdict=qa_verdict,
        )
        if freeze_errors:
            rollback_staged_files(cwd, tx_rec.staged_files)
            tx_rec.state = FinishTxState.ROLLBACK_REQUIRED
            tx_rec.error = "; ".join(freeze_errors)
            write_finish_tx(cwd, tx_rec)
            return MbFinishResult(
                ok=False,
                diagnostic_codes=["qa_checklist_enforce_failed"],
                shape_errors=freeze_errors,
            )
        freeze = ensure_freeze(cwd, epic_id=epic_id, role=role, state=st)
        if freeze is None:
            try:
                freeze = freeze_from_qa_checks(
                    epic_id=epic_id,
                    checks=checks,
                    ac_plus=ac_plus or None,
                    ac_minus=ac_minus or None,
                    section_011=section_011 or None,
                    blockers=blockers if qa_verdict in {"fail", "blocked"} else None,
                    source_path=qa_rel,
                )
            except ValueError:
                freeze = load_freeze(st)
        if freeze is not None and qa_verdict in {"fail", "blocked"}:
            freeze = with_prior_blockers(freeze, blockers)
            freeze = bump_reqa_cycle(freeze)
            if freeze.reqa_cycles >= REQA_CYCLE_MAX:
                st["qa_reqa_halt"] = True
                st["halt_reason"] = (
                    f"NEED_HUMAN: QA↔BUGFIX cap reached ({freeze.reqa_cycles}/"
                    f"{REQA_CYCLE_MAX}) on checklist_sha256={freeze.checklist_sha256}"
                )
        if freeze is not None:
            persist_freeze(st, freeze)
    save_epic_state(cwd, st)

    # Mark committed in journal
    tx_rec.state = FinishTxState.COMMITTED
    write_finish_tx(cwd, tx_rec)

    fp_data = f"qa:{utc_now()}"
    fp = hashlib.sha256(fp_data.encode("utf-8")).hexdigest()
    write_last_finish_tool(
        cwd,
        "mb-finish qa",
        fp,
        finished_step="QA",
        armed_after_finish=next_mode,
    )

    return MbFinishResult(
        ok=True,
        active_context=rendered,
        finished_step="QA",
        next_step=next_mode,
        next_phase=next_mode,
        epic_done=next_mode == "DONE",
    )




def _bugfix_artifact_for_finish(
    cwd: Path, role_dir: str, *, epic_id: str
) -> Path | None:
    """Prefer the bugfix artifact from activeContext load_now for this epic.

    Multi-artifact folders must not silently finish an older leftover file while
    the session worked on a newer one; fall back to latest only when AC has none.
    """
    try:
        ctx = read_active_context(cwd)
    except OSError:
        ctx = ""
    marker = f"{role_dir}/bugfix/{epic_id}/"
    for rel in extract_load_now(ctx):
        norm = str(rel or "").replace(chr(92), "/").strip()
        if marker not in norm:
            continue
        name = Path(norm).name
        if not name.startswith("bugfix-") or not name.endswith(".md"):
            continue
        candidate = cwd / norm
        if candidate.is_file():
            return candidate
    return latest_bugfix_artifact_for_reference(cwd, role_dir, epic_id=epic_id)



def finish_bugfix(req: MbFinishRequest) -> MbFinishResult:
    """Orchestrate Bugfix phase finish atomically."""
    cwd = Path(req.cwd).resolve()
    act_path = resolve_mb_root(cwd) / "activeContext.md"

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

    bugfix_art = _bugfix_artifact_for_finish(
        cwd, role_dir, epic_id=epic_id
    )
    try:
        mb_root_name = resolve_mb_root(cwd).name
    except Exception:
        mb_root_name = "memory-bank"
    if not bugfix_art or not bugfix_art.is_file():
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["bugfix_artifact_missing"],
            shape_errors=[
                f"Bugfix artifact missing: {mb_root_name}/{role_dir}/bugfix/"
                f"{epic_id}/bugfix-*.md"
            ],
        )

    # New loop state records an explicit BUGFIX phase after QA failure.  The
    # legacy mb-finish entry point did not persist that phase, so retain its
    # artifact-only compatibility while enforcing verify-bugfix for the real
    # QA→BUGFIX transition.
    bugfix_phase_active = str(
        state.get("phase") or state.get("armed_step") or ""
    ).upper() == "BUGFIX"
    if bugfix_phase_active:
        verify = _verify_pass_ready_for_step(cwd, "BUGFIX")
        if not verify.get("ok"):
            return MbFinishResult(ok=False, diagnostic_codes=[verify["diagnostic"]], shape_errors=[verify["error"]])

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

    # Transaction Journal: stage activeContext, commit and record states
    tx_id = f"tx-bugfix-{epic_id}-{hashlib.sha256(utc_now().encode('utf-8')).hexdigest()[:8]}"
    act_rel = str(act_path.relative_to(cwd)) if act_path.is_relative_to(cwd) else "memory-bank/activeContext.md"

    staged_act = stage_file_in_tx(cwd, tx_id, act_rel, rendered)
    tx_rec = FinishTxRecord(
        tx_id=tx_id,
        epic_id=epic_id,
        step_id="BUGFIX",
        phase="BACK BUGFIX",
        state=FinishTxState.PREPARED,
        staged_files=[staged_act],
        recovery_token=tx_id,
    )
    write_finish_tx(cwd, tx_rec)

    try:
        commit_staged_files(cwd, [staged_act])
        tx_rec.state = FinishTxState.CONTEXT_WRITTEN
        write_finish_tx(cwd, tx_rec)
    except ActiveContextLocked as exc:
        rollback_staged_files(cwd, tx_rec.staged_files)
        tx_rec.state = FinishTxState.ROLLBACK_REQUIRED
        tx_rec.error = str(exc)
        write_finish_tx(cwd, tx_rec)
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["runner_owns_active_context"],
            shape_errors=[str(exc)],
        )
    except Exception as exc:
        rollback_staged_files(cwd, tx_rec.staged_files)
        tx_rec.state = FinishTxState.ROLLBACK_REQUIRED
        tx_rec.error = str(exc)
        write_finish_tx(cwd, tx_rec)
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["active_context_write_failed"],
            shape_errors=[str(exc)],
        )

    appended = _append_event(cwd, role_dir, epic_id, "bugfix_done", bugfix_art)
    if not appended and not event_persisted(
        cwd, role_dir, epic_id, "bugfix_done", bugfix_art
    ):
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["bugfix_event_not_persisted"],
            shape_errors=[
                "bugfix_done event was not written to the epic event log; "
                "BUGFIX→QA transition is not atomic without it"
            ],
        )
    reconcile_epic_events(cwd, role_dir, epic_id)
    decision = reduce_epic_lifecycle(cwd, role_dir, epic_id)
    life_phase = lifecycle_arm_phase(str(decision.get("phase") or "QA"), decision)
    if life_phase == "BUGFIX" or str(decision.get("reason_code") or "") == "qa_failed":
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["bugfix_event_stale_vs_qa_fail"],
            shape_errors=[
                "bugfix_done did not reopen QA after the latest qa_fail "
                f"(reason={decision.get('reason_code')!r}, artifact={bugfix_rel}); "
                "finish the current BUGFIX artifact, not a leftover one"
            ],
        )

    st = load_epic_state(cwd)
    st["armed_step"] = "QA"
    st["phase"] = "QA"
    st["active"] = True
    st["status"] = "armed"
    st["halt_reason"] = None
    qa_dir = resolve_mb_root(cwd) / role_dir / "qa" / epic_id
    changed_paths = extract_changed_paths(bugfix_art.read_text(encoding="utf-8", errors="replace"))
    suite_plan = suite_plan_after_changes(changed_paths, epic_id=epic_id)
    st["qa_after_bugfix"] = QaAfterBugfix(
        epic_id=epic_id,
        phase_run_id=state.get("phase_run_id") or state.get("session_id") or os.environ.get("EPIC_RUNNER_SESSION_ID"),
        existing_artifacts=[
            path.relative_to(cwd).as_posix()
            for path in sorted(qa_dir.glob("*.yaml"))
            if path.name == "qa.yaml" or path.name.startswith("qa-")
        ],
        suite_scope=suite_plan.suite_scope,
        suite_command=suite_plan.suite_command,
        changed_paths=list(suite_plan.changed_paths),
    ).model_dump()
    from loop.qa_checklist_freeze import (
        ensure_freeze,
        persist_freeze,
        read_qa_artifact_lists,
        with_prior_blockers,
        with_verify_scope,
    )

    freeze = ensure_freeze(cwd, epic_id=epic_id, role=role, state=st, prior_only=True)
    latest_qa = latest_qa_any_artifact_for_reference(cwd, role_dir, epic_id=epic_id)
    if freeze is not None and latest_qa is not None and latest_qa.is_file():
        _checks, blockers, _ap, _am, _sha, _sec = read_qa_artifact_lists(latest_qa)
        if blockers:
            freeze = with_prior_blockers(freeze, blockers)
        freeze = with_verify_scope(freeze, "prior_only")
        persist_freeze(st, freeze)
    elif freeze is not None:
        freeze = with_verify_scope(freeze, "prior_only")
        persist_freeze(st, freeze)
    save_epic_state(cwd, st)

    # Mark committed in journal
    tx_rec.state = FinishTxState.COMMITTED
    write_finish_tx(cwd, tx_rec)

    sync_cursor_from_index(cwd)

    fp_data = f"bugfix:{utc_now()}"
    fp = hashlib.sha256(fp_data.encode("utf-8")).hexdigest()
    write_last_finish_tool(
        cwd,
        "mb-finish bugfix",
        fp,
        finished_step="BUGFIX",
        armed_after_finish="QA",
    )

    return MbFinishResult(
        ok=True,
        active_context=rendered,
        finished_step="BUGFIX",
        next_step="QA",
        next_phase="QA",
        epic_done=False,
    )



def finish_decompose(
    req: MbFinishRequest,
) -> MbFinishResult:
    """Orchestrate DECOMPOSE phase finish atomically with Transition Engine delegation."""
    cwd = Path(req.cwd).resolve()
    act_path = resolve_mb_root(cwd) / "activeContext.md"

    state = load_epic_state(cwd)
    epic_id = state.get("armed_epic") or ""
    role = (state.get("armed_role") or "BACK").upper()
    decompose_rel = state.get("armed_decompose") or ""

    if not decompose_rel and epic_id:
        resolved = find_decompose_index_path(cwd, role, str(epic_id))
        if resolved and resolved.is_file():
            try:
                decompose_rel = resolved.relative_to(cwd).as_posix()
            except ValueError:
                decompose_rel = str(resolved).replace("\\", "/")

    if not decompose_rel:
        ctx = ""
        try:
            ctx = read_active_context(cwd)
        except OSError:
            ctx = ""

        if ctx.strip():
            candidates = extract_load_now(ctx)
            preferred = [
                c
                for c in candidates
                if "/plan/" in c.replace("\\", "/")
                and c.endswith(("index.yaml", "index.yml", "index.md"))
            ]
            if not preferred:
                preferred = [
                    c
                    for c in candidates
                    if "/plan/" in c.replace("\\", "/")
                    and Path(c).name in {"index.yaml", "index.yml", "index.md", "decompose-index.yaml", "decompose-index.yml", "decompose-index.md"}
                ]
            if preferred:
                decompose_rel = preferred[0]

        if decompose_rel:
            # Derive role from decompose path when armed_role is missing.
            decompose_p = decompose_rel.replace("\\", "/")
            if not state.get("armed_role"):
                if "/front/" in decompose_p:
                    role = "FRONT"
                elif "/integration/" in decompose_p:
                    role = "INTEG"
                else:
                    role = "BACK"

    if not epic_id and decompose_rel:
        epic_id = epic_id_from_decompose_path(decompose_rel)

    if decompose_rel and not state.get("armed_decompose"):
        # Keep runtime state consistent for downstream transition/projection steps.
        state["armed_decompose"] = decompose_rel
        if epic_id and not state.get("armed_epic"):
            state["armed_epic"] = epic_id
        if role and not state.get("armed_role"):
            state["armed_role"] = role
        save_epic_state(cwd, state)

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
    except ActiveContextLocked as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["runner_owns_active_context"],
            shape_errors=[str(exc)],
        )
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

    st_after = load_epic_state(cwd)
    next_step = st_after.get("armed_step")
    next_phase = st_after.get("phase")
    epic_done = not st_after.get("active") and st_after.get("status") == "complete"

    write_last_finish_tool(
        cwd,
        "mb-finish decompose",
        fp,
        finished_step="DECOMPOSE",
        armed_after_finish=str(next_step) if next_step else None,
    )

    return MbFinishResult(
        ok=True,
        active_context=rendered,
        finished_step="DECOMPOSE",
        next_step=next_step,
        next_phase=next_phase,
        epic_done=epic_done,
    )



def finish_plan(
    req: MbFinishRequest,
) -> MbFinishResult:
    """Orchestrate PLAN phase finish atomically with Transition Engine delegation."""
    cwd = Path(req.cwd).resolve()
    act_path = resolve_mb_root(cwd) / "activeContext.md"

    state = load_epic_state(cwd)
    epic_id = state.get("armed_epic") or ""
    role = (state.get("armed_role") or "BACK").upper()
    plan_rel = state.get("armed_plan") or ""

    if not plan_rel and epic_id:
        from epic_paths import find_plan_md_path

        cand = find_plan_md_path(cwd, role, str(epic_id))
        if cand is not None and cand.is_file():
            plan_rel = cand.relative_to(cwd).as_posix()

    if not plan_rel or not (cwd / plan_rel).exists():
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["plan_artifact_missing"],
            shape_errors=["Plan artifact missing"],
        )

    from _lib import epic_ids_compatible, live_runner_owner, runner_owns_active_context_reason
    from loop.roadmap_queue import plan_stem_from_name, roadmap_upsert_batch

    lock_reason = runner_owns_active_context_reason(
        cwd, epic_id=epic_id or None, phase="PLAN"
    )
    if lock_reason:
        owner = live_runner_owner(cwd)
        own_epic = str(getattr(owner, "epic_id", "") or "") if owner else ""
        plan_name = Path(plan_rel).name
        stem = plan_stem_from_name(plan_name)
        finishing = stem or epic_id or ""
        if own_epic and epic_ids_compatible(own_epic, finishing):
            return MbFinishResult(
                ok=False,
                diagnostic_codes=["runner_owns_active_context"],
                shape_errors=[lock_reason],
            )
        m = re.match(r"^(T-[A-Z]+-\d+)", finishing)
        queue_id = m.group(1) if m else finishing
        upsert = roadmap_upsert_batch(
            cwd,
            role=role.lower(),
            batch="chat-plan",
            items=[
                {
                    "id": queue_id,
                    "epic_id": epic_id or stem,
                    "plan": plan_name,
                    "deps": [],
                }
            ],
        )
        if not upsert.get("ok"):
            return MbFinishResult(
                ok=False,
                diagnostic_codes=["plan_enqueue_failed"],
                shape_errors=[str(upsert.get("reason") or upsert.get("error") or upsert)],
            )
        return MbFinishResult(
            ok=True,
            diagnostic_codes=["cursor_unchanged_runner_owns_active_context"],
            shape_errors=[lock_reason],
            finished_step="PLAN",
            next_step="DECOMPOSE",
            next_phase="DECOMPOSE",
            epic_done=False,
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
    except ActiveContextLocked as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["runner_owns_active_context"],
            shape_errors=[str(exc)],
        )
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

    st_after = load_epic_state(cwd)
    next_step = st_after.get("armed_step")
    next_phase = st_after.get("phase")
    epic_done = not st_after.get("active") and st_after.get("status") == "complete"

    write_last_finish_tool(
        cwd,
        "mb-finish plan",
        fp,
        finished_step="PLAN",
        armed_after_finish=str(next_step) if next_step else None,
    )

    return MbFinishResult(
        ok=True,
        active_context=rendered,
        finished_step="PLAN",
        next_step=next_step,
        next_phase=next_phase,
        epic_done=epic_done,
    )



def finish_analyze(
    req: MbFinishRequest,
) -> MbFinishResult:
    """Orchestrate ANALYZE phase finish atomically.

    Fail-closed: analyze yaml + gate pass + promote to IMPLEMENT required.
    Never write IMPLEMENT activeContext while analyze_gate is still open.
    """
    cwd = Path(req.cwd).resolve()

    state = load_epic_state(cwd)
    epic_id = state.get("armed_epic") or ""
    role = (state.get("armed_role") or "BACK").upper()
    role_dir = role.lower()
    decompose_rel = state.get("armed_decompose") or ""

    if not epic_id and decompose_rel:
        epic_id = epic_id_from_decompose_path(decompose_rel)

    if not epic_id:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["epic_id_missing"],
            shape_errors=["armed_epic missing — cannot finish ANALYZE"],
        )

    evidence = state.get("last_verify_evidence")
    matched, diagnostic = gate_evidence_matches(cwd, evidence) if evidence else (False, "gate_evidence_missing")
    if not matched:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["gate_evidence_missing"],
            shape_errors=[f"Gate evidence invalid or missing: {diagnostic}"],
        )

    from loop.analyze_gate import analyze_required_before_implement
    from loop.roadmap_queue import find_decompose_index, load_steps_for_index

    idx_path = None
    if decompose_rel:
        cand = cwd / decompose_rel
        if cand.is_dir():
            cand = cand / "index.yaml"
        elif cand.name in {"index.md", "index.yml"}:
            cand = cand.with_name("index.yaml")
        if cand.is_file():
            idx_path = cand
    if idx_path is None:
        idx_path = find_decompose_index(cwd, role_dir, epic_id)
    if idx_path is None or not idx_path.is_file():
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["decompose_index_missing"],
            shape_errors=["decompose index.yaml missing — cannot finish ANALYZE"],
        )

    loaded = load_steps_for_index(cwd, idx_path)
    if not loaded.get("ok"):
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["decompose_index_invalid"],
            shape_errors=[str(loaded.get("error") or "decompose index load failed")],
        )
    steps = loaded.get("steps") or []
    gate = analyze_required_before_implement(
        cwd,
        role_dir,
        epic_id,
        steps,
        index_path=idx_path,
    )
    if gate.get("required"):
        reason = str(gate.get("reason") or "analyze_required")
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["analyze_gate_pending", reason],
            shape_errors=[f"ANALYZE gate still open: {reason}"],
        )

    from loop.epic_transition import promote_if_ready

    promoted = promote_if_ready(cwd, epic_id, role_dir)
    if not (isinstance(promoted, dict) and promoted.get("ok")):
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["analyze_promote_failed"],
            shape_errors=[
                "ANALYZE finish refused: promote to IMPLEMENT failed "
                "(gate open, empty steps, or arm error)"
            ],
        )

    sync_cursor_from_index(cwd)

    fp_data = f"analyze:{utc_now()}"
    fp = hashlib.sha256(fp_data.encode("utf-8")).hexdigest()

    st_after = load_epic_state(cwd)
    next_step = st_after.get("armed_step")
    next_phase = st_after.get("phase")
    epic_done = not st_after.get("active") and st_after.get("status") == "complete"

    write_last_finish_tool(
        cwd,
        "mb-finish analyze",
        fp,
        finished_step="ANALYZE",
        armed_after_finish=str(next_step) if next_step else None,
    )

    return MbFinishResult(
        ok=True,
        active_context=read_active_context(cwd),
        finished_step="ANALYZE",
        next_step=next_step,
        next_phase=next_phase,
        epic_done=epic_done,
    )



def finish_audit(
    req: MbFinishRequest,
) -> MbFinishResult:
    """Orchestrate AUDIT phase finish atomically."""
    cwd = Path(req.cwd).resolve()
    act_path = resolve_mb_root(cwd) / "activeContext.md"

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

    from harness.hooks.epic.audit_validate import validate_audit_artifact

    role_norm = role_dir
    if role_norm == "integ":
        role_norm = "integration"
    shape_errs = validate_audit_artifact(
        cwd, role_dir=role_norm, epic_id=str(epic_id or ""), audit_path=audit_art
    )
    if shape_errs:
        codes = ["audit_artifact_invalid", "audit_plan_parity_failed"]
        for err in shape_errs:
            code = err.split(":", 1)[0]
            if code and code not in codes:
                codes.append(code)
        return MbFinishResult(
            ok=False,
            diagnostic_codes=codes,
            shape_errors=shape_errs,
        )

    try:
        audit_rel = audit_art.relative_to(cwd).as_posix()
    except ValueError:
        audit_rel = str(audit_art)

    load_now = [
        LoadNowItem(
            path=audit_rel,
            description="Audit artifact (epic-audit/v2 plan↔runtime)",
        ),
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
    except ActiveContextLocked as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["runner_owns_active_context"],
            shape_errors=[str(exc)],
        )
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

    if role_dir == "integ":
        role_dir = "integration"
    if epic_id:
        _append_event(cwd, role_dir, epic_id, "audit_done", audit_art)
        reconcile_epic_events(cwd, role_dir, epic_id)

    st_after = load_epic_state(cwd)
    st_after["armed_step"] = "QA"
    st_after["phase"] = "QA"
    st_after["active"] = True
    st_after["status"] = "running"
    st_after["halt_reason"] = None
    save_epic_state(cwd, st_after)

    sync_cursor_from_index(cwd)

    fp_data = f"audit:{utc_now()}"
    fp = hashlib.sha256(fp_data.encode("utf-8")).hexdigest()

    write_last_finish_tool(
        cwd,
        "mb-finish audit",
        fp,
        finished_step="AUDIT",
        armed_after_finish="QA",
    )

    return MbFinishResult(
        ok=True,
        active_context=rendered,
        finished_step="AUDIT",
        next_step="QA",
        next_phase="QA",
        epic_done=False,
    )



def finish_creative(
    req: MbFinishRequest,
) -> MbFinishResult:
    """Orchestrate CREATIVE phase finish atomically."""
    cwd = Path(req.cwd).resolve()
    act_path = resolve_mb_root(cwd) / "activeContext.md"

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
    except ActiveContextLocked as exc:
        return MbFinishResult(
            ok=False,
            diagnostic_codes=["runner_owns_active_context"],
            shape_errors=[str(exc)],
        )
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

    st_after = load_epic_state(cwd)
    next_step = st_after.get("armed_step")
    next_phase = st_after.get("phase")
    epic_done = not st_after.get("active") and st_after.get("status") == "complete"

    write_last_finish_tool(
        cwd,
        "mb-finish creative",
        fp,
        finished_step="CREATIVE",
        armed_after_finish=str(next_step) if next_step else None,
    )

    return MbFinishResult(
        ok=True,
        active_context=rendered,
        finished_step="CREATIVE",
        next_step=next_step,
        next_phase=next_phase,
        epic_done=epic_done,
    )
