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
    verdict = extract_verdict(msg)

    if agent_type in {"verify", "reviewer"} and not verdict:
        if agent_type == "verify":
            st["verify_incomplete"] = int(st.get("verify_incomplete") or 0) + 1
            save_state(session_id, cwd, st)
        print(
            f"{agent_type}: в финале обязателен VERDICT: PASS|FAIL"
            + ("|BLOCKED" if agent_type == "reviewer" else "")
            + ". Допиши отчёт в формате агента, затем остановись."
            + (
                " Parent: макс. 1 retry @verify без VERDICT, иначе "
                "NEED_HUMAN: verify_no_verdict."
                if agent_type == "verify"
                else ""
            ),
            file=sys.stderr,
        )
        sys.exit(2)

    if agent_type == "verify" and verdict:
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
                "verify VERDICT: FAIL — parent чинит blockers в ЭТОМ эпике "
                "(pending cp / gaps / harness / parity / seed), потом снова @verify. "
                "Не FINISH. FORBIDDEN: BLOCKED + отдельный bugfix для incomplete AC.",
                file=sys.stderr,
            )
            return
        return

    if agent_type == "reviewer" and verdict:
        identity = current_gate_identity(cwd, session_id)
        sync_gate_identity(st, identity)
        evidence = verdict_evidence(identity, verdict)
        record_verdict(st, "reviewer", verdict, evidence)
        clear_in_flight(st, agent=agent_type)
        save_state(session_id, cwd, st)
        return

    if agent_type:
        clear_in_flight(st, agent=str(agent_type))
        save_state(session_id, cwd, st)


if __name__ == "__main__":
    main()
