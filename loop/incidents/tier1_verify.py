"""Post-tier1 verify AC slice orchestration for loop autopilot incidents."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from loop.incidents.schema import IncidentRecord
from loop.incidents.store import resolve_incident


@dataclass
class VerifyResult:
    passed: bool
    output: str
    command: str


def build_verify_ac_slice(incident: IncidentRecord, project_root: Path | str) -> list[str]:
    """Return list of pytest commands covering orchestration invariants for diagnostic codes."""
    commands: list[str] = []

    # Map diagnostic codes to specific loop/ pytest commands (strictly NO product tests / non-loop paths)
    diag_codes = incident.diagnostic_codes if incident.diagnostic_codes else []

    handled = False
    for code in diag_codes:
        if code == "active_context_shape_invalid":
            commands.append(".venv/bin/pytest loop/tests/test_incidents_schema_store.py -q --tb=line")
            handled = True
        elif code == "index_step_missing":
            commands.append(".venv/bin/pytest loop/tests/ -k index -q --tb=line")
            handled = True

    if not handled or not commands:
        commands.append(".venv/bin/pytest loop/tests/ -q --tb=line")

    return commands


def run_tier1_verify(
    incident: IncidentRecord,
    project_root: Path | str,
    epic_dir: Path | str | None = None,
) -> VerifyResult:
    """Execute verify commands for orchestration invariants. Pass if all exit 0, Fail otherwise."""
    root = Path(project_root)
    commands = build_verify_ac_slice(incident, root)

    combined_outputs: list[str] = []
    all_passed = True

    for cmd in commands:
        try:
            res = subprocess.run(
                cmd,
                shell=True,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=120,
            )
            combined_outputs.append(f"Command: {cmd}\nExit: {res.returncode}\nStdout: {res.stdout}\nStderr: {res.stderr}")
            if res.returncode != 0:
                all_passed = False
                break
        except Exception as exc:
            all_passed = False
            combined_outputs.append(f"Command: {cmd}\nException: {exc}")
            break

    result_output = "\n---\n".join(combined_outputs)
    joined_cmds = " && ".join(commands)

    verify_res = VerifyResult(
        passed=all_passed,
        output=result_output,
        command=joined_cmds,
    )

    if all_passed and epic_dir:
        resolve_incident(
            epic_dir=epic_dir,
            incident_id=incident.incident_id,
            resolution_tier="tier1",
            resolution_action="verify_pass",
        )

    return verify_res
