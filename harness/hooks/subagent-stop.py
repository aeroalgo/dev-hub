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


def main() -> None:
    data = read_stdin()
    if data.get("stop_hook_active"):
        return

    agent_type = normalize_type(data.get("agent_type")) or data.get("agent_type")
    msg = data.get("last_assistant_message") or ""
    # Prefer full transcript tail when CC provides path (flash models truncate last msg).
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
    # Native DSH can provide the already-extracted verdict while the CC bridge
    # omits the assistant message. Prefer the transcript/message when present,
    # but accept only the same canonical values from the enriched payload.
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

    if agent_type in {"verify", "verify-implement", "reviewer", "verify-qa"} and not verdict:
        if agent_type in {"verify", "verify-implement"}:
            st["verify_incomplete"] = int(st.get("verify_incomplete") or 0) + 1
            save_state(session_id, cwd, st)
        print(
            f"{agent_type}: в финале обязателен VERDICT: PASS|FAIL"
            + ("|BLOCKED" if agent_type in {"reviewer", "verify-qa"} else "")
            + ". Допиши отчёт в формате агента, затем остановись."
            + (
                " Parent: макс. 1 retry @verify без VERDICT, иначе "
                "NEED_HUMAN: verify_no_verdict."
                if agent_type in {"verify", "verify-implement"}
                else ""
            ),
            file=sys.stderr,
        )
        sys.exit(2)

    if agent_type in {"verify", "verify-implement"} and verdict:
        identity = current_gate_identity(cwd, session_id)
        sync_gate_identity(st, identity)
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
        evidence = verdict_evidence(identity, verdict)
        matched, _diagnostic = record_verdict(st, "verify", verdict, evidence)
        dedupe_key = verdict_dedupe_key(
            session_id,
            "verify",
            tool_use_id=str(data.get("tool_use_id") or "").strip() or None,
            verdict=verdict,
        )
        if not should_skip_verdict_record(st, dedupe_key):
            mark_verdict_recorded(st, dedupe_key)
        st["verify_incomplete"] = 0
        st["verify_no_verdict_retries"] = 0
        clear_in_flight(st, agent=agent_type)
        save_state(session_id, cwd, st)
        if matched:
            try:
                from epic_lib import mirror_verify_verdict

                mirror_verify_verdict(cwd, verdict, evidence=evidence)
            except Exception as exc:
                print(
                    f"verify: mirror_verify_verdict failed: {exc}",
                    file=sys.stderr,
                )
        if verdict == "FAIL":
            print(
                "verify VERDICT: FAIL — parent: @gate-repair (BLOCKERS + ALLOW WRITE + VERIFY) "
                "или чини blockers сам, затем retry @verify. "
                "Не FINISH. FORBIDDEN: «ожидаю verify», BLOCKED + отдельный bugfix для incomplete AC.",
                file=sys.stderr,
            )
            return
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

    if agent_type in {"reviewer", "verify-qa"} and verdict:
        identity = current_gate_identity(cwd, session_id)
        sync_gate_identity(st, identity)
        if verdict == "BLOCKED":
            st["qa_blocked"] = True
        evidence = verdict_evidence(identity, verdict)
        record_verdict(st, "reviewer", verdict, evidence)
        clear_in_flight(st, agent=agent_type)
        save_state(session_id, cwd, st)
        try:
            from epic_lib import mirror_gate_verdict

            mirror_gate_verdict(cwd, "reviewer", verdict, evidence=evidence)
        except Exception as exc:
            print(
                f"reviewer: mirror_gate_verdict failed: {exc}",
                file=sys.stderr,
            )
        return

    if agent_type:
        clear_in_flight(st, agent=str(agent_type))
        save_state(session_id, cwd, st)


if __name__ == "__main__":
    main()
