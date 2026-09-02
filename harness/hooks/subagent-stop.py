#!/usr/bin/env python3
"""SubagentStop — require VERDICT for verify/reviewer; mark gates done."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (
    product_cwd,  # noqa: E402
    clear_in_flight,
    current_gate_identity,
    extract_repair_result,
    extract_verdict,
    load_state,
    mark_verdict_recorded,
    normalize_type,
    read_stdin,
    record_verdict,
    save_state,
    should_skip_verdict_record,
    sync_gate_identity,
    verdict_dedupe_key,
    verdict_evidence,
    workflow_state_active,
)

_HUB_ROOT = Path(__file__).resolve().parents[2]
if str(_HUB_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUB_ROOT))

from loop.mb_finish.verify_hint import (  # noqa: E402
    BLOCKED_VERDICT_AGENTS,
    COERCE_VERIFY_AGENTS,
    REVIEWER_MIRROR_AGENTS,
    VERIFY_FINISH_AGENTS,
    mb_finish_hint_after_verdict,
    record_agent_key,
)


def _require_verdict_message(agent_type: str) -> str:
    blocked = "|BLOCKED" if agent_type in BLOCKED_VERDICT_AGENTS else ""
    retry = (
        " Parent: макс. 1 retry @verify без VERDICT, иначе "
        "NEED_HUMAN: verify_no_verdict."
        if agent_type in COERCE_VERIFY_AGENTS
        else ""
    )
    return (
        f"{agent_type}: в финале обязателен VERDICT: PASS|FAIL{blocked}. "
        "Допиши отчёт в формате агента, затем остановись."
        f"{retry}"
    )


def _fail_hint(agent_type: str) -> str:
    if agent_type in COERCE_VERIFY_AGENTS:
        return (
            "verify VERDICT: FAIL — parent: @gate-repair (BLOCKERS + ALLOW WRITE + VERIFY) "
            "или чини blockers сам, затем retry @verify. "
            "Не FINISH. FORBIDDEN: «ожидаю verify», BLOCKED + отдельный bugfix для incomplete AC."
        )
    return (
        f"{agent_type} VERDICT: FAIL — parent: устрани blockers и retry @{agent_type}. "
        "Не FINISH до VERDICT: PASS."
    )


def _handle_verify_finish_agent(
    *,
    agent_type: str,
    verdict: str,
    cwd: str,
    session_id: str,
    st: dict,
    data: dict,
) -> None:
    identity = current_gate_identity(cwd, session_id)
    sync_gate_identity(st, identity)

    if agent_type in COERCE_VERIFY_AGENTS and verdict == "PASS":
        try:
            from epic_lib import coerce_verify_verdict

            effective, demote_blockers = coerce_verify_verdict(cwd, verdict)
            if demote_blockers:
                print(
                    "verify VERDICT: PASS demoted → FAIL — step incomplete: "
                    + "; ".join(demote_blockers)
                    + ". Parent: добей checkpoints/gaps в этом шаге, потом снова @verify. "
                    "FORBIDDEN: BLOCKED + отдельный bugfix для incomplete AC этого эпика.",
                    file=sys.stderr,
                )
                verdict = effective or "FAIL"
        except Exception as exc:
            print(
                f"verify: coerce_verify_verdict failed: {exc}",
                file=sys.stderr,
            )

    if agent_type in REVIEWER_MIRROR_AGENTS and verdict == "BLOCKED":
        st["qa_blocked"] = True

    record_key = record_agent_key(agent_type)
    evidence = verdict_evidence(identity, verdict)
    matched, _diagnostic = record_verdict(st, record_key, verdict, evidence)
    dedupe_key = verdict_dedupe_key(
        session_id,
        record_key,
        tool_use_id=str(data.get("tool_use_id") or "").strip() or None,
        verdict=verdict,
    )
    if not should_skip_verdict_record(st, dedupe_key):
        mark_verdict_recorded(st, dedupe_key)

    if agent_type in COERCE_VERIFY_AGENTS:
        st["verify_incomplete"] = 0
        st["verify_no_verdict_retries"] = 0

    clear_in_flight(st, agent=agent_type)
    save_state(session_id, cwd, st)

    if matched:
        try:
            if agent_type in COERCE_VERIFY_AGENTS:
                from epic_lib import mirror_verify_verdict

                mirror_verify_verdict(cwd, verdict, evidence=evidence)
            elif agent_type in REVIEWER_MIRROR_AGENTS:
                from epic_lib import mirror_gate_verdict

                mirror_gate_verdict(
                    cwd, verdict, agent_id="reviewer", evidence=evidence
                )
        except Exception as exc:
            print(
                f"{agent_type}: mirror verdict failed: {exc}",
                file=sys.stderr,
            )

    if verdict == "FAIL":
        print(_fail_hint(agent_type), file=sys.stderr)
        return

    hint = mb_finish_hint_after_verdict(agent_type, verdict, cwd)
    if hint:
        print(hint, file=sys.stderr)


def main() -> None:
    data = read_stdin()
    if data.get("stop_hook_active"):
        return

    agent_type = normalize_type(data.get("agent_type")) or data.get("agent_type")
    msg = data.get("last_assistant_message") or ""
    transcript = data.get("transcript_path") or data.get("agent_transcript_path")
    if transcript:
        try:
            raw = Path(transcript).read_text(encoding="utf-8", errors="replace")
            if raw.strip():
                msg = f"{msg}\n{raw[-12000:]}"
        except OSError:
            pass
    session_id = data.get("session_id") or ""
    cwd = str(product_cwd(data.get("cwd") or ""))
    st = load_state(session_id, cwd)
    if not workflow_state_active(st, cwd or None):
        return

    transcript_text = data.get("transcript")
    if isinstance(transcript_text, str) and transcript_text.strip():
        msg = f"{msg}\n{transcript_text}"
    verdict = extract_verdict(msg)
    if not verdict:
        provided_verdict = data.get("verdict")
        if isinstance(provided_verdict, str):
            candidate = provided_verdict.strip().upper()
            if candidate in {"PASS", "FAIL", "BLOCKED"}:
                verdict = candidate
    if not verdict:
        for field in ("output", "last_message"):
            candidate = data.get(field)
            if isinstance(candidate, str):
                verdict = extract_verdict(candidate)
                if verdict:
                    break

    if agent_type in VERIFY_FINISH_AGENTS and not verdict:
        if agent_type in COERCE_VERIFY_AGENTS:
            st["verify_incomplete"] = int(st.get("verify_incomplete") or 0) + 1
            save_state(session_id, cwd, st)
        print(_require_verdict_message(str(agent_type)), file=sys.stderr)
        sys.exit(2)

    if agent_type in VERIFY_FINISH_AGENTS and verdict:
        _handle_verify_finish_agent(
            agent_type=str(agent_type),
            verdict=verdict,
            cwd=cwd,
            session_id=session_id,
            st=st,
            data=data,
        )
        return

    if agent_type == "gate-repair":
        result = extract_repair_result(msg)
        clear_in_flight(st, agent=str(agent_type))
        st["repair_in_flight"] = False
        if not result:
            save_state(session_id, cwd, st)
            print(
                "gate-repair: обязателен JSON fence loop-repair-result/v1 "
                "(status done|partial|fail).",
                file=sys.stderr,
            )
            sys.exit(2)
        status = str(result.get("status") or "fail").lower()
        st["repair_done"] = True
        st["repair_status"] = status
        st["repair_result"] = result
        save_state(session_id, cwd, st)
        if status in {"done", "partial"}:
            print(
                f"gate-repair: status={status} — parent retry @verify с packed prompt; "
                "FORBIDDEN FINISH до VERDICT: PASS.",
                file=sys.stderr,
            )
        else:
            print(
                "gate-repair: status=fail — parent расширь ALLOW WRITE / blockers, "
                "затем retry @gate-repair или @verify.",
                file=sys.stderr,
            )
        return

    if agent_type:
        clear_in_flight(st, agent=str(agent_type))
        save_state(session_id, cwd, st)


if __name__ == "__main__":
    main()
