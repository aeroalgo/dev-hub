"""incidents.jsonl store for loop incidents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from loop.incidents.metrics import increment_counter
from loop.incidents.schema import IncidentRecord


class CorruptIncidentError(ValueError):
    """Raised when parsing incidents.jsonl encounters a corrupt line (fail-closed)."""

    def __init__(self, line_number: int, line_content: str, detail: str) -> None:
        super().__init__(
            f"Corrupt JSONL line {line_number} in incidents log: {detail}. Line content: {line_content!r}"
        )
        self.line_number = line_number
        self.line_content = line_content
        self.detail = detail


def parse_incidents_jsonl(path: Path | str) -> list[IncidentRecord]:
    """Parse incidents.jsonl file fail-closed on corrupt line."""
    p = Path(path)
    if not p.exists():
        return []

    records: list[IncidentRecord] = []
    lines = p.read_text(encoding="utf-8").splitlines()
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise CorruptIncidentError(idx, line, f"invalid JSON: {exc}") from exc

        try:
            record = IncidentRecord.model_validate(data)
        except ValidationError as exc:
            raise CorruptIncidentError(idx, line, f"validation error: {exc}") from exc

        records.append(record)

    return records


def _write_incidents_jsonl(path: Path, records: list[IncidentRecord]) -> None:
    """Atomic write of all IncidentRecords back to incidents.jsonl."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(r.model_dump(by_alias=True, exclude_none=True), ensure_ascii=False)
        for r in records
    ]
    content = "\n".join(lines) + ("\n" if lines else "")
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def append_incident(epic_dir: Path | str, incident: IncidentRecord) -> IncidentRecord:
    """Append new incident or update existing open incident if matching (idempotency FR-013)."""
    epic_path = Path(epic_dir)
    incidents_path = epic_path / "incidents.jsonl"

    records = parse_incidents_jsonl(incidents_path)

    # Check for existing open incident with same fingerprint + session_id + sorted diagnostic_codes
    target_diag = sorted(incident.diagnostic_codes)
    existing_index: int | None = None

    for idx, r in enumerate(records):
        if (
            r.status == "open"
            and r.fingerprint == incident.fingerprint
            and r.session_id == incident.session_id
            and sorted(r.diagnostic_codes) == target_diag
        ):
            existing_index = idx
            break

    if existing_index is not None:
        # Idempotency bump
        existing = records[existing_index]
        updated_attempts = existing.tier0_attempts + max(1, incident.tier0_attempts)
        combined_repair_log = list(existing.tier0_repair_log) + incident.tier0_repair_log
        combined_metadata = {**existing.metadata, **incident.metadata}

        updated_dict = existing.model_dump(by_alias=True)
        updated_dict["tier0_attempts"] = updated_attempts
        updated_dict["tier0_repair_log"] = combined_repair_log
        updated_dict["metadata"] = combined_metadata

        updated_record = IncidentRecord.model_validate(updated_dict)
        records[existing_index] = updated_record
        _write_incidents_jsonl(incidents_path, records)
        return updated_record
    else:
        records.append(incident)
        _write_incidents_jsonl(incidents_path, records)
        increment_counter(epic_dir, "incidents_opened")
        return incident


def resolve_incident(
    epic_dir: Path | str,
    incident_id: str,
    resolution: dict[str, Any] | None = None,
    **kwargs: Any,
) -> IncidentRecord | None:
    """Resolve an open incident by ID."""
    epic_path = Path(epic_dir)
    incidents_path = epic_path / "incidents.jsonl"

    records = parse_incidents_jsonl(incidents_path)
    res_data = dict(resolution or {})
    res_data.update(kwargs)

    target_index: int | None = None
    for idx, r in enumerate(records):
        if r.incident_id == incident_id and r.status == "open":
            target_index = idx
            break

    if target_index is None:
        # Check if incident exists at all even if not open
        for idx, r in enumerate(records):
            if r.incident_id == incident_id:
                target_index = idx
                break

    if target_index is None:
        return None

    existing = records[target_index]
    data = existing.model_dump(by_alias=True)
    data["status"] = res_data.get("status", "resolved")
    if "resolved_at" in res_data:
        data["resolved_at"] = res_data["resolved_at"]
    if "resolution_tier" in res_data:
        data["resolution_tier"] = res_data["resolution_tier"]
    if "resolution_action" in res_data:
        data["resolution_action"] = res_data["resolution_action"]
    if "runbook_rel" in res_data:
        data["runbook_rel"] = res_data["runbook_rel"]

    updated = IncidentRecord.model_validate(data)
    records[target_index] = updated
    _write_incidents_jsonl(incidents_path, records)
    return updated


def list_open_incidents(epic_dir: Path | str) -> list[IncidentRecord]:
    """List all open incidents in the given epic directory."""
    epic_path = Path(epic_dir)
    incidents_path = epic_path / "incidents.jsonl"
    records = parse_incidents_jsonl(incidents_path)
    return [r for r in records if r.status == "open"]


def reset_tier1_attempts(epic_dir: Path | str, incident_id: str) -> IncidentRecord | None:
    """Reset tier1_attempts to 0, status to open, and set last_updated for an incident."""
    from datetime import datetime, timezone

    epic_path = Path(epic_dir)
    incidents_path = epic_path / "incidents.jsonl"
    records = parse_incidents_jsonl(incidents_path)

    target_index: int | None = None
    for idx, r in enumerate(records):
        if r.incident_id == incident_id:
            target_index = idx
            break

    if target_index is None:
        return None

    existing = records[target_index]
    data = existing.model_dump(by_alias=True)
    if "metadata" not in data or not isinstance(data["metadata"], dict):
        data["metadata"] = {}
    data["metadata"]["tier1_attempts"] = 0
    data["metadata"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    data["status"] = "open"

    updated = IncidentRecord.model_validate(data)
    records[target_index] = updated
    _write_incidents_jsonl(incidents_path, records)
    return updated

