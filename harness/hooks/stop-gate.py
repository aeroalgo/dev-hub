#!/usr/bin/env python3
"""Stop — block parent stop without mandatory verify/reviewer / epic FINISH."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
_HUB_ROOT = Path(__file__).resolve().parents[2]
if _HUB_ROOT.is_dir() and str(_HUB_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUB_ROOT))
from _lib import (
    product_cwd,  # noqa: E402
    FINISH_RE,
    _discover_registry,
    _managed_policy,
    agent_enabled,
    has_blocked_verify_no_verdict,  # compat: BLOCKED|NEED_HUMAN; deprecate BLOCKED в 004
    is_epic_loop_env,
    load_state,
    merged_project_env_map,
    neutralize_state,
    resolve_runtime_config,
    read_stdin,
    save_state,
    verify_no_verdict_exhausted,
    workflow_state_active,
)
from agent_policy import AgentContext, PolicyErrorCode  # noqa: E402
from epic import (  # noqa: E402
    _decompose_index_path,
    extract_handoff_block,
    extract_load_now,
    fingerprint_context,
    halt_epic,
    index_yaml_path,
    load_epic_state,
    load_index_yaml,
    project_handoff_from_reducer,
    read_active_context,
    validate_active_context_shape,
    validate_finish_integrity,
    validate_qa_finish_handoff,
)
from loop.schemas.active_context import parse_frontmatter
from epic_paths import resolve_decompose_ref_for_gate  # noqa: E402
from epic_yaml import validate_decompose_tree  # noqa: E402


def _block(reason: str) -> None:
    sys.stdout.write(
        json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False)
    )


def _gate_status(agent_id: str, cwd: str) -> tuple[bool, str | None, str | None]:
    """Return active, bypass reason, and fail-closed diagnostic for a required gate."""
    registry = _discover_registry(cwd)
    definition = registry.get(agent_id)
    if definition is None:
        return agent_enabled(agent_id, cwd), None, None
    if not definition.managed or definition.mode != "gate":
        return False, None, None
    context = AgentContext.LOOP if is_epic_loop_env() else AgentContext.CHAT
    policy = _managed_policy(definition, context, cwd)
    if policy.error == PolicyErrorCode.MODEL_INVALID:
        return False, None, f"agent_invalid:{agent_id}:model_invalid"
    if any(
        diagnostic.agent_id == agent_id and diagnostic.code == "model_invalid"
        for diagnostic in registry.errors
    ):
        return False, None, f"agent_invalid:{agent_id}:model_invalid"
    if not definition.runnable:
        return False, None, f"agent_invalid:{agent_id}:not_runnable"
    if not policy.enabled:
        return False, f"agent_disabled:{agent_id}", None
    return True, None, None


def _record_gate_bypass(state: dict, agent_id: str, reason: str) -> None:
    state["gate_bypass_reason"] = reason
    state["gate_bypassed_disabled"] = int(state.get("gate_bypassed_disabled") or 0) + 1


DSH_SELF_LIMIT_DEFAULT = 8
DSH_SELF_LIMIT_MIN = 1
DSH_SELF_LIMIT_MAX = 100


def _dsh_self_limit(cwd: str) -> tuple[int | None, str | None]:
    """Resolve the DSH stop limit and reject malformed overrides fail-closed."""
    project = merged_project_env_map(cwd)
    raw = os.environ.get("DSH_SELF_LIMIT_MAX")
    source = "process"
    if raw is None:
        raw = project.get("DSH_SELF_LIMIT_MAX")
        source = "project"
    if raw is None or not str(raw).strip():
        return DSH_SELF_LIMIT_DEFAULT, None
    try:
        value = int(str(raw).strip(), 10)
    except (TypeError, ValueError):
        return None, f"invalid DSH self-limit configuration from {source}: {raw!r}"
    if value < DSH_SELF_LIMIT_MIN or value > DSH_SELF_LIMIT_MAX:
        return None, f"invalid DSH self-limit configuration from {source}: {raw!r}"
    return value, None


def _is_handoff_strict(cwd: str) -> bool:
    project = merged_project_env_map(cwd)
    raw = os.environ.get("PROJECT_LOOP_HANDOFF_STRICT")
    if raw is None:
        raw = project.get("PROJECT_LOOP_HANDOFF_STRICT")
    return str(raw or "").strip() in {"1", "true", "yes"}


def _is_dsh_runtime(cwd: str) -> bool:
    """Detect the DSH hook bridge without changing Claude-path behavior."""
    if str(os.environ.get("DSH_HOOKS_BRIDGE", "")).lower() in {"1", "true", "yes"}:
        return True
    try:
        return resolve_runtime_config(cwd).epic_runtime == "dsh"
    except (OSError, TypeError, ValueError):
        return False


def _get_consecutive_blocks(state: dict) -> int:
    try:
        return max(0, int(state.get("dsh_consecutive_blocks") or 0))
    except (TypeError, ValueError):
        return 0


def _increment_consecutive_blocks(state: dict) -> int:
    blocks = _get_consecutive_blocks(state) + 1
    state["dsh_consecutive_blocks"] = blocks
    return blocks


def _reset_consecutive_blocks(state: dict) -> None:
    state["dsh_consecutive_blocks"] = 0


def _epic_progressed(cwd: str, epic: dict) -> tuple[bool, str]:
    """True when Handoff+load_now fingerprint changed vs pending_fingerprint_before."""
    ctx = read_active_context(cwd)
    handoff = extract_handoff_block(ctx)
    before = epic.get("pending_fingerprint_before")
    now_fp = fingerprint_context(ctx)
    if not handoff.strip():
        return False, now_fp
    if before is None:
        return True, now_fp
    return now_fp != before, now_fp


def _check_stale_load_now(cwd: str, epic: dict) -> str | None:
    """Return a block reason when load_now points at a completed step."""
    decompose = epic.get("armed_decompose")
    if not decompose:
        return None
    idx = _decompose_index_path(cwd, decompose)
    if idx is None:
        return None
    ypath = index_yaml_path(idx)
    if not ypath.is_file():
        return None
    try:
        doc = load_index_yaml(ypath)
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    steps_by_id = {
        step.get("id"): step.get("status", "")
        for step in doc.get("steps", [])
        if isinstance(step, dict) and step.get("id")
    }
    stale: set[str] = set()
    for path in extract_load_now(read_active_context(cwd)):
        match = re.search(r"(?:^|/)(s|e)(\d{2})-", path)
        if match:
            step_id = f"{match.group(1)}{match.group(2)}"
            if steps_by_id.get(step_id) in {"completed", "done"}:
                stale.add(step_id)
    if not stale:
        return None
    completed = ", ".join(sorted(stale))
    return f"epic-gate: stale load_now — completed шаг(и): {completed}"


def main() -> None:
    data = read_stdin()
    session_id = data.get("session_id") or ""
    cwd = str(product_cwd(data.get("cwd") or ""))
    msg = data.get("last_assistant_message") or ""
    st = load_state(session_id, cwd)
    if not workflow_state_active(st, cwd or None):
        neutralize_state(st)
        save_state(session_id, cwd, st)
        return

    epic = load_epic_state(cwd) if cwd else {}
    if cwd:
        from _lib import current_gate_identity, sync_gate_identity, match_gate_evidence

        identity = current_gate_identity(cwd, session_id)
        sync_gate_identity(st, identity)
        for agent in ("verify", "reviewer"):
            evidence = st.get(f"{agent}_evidence")
            if evidence:
                matched, diagnostic = match_gate_evidence(evidence, identity)
                evidence["valid"] = matched
                evidence["diagnostic"] = diagnostic
                if not matched:
                    st[f"{agent}_done"] = False
                    st[f"{agent}_verdict"] = None
                    st["gate_diagnostic"] = diagnostic
        save_state(session_id, cwd, st)
    epic_loop = is_epic_loop_env()
    epic_on = bool(
        epic_loop and epic.get("active") and epic.get("status") == "running"
    )
    stop_hook_active = bool(data.get("stop_hook_active"))

    # Validate registry finish gates if phase is present
    current_phase = epic.get("phase") or st.get("mode") or ""
    if current_phase:
        from loop.epic_transition import get_phase_config
        try:
            cfg = get_phase_config(str(current_phase))
            finish_gates = cfg.get("finish_gates")
            if isinstance(finish_gates, list):
                for g in finish_gates:
                    g_type = g.get("type") if isinstance(g, dict) else None
                    if g_type == "cli":
                        cmd = g.get("cmd") or g.get("command") or g.get("name")
                        if cmd:
                            res = subprocess.run(
                                [cmd, "--cwd", cwd] if cwd else [cmd],
                                capture_output=True,
                                text=True,
                            )
                            if res.returncode != 0:
                                _block(f"finish-gate: cli gate {cmd} failed with exit code {res.returncode}")
                                return
                    elif g_type == "artifact":
                        pattern = g.get("pattern") or g.get("path")
                        if pattern:
                            found = list(Path(cwd).glob(pattern)) if cwd else []
                            if not found:
                                _block(f"finish-gate: artifact gate {pattern} not found")
                                return
                    else:
                        raise ValueError(f"unknown gate type {g_type!r}: fail-closed")
        except ValueError as err:
            if "unknown gate type" in str(err) or "unknown phase" in str(err):
                _block(f"spawn-gate: {err}")
                return

    # Default anti-loop: allow stop after a prior hook block — EXCEPT epic (need progress).
    if stop_hook_active and not epic_on:
        return

    finishing = bool(FINISH_RE.search(msg))
    if not finishing and st.get("mode") == "qa":
        finishing = bool(
            re.search(
                r"(?i)(suite\s+(green|pass)|qa\s+pass|FINISH\s+QA|блокеры зафиксир)",
                msg,
            )
        )
    if not finishing and st.get("mode") == "audit":
        finishing = bool(
            re.search(r"(?i)(FINISH\s+AUDIT|gap-матрица\s+полна|audit.*записан)", msg)
        )

    verify_active, verify_bypass, verify_invalid = _gate_status("verify", cwd)
    armed_step_u = str(epic.get("armed_step") or "").upper() if epic_on else ""
    if armed_step_u == "DECOMPOSE":
        st["need_verify"] = False
        save_state(session_id, cwd, st)

        # Check DECOMPOSE semantic verification if verify-decompose is enabled
        v_dec_active, _, v_dec_invalid = _gate_status("verify-decompose", cwd)
        if v_dec_invalid and finishing:
            _block(f"spawn-gate: required gate verify-decompose invalid — fail-closed. diagnostic={v_dec_invalid}")
            return
        if v_dec_active and finishing:
            # Check if verify-decompose verdict exists and is PASS
            v_done = st.get("verify_done") or st.get("verify_decompose_done")
            v_verdict = st.get("verify_verdict") or st.get("verify_decompose_verdict")
            if not v_done or v_verdict != "PASS":
                if not stop_hook_active:
                    _block(
                        "spawn-gate: DECOMPOSE phase requires verify-decompose VERDICT: PASS before FINISH."
                    )
                    return
    if verify_bypass and st.get("need_verify"):
        _record_gate_bypass(st, "verify", verify_bypass)
        st["need_verify"] = False
        save_state(session_id, cwd, st)
    if verify_invalid and st.get("need_verify") and finishing:
        _block(
            "spawn-gate: required gate verify invalid — fail-closed. "
            f"diagnostic={verify_invalid}"
        )
        return
    if (
        verify_active
        and st.get("need_verify")
        and finishing
        and not st.get("verify_done")
    ):
        if verify_no_verdict_exhausted(st) and has_blocked_verify_no_verdict(
            msg, cwd
        ):
            st["verify_blocked_no_verdict"] = True
            st["need_verify"] = False
            save_state(session_id, cwd, st)
        elif stop_hook_active:
            return
        else:
            _block(
                "spawn-gate: перед FINISH/Handoff обязателен @verify "
                "(Agent subagent_type=verify) с packed AC+ · AC− · §0.11 · VERIFY · ALLOW READ. "
                "Порядок: seed-implement → flush cp → suite → evidence (in_progress) → "
                "Handoff → @verify → "
                "FAIL/DENY: fix → снова @verify → PASS → finalize-step → FINISH/stop. "
                "Не вызывать @verify повторно после VERDICT: PASS. "
                "Без VERDICT после 1 retry → Handoff `NEED_HUMAN: verify_no_verdict` и stop. "
                f"state={json.dumps({k: st.get(k) for k in ('mode','need_verify','verify_done','verify_verdict','verify_incomplete','verify_no_verdict_retries')})}"
            )
            return

    reviewer_active, reviewer_bypass, reviewer_invalid = _gate_status("reviewer", cwd)
    if reviewer_bypass and st.get("need_reviewer"):
        _record_gate_bypass(st, "reviewer", reviewer_bypass)
        st["need_reviewer"] = False
        save_state(session_id, cwd, st)
    if reviewer_invalid and st.get("need_reviewer") and finishing:
        _block(
            "spawn-gate: required gate reviewer invalid — fail-closed. "
            f"diagnostic={reviewer_invalid}"
        )
        return
    if (
        reviewer_active
        and st.get("need_reviewer")
        and finishing
        and not st.get("reviewer_done")
    ):
        if stop_hook_active:
            return
        _block(
            "spawn-gate: QA FINISH без @reviewer запрещён. "
            "Сначала Agent subagent_type=reviewer с Suite results · AC+ · AC− · "
            "§0.11 · ALLOW READ. "
            f"state={json.dumps({k: st.get(k) for k in ('mode','need_reviewer','reviewer_done','reviewer_verdict')})}"
        )
        return

    if st.get("mode") == "qa" and finishing and st.get("reviewer_done"):
        # QA BLOCKED verdict allowed (stop-gate allows FINISH + expects BUGFIX handoff)
        rev_verdict = st.get("reviewer_verdict")
        if rev_verdict == "BLOCKED" or st.get("qa_blocked"):
            pass  # BLOCKED allowed, validate_qa_finish_handoff will ensure BUGFIX handoff
        ac = Path(cwd) / "memory-bank" / "activeContext.md" if cwd else None
        if ac and ac.is_file():
            text = ac.read_text(encoding="utf-8", errors="replace")
            qa_handoff_ok, qa_handoff_err = validate_qa_finish_handoff(cwd, text)
            if not qa_handoff_ok:
                if stop_hook_active:
                    return
                _block(
                    f"spawn-gate: {qa_handoff_err}. "
                    "pass → ## Handoff BACK REFLECT; blocked/fail → ## Handoff BACK BUGFIX."
                )
                return
        else:
            if stop_hook_active:
                return
            _block(
                "spawn-gate: BACK QA FINISH без memory-bank/activeContext.md. "
                "Перепиши Handoff (pass→REFLECT; blocked→BUGFIX) + load_now, затем остановись."
            )
            return

    if st.get("mode") == "audit" and finishing:
        ac = Path(cwd) / "memory-bank" / "activeContext.md" if cwd else None
        handoff_ok = False
        if ac and ac.is_file():
            text = ac.read_text(encoding="utf-8", errors="replace")
            handoff_ok = bool(
                re.search(r"(?im)^##\s*Handoff\s+.*\bAUDIT\b", text)
            )
        if not handoff_ok:
            if stop_hook_active:
                return
            _block(
                "spawn-gate: BACK AUDIT FINISH без ## Handoff BACK AUDIT "
                "в memory-bank/activeContext.md. "
                "Перепиши Handoff: gap-матрица + next (IMPLEMENT новых sNN | BACK QA). "
                "затем остановись."
            )
            return

    if st.get("verify_done") and st.get("verify_verdict") == "FAIL" and finishing:
        if stop_hook_active:
            return
        _block(
            "spawn-gate: verify=FAIL — нельзя FINISH. "
            "Запусти @gate-repair (BLOCKERS + ALLOW WRITE + VERIFY из verify-отчёта), "
            "затем retry @verify до VERDICT: PASS."
        )
        return

    if os.environ.get("EPIC_LOOP") == "1" and finishing and cwd:
        ac = Path(cwd) / "memory-bank" / "activeContext.md"
        if ac.is_file():
            handoff = extract_handoff_block(
                ac.read_text(encoding="utf-8", errors="replace")
            ) or ""
            if re.search(
                r"(?i)(?:BACK|FRONT|INTEG)\s+ARCHIVE\s+NOW|`\s*BACK\s+ARCHIVE\s+NOW`",
                handoff,
            ):
                if stop_hook_active:
                    return
                _block(
                    "spawn-gate: ARCHIVE NOW запрещён в loop-сессии (EPIC_LOOP=1). "
                    "ARCHIVE — только вручную вне loop после EPIC_DONE / stop runner. "
                    "На FINISH: EPIC_DONE или Handoff → REFLECT/QA; не переносить артефакты в archive/."
                )
                return

    current_phase_u = str(epic.get("phase") or st.get("mode") or "").upper()
    if finishing and current_phase_u == "IMPLEMENT":
        lft = epic.get("last_finish_tool")
        if not lft or not isinstance(lft, dict) or not lft.get("fingerprint"):
            if not stop_hook_active:
                _block(
                    "spawn-gate: FINISH IMPLEMENT requires finish tool execution (last_finish_tool missing). "
                    "diagnostic=finish_tool_required"
                )
                return

    if finishing and epic.get("last_verify_verdict") == "PASS":
        if armed_step_u != "DECOMPOSE":
            integrity = validate_finish_integrity(
                cwd,
                decompose=epic.get("armed_decompose"),
                step_id=str(epic.get("armed_step") or st.get("step") or ""),
                require_verify_pass=True,
            )
            if not integrity["ok"]:
                diagnostics = ", ".join(integrity["diagnostic_codes"])
                errors = "; ".join(integrity["errors"])
                if "mark_index_missing" in integrity["diagnostic_codes"]:
                    retries = int(st.get("mark_index_missing_blocks") or 0) + 1
                    st["mark_index_missing_blocks"] = retries
                    save_state(session_id, cwd, st)
                    if retries >= 2:
                        _block(
                            "NEED_HUMAN: mark_index_missing — index не синхронизирован после "
                            "verify PASS. Выполни finalize-step и дождись JSON `ok: true`. "
                            + errors
                        )
                        return
                _block(
                    "epic-gate: finish_integrity FAIL — "
                    f"diagnostic_codes={diagnostics}; {errors}. "
                    "Вызови finalize-step, дождись JSON `ok: true`, затем повтори stop."
                )
                return

    if _is_dsh_runtime(cwd):
        limit, config_error = _dsh_self_limit(cwd)
        if config_error:
            st["dsh_consecutive_blocks"] = _get_consecutive_blocks(st)
            save_state(session_id, cwd, st)
            _block(config_error)
            return
        assert limit is not None
        progressed, _fp = _epic_progressed(cwd, epic)
        if progressed:
            _reset_consecutive_blocks(st)
            st["epic_stop_blocks"] = 0
            save_state(session_id, cwd, st)
            return
        blocks = _increment_consecutive_blocks(st)
        save_state(session_id, cwd, st)
        if blocks >= limit:
            sys.stdout.write(
                json.dumps(
                    {
                        "decision": "allow",
                        "reason": f"DSH self-limit reached ({blocks}/{limit}); allowing stop",
                    },
                    ensure_ascii=False,
                )
            )
            return
        _block(f"DSH self-limit: progress required before stop ({blocks}/{limit})")
        return

    # EPIC MODE: allow stop only when Handoff/load_now fingerprint advanced.
    progressed, _fp = _epic_progressed(cwd, epic)
    if progressed:
        if armed_step_u == "DECOMPOSE":
            decompose_ref = resolve_decompose_ref_for_gate(cwd, epic)
            shard_errs = validate_decompose_tree(cwd, decompose_ref)
            if shard_errs:
                if stop_hook_active:
                    return
                _block(
                    "epic-gate: DECOMPOSE FINISH blocked — index.md coverage + "
                    "sNN-<slug>.yaml + schema epic-decompose/v1 (+ role, as_built/delta lists) "
                    "по .cursor/templates/decompose/. "
                    "FORBIDDEN: epic-decompose-shard/*, invented schemas, as_built dict, bare sNN.yaml. "
                    "Исправь → validate-decompose-tree. "
                    + "; ".join(shard_errs[:12])
                )
                return
        strict = _is_handoff_strict(cwd)
        shape_errs = validate_active_context_shape(read_active_context(cwd))
        blocking_shape = [
            code
            for code in shape_errs
            if code.startswith("handoff_frontmatter")
            or (code == "missing_handoff_frontmatter" and strict)
            or code in {"missing_load_now", "missing_handoff", "multiple_handoff"}
        ]
        if blocking_shape:
            if stop_hook_active:
                return
            _block(
                "epic-gate: activeContext shape FAIL — "
                + "; ".join(blocking_shape)
                + ". Preserve loop-handoff/v1 frontmatter from session start; "
                "write full memory-bank/activeContext.md (load_now + Handoff)."
            )
            return
        residual_shape = [
            code
            for code in shape_errs
            if not code.startswith("handoff_frontmatter")
            and code != "missing_handoff_frontmatter"
        ]
        if residual_shape:
            if stop_hook_active:
                return
            _block(
                "epic-gate: activeContext shape FAIL — "
                + "; ".join(residual_shape)
                + ". Write весь memory-bank/activeContext.md целиком: "
                "## load_now → ровно 1× ## Handoff → ≤1× ## done. "
                "FORBIDDEN: sandwich/append старых Handoff/done в хвосте."
            )
            return
        stale = _check_stale_load_now(cwd, epic)
        if stale:
            if stop_hook_active:
                return
            _block(stale)
            return

        if not strict:
            project_handoff_from_reducer(cwd)
            return
        st["epic_stop_blocks"] = 0
        save_state(session_id, cwd, st)
        return

    blocks = int(st.get("epic_stop_blocks") or 0) + 1
    st["epic_stop_blocks"] = blocks
    save_state(session_id, cwd, st)
    if blocks >= 3:
        halt_epic(cwd, "stuck without Handoff/load_now progress (stop×3)")
        return

    ctx = read_active_context(cwd)
    missing: list[str] = []
    if "## load_now" not in ctx:
        missing.append("load_now")
    if not extract_handoff_block(ctx).strip():
        missing.append("Handoff section")
    if epic.get("pending_fingerprint_before") is not None:
        missing.append("fingerprint не изменился (нет прогресса)")
    details = ", ".join(missing) or "Handoff/load_now progress"
    _block(
        "epic-gate: нельзя end_turn без прогресса. "
        f"Не найдено: {details}. "
        "Write весь activeContext.md: ## load_now → ровно 1× ## Handoff → ≤1× ## done. "
        f"Попытка {blocks}/3; дальше epic halt. "
        "FORBIDDEN: остановиться после «начинаю» без FINISH; sandwich Handoff. "
        "Или: python3 .claude/hooks/epic_resolve.py halt --reason '…'"
    )


if __name__ == "__main__":
    main()
