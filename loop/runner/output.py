"""Pure formatting functions for loop runner terminal outputs and diagnostics."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence


def format_session_banner(iteration: int) -> str:
    """Format session header banner for outer loop iteration."""
    return f"\n======== SESSION {iteration} ========"


def format_pruned_logs(removed: int, kept: int) -> str:
    """Format log pruning notification."""
    return f"==> pruned {removed} old session log(s); kept {kept}"


def format_prepare_summary(
    prep_data: Mapping[str, Any],
    *,
    verbose: bool = False,
) -> str:
    """Format session prepare outcome summary."""
    if verbose:
        return json.dumps(dict(prep_data), indent=2, ensure_ascii=False)

    lines: list[str] = []
    status = "ok" if prep_data.get("ok") else (prep_data.get("reason") or "unknown")
    lines.append(f"==> prepare: {status}")

    phase = prep_data.get("phase") or prep_data.get("loop_phase") or ""
    step = prep_data.get("armed_step") or ""
    if phase or step:
        lines.append(f"==> working: {phase or '?'} step={step or '?'}")

    if prep_data.get("degraded"):
        lines.append("==> warn: context degraded — agent chooses next step from files")
        errs = prep_data.get("shape_errors") or []
        if errs:
            lines.append(f"==> shape: {'; '.join(errs)[:200]}")

    load_now = prep_data.get("load_now") or []
    if load_now:
        lines.append(f"==> load_now: {', '.join(str(p) for p in load_now[:4])}")

    return "\n".join(lines)


def format_session_model_info(
    model: str | None,
    phase: str | None,
    step: str | None,
    source: str | None,
) -> str:
    """Format session model and dispatch metadata line."""
    return (
        f"==> session model={model or '?'} phase={phase or '?'} "
        f"step={step or '?'} source={source or '?'}"
    )


def format_session_exit(
    runtime_name: str,
    exit_code: int,
    attempt: int,
    max_attempts: int,
) -> str:
    """Format session exit diagnostic line."""
    return f"==> {runtime_name} exit={exit_code} (try {attempt}/{max_attempts})"


def format_transient_retry(
    reason: str,
    backoff_sec: int,
    *,
    is_subagent: bool = False,
    subagent_attempt: int | None = None,
    max_subagent: int | None = None,
) -> list[str]:
    """Format lines for a transient retry occurrence."""
    lines: list[str] = []
    if reason.startswith("gate_integrity:"):
        lines.append(f"==> TRANSIENT gate integrity — retry after {backoff_sec}s")
    else:
        lines.append(f"==> TRANSIENT API abort — retry after {backoff_sec}s")
    lines.append(f"==> reason: {reason}")
    if is_subagent and subagent_attempt is not None and max_subagent is not None:
        lines.append(
            f"==> native collaboration retry: subagent retry {subagent_attempt}/{max_subagent}; "
            "new root Codex session will repeat spawn_agent → wait"
        )
    return lines


def format_transient_cap_reached(reason: str) -> list[str]:
    """Format lines when transient retry cap is reached."""
    return [
        "==> TRANSIENT API abort — retry cap reached; resume in next outer session",
        f"==> reason: {reason}",
    ]


def format_transient_reprepare_complete(
    armed_step: str | None,
    prev_step: str | None,
) -> str:
    """Format message when epic completed during transient retry."""
    return f"==> transient retry: epic complete — skip stale armed_step={prev_step or '?'} retry"


def format_transient_reprepare_resync(
    armed_step: str | None,
    prev_step: str | None,
) -> str:
    """Format message for armed_step resync during transient retry."""
    if prev_step and armed_step != prev_step:
        return f"==> transient retry: armed_step resynced {prev_step} → {armed_step or '?'}"
    return f"==> transient retry: re-prepared (step={armed_step or '?'})"


def format_abort_diagnostic(
    reason: str | None,
    abort_kind: str | None,
) -> str:
    """Format session abort summary line."""
    return f"==> abort: {reason or 'unknown'} kind= {abort_kind or 'unknown'}"


def format_check_after_summary(
    after_data: Mapping[str, Any],
    *,
    verbose: bool = False,
) -> str:
    """Format check-after inspection result."""
    if verbose:
        return json.dumps(dict(after_data), indent=2, ensure_ascii=False)

    lines: list[str] = []
    status = (
        after_data.get("reason")
        or after_data.get("stop")
        or ("continue" if after_data.get("ok") else "halt")
    )
    lines.append(f"==> after: {status}")

    fr = after_data.get("fingerprint_repair") or {}
    if fr.get("repaired"):
        lines.append(f"==> fingerprint-repair: {fr.get('mode')} step={fr.get('step_id') or ''}")

    if after_data.get("retry_fingerprint_stall"):
        stall_count = after_data.get("fingerprint_stall_count", "?")
        lines.append(f"==> fingerprint-stall: outer retry {stall_count} (new agent)")

    return "\n".join(lines)


def format_roadmap_advance(
    advance_data: Mapping[str, Any],
    *,
    verbose: bool = False,
) -> str:
    """Format roadmap-advance outcome."""
    if verbose:
        return json.dumps(dict(advance_data), indent=2, ensure_ascii=False)
    val = (
        advance_data.get("epic")
        or advance_data.get("stop")
        or advance_data.get("reason")
        or advance_data.get("complete")
        or "unknown"
    )
    return f"==> roadmap-advance: {val}"


def format_dag_fanout(
    fanout_data: Mapping[str, Any],
    *,
    verbose: bool = False,
) -> str:
    """Format DAG fanout outcome."""
    if verbose:
        return json.dumps(dict(fanout_data), indent=2, ensure_ascii=False)
    val = (
        fanout_data.get("node")
        or fanout_data.get("reason")
        or fanout_data.get("complete")
        or "unknown"
    )
    return f"==> fanout: {val}"


def format_cleared_incidents(
    cleared_count: int,
    diagnostic_codes: Sequence[str],
) -> str:
    """Format initial incident clearance message."""
    codes = ",".join(diagnostic_codes) or "?"
    return f"==> cleared {cleared_count} open incident(s) on loop start ({codes})"


def format_loop_complete(label: str = "stop marker") -> str:
    """Format loop completion termination banner."""
    return f"==> LOOP COMPLETE ({label})"


__all__ = [
    "format_abort_diagnostic",
    "format_check_after_summary",
    "format_cleared_incidents",
    "format_dag_fanout",
    "format_loop_complete",
    "format_prepare_summary",
    "format_pruned_logs",
    "format_roadmap_advance",
    "format_session_banner",
    "format_session_exit",
    "format_session_model_info",
    "format_transient_cap_reached",
    "format_transient_reprepare_complete",
    "format_transient_reprepare_resync",
    "format_transient_retry",
]
