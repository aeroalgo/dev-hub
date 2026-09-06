"""Persist sunset inventory sidecars — typed result storage for parent agents."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

_HUB_ROOT = Path(__file__).resolve().parents[1]
if _HUB_ROOT.is_dir() and str(_HUB_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUB_ROOT))

_HOOKS_DIR = _HUB_ROOT / "harness" / "hooks"
if _HOOKS_DIR.is_dir() and str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from loop.schemas.sunset_inventory import SunsetReport, SCHEMA_LOOP_SUNSET_INVENTORY


def sunset_dir(cwd: str | Path) -> Path:
    """Return runtime epic directory for sunset sidecars."""
    from epic_paths import epic_dir

    path = epic_dir(cwd)
    path.mkdir(parents=True, exist_ok=True)
    return path


def sunset_sidecar_path(
    cwd: str | Path,
    session_id: str,
    *,
    step_id: str | None = None,
) -> Path:
    """Compute deterministic sidecar path: `.claude/runtime/epic/sunset-<session>[-<step>].json`."""
    safe_session = "".join(
        ch if ch.isalnum() or ch in "-_" else "_" for ch in (session_id or "default").strip()
    )
    if step_id and str(step_id).strip():
        safe_step = "".join(
            ch if ch.isalnum() or ch in "-_" else "_" for ch in str(step_id).strip()
        )
        filename = f"sunset-{safe_session or 'session'}-{safe_step}.json"
    else:
        filename = f"sunset-{safe_session or 'session'}.json"
    return sunset_dir(cwd) / filename


def write_sunset_sidecar(
    cwd: str | Path,
    session_id: str,
    payload: dict[str, Any] | SunsetReport,
    *,
    step_id: str | None = None,
) -> SunsetReport:
    """Validate and atomically persist SunsetReport to disk in gate-family path.

    Raises ValidationError or OSError if validation or write fails (fail-closed).
    """
    if isinstance(payload, SunsetReport):
        report = payload
    else:
        report = SunsetReport.model_validate(payload)

    path = sunset_sidecar_path(cwd, session_id, step_id=step_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(report.model_dump(by_alias=True), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with tmp.open("r+") as handle:
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)
    return report


def read_sunset_sidecar(
    cwd: str | Path,
    session_id: str,
    *,
    step_id: str | None = None,
) -> SunsetReport | None:
    """Read and validate persisted sunset inventory sidecar for parent agent."""
    path = sunset_sidecar_path(cwd, session_id, step_id=step_id)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    try:
        return SunsetReport.model_validate(raw)
    except Exception:
        return None
