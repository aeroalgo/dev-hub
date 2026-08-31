"""Persist gate verdict sidecars — typed alternative to transcript regex."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

_HUB_ROOT = Path(__file__).resolve().parents[1]
if _HUB_ROOT.is_dir() and str(_HUB_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUB_ROOT))

from loop.schemas.gate_verdict import GateVerdictRecord, GateVerdictValue


def gates_dir(cwd: str | Path) -> Path:
    from epic_paths import epic_dir

    path = epic_dir(cwd) / "gates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def gate_verdict_path(cwd: str | Path, agent_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in agent_id.strip())
    return gates_dir(cwd) / f"{safe or 'gate'}.json"


def write_gate_verdict(
    cwd: str | Path,
    agent_id: str,
    verdict: GateVerdictValue | str,
    *,
    step_id: str | None = None,
    session_id: str | None = None,
    epic_id: str | None = None,
    recorded_at: str,
    evidence_sha256: str | None = None,
) -> GateVerdictRecord:
    data = {
        "agent_id": agent_id.strip() if isinstance(agent_id, str) else agent_id,
        "verdict": str(verdict).upper(),
        "step_id": step_id,
        "session_id": session_id,
        "epic_id": epic_id,
        "recorded_at": recorded_at,
        "evidence_sha256": evidence_sha256,
    }
    record = GateVerdictRecord.model_validate(data)
    path = gate_verdict_path(cwd, agent_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(record.model_dump(by_alias=True), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    with tmp.open("r+") as handle:
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)
    return record


def read_gate_verdict(cwd: str | Path, agent_id: str) -> GateVerdictRecord | None:
    path = gate_verdict_path(cwd, agent_id)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    try:
        return GateVerdictRecord.model_validate(raw)
    except Exception:
        return None


def gate_verdict_for_step(
    cwd: str | Path,
    agent_id: str,
    *,
    step_id: str | None = None,
    session_id: str | None = None,
) -> GateVerdictRecord | None:
    record = read_gate_verdict(cwd, agent_id)
    if record is None:
        return None
    if step_id and record.step_id and record.step_id != step_id:
        return None
    if session_id and record.session_id and record.session_id != session_id:
        return None
    return record
