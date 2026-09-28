"""Typed inventory reports for non-advancing managed subagents.

Sunset inventory is the first concrete contract. New inventory agents register
in ``INVENTORY_AGENT_SCHEMAS`` and reuse the same validate → sidecar → lifecycle
path without advancing the loop cursor.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .store import LoopPaths

SCHEMA_SUNSET_INVENTORY = "loop-sunset-inventory/v1"
MANAGED_INVENTORY_AGENTS = frozenset({"sunset-inventory"})
INVENTORY_AGENT_ALIASES = {
    "sunset": "sunset-inventory",
}
INVENTORY_AGENT_SCHEMAS: dict[str, str] = {
    "sunset-inventory": SCHEMA_SUNSET_INVENTORY,
}

SunsetKind = Literal["A", "B", "C", "I"]
SunsetMark = Literal["REPLACE"]

_SAFE_RE = re.compile(r"[^a-zA-Z0-9_-]+")


class SunsetItem(BaseModel):
    kind: SunsetKind
    symbol: str
    path: str
    start_line: int
    end_line: int
    excerpt: str
    mark: SunsetMark
    role: str
    notes: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("excerpt")
    @classmethod
    def validate_excerpt_budget(cls, value: str) -> str:
        lines = value.splitlines()
        if len(lines) > 40:
            raise ValueError(f"excerpt exceeds maximum budget of 40 lines (got {len(lines)})")
        return value

    @field_validator("symbol", "path", "role", mode="before")
    @classmethod
    def require_non_empty(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("field cannot be empty")
            return stripped
        return value


class SunsetReport(BaseModel):
    schema_id: str = Field(
        default=SCHEMA_SUNSET_INVENTORY,
        validation_alias="schema",
        serialization_alias="schema",
    )
    boundary_id: str
    new_sot: str
    forbidden_for_parent: list[str] = Field(default_factory=list)
    diagnostic_codes: list[str] = Field(default_factory=list)
    ok: bool = True
    items: list[SunsetItem] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("schema_id")
    @classmethod
    def validate_schema(cls, value: str) -> str:
        if value != SCHEMA_SUNSET_INVENTORY:
            raise ValueError(f"unsupported sunset inventory schema: {value!r}")
        return value

    @field_validator("boundary_id", "new_sot", mode="before")
    @classmethod
    def require_non_empty(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("field cannot be empty")
            return stripped
        return value


INVENTORY_SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    SCHEMA_SUNSET_INVENTORY: SunsetReport,
}


def normalize_inventory_agent_id(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    return INVENTORY_AGENT_ALIASES.get(normalized, normalized)


def inventory_schema_for_agent(agent_id: str | None) -> str | None:
    normalized = normalize_inventory_agent_id(agent_id)
    return INVENTORY_AGENT_SCHEMAS.get(normalized)


def _safe_token(value: str, *, fallback: str) -> str:
    cleaned = _SAFE_RE.sub("_", (value or "").strip()).strip("_")
    return cleaned or fallback


def inventory_sidecar_path(
    paths: LoopPaths,
    *,
    agent_id: str,
    session_id: str,
    step_id: str | None = None,
) -> Path:
    agent = _safe_token(normalize_inventory_agent_id(agent_id), fallback="inventory")
    session = _safe_token(session_id, fallback="session")
    if step_id and str(step_id).strip():
        step = _safe_token(str(step_id), fallback="step")
        name = f"{agent}-{session}-{step}.json"
    else:
        name = f"{agent}-{session}.json"
    return paths.runtime / "inventory" / name


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


def write_inventory_sidecar(
    paths: LoopPaths,
    *,
    agent_id: str,
    session_id: str,
    payload: dict[str, Any] | BaseModel,
    step_id: str | None = None,
) -> BaseModel:
    schema_id = inventory_schema_for_agent(agent_id)
    if schema_id is None:
        raise ValueError(f"unsupported inventory agent: {agent_id!r}")
    model = INVENTORY_SCHEMA_MODELS[schema_id]
    if isinstance(payload, BaseModel):
        if not isinstance(payload, model):
            raise TypeError(f"payload must be {model.__name__}, got {type(payload).__name__}")
        report = payload
    else:
        report = model.model_validate(payload)
    target = inventory_sidecar_path(
        paths,
        agent_id=agent_id,
        session_id=session_id,
        step_id=step_id,
    )
    dumped = report.model_dump(by_alias=True)
    _atomic_write_json(target, dumped)
    return report


def read_inventory_sidecar(
    paths: LoopPaths,
    *,
    agent_id: str,
    session_id: str,
    step_id: str | None = None,
) -> BaseModel | None:
    schema_id = inventory_schema_for_agent(agent_id)
    if schema_id is None:
        return None
    model = INVENTORY_SCHEMA_MODELS[schema_id]
    path = inventory_sidecar_path(
        paths,
        agent_id=agent_id,
        session_id=session_id,
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
    try:
        return model.model_validate(raw)
    except Exception:
        return None


def write_sunset_sidecar(
    paths: LoopPaths,
    *,
    session_id: str,
    payload: dict[str, Any] | SunsetReport,
    step_id: str | None = None,
) -> SunsetReport:
    report = write_inventory_sidecar(
        paths,
        agent_id="sunset-inventory",
        session_id=session_id,
        payload=payload,
        step_id=step_id,
    )
    assert isinstance(report, SunsetReport)
    return report


def read_sunset_sidecar(
    paths: LoopPaths,
    *,
    session_id: str,
    step_id: str | None = None,
) -> SunsetReport | None:
    report = read_inventory_sidecar(
        paths,
        agent_id="sunset-inventory",
        session_id=session_id,
        step_id=step_id,
    )
    return report if isinstance(report, SunsetReport) else None


__all__ = [
    "INVENTORY_AGENT_ALIASES",
    "INVENTORY_AGENT_SCHEMAS",
    "INVENTORY_SCHEMA_MODELS",
    "MANAGED_INVENTORY_AGENTS",
    "SCHEMA_SUNSET_INVENTORY",
    "SunsetItem",
    "SunsetReport",
    "inventory_schema_for_agent",
    "inventory_sidecar_path",
    "normalize_inventory_agent_id",
    "read_inventory_sidecar",
    "read_sunset_sidecar",
    "write_inventory_sidecar",
    "write_sunset_sidecar",
]
