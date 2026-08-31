"""Tier-0 standalone repair functions for incidents."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from _lib import load_runner_owner, runner_pid_alive
from epic_paths import epic_dir

logger = logging.getLogger(__name__)


def clear_stale_runner_lock(cwd: str | Path) -> dict[str, Any]:
    """Clear runner lock and owner file if owner process is dead."""
    sp = epic_dir(cwd)
    owner_path = sp / "runner.json"
    lock_path = sp / "runner.lock"

    owner = load_runner_owner(owner_path)
    if owner and runner_pid_alive(owner.pid):
        logger.info("Runner process %s is still alive, skip clear", owner.pid)
        return {"repaired": False, "reason": "owner_alive"}

    cleared = False
    if owner_path.is_file():
        try:
            owner_path.unlink()
            cleared = True
        except OSError:
            pass
    if lock_path.is_file():
        try:
            lock_path.unlink()
            cleared = True
        except OSError:
            pass

    return {"repaired": cleared, "cleared_owner": owner_path.name if cleared else None}


def verify_runner_owner(cwd: str | Path) -> bool:
    """Verify runner owner is not stale (returns True if OK / valid state)."""
    sp = epic_dir(cwd)
    owner_path = sp / "runner.json"
    owner = load_runner_owner(owner_path)
    if owner is None:
        return True
    return runner_pid_alive(owner.pid)


def repair_active_context_shape(cwd: str | Path) -> dict[str, Any]:
    """Rebuild activeContext from decompose index when shape validation fails."""
    from epic.core import (
        arm_active_context_from_decompose,
        load_epic_state,
        read_active_context,
        sync_cursor_from_index,
        validate_active_context_shape,
    )

    cwd_p = Path(cwd)
    errors = validate_active_context_shape(read_active_context(cwd_p))
    if not errors:
        return {"repaired": False, "ok": False, "reason": "already_valid"}

    state = load_epic_state(cwd_p)
    decompose = (state.get("armed_decompose") or "").strip()
    if not decompose:
        return {"repaired": False, "ok": False, "reason": "no_decompose"}

    synced = sync_cursor_from_index(cwd_p)
    if synced.get("synced") or synced.get("ok"):
        if not validate_active_context_shape(read_active_context(cwd_p)):
            return {
                "repaired": True,
                "ok": True,
                "mode": synced.get("mode") or "sync_cursor",
            }

    arm = arm_active_context_from_decompose(cwd_p, decompose)
    if arm.get("ok") and not validate_active_context_shape(read_active_context(cwd_p)):
        return {"repaired": True, "ok": True, "mode": "arm_from_decompose", "arm": arm}

    return {
        "repaired": False,
        "ok": False,
        "reason": "shape_still_invalid",
        "sync": synced,
        "arm": arm,
    }


def verify_active_context_shape(cwd: str | Path) -> bool:
    from epic.core import read_active_context, validate_active_context_shape

    return len(validate_active_context_shape(read_active_context(cwd))) == 0
