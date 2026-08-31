"""Tier-1 autopilot session runner and eligibility/attempt checker."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loop.incidents.alert import escalate_incident
from loop.incidents.events import (
    emit_tier1_spawn,
    emit_tier1_verify_pass,
    emit_tier1_verify_fail,
    emit_tier1_escalated,
)
from loop.incidents.metrics import increment_counter
from loop.incidents.schema import IncidentRecord
from loop.incidents.scope import build_allowlist, write_scope_file
from loop.incidents.store import parse_incidents_jsonl
from loop.incidents.tier1 import is_tier1_eligible
from loop.incidents.tier1_prompt import build_tier1_prompt
from loop.incidents.tier1_verify import VerifyResult, run_tier1_verify


@dataclass
class Tier1Result:
    success: bool
    session_log_path: str | None = None
    attempt_number: int = 1
    error: str | None = None
    verify_result: VerifyResult | None = None


def get_tier1_attempts(incident_id: str, epic_dir: Path | str) -> int:
    """Read number of tier-1 attempts for incident_id from incidents.jsonl metadata."""
    epic_path = Path(epic_dir)
    incidents_path = epic_path / "incidents.jsonl"
    if not incidents_path.is_file():
        return 0

    try:
        records = parse_incidents_jsonl(incidents_path)
    except Exception:
        return 0

    for rec in records:
        if rec.incident_id == incident_id:
            attempts = rec.metadata.get("tier1_attempts", 0)
            if isinstance(attempts, int):
                return attempts
            try:
                return int(attempts)
            except (ValueError, TypeError):
                return 0
    return 0


def should_attempt_tier1(
    incident: IncidentRecord | None,
    epic_dir: Path | str,
    eligibility_config_path: Path | str | None = None,
) -> bool:
    """Check whether a tier-1 session should be attempted."""
    tier1_enabled = os.environ.get("EPIC_INCIDENT_TIER1", "1")
    if tier1_enabled in ("0", "false", "False", "no"):
        return False

    if incident is None:
        return False

    if not is_tier1_eligible(incident, config_path=eligibility_config_path):
        return False

    try:
        max_attempts = int(os.environ.get("EPIC_INCIDENT_TIER1_MAX", "2"))
    except ValueError:
        max_attempts = 2

    attempts = get_tier1_attempts(incident.incident_id, epic_dir)
    if attempts >= max_attempts:
        return False

    return True


def run_tier1_session(
    incident: IncidentRecord,
    epic_dir: Path | str,
    project_root: Path | str,
    eligibility_config_path: Path | str | None = None,
) -> Tier1Result:
    """Run a Tier-1 incident resolution session using Claude CLI."""
    epic_path = Path(epic_dir)
    root_path = Path(project_root)

    attempts = get_tier1_attempts(incident.incident_id, epic_path) + 1

    # Emit tier1_spawn event & metric increment
    emit_tier1_spawn(
        cwd=root_path,
        incident_id=incident.incident_id,
        attempt_number=attempts,
        metadata={"diagnostic_codes": list(incident.diagnostic_codes)},
        epic_id=incident.epic_id,
    )
    increment_counter(epic_path, "tier1_attempts_total")

    # 1. Build allowlist and write scope file
    allowlist = build_allowlist(incident, root_path)
    scope_path = epic_path / f"tier1_scope_{incident.incident_id}.json"
    write_scope_file(allowlist, scope_path)

    # 2. Build prompt
    prompt = build_tier1_prompt(incident, epic_path, allowlist)

    # 3. Environment setup
    env = os.environ.copy()
    env["EPIC_INCIDENT_SESSION"] = "1"
    env["EPIC_INCIDENT_SCOPE_FILE"] = str(scope_path)
    model = env.get("PROJECT_LOOP_BUGFIX_MODEL") or env.get("ANTHROPIC_MODEL") or "claude-sonnet-3-5"

    log_dir = epic_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    session_log_path = log_dir / f"tier1_{incident.incident_id}_{attempts}.log"

    cli_cmd = env.get("TIER1_CLAUDE_CMD")
    if cli_cmd:
        cmd = cli_cmd.split() + [prompt]
    else:
        cmd = ["claude", "--model", model, "-p", prompt]

    try:
        with session_log_path.open("w", encoding="utf-8") as out:
            proc = subprocess.run(
                cmd,
                cwd=str(root_path),
                env=env,
                stdout=out,
                stderr=subprocess.STDOUT,
                timeout=int(env.get("EPIC_TIER1_TIMEOUT", "300")),
            )
        session_success = proc.returncode == 0
        if session_success:
            verify_res = run_tier1_verify(incident, root_path, epic_dir=epic_path)
            if verify_res.passed:
                emit_tier1_verify_pass(
                    cwd=root_path,
                    incident_id=incident.incident_id,
                    attempt_number=attempts,
                    epic_id=incident.epic_id,
                )
                increment_counter(epic_path, "tier1_resolved_total")
            else:
                emit_tier1_verify_fail(
                    cwd=root_path,
                    incident_id=incident.incident_id,
                    attempt_number=attempts,
                    epic_id=incident.epic_id,
                )
            return Tier1Result(
                success=verify_res.passed,
                session_log_path=str(session_log_path),
                attempt_number=attempts,
                verify_result=verify_res,
            )
        emit_tier1_verify_fail(
            cwd=root_path,
            incident_id=incident.incident_id,
            attempt_number=attempts,
            epic_id=incident.epic_id,
        )
        res = Tier1Result(
            success=False,
            session_log_path=str(session_log_path),
            attempt_number=attempts,
        )
        if not should_attempt_tier1(incident, epic_path):
            escalate_incident(incident, epic_path, root_path)
            emit_tier1_escalated(
                cwd=root_path,
                incident_id=incident.incident_id,
                attempt_number=attempts,
                epic_id=incident.epic_id,
            )
            increment_counter(epic_path, "tier1_escalated_total")
        return res
    except Exception as exc:
        emit_tier1_verify_fail(
            cwd=root_path,
            incident_id=incident.incident_id,
            attempt_number=attempts,
            epic_id=incident.epic_id,
        )
        res = Tier1Result(
            success=False,
            session_log_path=str(session_log_path),
            attempt_number=attempts,
            error=str(exc),
        )
        if not should_attempt_tier1(incident, epic_path):
            escalate_incident(incident, epic_path, root_path)
            emit_tier1_escalated(
                cwd=root_path,
                incident_id=incident.incident_id,
                attempt_number=attempts,
                epic_id=incident.epic_id,
            )
            increment_counter(epic_path, "tier1_escalated_total")
        return res
