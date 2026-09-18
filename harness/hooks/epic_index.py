#!/usr/bin/env python3
"""Canonical YAML decomposition index reader and writer.

The lifecycle queue is YAML-only. Markdown indexes and migration/mirror helpers
are intentionally not part of the runtime API.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from loop.schemas.decompose_index import DecomposeIndex

SCHEMA_DECOMPOSE_INDEX = "epic-decompose-index/v1"
_STEP_STATUS_WORDS = ("pending", "active", "completed", "done", "blocked")
_STEP_ID_RE = re.compile(r"^[sera]\d{2}$")


def index_yaml_path(path: Path) -> Path:
    """Resolve a canonical v2 decomposition index path.

    Markdown index paths are rejected instead of being converted implicitly.
    """

    value = Path(path)
    if value.suffix.lower() in {".md", ".markdown"}:
        raise ValueError(f"markdown decomposition indexes are unsupported: {value}")
    if value.is_dir():
        v2 = value / "yaml" / "decompose-index.yaml"
        if v2.is_file():
            return v2
        for candidate in (value / "decompose-index.yaml", value / "index.yaml"):
            if candidate.is_file():
                return candidate
        return v2
    if value.name in {"decompose-index.yaml", "decompose-index.yml", "index.yaml", "index.yml"}:
        return value
    if value.parent.name == "steps" and value.parent.parent.name == "yaml":
        return value.parent.parent / "decompose-index.yaml"
    return value.parent / "index.yaml"


def load_index_yaml(path: Path) -> dict[str, Any] | None:
    """Load and validate one decomposition index through its Pydantic contract."""

    index_path = index_yaml_path(path)
    if not index_path.is_file():
        return None
    raw = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"decomposition index must be a mapping: {index_path}")
    DecomposeIndex.model_validate(raw)
    return raw


def dump_index_yaml(doc: dict[str, Any]) -> str:
    """Validate and serialize a decomposition index."""

    DecomposeIndex.model_validate(doc)
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)


def steps_from_doc(doc: dict[str, Any]) -> list[dict[str, str]]:
    """Return validated queue rows from an already-loaded YAML document."""

    parsed = DecomposeIndex.model_validate(doc)
    return [
        {
            "id": step.id.lower(),
            "file": step.file.strip(),
            "implement": (step.implement or "").strip(),
            "next_phase": step.next_phase.strip(),
            "status": step.status.strip().lower(),
            "title": step.title.strip() or step.id.lower(),
        }
        for step in parsed.steps
    ]


def find_next_step(steps: list[dict[str, str]]) -> dict[str, str] | None:
    for step in steps:
        if step.get("status") in {"active", "pending", "blocked"}:
            return step
    return None


def set_step_status_in_doc(doc: dict[str, Any], step_id: str, status: str) -> str | None:
    """Mutate one validated YAML document and return its previous status."""

    sid = step_id.strip().lower()
    status_l = status.strip().lower()
    if status_l not in _STEP_STATUS_WORDS:
        raise ValueError(f"unsupported step status: {status!r}")
    if not _STEP_ID_RE.match(sid):
        raise ValueError(f"unsupported step id: {step_id!r}")
    DecomposeIndex.model_validate(doc)
    for item in doc.get("steps") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("id") or "").strip().lower() != sid:
            continue
        previous = str(item.get("status") or "pending").strip().lower()
        item["status"] = status_l
        DecomposeIndex.model_validate(doc)
        return previous
    return None
