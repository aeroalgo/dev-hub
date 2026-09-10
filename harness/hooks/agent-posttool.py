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


def _tool_response_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        content = value.get("content")
        if isinstance(content, list):
            parts = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and isinstance(item.get("text"), str)
            ]
            return "\n".join(parts)
        if isinstance(content, str):
            return content
    if isinstance(value, list):
        return "\n".join(_tool_response_text(item) for item in value)
    return ""


def main() -> None:
    data = read_stdin()
    tool_name = str(data.get("tool_name") or data.get("tool") or data.get("name") or "")
    session_id = data.get("session_id") or ""
    cwd = product_cwd(data.get("cwd"))

    # Post-tool write invalidation boundary + epic touch ledger
    if tool_name in WRITE_TOOL_ALIASES:
        try:
            evaluate_write_payload(data, provider="claude", cwd=cwd)
        except Exception:
            pass
        try:
            from context_ledger_adapters import normalize_write_payload
            from touch_ledger import record_touch

            payload = normalize_write_payload(data, provider="claude", default_cwd=cwd)
            record_touch(
                cwd,
                payload.raw_path,
                operation=str(payload.operation or "edit"),
            )
        except Exception:
            pass
        return

    text = _tool_response_text(data.get("tool_response"))
    tool_input = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    agent_type = str(
        data.get("agent_type") or tool_input.get("subagent_type") or ""
    ).strip() or None
    sidecar_agent = str(data.get("sidecar_agent") or "").strip() or None

    st = load_state(session_id, cwd)

    # Repair completion never authorizes a verifier PASS; parent must retry @verify.
    if st.get("repair_in_flight"):
        st["repair_in_flight"] = False
        st["gate_diagnostic"] = "repair_complete_verify_required"
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
            mirror_verify_verdict(
                cwd,
                verdict,
                evidence=evidence,
                session_id=session_id,
                agent_id=sidecar_agent or agent_type,
            )
            print(
                f"posttool: recorded verify verdict={verdict}",
                file=sys.stderr,
            )
        except (ImportError, OSError, TypeError, ValueError) as exc:
            print(
                f"posttool: mirror_verify_verdict failed: {exc}",
                file=sys.stderr,
            )

    # Record or update telemetry counters and DecisionReceipt state
    if session_id and cwd:
        try:
            from context_telemetry import collect_session_telemetry
            agg, diag = collect_session_telemetry(cwd, session_id)
            if diag and diag != "missing_ledger":
                print(f"agent-posttool: telemetry diagnostic warning: {diag}", file=sys.stderr)
            elif agg:
                st["context_telemetry_counters"] = {
                    "unique_reads": agg.unique_reads,
                    "duplicate_reads": agg.duplicate_reads,
                    "monolith_plan_attempts": agg.monolith_plan_attempts,
                    "search_exceptions": agg.search_exceptions,
                    "highest_repeat_path": agg.highest_repeat_path,
                }
        except Exception as exc:
            print(f"agent-posttool: collect_session_telemetry failed: {exc}", file=sys.stderr)

    save_state(session_id, cwd, st)


if __name__ == "__main__":
    main()
