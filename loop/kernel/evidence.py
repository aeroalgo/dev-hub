"""Fail-closed validation for runtime evidence referenced by workflow artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


# Anchors (done_at / last_run_at) must equal evidence.timestamp.
# Tolerance is clock/ISO second rounding only — not a window to reuse stale runs.
RUNTIME_EVIDENCE_MAX_SKEW_SECONDS = 15

_RUNTIME_CLASSES = frozenset(
    {
        "behavior_smoke",
        "browser",
        "e2e",
        "live_smoke",
        "runtime",
        "wire_journey",
    }
)
_RUNTIME_COMMAND_MARKERS = (
    "browser",
    "curl",
    "compose_smoke",
    "docker compose",
    "live_smoke",
    "playwright",
    "run_browser_qa",
    "scripts/live_smoke.sh",
)
_RUNTIME_TEXT_MARKERS = ("browser", "http", "live", "runtime", "smoke", "wire")
_SYNTHETIC_MARKERS = (
    "mock_",
    "route.fulfill",
    "asgi",
    "in-process",
    "in process",
    "synthetic authorization",
)
_PATH_KEYS = ("evidence_file", "runtime_evidence_file", "trace_file")
_TIMESTAMP_KEYS = ("timestamp", "recorded_at", "finished_at")


def _normalized_text(value: object) -> str:
    return " ".join(str(value or "").replace("\n", " ").split()).strip().lower()


def _flatten_text(value: object) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value)
    return str(value or "")


def is_runtime_claim(value: object) -> bool:
    """Return whether an artifact claims a live/runtime/browser outcome."""

    if not isinstance(value, dict):
        text = _normalized_text(value)
        return "live" in text and any(marker in text for marker in _RUNTIME_TEXT_MARKERS)

    status = _normalized_text(value.get("status"))
    if status in {"skip", "skipped", "n/a", "not_run", "not applicable"}:
        return False
    claim_class = _normalized_text(value.get("class") or value.get("lane") or value.get("kind"))
    if claim_class in _RUNTIME_CLASSES:
        return True
    declared_evidence_file = any(
        isinstance(value.get(key), str) and value.get(key).strip()
        for key in _PATH_KEYS
    )
    if declared_evidence_file and requires_runtime_verification(
        value.get("verify") or value.get("command")
    ):
        return True
    text = _normalized_text(_flatten_text(value))
    if "mock_" in text and ("live" in text or "browser" in text or "http" in text):
        return True
    return "live" in text and any(marker in text for marker in _RUNTIME_TEXT_MARKERS)


def requires_runtime_verification(command: object) -> bool:
    """Identify verification commands whose result cannot be prose-only."""

    text = _normalized_text(command)
    return any(marker in text for marker in _RUNTIME_COMMAND_MARKERS)


def evidence_file_ref(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    for key in _PATH_KEYS:
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def _resolve_evidence_file(project: Path, raw_path: str) -> Path | None:
    candidate_text = str(raw_path or "").strip()
    if not candidate_text:
        return None
    candidate = Path(candidate_text)
    if candidate.is_absolute():
        return None
    root = project.resolve()
    resolved = (project / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return None
    return resolved


def _load_mapping(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        try:
            payload = yaml.safe_load(raw)
        except yaml.YAMLError:
            return None
    return payload if isinstance(payload, dict) else None


def _timestamp(value: object) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _first_timestamp(payload: dict[str, Any]) -> float | None:
    for key in _TIMESTAMP_KEYS:
        parsed = _timestamp(payload.get(key))
        if parsed is not None:
            return parsed
    return None


def _first_timestamp_value(payload: dict[str, Any]) -> str:
    for key in _TIMESTAMP_KEYS:
        raw = str(payload.get(key) or "").strip()
        if _timestamp(raw) is not None:
            return raw
    return ""


def _observable(value: object) -> bool:
    if isinstance(value, dict):
        return any(_observable(item) for item in value.values())
    if isinstance(value, list):
        return bool(value) and any(_observable(item) for item in value)
    return bool(str(value or "").strip())


def _commands_overlap(expected: str, actual: str) -> bool:
    left = _normalized_text(expected).strip("'\"")
    right = _normalized_text(actual).strip("'\"")
    if not left or not right:
        return False
    return left in right or right in left


def validate_runtime_evidence(
    project: Path,
    reference: object,
    *,
    expected_command: object = "",
    anchor: object = "",
) -> tuple[bool, str]:
    """Validate a typed runtime artifact.

    The validator intentionally does not infer live success from a prose field.
    A live claim needs a repository-local artifact with a successful command,
    timestamp, observable output, and no synthetic/mock markers.

    When ``anchor`` is set (queue ``done_at`` / ``last_run_at``), it must equal
    ``evidence.timestamp`` within ``RUNTIME_EVIDENCE_MAX_SKEW_SECONDS``. Agents
    copy the timestamp from the evidence file — they must not invent wall-clock
    anchors or reuse an old evidence timestamp after a new VERIFY run.
    """

    raw_path = str(reference or "").strip()
    if not raw_path:
        return False, "runtime_evidence_required"
    path = _resolve_evidence_file(project, raw_path)
    if path is None:
        return False, "runtime_evidence_path_invalid"
    if not path.is_file():
        return False, "runtime_evidence_file_missing"
    payload = _load_mapping(path)
    if payload is None:
        return False, "runtime_evidence_file_invalid"

    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).lower()
    if any(marker in serialized for marker in _SYNTHETIC_MARKERS):
        return False, "runtime_evidence_synthetic"

    if not str(payload.get("schema") or "").strip():
        return False, "runtime_evidence_schema_missing"
    status = _normalized_text(payload.get("status"))
    if status not in {"pass", "passed", "ok", "success"}:
        return False, "runtime_evidence_not_pass"
    if payload.get("live_evidence") is not True:
        return False, "runtime_evidence_not_live"
    evidence_type = _normalized_text(payload.get("evidence_type"))
    if not evidence_type or evidence_type.startswith("synthetic"):
        return False, "runtime_evidence_type_missing"
    if not any(marker in evidence_type for marker in ("runtime", "http", "browser", "trace", "e2e")):
        return False, "runtime_evidence_type_invalid"

    command = payload.get("command")
    if not isinstance(command, str) or not command.strip():
        return False, "runtime_evidence_command_missing"
    if expected_command and not _commands_overlap(str(expected_command), command):
        return False, "runtime_evidence_command_mismatch"

    timestamp = _first_timestamp(payload)
    if timestamp is None:
        return False, "runtime_evidence_timestamp_missing"
    exit_code = payload.get("exit_code")
    if not isinstance(exit_code, int) or isinstance(exit_code, bool) or exit_code != 0:
        return False, "runtime_evidence_exit_code_failed"

    observable_keys = ("raw_http", "journeys", "checks", "artifacts", "observations", "responses")
    if not any(_observable(payload.get(key)) for key in observable_keys):
        return False, "runtime_evidence_observation_missing"

    anchor_timestamp = _timestamp(anchor)
    if anchor and anchor_timestamp is None:
        return False, "runtime_evidence_anchor_invalid"
    if anchor_timestamp is not None:
        skew = abs(timestamp - anchor_timestamp)
        if skew > RUNTIME_EVIDENCE_MAX_SKEW_SECONDS:
            return False, "runtime_evidence_anchor_mismatch"

    return True, "runtime_evidence_valid"


def runtime_evidence_timestamp(
    project: Path,
    reference: object,
    *,
    expected_command: object = "",
) -> tuple[str | None, str]:
    """Return the typed timestamp from a valid runtime artifact.

    This is used when a later VERIFY run rewrites the same declared artifact:
    the caller can move queue anchors to the new evidence timestamp while
    still rejecting invalid or older captures.
    """

    raw_path = str(reference or "").strip()
    path = _resolve_evidence_file(project, raw_path)
    if path is None:
        return None, "runtime_evidence_path_invalid"
    valid, reason = validate_runtime_evidence(
        project,
        raw_path,
        expected_command=expected_command,
    )
    if not valid:
        return None, reason
    payload = _load_mapping(path)
    if payload is None:
        return None, "runtime_evidence_file_invalid"
    timestamp = _first_timestamp_value(payload)
    if not timestamp:
        return None, "runtime_evidence_timestamp_missing"
    return timestamp, "runtime_evidence_valid"


def validate_runtime_artifact_path(project: Path, reference: object) -> tuple[bool, str]:
    """Validate a non-JSON browser artifact reference exists inside the project."""

    raw_path = str(reference or "").strip()
    path = _resolve_evidence_file(project, raw_path)
    if path is None:
        return False, "runtime_evidence_path_invalid"
    if not path.is_file():
        return False, "runtime_evidence_file_missing"
    return True, "runtime_artifact_valid"


__all__ = [
    "RUNTIME_EVIDENCE_MAX_SKEW_SECONDS",
    "evidence_file_ref",
    "is_runtime_claim",
    "requires_runtime_verification",
    "runtime_evidence_timestamp",
    "validate_runtime_artifact_path",
    "validate_runtime_evidence",
]
