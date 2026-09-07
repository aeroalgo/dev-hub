#!/usr/bin/env python3
"""PostToolUse Agent & Write — parse verdict, update gate state, refresh context ledger invalidations."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (  # noqa: E402
    current_gate_identity,
    extract_verdict,
    is_schema_error,
    is_semantic_error,
    load_state,
    mark_verdict_recorded,
    product_cwd,
    read_stdin,
    record_verdict,
    save_state,
    should_skip_verdict_record,
    sync_gate_identity,
    verdict_dedupe_key,
    verdict_evidence,
    _discover_registry,
)
from context_ledger_adapters import (
    WRITE_TOOL_ALIASES,
    evaluate_write_payload,
)


def main() -> None:
    data = read_stdin()
    tool_name = str(data.get("tool_name") or data.get("tool") or data.get("name") or "")
    session_id = data.get("session_id") or ""
    cwd = product_cwd(data.get("cwd"))

    # Post-tool write invalidation boundary
    if tool_name in WRITE_TOOL_ALIASES:
        try:
            evaluate_write_payload(data, provider="claude", cwd=cwd)
        except Exception:
            pass
        return

    text = str(data.get("tool_response") or "")
    agent_type = str(data.get("agent_type") or "").strip() or None
    sidecar_agent = str(data.get("sidecar_agent") or "").strip() or None

    st = load_state(session_id, cwd)

    # repair_in_flight: mirror_verify_verdict failed -> clear on subagent completion
    if st.get("repair_in_flight"):
        try:
            from epic_lib import mirror_verify_verdict
            mirror_verify_verdict(cwd, "PASS", evidence="repair cleared")
            st["repair_in_flight"] = False
            save_state(session_id, cwd, st)
        except (ImportError, OSError, TypeError, ValueError) as exc:
            print(
                f"posttool: mirror_verify_verdict failed: {exc}",
                file=sys.stderr,
            )
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
            print(
                f"posttool: recorded verify verdict={verdict}",
                file=sys.stderr,
            )
        except (ImportError, OSError, TypeError, ValueError) as exc:
            print(
                f"posttool: mirror_verify_verdict failed: {exc}",
                file=sys.stderr,
            )

    save_state(session_id, cwd, st)


if __name__ == "__main__":
    main()
