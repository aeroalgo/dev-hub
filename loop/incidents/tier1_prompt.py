"""Tier-1 incident autopilot prompt assembly and runbook context loader."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loop.incidents.schema import IncidentRecord

DEFAULT_RUNBOOKS_DIR = Path(__file__).parent / "runbooks"

FORBIDDEN_WRITES_TEXT = (
    "FORBIDDEN: You must NOT edit or write any files outside the specified allowed scope paths.\n"
    "FORBIDDEN: Do not modify product source code (src/**), system configs, or project secrets."
)


def load_runbook(diagnostic_code: str, runbooks_dir: Path | str | None = None) -> str:
    """Read runbook for diagnostic_code. Return fallback text if missing."""
    if runbooks_dir is None:
        rb_dir = DEFAULT_RUNBOOKS_DIR
    else:
        rb_dir = Path(runbooks_dir)

    rb_file = rb_dir / f"{diagnostic_code}.md"
    if not rb_file.is_file():
        return f"No runbook for {diagnostic_code}"

    try:
        return rb_file.read_text(encoding="utf-8").strip()
    except Exception:
        return f"No runbook for {diagnostic_code}"


def format_scope_block(allowlist: list[str]) -> str:
    """Format allowed scope paths and explicit forbidden block."""
    sorted_scope = sorted(set(allowlist))
    items = "\n".join(f"- {path}" for path in sorted_scope)
    return (
        "## Scope\n"
        "Allowed file paths for edits:\n"
        f"{items}\n\n"
        "## Forbidden writes\n"
        f"{FORBIDDEN_WRITES_TEXT}"
    )


def build_tier1_prompt(
    incident: IncidentRecord,
    epic_dir: Path | str,
    scope_allowlist: list[str],
    runbooks_dir: Path | str | None = None,
) -> str:
    """Assemble deterministic BUGFIX prompt for Tier-1 autopilot session."""
    sorted_codes = sorted(set(incident.diagnostic_codes))
    runbook_sections: list[str] = []

    for code in sorted_codes:
        content = load_runbook(code, runbooks_dir=runbooks_dir)
        runbook_sections.append(f"### Runbook: {code}\n{content}")

    runbooks_block = "\n\n".join(runbook_sections) if runbook_sections else "No diagnostic runbooks assigned."
    scope_block = format_scope_block(scope_allowlist)

    epic_dir_path = Path(epic_dir)
    codes_str = ", ".join(sorted_codes)

    prompt = (
        f"# Tier-1 Incident Repair Prompt — {incident.incident_id}\n\n"
        "## Incident\n"
        f"- Incident ID: {incident.incident_id}\n"
        f"- Epic ID: {incident.epic_id}\n"
        f"- Step ID: {incident.step_id}\n"
        f"- Phase: {incident.phase}\n"
        f"- Diagnostic Codes: {codes_str}\n\n"
        "## Runbook Context\n"
        f"{runbooks_block}\n\n"
        f"{scope_block}\n\n"
        "## Goal\n"
        "Fix the specified incident by addressing the root cause identified in the runbook.\n"
        "Ensure all changes strictly remain within the specified allowed scope.\n\n"
        "## Verify command\n"
        f"python3 .claude/hooks/epic_resolve.py validate-step --path {epic_dir_path}"
    )

    return prompt
