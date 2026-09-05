"""Lifecycle projection event emission helpers for incident & repair events."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from epic_events import EVENT_KINDS, build_event
from epic_paths import epic_dir

logger = logging.getLogger(__name__)

TIER1_SPAWN = "tier1_spawn"
TIER1_VERIFY_PASS = "tier1_verify_pass"
TIER1_VERIFY_FAIL = "tier1_verify_fail"
TIER1_ESCALATED = "tier1_escalated"

_TIER1_EVENT_KINDS = {
    "incident_opened",
    "incident_resolved",
    "repair_applied",
    TIER1_SPAWN,
    TIER1_VERIFY_PASS,
    TIER1_VERIFY_FAIL,
    TIER1_ESCALATED,
}

# Dynamically patch EVENT_KINDS if needed or ensure event emission works safely.
# Note: epic_events validation checks `kind in EVENT_KINDS`.
try:
    from epic_events import EVENT_KINDS as _EVENT_KINDS
    if isinstance(_EVENT_KINDS, (set, frozenset)):
        import epic_events
        epic_events.EVENT_KINDS = frozenset(_EVENT_KINDS | _TIER1_EVENT_KINDS)
except Exception as exc:
    logger.warning("Failed to register incident event kinds in epic_events: %s", exc)


def _get_epic_info(cwd: Path) -> tuple[str, str] | None:
    """Discover role_dir and epic_id for event path resolution."""
    try:
        from epic import discover_epic_for_pipeline
        info = discover_epic_for_pipeline(cwd)
        if info and info.get("epic_id") and info.get("role_dir"):
            return info["role_dir"], info["epic_id"]
    except Exception as exc:
        logger.debug("Could not discover epic identity for event emission: %s", exc)
    return None


def _append_event_to_jsonl(cwd: Path, epic_id: str, role_dir: str, kind: str, metadata: dict[str, Any]) -> bool:
    """Append event to <mb_root>/<role_dir>/events/<epic_id>/events.jsonl using build_event."""
    try:
        from loop.paths.pack_layout import resolve_mb_root
        mb_root = resolve_mb_root(cwd=cwd)
    except Exception:
        mb_root = cwd / "memory-bank"

    try:
        from epic import _append_event, _event_log_path, _next_event_seq, read_event_log_result, utc_now, atomic_write_text
    except ImportError:
        try:
            from epic.core import _append_event, _event_log_path, _next_event_seq, read_event_log_result, utc_now, atomic_write_text
        except ImportError:
            logger.error("Could not import epic helpers for event emission")
            return False

    events_path = mb_root / role_dir / "events" / epic_id / "events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)

    stream = read_event_log_result(events_path, expected_epic_id=epic_id, cwd=cwd)
    events = list(stream.events) if not stream.diagnostics else []

    try:
        dummy_artifact = events_path.relative_to(cwd).as_posix()
    except ValueError:
        dummy_artifact = f"{mb_root.name}/{role_dir}/events/{epic_id}/events.jsonl"

    # Sanitize metadata to strip secret keys/values or prompt fields before build_event
    safe_metadata = {}
    if metadata:
        for k, v in metadata.items():
            if k.lower() in ("prompt", "token", "api_key", "secret", "password"):
                continue
            if isinstance(v, (list, tuple)):
                v = ",".join(str(x) for x in v)
            elif not isinstance(v, (str, int, float, bool)) and v is not None:
                v = str(v)
            safe_metadata[k] = v

    try:
        event = build_event(
            epic_id=epic_id,
            kind=kind,
            artifact=dummy_artifact,
            artifact_sha256="0" * 64,
            seq=len(events) + 1,
            timestamp=utc_now(),
            metadata=safe_metadata,
        )
    except Exception as exc:
        logger.error("Failed to build event kind=%s for epic=%s: %s", kind, epic_id, exc)
        return False

    events.append(event)
    try:
        atomic_write_text(
            events_path,
            "".join(import_json().dumps(e, ensure_ascii=False) + "\n" for e in events),
        )
        return True
    except Exception as exc:
        logger.error("Failed to write event log %s: %s", events_path, exc)
        return False


def import_json():
    import json
    return json


def emit_incident_opened(cwd: str | Path, epic_id: str | None = None, metadata: dict[str, Any] | None = None) -> bool:
    """Emit incident_opened event when epic_id is known."""
    cwd_p = Path(cwd).resolve()
    role_dir = None
    if not epic_id:
        info = _get_epic_info(cwd_p)
        if info:
            role_dir, epic_id = info
    else:
        info = _get_epic_info(cwd_p)
        if info:
            role_dir = info[0]
        else:
            role_dir = "back"

    if not epic_id or not role_dir:
        logger.debug("Skip incident_opened emission: unknown epic_id or role_dir")
        return False

    return _append_event_to_jsonl(cwd_p, epic_id, role_dir, "incident_opened", metadata or {})


def emit_incident_resolved(cwd: str | Path, epic_id: str | None = None, metadata: dict[str, Any] | None = None) -> bool:
    """Emit incident_resolved event when epic_id is known."""
    cwd_p = Path(cwd).resolve()
    role_dir = None
    if not epic_id:
        info = _get_epic_info(cwd_p)
        if info:
            role_dir, epic_id = info
    else:
        info = _get_epic_info(cwd_p)
        if info:
            role_dir = info[0]
        else:
            role_dir = "back"

    if not epic_id or not role_dir:
        logger.debug("Skip incident_resolved emission: unknown epic_id or role_dir")
        return False

    return _append_event_to_jsonl(cwd_p, epic_id, role_dir, "incident_resolved", metadata or {})


def emit_repair_applied(cwd: str | Path, epic_id: str | None = None, metadata: dict[str, Any] | None = None) -> bool:
    """Emit repair_applied event when epic_id is known."""
    cwd_p = Path(cwd).resolve()
    role_dir = None
    if not epic_id:
        info = _get_epic_info(cwd_p)
        if info:
            role_dir, epic_id = info
    else:
        info = _get_epic_info(cwd_p)
        if info:
            role_dir = info[0]
        else:
            role_dir = "back"

    if not epic_id or not role_dir:
        logger.debug("Skip repair_applied emission: unknown epic_id or role_dir")
        return False

    return _append_event_to_jsonl(cwd_p, epic_id, role_dir, "repair_applied", metadata or {})


def emit_event(
    cwd: str | Path,
    kind: str,
    epic_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Emit generic event kind when epic_id is known or discoverable."""
    cwd_p = Path(cwd).resolve()
    role_dir = None
    if not epic_id:
        info = _get_epic_info(cwd_p)
        if info:
            role_dir, epic_id = info
    else:
        info = _get_epic_info(cwd_p)
        if info:
            role_dir = info[0]
        else:
            role_dir = "back"

    if not epic_id or not role_dir:
        logger.debug("Skip event emission kind=%s: unknown epic_id or role_dir", kind)
        return False

    return _append_event_to_jsonl(cwd_p, epic_id, role_dir, kind, metadata or {})


