"""Epic/step touch ledger — SoT of files this session actually edited.

Scope checks and verify MUST use this ledger, not whole-repo ``git status``.
Pre-existing dirty files from other epics/sessions are not blockers and MUST NOT
be discarded via ``git checkout --`` / ``git restore`` / ``git reset --hard``.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "loop-touch-ledger/v1"
LEDGER_NAME = "touch-ledger.json"


def touch_ledger_path(cwd: str | Path) -> Path:
    from epic_paths import epic_dir

    return epic_dir(cwd) / LEDGER_NAME


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm_rel(cwd: str | Path, path: str | Path) -> str | None:
    root = Path(cwd).expanduser().resolve()
    raw = str(path or "").strip()
    if not raw:
        return None
    p = Path(raw).expanduser()
    try:
        if p.is_absolute():
            rel = p.resolve().relative_to(root)
        else:
            rel = Path(str(p).replace("\\", "/").lstrip("./"))
    except (OSError, ValueError):
        return None
    out = str(rel).replace("\\", "/").strip().lstrip("./")
    if not out or ".." in Path(out).parts:
        return None
    return out


def empty_ledger(
    *,
    epic_id: str | None = None,
    step_id: str | None = None,
    phase_run_id: str | None = None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "epic_id": str(epic_id or "").strip() or None,
        "step_id": str(step_id or "").strip() or None,
        "phase_run_id": str(phase_run_id or "").strip() or None,
        "updated_at": _utc_now(),
        "paths": [],
    }


def load_touch_ledger(cwd: str | Path) -> dict[str, Any]:
    path = touch_ledger_path(cwd)
    if not path.is_file():
        return empty_ledger()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_ledger()
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return empty_ledger()
    paths = data.get("paths")
    if not isinstance(paths, list):
        data["paths"] = []
    return data


def save_touch_ledger(cwd: str | Path, data: dict[str, Any]) -> Path:
    path = touch_ledger_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(data)
    payload["schema"] = SCHEMA
    payload["updated_at"] = _utc_now()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)
    return path


def reset_touch_ledger(
    cwd: str | Path,
    *,
    epic_id: str | None = None,
    step_id: str | None = None,
    phase_run_id: str | None = None,
) -> dict[str, Any]:
    data = empty_ledger(
        epic_id=epic_id,
        step_id=step_id,
        phase_run_id=phase_run_id,
    )
    save_touch_ledger(cwd, data)
    return data


def ensure_touch_ledger_identity(
    cwd: str | Path,
    *,
    epic_id: str | None,
    step_id: str | None,
    phase_run_id: str | None = None,
) -> dict[str, Any]:
    """Reset ledger when armed epic/step (or phase_run) changes."""
    cur = load_touch_ledger(cwd)
    eid = str(epic_id or "").strip() or None
    sid = str(step_id or "").strip() or None
    prid = str(phase_run_id or "").strip() or None
    same = (
        (cur.get("epic_id") or None) == eid
        and (cur.get("step_id") or None) == sid
        and (not prid or (cur.get("phase_run_id") or None) == prid)
    )
    if same and cur.get("schema") == SCHEMA:
        if prid and not cur.get("phase_run_id"):
            cur["phase_run_id"] = prid
            save_touch_ledger(cwd, cur)
        return cur
    return reset_touch_ledger(
        cwd,
        epic_id=eid,
        step_id=sid,
        phase_run_id=prid or cur.get("phase_run_id"),
    )


def record_touch(
    cwd: str | Path,
    path: str | Path,
    *,
    operation: str = "edit",
    epic_id: str | None = None,
    step_id: str | None = None,
    phase_run_id: str | None = None,
) -> dict[str, Any]:
    """Append a touched path for the current epic/step (idempotent per path)."""
    rel = _norm_rel(cwd, path)
    if not rel:
        return load_touch_ledger(cwd)

    eid = epic_id
    sid = step_id
    prid = phase_run_id
    if eid is None or sid is None or prid is None:
        try:
            from epic.core import load_epic_state

            st = load_epic_state(cwd) or {}
            eid = eid or st.get("armed_epic") or st.get("epic_id") or st.get("epic")
            sid = sid or st.get("armed_step") or st.get("step")
            prid = prid or st.get("phase_run_id")
        except Exception:
            pass

    data = ensure_touch_ledger_identity(
        cwd,
        epic_id=str(eid or "").strip() or None,
        step_id=str(sid or "").strip() or None,
        phase_run_id=str(prid or "").strip() or None,
    )
    entries = list(data.get("paths") or [])
    op = str(operation or "edit").strip() or "edit"
    found = False
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("path") or "") == rel:
            entry["operation"] = op
            entry["at"] = _utc_now()
            found = True
            break
    if not found:
        entries.append({"path": rel, "operation": op, "at": _utc_now()})
    data["paths"] = entries
    save_touch_ledger(cwd, data)
    return data


def touched_paths(
    cwd: str | Path,
    *,
    epic_id: str | None = None,
    step_id: str | None = None,
) -> list[str]:
    data = load_touch_ledger(cwd)
    if epic_id and (data.get("epic_id") or None) != str(epic_id).strip():
        return []
    if step_id and (data.get("step_id") or None) != str(step_id).strip():
        return []
    out: list[str] = []
    seen: set[str] = set()
    for entry in data.get("paths") or []:
        if not isinstance(entry, dict):
            continue
        rel = str(entry.get("path") or "").strip()
        if not rel or rel in seen:
            continue
        seen.add(rel)
        out.append(rel)
    return out


def touch_ledger_prompt_block(cwd: str | Path) -> str:
    data = load_touch_ledger(cwd)
    paths = touched_paths(cwd)
    lines = [
        "## Touch ledger (scope SoT — HARD)",
        f"epic_id: {data.get('epic_id') or '—'}",
        f"step_id: {data.get('step_id') or '—'}",
        "Scope of *this* session edits = paths below (hook-recorded Write/Edit).",
        "Whole-repo `git status` dirty ≠ blocker. Foreign/pre-existing dirty MUST be ignored.",
        "FORBIDDEN: `git checkout --` / `git restore` / `git reset --hard` / `git clean` "
        "to discard files not listed here.",
        "REVERT только path из этого ledger, если он вне shard `files:` allowlist.",
    ]
    if paths:
        lines.append("touched:")
        for p in paths:
            lines.append(f"- `{p}`")
    else:
        lines.append("touched: (empty — no Write/Edit recorded yet)")
    return "\n".join(lines)
