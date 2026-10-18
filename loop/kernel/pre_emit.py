from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .model import utc_now
from .store import LoopPaths
from .verdict import MANAGED_GATE_AGENTS, SCHEMA_GATE_VERDICT, normalize_agent_id


_SAFE_RE = re.compile(r"[^a-zA-Z0-9._-]+")

# Wall-clock only: agents often regenerate recorded_at between validate-verdict and the
# final fence. Binding ignores it; every other gate field must match the stamp.
_BINDING_EXCLUDED_KEYS = frozenset({"recorded_at"})


def binding_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key not in _BINDING_EXCLUDED_KEYS}


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_payload_sha256(payload: dict[str, Any]) -> str:
    encoded = canonical_json(binding_payload(payload))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def emit_exactly_payload(stamped: dict[str, Any], *, recorded_at: str | None = None) -> dict[str, Any]:
    exact = dict(stamped)
    if recorded_at:
        exact["recorded_at"] = recorded_at
    return exact


def _safe_token(value: str) -> str:
    cleaned = _SAFE_RE.sub("_", str(value or "").strip())
    return cleaned[:120] or "unknown"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def pre_emit_stamp_path(
    paths: LoopPaths,
    *,
    session_id: str,
    agent_id: str,
    step_id: str,
) -> Path:
    name = (
        f"{_safe_token(session_id)}__{_safe_token(normalize_agent_id(agent_id))}__"
        f"{_safe_token(step_id)}.json"
    )
    return paths.runtime / "pre-emit" / name


@dataclass(frozen=True)
class PreEmitStamp:
    schema: str
    session_id: str
    agent_id: str
    step_id: str
    epic_id: str
    payload_sha256: str
    recorded_at: str
    payload: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema": "loop-pre-emit-stamp/v1",
            "gate_schema": self.schema,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "step_id": self.step_id,
            "epic_id": self.epic_id,
            "payload_sha256": self.payload_sha256,
            "binding_sha256": self.payload_sha256,
            "recorded_at": self.recorded_at,
        }
        if self.payload is not None:
            body["payload"] = self.payload
            body["emit_exactly"] = self.payload
        return body


def write_pre_emit_stamp(paths: LoopPaths, payload: dict[str, Any]) -> PreEmitStamp | None:
    schema = str(payload.get("schema") or "")
    agent_id = normalize_agent_id(str(payload.get("agent_id") or ""))
    if schema != SCHEMA_GATE_VERDICT or agent_id not in MANAGED_GATE_AGENTS:
        return None
    session_id = str(payload.get("session_id") or "").strip()
    step_id = str(payload.get("step_id") or "").strip()
    epic_id = str(payload.get("epic_id") or "").strip()
    if not session_id or not step_id or not epic_id:
        return None
    stored = json.loads(canonical_json(payload))
    stamp = PreEmitStamp(
        schema=schema,
        session_id=session_id,
        agent_id=agent_id,
        step_id=step_id,
        epic_id=epic_id,
        payload_sha256=canonical_payload_sha256(stored),
        recorded_at=utc_now(),
        payload=stored,
    )
    target = pre_emit_stamp_path(
        paths,
        session_id=session_id,
        agent_id=agent_id,
        step_id=step_id,
    )
    _atomic_write_json(target, stamp.as_dict())
    return stamp


def read_pre_emit_stamp(
    paths: LoopPaths,
    *,
    session_id: str,
    agent_id: str,
    step_id: str,
) -> PreEmitStamp | None:
    path = pre_emit_stamp_path(
        paths,
        session_id=session_id,
        agent_id=agent_id,
        step_id=step_id,
    )
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    stored = raw.get("payload")
    payload = stored if isinstance(stored, dict) else None
    digest = str(raw.get("binding_sha256") or raw.get("payload_sha256") or "")
    try:
        return PreEmitStamp(
            schema=str(raw.get("gate_schema") or ""),
            session_id=str(raw.get("session_id") or ""),
            agent_id=normalize_agent_id(str(raw.get("agent_id") or "")),
            step_id=str(raw.get("step_id") or ""),
            epic_id=str(raw.get("epic_id") or ""),
            payload_sha256=digest,
            recorded_at=str(raw.get("recorded_at") or ""),
            payload=payload,
        )
    except Exception:
        return None


