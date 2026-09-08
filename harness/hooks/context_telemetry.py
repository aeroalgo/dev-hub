"""Context telemetry collector and finish projection for T-HUB-078.

Aggregates attributable metadata counters across root and subagents for Claude and Codex.
Enforces content-free projection, secret redaction, actor/provider breakdown,
and explicit non-green diagnostics on missing or corrupt ledger state.

Part of T-HUB-078 (FR-005, FR-007, FR-008, FR-010).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import sys
from typing import Any

_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))
_HUB_ROOT = Path(__file__).resolve().parents[2]
if str(_HUB_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUB_ROOT))

from loop.schemas.telemetry import (
    FORBIDDEN_CONTENT_KEYS,
    SCHEMA_CONTEXT_TELEMETRY,
    SCHEMA_FINISH_RECEIPT,
    ActorTelemetry,
    FinishReceipt,
    ProviderTelemetry,
    TelemetryAggregate,
)

logger = logging.getLogger(__name__)


def redact_path(raw_path: str | Path | None, project_root: str | Path) -> str | None:
    """Redact canonical path relative to project root without exposing home directories."""
    if not raw_path:
        return None
    p_str = str(raw_path).strip()
    if not p_str:
        return None
    try:
        root_p = Path(project_root).resolve()
        p_obj = Path(p_str).resolve()
        if p_obj.is_relative_to(root_p):
            return p_obj.relative_to(root_p).as_posix()
        # Outside project root: redact parent dirs, preserve basename/relative component
        return p_obj.name
    except Exception:
        return Path(p_str).name


def verify_telemetry_secret_free(data: Any) -> tuple[bool, list[str]]:
    """Validate that telemetry payload contains zero raw file content, tokens, or secret keys."""
    violations: list[str] = []

    def _check(val: Any, path: str) -> None:
        if isinstance(val, dict):
            for k, v in val.items():
                k_lower = str(k).lower()
                if k_lower in FORBIDDEN_CONTENT_KEYS:
                    violations.append(f"forbidden_key:{path}.{k}")
                _check(v, f"{path}.{k}")
        elif isinstance(val, (list, tuple, set)):
            for idx, item in enumerate(val):
                _check(item, f"{path}[{idx}]")
        elif isinstance(val, str):
            # Check for suspicious source code or long text blocks
            if len(val) > 2048 and "\n" in val:
                violations.append(f"potential_source_leak:{path}:len={len(val)}")

    _check(data, "root")
    return (len(violations) == 0, violations)


def collect_session_telemetry(
    project_root: str | Path,
    session_id: str,
    runtime_dir: Path | None = None,
) -> tuple[TelemetryAggregate | None, str | None]:
    """Aggregate session-wide telemetry from all actor ledgers.

    Returns (TelemetryAggregate, None) on success, or (None, diagnostic_code) on error.
    Never synthesizes zero duplicates when ledger is corrupt or missing.
    """
    root_p = Path(project_root).resolve()
    if runtime_dir is None:
        from epic_paths import epic_dir as runtime_epic_dir
        base_dir = runtime_epic_dir(root_p).parent
    else:
        base_dir = runtime_dir
    safe_proj = re.sub(r"[^a-zA-Z0-9._-]+", "_", root_p.name or "proj")[:64]
    safe_sess = re.sub(r"[^a-zA-Z0-9._-]+", "_", session_id or "sess")[:64]
    sess_dir = base_dir / "context-ledger" / safe_proj / safe_sess

    if not sess_dir.is_dir():
        return None, "missing_ledger"

    ledger_files = sorted(
        [
            f
            for f in sess_dir.glob("*.json")
            if not f.name.endswith(".lock") and ".tmp." not in f.name
        ]
    )

    if not ledger_files:
        return None, "missing_ledger"

    actors: list[ActorTelemetry] = []
    provider_map: dict[str, dict[str, int]] = {}
    all_file_read_counts: dict[str, int] = {}

    tot_unique = 0
    tot_duplicate = 0
    tot_bytes = 0
    tot_ranges = 0
    tot_monolith = 0
    tot_search_exc = 0
    tot_denials = 0
    tot_invalidations = 0
    tot_requests = 0

    for l_file in ledger_files:
        try:
            raw_text = l_file.read_text(encoding="utf-8")
            if not raw_text.strip():
                return None, "corrupt_ledger"
            data = json.loads(raw_text)
        except Exception:
            return None, "corrupt_ledger"

        if not isinstance(data, dict):
            return None, "corrupt_ledger"
        if data.get("schema") != "context-ledger/v1":
            return None, "corrupt_ledger"

        is_clean, violations = verify_telemetry_secret_free(data)
        if not is_clean:
            return None, "content_leakage_detected"

        actor_k = data.get("actor_key") or {}
        counters = data.get("counters") or {}
        files = data.get("files") or {}

        # Highest repeat path for this actor
        actor_highest_path: str | None = None
        actor_max_reads = 0
        for fpath, finfo in files.items():
            cnt = int(finfo.get("read_count", 0)) if isinstance(finfo, dict) else 0
            if cnt > actor_max_reads:
                actor_max_reads = cnt
                actor_highest_path = fpath
            all_file_read_counts[fpath] = all_file_read_counts.get(fpath, 0) + cnt

        u_reads = int(counters.get("unique_reads", 0))
        d_reads = int(counters.get("duplicate_reads", 0))
        b_reads = int(counters.get("bytes_read", 0))
        r_reads = int(counters.get("ranges_read", counters.get("read_ranges", 0)))
        m_att = int(counters.get("monolith_plan_attempts", 0))
        s_exc = int(counters.get("search_exceptions", 0))
        den = int(counters.get("denials", 0))
        inv = int(counters.get("invalidations", 0))
        reqs = int(counters.get("total_requests", 0))

        tot_unique += u_reads
        tot_duplicate += d_reads
        tot_bytes += b_reads
        tot_ranges += r_reads
        tot_monolith += m_att
        tot_search_exc += s_exc
        tot_denials += den
        tot_invalidations += inv
        tot_requests += reqs

        provider = str(actor_k.get("runtime_provider", "claude")).lower()
        if provider not in provider_map:
            provider_map[provider] = {
                "unique_reads": 0,
                "duplicate_reads": 0,
                "bytes_read": 0,
                "ranges_read": 0,
                "monolith_plan_attempts": 0,
                "search_exceptions": 0,
                "total_requests": 0,
            }
        provider_map[provider]["unique_reads"] += u_reads
        provider_map[provider]["duplicate_reads"] += d_reads
        provider_map[provider]["bytes_read"] += b_reads
        provider_map[provider]["ranges_read"] += r_reads
        provider_map[provider]["monolith_plan_attempts"] += m_att
        provider_map[provider]["search_exceptions"] += s_exc
        provider_map[provider]["total_requests"] += reqs

        actor_telemetry = ActorTelemetry(
            actor_kind="subagent" if actor_k.get("actor_kind") == "subagent" else "root",
            agent_invocation_id=str(actor_k.get("agent_invocation_id") or l_file.stem),
            runtime_provider=provider,
            parent_invocation_id=actor_k.get("parent_invocation_id"),
            unique_reads=u_reads,
            duplicate_reads=d_reads,
            bytes_read=b_reads,
            ranges_read=r_reads,
            monolith_plan_attempts=m_att,
            search_exceptions=s_exc,
            denials=den,
            invalidations=inv,
            total_requests=reqs,
            highest_repeat_path=redact_path(actor_highest_path, root_p),
            files_tracked=len(files),
        )
        actors.append(actor_telemetry)

    # Calculate global highest repeat path
    session_highest_path: str | None = None
    session_max_reads = 0
    for fpath, cnt in all_file_read_counts.items():
        if cnt > session_max_reads:
            session_max_reads = cnt
            session_highest_path = fpath

    aggregate = TelemetryAggregate(
        schema=SCHEMA_CONTEXT_TELEMETRY,
        session_id=session_id,
        project_root=str(root_p),
        unique_reads=tot_unique,
        duplicate_reads=tot_duplicate,
        bytes_read=tot_bytes,
        ranges_read=tot_ranges,
        monolith_plan_attempts=tot_monolith,
        search_exceptions=tot_search_exc,
        highest_repeat_path=redact_path(session_highest_path, root_p),
        total_requests=tot_requests,
        denials=tot_denials,
        invalidations=tot_invalidations,
        files_tracked=len(all_file_read_counts),
        actors=actors,
        provider_breakdown=provider_map,
        is_green=True,
        diagnostic_code=None,
    )
    return aggregate, None


def build_finish_receipt(
    project_root: str | Path,
    session_id: str,
    epic_id: str | None = None,
    step_id: str | None = None,
    runtime_dir: Path | None = None,
) -> FinishReceipt:
    """Construct FinishReceipt for session completion.

    Fails closed with non-green status when ledger is corrupt or missing.
    """
    agg, diag = collect_session_telemetry(project_root, session_id, runtime_dir=runtime_dir)
    now_ts = datetime.now(timezone.utc).isoformat()

    if agg is None or diag is not None:
        fail_diag = diag or "telemetry_failure"
        placeholder_agg = TelemetryAggregate(
            schema=SCHEMA_CONTEXT_TELEMETRY,
            session_id=session_id,
            project_root=str(Path(project_root).resolve()),
            unique_reads=0,
            duplicate_reads=0,
            bytes_read=0,
            ranges_read=0,
            monolith_plan_attempts=0,
            search_exceptions=0,
            highest_repeat_path=None,
            total_requests=0,
            denials=0,
            invalidations=0,
            files_tracked=0,
            actors=[],
            provider_breakdown={},
            is_green=False,
            diagnostic_code=fail_diag,
        )
        return FinishReceipt(
            schema=SCHEMA_FINISH_RECEIPT,
            session_id=session_id,
            epic_id=epic_id,
            step_id=step_id,
            aggregate=placeholder_agg,
            status="corrupt" if fail_diag == "corrupt_ledger" else ("missing" if fail_diag == "missing_ledger" else "non_green"),
            diagnostics=[fail_diag],
            timestamp=now_ts,
            secret_free=True,
        )

    return FinishReceipt(
        schema=SCHEMA_FINISH_RECEIPT,
        session_id=session_id,
        epic_id=epic_id,
        step_id=step_id,
        aggregate=agg,
        status="green",
        diagnostics=[],
        timestamp=now_ts,
        secret_free=True,
    )


def format_telemetry_summary(receipt_or_aggregate: FinishReceipt | TelemetryAggregate) -> str:
    """Format short human/machine-readable projection string."""
    if isinstance(receipt_or_aggregate, FinishReceipt):
        status = receipt_or_aggregate.status
        agg = receipt_or_aggregate.aggregate
    else:
        status = "green" if receipt_or_aggregate.is_green else "non_green"
        agg = receipt_or_aggregate

    if not agg.is_green or status != "green":
        diag = agg.diagnostic_code or "non_green"
        return f"[NON-GREEN: {diag}]"

    highest_str = agg.highest_repeat_path or "none"
    return (
        f"unique_reads={agg.unique_reads}, "
        f"duplicate_reads={agg.duplicate_reads}, "
        f"bytes_read={agg.bytes_read}, "
        f"ranges_read={agg.ranges_read}, "
        f"monolith_attempts={agg.monolith_plan_attempts}, "
        f"search_exceptions={agg.search_exceptions}, "
        f"highest_repeat={highest_str} (green)"
    )
