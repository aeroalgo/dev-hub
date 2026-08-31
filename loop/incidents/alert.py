"""Alerting and escalation functions for loop incidents."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

from loop.incidents.alert_schema import LoopAlertV1Payload
from loop.incidents.board_soft import try_mark_board_execution_failed
from loop.incidents.schema import IncidentRecord
from loop.incidents.store import resolve_incident

logger = logging.getLogger(__name__)


def write_need_human_file(epic_dir: Path | str, incident: IncidentRecord) -> Path:
    """Write NEED_HUMAN file in epic_dir with incident details."""
    epic_path = Path(epic_dir)
    epic_path.mkdir(parents=True, exist_ok=True)
    need_human_path = epic_path / "NEED_HUMAN"

    codes_str = ",".join(incident.diagnostic_codes)
    runbook = incident.runbook_rel or "docs/runbooks/incident.md"
    content = (
        f"NEED_HUMAN: incident_{codes_str}\n"
        f"incident_id: {incident.incident_id}\n"
        f"runbook: {runbook}\n"
    )

    need_human_path.write_text(content, encoding="utf-8")
    return need_human_path


def print_stderr_banner(incident: IncidentRecord) -> None:
    """Print multi-line stderr banner with NEED_HUMAN marker + runbook path."""
    runbook = incident.runbook_rel or "docs/runbooks/incident.md"
    banner = (
        f"\n=======================================================\n"
        f" NEED_HUMAN ESCALATION: Incident {incident.incident_id}\n"
        f" Diagnostic Codes: {', '.join(incident.diagnostic_codes)}\n"
        f" Runbook: {runbook}\n"
        f"=======================================================\n"
    )
    sys.stderr.write(banner)
    sys.stderr.flush()


def post_webhook(incident: IncidentRecord, url: str | None = None, project_root: Path | str = "") -> bool:
    """POST loop-alert/v1 JSON to EPIC_ALERT_WEBHOOK_URL.

    Fail-closed: returns False and logs error on 4xx/5xx or connection error, does not raise.
    Does NOT contain secrets.
    """
    target_url = url or os.environ.get("EPIC_ALERT_WEBHOOK_URL")
    if not target_url:
        return True

    now_iso = datetime.now(timezone.utc).isoformat()
    payload = LoopAlertV1Payload(
        schema="loop-alert/v1",
        incident_id=incident.incident_id,
        diagnostic_codes=list(incident.diagnostic_codes),
        epic_id=incident.epic_id,
        step_id=incident.step_id,
        project_root=str(project_root),
        timestamp=now_iso,
    )

    data_bytes = json.dumps(payload.to_dict()).encode("utf-8")
    req = urllib.request.Request(
        target_url,
        data=data_bytes,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if 200 <= response.status < 300:
                return True
            logger.error("Alert webhook returned status %s", response.status)
            return False
    except urllib.error.HTTPError as exc:
        logger.error("Alert webhook HTTP Error %s: %s", exc.code, exc.reason)
        return False
    except Exception as exc:
        logger.error("Alert webhook failed: %s", exc)
        return False


def escalate_incident(
    incident: IncidentRecord,
    epic_dir: Path | str,
    project_root: Path | str = "",
    url: str | None = None,
) -> IncidentRecord:
    """Perform escalation flow:
    1. resolve_incident(store, 'escalated', tier='escalation')
    2. write_need_human_file(epic_dir, incident)
    3. print_stderr_banner(incident)
    4. post_webhook(incident)
    """
    epic_path = Path(epic_dir)
    updated = resolve_incident(
        epic_path,
        incident.incident_id,
        status="escalated",
        resolution_tier="escalation",
    )
    write_need_human_file(epic_path, updated)
    try_mark_board_execution_failed(updated, project_root=project_root)
    print_stderr_banner(updated)
    post_webhook(updated, url=url, project_root=project_root)
    return updated