def verify_pre_emit_stamp(
    paths: LoopPaths,
    payload: dict[str, Any],
) -> tuple[bool, tuple[str, ...], tuple[str, ...]]:
    agent_id = normalize_agent_id(str(payload.get("agent_id") or ""))
    session_id = str(payload.get("session_id") or "").strip()
    step_id = str(payload.get("step_id") or "").strip()
    stamp = read_pre_emit_stamp(
        paths,
        session_id=session_id,
        agent_id=agent_id,
        step_id=step_id,
    )
    if stamp is None:
        return (
            False,
            (
                "pre-emit stamp missing: run "
                "`python3 $DEV_HUB/bin/loop.py validate-verdict --project \"$PROJECT_ROOT\" "
                "--payload '<exact-final-json>'` and emit only after valid:true",
            ),
            ("pre_emit_validate_missing",),
        )
    digest = canonical_payload_sha256(payload)
    if stamp.payload_sha256 != digest:
        errors: list[str] = [
            "pre-emit stamp mismatch: semantic gate fields differ from validate-verdict "
            f"(stamp={stamp.payload_sha256} fence={digest}). "
            "recorded_at may differ; schema/agent_id/verdict/step_id/session_id/epic_id/"
            "evidence_sha256 must match. Re-run validate-verdict after any semantic change.",
        ]
        if stamp.payload is not None:
            suggested = emit_exactly_payload(
                stamp.payload,
                recorded_at=str(payload.get("recorded_at") or stamp.payload.get("recorded_at") or ""),
            )
            errors.insert(0, f"EMIT_EXACTLY={canonical_json(suggested)}")
        return (
            False,
            tuple(errors),
            ("pre_emit_validate_mismatch",),
        )
    if stamp.agent_id != agent_id or stamp.session_id != session_id or stamp.step_id != step_id:
        return (
            False,
            ("pre-emit stamp identity mismatch",),
            ("pre_emit_validate_mismatch",),
        )
    return True, (), ()


GATE_VERDICT_ALLOWED_KEYS = (
    "schema",
    "agent_id",
    "verdict",
    "step_id",
    "session_id",
    "epic_id",
    "recorded_at",
    "evidence_sha256",
)

GATE_VERDICT_FORBIDDEN_HINTS = (
    "evidence",
    "blockers",
    "touched_paths",
    "evidence_id",
    "reason",
    "findings",
    "gate",
    "status",
    "checkpoints",
)


def schema_reject_reason(
    *,
    schema_id: str,
    retry_number: int,
    max_retries: int,
    diagnostic_codes: list[str] | tuple[str, ...],
    errors: list[str] | tuple[str, ...],
    payload: dict[str, Any] | None = None,
) -> str:
    extras: list[str] = []
    if isinstance(payload, dict):
        extras = sorted(key for key in payload if key not in GATE_VERDICT_ALLOWED_KEYS)
    lines = [
        f"re-emit valid {schema_id} JSON fence (retry {retry_number}/{max_retries})",
        f"allowed_keys={','.join(GATE_VERDICT_ALLOWED_KEYS)}",
    ]
    if extras:
        lines.append(f"forbidden_keys_present={','.join(extras)}")
    else:
        lines.append(f"never_emit_keys={','.join(GATE_VERDICT_FORBIDDEN_HINTS)}")
    if diagnostic_codes:
        lines.append("diagnostic_codes=" + ",".join(str(code) for code in diagnostic_codes))
    if errors:
        rendered: list[str] = []
        for error in errors[:3]:
            text = str(error)
            if text.startswith("EMIT_EXACTLY="):
                rendered.append(text)
            else:
                rendered.append(text[:240])
        lines.append("errors=" + " | ".join(rendered))
    lines.append(
        "REQUIRED: Bash validate-verdict until valid:true (writes pre-emit stamp + emit_exactly); "
        "final fence must match emit_exactly on all fields except recorded_at; zero extra keys. "
        "Handoff reject means NOT accepted — do not claim PASS."
    )
    return "; ".join(lines)


__all__ = [
    "GATE_VERDICT_ALLOWED_KEYS",
    "GATE_VERDICT_FORBIDDEN_HINTS",
    "PreEmitStamp",
    "binding_payload",
    "canonical_json",
    "canonical_payload_sha256",
    "emit_exactly_payload",
    "pre_emit_stamp_path",
    "read_pre_emit_stamp",
    "schema_reject_reason",
    "verify_pre_emit_stamp",
    "write_pre_emit_stamp",
]
