#!/usr/bin/env python3
"""PostToolUse Agent — mark gates from completed subagent content when present."""
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
    parse_gate_verdict_message,
    record_verdict,
    read_stdin,
    save_state,
    should_skip_verdict_record,
    sync_gate_identity,
    utc_now,
    verdict_dedupe_key,
    verdict_evidence,
    workflow_state_active,
    _discover_registry,
)

_HUB_ROOT = Path(__file__).resolve().parents[2]
if str(_HUB_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUB_ROOT))

from loop.mb_finish.verify_hint import record_agent_key, VERIFY_FINISH_AGENTS  # noqa: E402


def _text_from_response(resp: object) -> str:
    if resp is None:
        return ""
    if isinstance(resp, str):
        return resp
    if isinstance(resp, dict):
        parts = []
        for block in resp.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text") or "")
        if parts:
            return "\n".join(parts)
        return json_dumps_safe(resp)
    return str(resp)


def json_dumps_safe(obj: object) -> str:
    import json

    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)


def main() -> None:
    data = read_stdin()
    if data.get("tool_name") not in {"Agent", "Task"}:
        return

    tool_input = data.get("tool_input") or {}
    agent_type = normalize_type(
        tool_input.get("subagent_type") or tool_input.get("agent_type")
    )
    resp = data.get("tool_response")
    session_id = data.get("session_id") or ""
    cwd = str(product_cwd(data.get("cwd") or ""))
    if isinstance(resp, dict) and resp.get("status") == "async_launched":
        return

    st = load_state(session_id, cwd)
    if not workflow_state_active(st, cwd or None):
        return

    # Sync Agent completion: release in_flight (async_launched keeps slot).
    if agent_type and clear_in_flight(
        st,
        agent=agent_type,
        tool_use_id=(
            str(data["tool_use_id"]) if data.get("tool_use_id") else None
        ),
    ):
        save_state(session_id, cwd, st)

    text = _text_from_response(resp)

    sidecar_agent = (
        record_agent_key(str(agent_type)) if agent_type in VERIFY_FINISH_AGENTS else None
    )
    if sidecar_agent:
        parse_gate_verdict_message(
            text,
            cwd,
            sidecar_agent,
            recorded_at=utc_now(),
            session_id=session_id or None,
        )

    if agent_type == "gate-repair":
        result = extract_repair_result(text)
        if result:
            st["repair_done"] = True
            st["repair_status"] = str(result.get("status") or "fail").lower()
            st["repair_result"] = result
            st["repair_in_flight"] = False
            save_state(session_id, cwd, st)
        return

    verdict = extract_verdict(
        text,
        cwd=cwd,
        agent_id=sidecar_agent or "verify",
    )
    if not agent_type or not verdict:
        return

    definition = _discover_registry(cwd or None).get(agent_type)
    if (
        definition is not None
        and definition.managed
        and definition.mode == "optional"
        and definition.verdict == "none"
    ):
        return
    tool_use_id = str(data.get("tool_use_id") or "").strip() or None
    dedupe_key = verdict_dedupe_key(
        session_id,
        agent_type,
        tool_use_id=tool_use_id,
        verdict=verdict,
    )
    if should_skip_verdict_record(st, dedupe_key):
        return
    identity = current_gate_identity(cwd, session_id)
    sync_gate_identity(st, identity)
    evidence = verdict_evidence(identity, verdict)
    record_key = sidecar_agent if sidecar_agent else agent_type
    matched, _diagnostic = record_verdict(st, record_key, verdict, evidence)
    mark_verdict_recorded(st, dedupe_key)
    if record_key == "verify" and matched:
        try:
            from epic_lib import mirror_verify_verdict

            mirror_verify_verdict(cwd, verdict, evidence=evidence)
        except (ImportError, OSError, TypeError, ValueError) as exc:
            print(
                f"posttool: mirror_verify_verdict failed: {exc}",
                file=sys.stderr,
            )
    save_state(session_id, cwd, st)


if __name__ == "__main__":
    main()