def emit_tier1_spawn(
    cwd: str | Path,
    incident_id: str,
    attempt_number: int = 1,
    metadata: dict[str, Any] | None = None,
    epic_id: str | None = None,
) -> bool:
    """Emit tier1_spawn event."""
    meta = dict(metadata or {})
    meta["incident_id"] = incident_id
    meta["attempt_number"] = attempt_number
    return emit_event(cwd, TIER1_SPAWN, epic_id=epic_id, metadata=meta)


def emit_tier1_verify_pass(
    cwd: str | Path,
    incident_id: str,
    attempt_number: int = 1,
    metadata: dict[str, Any] | None = None,
    epic_id: str | None = None,
) -> bool:
    """Emit tier1_verify_pass event."""
    meta = dict(metadata or {})
    meta["incident_id"] = incident_id
    meta["attempt_number"] = attempt_number
    return emit_event(cwd, TIER1_VERIFY_PASS, epic_id=epic_id, metadata=meta)


def emit_tier1_verify_fail(
    cwd: str | Path,
    incident_id: str,
    attempt_number: int = 1,
    metadata: dict[str, Any] | None = None,
    epic_id: str | None = None,
) -> bool:
    """Emit tier1_verify_fail event."""
    meta = dict(metadata or {})
    meta["incident_id"] = incident_id
    meta["attempt_number"] = attempt_number
    return emit_event(cwd, TIER1_VERIFY_FAIL, epic_id=epic_id, metadata=meta)


def emit_tier1_escalated(
    cwd: str | Path,
    incident_id: str,
    attempt_number: int = 1,
    metadata: dict[str, Any] | None = None,
    epic_id: str | None = None,
) -> bool:
    """Emit tier1_escalated event."""
    meta = dict(metadata or {})
    meta["incident_id"] = incident_id
    meta["attempt_number"] = attempt_number
    return emit_event(cwd, TIER1_ESCALATED, epic_id=epic_id, metadata=meta)

