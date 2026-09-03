"""Canonical loop event v2 records and the v1 history adapter."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

EVENT_SCHEMA = "loop-event/v2"
EVENT_KINDS = frozenset({
    "audit_done",
    "qa_pass",
    "qa_fail",
    "bugfix_done",
    "incident_opened",
    "incident_resolved",
    "repair_applied",
    "tier1_spawn",
    "tier1_verify_pass",
    "tier1_verify_fail",
    "tier1_escalated",
    "implement_done",
    "decompose_step_done",
    "phase_transition",
    "traceability_warn",
    "traceability_fail",
})
# Historical event.log rows — parse for seq continuity; reducer ignores these kinds.
LEGACY_DEAD_EVENT_KINDS = frozenset({"reflection_done"})
_VALIDATABLE_EVENT_KINDS = EVENT_KINDS | LEGACY_DEAD_EVENT_KINDS
MAX_METADATA_KEYS = 32
MAX_METADATA_BYTES = 2048
MAX_METADATA_KEY_LENGTH = 64
MAX_METADATA_VALUE_LENGTH = 256
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_EVENT_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_FORBIDDEN_METADATA = re.compile(
    r"(?:secret|token|password|passwd|credential|api[_-]?key|private[_-]?key|prompt)",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(
    r"(?:-----BEGIN [^-]+-----|(?:sk|pk|ghp|github_pat|xox[baprs])[-_][A-Za-z0-9_-]{12,}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EventDiagnostic:
    code: str
    field: str
    message: str


@dataclass(frozen=True)
class EventValidation:
    event: dict[str, Any] | None
    diagnostics: tuple[EventDiagnostic, ...] = ()

    @property
    def valid(self) -> bool:
        return self.event is not None and not self.diagnostics

    @property
    def ok(self) -> bool:
        return self.valid


@dataclass(frozen=True)
class EventLogResult:
    events: tuple[dict[str, Any], ...]
    diagnostics: tuple[EventDiagnostic, ...] = ()
    invalid_count: int = 0
    archive_count: int = 0
    collision_count: int = 0
    gap_count: int = 0

    @property
    def valid(self) -> bool:
        return not self.diagnostics

    @property
    def ok(self) -> bool:
        return self.invalid_count == 0


def _diagnostic(code: str, field: str, message: str) -> EventDiagnostic:
    return EventDiagnostic(code=code, field=field, message=message)


def _metadata_diagnostics(metadata: Any) -> list[EventDiagnostic]:
    errors: list[EventDiagnostic] = []
    if not isinstance(metadata, dict):
        return [_diagnostic("metadata_type", "metadata", "metadata must be an object")]
    if len(metadata) > MAX_METADATA_KEYS:
        errors.append(_diagnostic("metadata_too_many_keys", "metadata", "metadata has too many keys"))
    encoded = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(encoded.encode("utf-8")) > MAX_METADATA_BYTES:
        errors.append(_diagnostic("metadata_too_large", "metadata", "metadata exceeds the byte limit"))
    for key, value in metadata.items():
        if not isinstance(key, str) or not key or len(key) > MAX_METADATA_KEY_LENGTH:
            errors.append(_diagnostic("metadata_key", "metadata", "metadata keys must be bounded strings"))
            continue
        if _FORBIDDEN_METADATA.search(key):
            errors.append(_diagnostic("metadata_secret", f"metadata.{key}", "secret-like metadata is forbidden"))
        if isinstance(value, str):
            if len(value) > MAX_METADATA_VALUE_LENGTH:
                errors.append(_diagnostic("metadata_value", f"metadata.{key}", "metadata string is too long"))
            if _SECRET_VALUE.search(value):
                errors.append(_diagnostic("metadata_secret", f"metadata.{key}", "secret-like metadata is forbidden"))
        elif not isinstance(value, (bool, int, float)) and value is not None:
            errors.append(_diagnostic("metadata_value_type", f"metadata.{key}", "metadata values must be scalar"))
    return errors


def normalize_artifact_path(artifact: Any) -> tuple[str | None, list[EventDiagnostic]]:
    if not isinstance(artifact, str) or not artifact.strip():
        return None, [_diagnostic("artifact_type", "artifact", "artifact must be a non-empty string")]
    raw = artifact.strip().replace("\\", "/")
    path = Path(raw)
    if path.is_absolute() or raw.startswith("/"):
        return None, [_diagnostic("artifact_absolute", "artifact", "artifact must be repo-relative")]
    parts = [part for part in raw.split("/") if part not in {""}]
    if not parts or any(part in {".", ".."} for part in parts):
        return None, [_diagnostic("artifact_path", "artifact", "artifact path contains unsafe segments")]
    normalized = "/".join(parts)
    if normalized.startswith("memory-bank/") or normalized.startswith(".claude/"):
        return normalized, []
    return normalized, []


def validate_event(
    record: Any,
    *,
    expected_epic_id: str | None = None,
) -> EventValidation:
    if not isinstance(record, dict):
        return EventValidation(None, (_diagnostic("event_type", "event", "event must be an object"),))
    errors: list[EventDiagnostic] = []
    required = (
        "schema", "event_id", "seq", "kind", "artifact", "artifact_sha256",
        "epic_id", "epoch", "t", "metadata",
    )
    for field in required:
        if field not in record:
            errors.append(_diagnostic("missing_field", field, f"required field {field!r} is missing"))
    if record.get("schema") != EVENT_SCHEMA:
        errors.append(_diagnostic("schema", "schema", f"schema must be {EVENT_SCHEMA!r}"))
    event_id = record.get("event_id")
    if not isinstance(event_id, str) or not _EVENT_ID_RE.fullmatch(event_id):
        errors.append(_diagnostic("event_id", "event_id", "event_id has an invalid type or format"))
    seq = record.get("seq")
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 1:
        errors.append(_diagnostic("seq", "seq", "seq must be a positive integer"))
    kind = record.get("kind")
    if kind not in _VALIDATABLE_EVENT_KINDS:
        errors.append(_diagnostic("kind", "kind", f"kind must be one of {sorted(EVENT_KINDS)}"))
    artifact, artifact_errors = normalize_artifact_path(record.get("artifact"))
    errors.extend(artifact_errors)
    digest = record.get("artifact_sha256")
    if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
        errors.append(_diagnostic("artifact_hash", "artifact_sha256", "artifact_sha256 must be a lowercase SHA-256"))
    epic_id = record.get("epic_id")
    if not isinstance(epic_id, str) or not epic_id.strip():
        errors.append(_diagnostic("epic_id", "epic_id", "epic_id must be a non-empty string"))
    elif expected_epic_id is not None and epic_id != expected_epic_id:
        errors.append(_diagnostic("epic_ownership", "epic_id", "event belongs to another epic"))
    epoch = record.get("epoch")
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
        errors.append(_diagnostic("epoch", "epoch", "epoch must be a non-negative integer"))
    timestamp = record.get("t")
    if not isinstance(timestamp, str) or not timestamp.strip():
        errors.append(_diagnostic("timestamp", "t", "t must be a non-empty timestamp string"))
    errors.extend(_metadata_diagnostics(record.get("metadata")))
    if errors:
        return EventValidation(None, tuple(errors))
    canonical = dict(record)
    canonical["artifact"] = artifact
    return EventValidation(canonical, ())


def _stable_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _artifact_digest(cwd: Path | None, artifact: str, legacy: Any) -> str:
    if cwd is not None:
        path = cwd / artifact
        try:
            if path.is_file():
                return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            pass
    return _stable_digest(legacy)


def _safe_legacy_metadata(record: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in record.items():
        if key in {"schema", "event_id", "seq", "kind", "artifact", "artifact_sha256", "epic_id", "epoch", "t", "metadata"}:
            continue
        if not isinstance(key, str) or _FORBIDDEN_METADATA.search(key):
            continue
        if isinstance(value, (str, bool, int, float)) and (not isinstance(value, str) or len(value) <= MAX_METADATA_VALUE_LENGTH):
            result[key] = value
        if len(result) >= MAX_METADATA_KEYS:
            break
    return result


def adapt_v1_event(
    record: Any,
    *,
    seq: int,
    epic_id: str,
    cwd: str | Path | None = None,
) -> EventValidation:
    if not isinstance(record, dict):
        return EventValidation(None, (_diagnostic("event_type", "event", "legacy event must be an object"),))
    kind = record.get("kind")
    if kind not in _VALIDATABLE_EVENT_KINDS:
        return EventValidation(None, (_diagnostic("kind", "kind", "legacy event has an unsupported kind"),))
    artifact, path_errors = normalize_artifact_path(record.get("artifact"))
    if path_errors or artifact is None:
        return EventValidation(None, tuple(path_errors))
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 1:
        return EventValidation(None, (_diagnostic("seq", "seq", "migration seq must be positive"),))
    root = Path(cwd) if cwd is not None else None
    metadata = _safe_legacy_metadata(record)
    digest = _artifact_digest(root, artifact, record)
    event_id = _stable_digest({"legacy": record, "seq": seq, "epic_id": epic_id})[:32]
    event = {
        "schema": EVENT_SCHEMA,
        "event_id": event_id,
        "seq": seq,
        "kind": kind,
        "artifact": artifact,
        "artifact_sha256": digest,
        "epic_id": epic_id,
        "epoch": 0,
        "t": record.get("t") if isinstance(record.get("t"), str) and record.get("t") else "1970-01-01T00:00:00+00:00",
        "metadata": metadata,
    }
    return validate_event(event, expected_epic_id=epic_id)


def read_event_log_result(
    path: str | Path,
    *,
    expected_epic_id: str | None = None,
    cwd: str | Path | None = None,
    include_archives: bool = True,
) -> EventLogResult:
    event_path = Path(path)
    if not event_path.exists() and not (
        include_archives and event_path.parent.is_dir()
    ):
        return EventLogResult(())
    if include_archives:
        files = sorted(
            [*event_path.parent.glob("archive-*.jsonl"), event_path],
            key=lambda item: item.name,
        )
        files = [f for f in files if f.is_file()]
    elif event_path.is_file():
        files = [event_path]
    else:
        return EventLogResult(())
    epic = expected_epic_id or event_path.parent.name
    root = Path(cwd) if cwd is not None else None
    events: list[dict[str, Any]] = []
    diagnostics: list[EventDiagnostic] = []
    invalid_count = archive_count = 0
    for source in files:
        if source.name.startswith("archive-"):
            archive_count += 1
        try:
            lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            diagnostics.append(_diagnostic("read_error", source.name, str(exc)))
            invalid_count += 1
            continue
        for index, line in enumerate(lines, start=1):
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                diagnostics.append(_diagnostic("invalid_json", f"{source.name}[line[{index}]]", str(exc)))
                invalid_count += 1
                continue
            if isinstance(raw, dict) and raw.get("schema") == EVENT_SCHEMA:
                result = validate_event(raw, expected_epic_id=expected_epic_id)
            else:
                result = adapt_v1_event(raw, seq=index, epic_id=epic, cwd=root)
            if result.valid and result.event is not None:
                events.append(result.event)
            else:
                diagnostics.extend(result.diagnostics)
                invalid_count += 1

    by_seq: dict[int, dict[str, Any]] = {}
    collision_count = 0
    for event in events:
        seq = event["seq"]
        previous = by_seq.get(seq)
        if previous is not None:
            if event_revision_key(event) == event_revision_key(previous):
                continue
            collision_count += 1
            diagnostics.append(_diagnostic("sequence_collision", f"seq[{seq}]", "multiple events use the same sequence"))
            continue
        by_seq[seq] = event
    ordered = [by_seq[seq] for seq in sorted(by_seq)]
    gap_count = 0
    # Live-only window after rollover starts mid-sequence; gaps are expected.
    if include_archives and ordered:
        expected = list(range(1, ordered[-1]["seq"] + 1))
        missing = sorted(set(expected) - set(by_seq))
        gap_count = len(missing)
        if missing:
            diagnostics.append(_diagnostic("sequence_gap", "seq", f"missing sequences: {missing}"))
    return EventLogResult(
        tuple(ordered), tuple(diagnostics), invalid_count,
        archive_count, collision_count, gap_count,
    )


def migrate_event_log(
    path: str | Path,
    *,
    epic_id: str,
    cwd: str | Path | None = None,
) -> dict[str, Any]:
    """Migrate legacy event files in deterministic physical order, once."""
    event_path = Path(path)
    root = Path(cwd) if cwd is not None else event_path.parent
    files = sorted(
        [*event_path.parent.glob("archive-*.jsonl"), event_path],
        key=lambda item: item.name,
    )
    if not event_path.exists():
        report: dict[str, Any] = {
            "ok": True,
            "migrated": 0,
            "events": [],
            "replay_digest": event_stream_digest(EventLogResult(())),
            "diagnostics": [],
        }
        _write_migration_report(root, report)
        return report

    migrated_files: dict[Path, list[dict[str, Any]]] = {}
    events: list[dict[str, Any]] = []
    diagnostics: list[EventDiagnostic] = []
    migrated = 0
    seq = 0
    for source in files:
        records: list[dict[str, Any]] = []
        try:
            lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            diagnostics.append(_diagnostic("read_error", source.name, str(exc)))
            continue
        for line_no, line in enumerate(lines, start=1):
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                diagnostics.append(_diagnostic("invalid_json", f"{source.name}[{line_no}]", str(exc)))
                continue
            seq += 1
            if isinstance(raw, dict) and raw.get("schema") == EVENT_SCHEMA:
                result = validate_event(raw, expected_epic_id=epic_id)
            else:
                result = adapt_v1_event(raw, seq=seq, epic_id=epic_id, cwd=root)
                if result.valid and result.event is not None:
                    metadata = dict(result.event.get("metadata") or {})
                    metadata["migrated_from"] = "loop-event/v1"
                    candidate = dict(result.event)
                    candidate["metadata"] = metadata
                    result = validate_event(candidate, expected_epic_id=epic_id)
                    migrated += int(result.valid)
            if result.valid and result.event is not None and isinstance(raw, dict):
                metadata = result.event.get("metadata") or {}
                if isinstance(metadata, dict) and metadata.get("migrated_from") == "loop-event/v1":
                    migrated += 0
            if not result.valid or result.event is None:
                diagnostics.extend(result.diagnostics)
                continue
            records.append(result.event)
            events.append(result.event)
        migrated_files[source] = records

    replay_digest = event_stream_digest(EventLogResult(tuple(sorted(events, key=lambda item: item["seq"]))))
    report = {
        "ok": not diagnostics,
        "migrated": migrated,
        "events": events,
        "replay_digest": replay_digest,
        "diagnostics": [item.__dict__ for item in diagnostics],
    }
    if not diagnostics:
        for source, records in migrated_files.items():
            _atomic_write_jsonl(source, records)
    _write_migration_report(root, report)
    return report


def _atomic_write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_migration_report(root: Path, report: dict[str, Any]) -> None:
    marker = root / ".claude" / "runtime" / "epic" / "migration-v1.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def event_stream_digest(result: EventLogResult) -> str:
    payload = "".join(json.dumps(event, sort_keys=True, separators=(",", ":")) for event in result.events)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def revision_key(event: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(event.get("epic_id", "")),
        str(event.get("kind", "")),
        str(event.get("artifact", "")),
        str(event.get("artifact_sha256", "")),
    )


def event_revision_key(event: dict[str, Any]) -> tuple[str, str, str, str]:
    return revision_key(event)


def build_event(
    *,
    epic_id: str,
    kind: str,
    artifact: str,
    artifact_sha256: str,
    seq: int,
    epoch: int = 0,
    timestamp: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if kind not in EVENT_KINDS:
        raise ValueError(f"kind must be one of {sorted(EVENT_KINDS)}")
    artifact_path, errors = normalize_artifact_path(artifact)
    if errors or artifact_path is None:
        raise ValueError(errors[0].message if errors else "invalid artifact")
    event_without_id = {
        "schema": EVENT_SCHEMA,
        "seq": seq,
        "kind": kind,
        "artifact": artifact_path,
        "artifact_sha256": artifact_sha256,
        "epic_id": epic_id,
        "epoch": epoch,
        "t": timestamp,
        "metadata": metadata or {},
    }
    event_without_id["event_id"] = _stable_digest(event_without_id)[:32]
    result = validate_event(event_without_id, expected_epic_id=epic_id)
    if not result.valid or result.event is None:
        message = "; ".join(error.message for error in result.diagnostics)
        raise ValueError(message)
    return result.event


def iter_events(records: Iterable[Any], *, epic_id: str) -> EventLogResult:
    events: list[dict[str, Any]] = []
    diagnostics: list[EventDiagnostic] = []
    for seq, record in enumerate(records, start=1):
        result = (
            validate_event(record, expected_epic_id=epic_id)
            if isinstance(record, dict) and record.get("schema") == EVENT_SCHEMA
            else adapt_v1_event(record, seq=seq, epic_id=epic_id)
        )
        if result.valid and result.event is not None:
            events.append(result.event)
        else:
            diagnostics.extend(result.diagnostics)
    return EventLogResult(tuple(events), tuple(diagnostics), len(diagnostics))
