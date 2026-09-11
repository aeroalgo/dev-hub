"""Typed epic-bugfix-queue/v1 contract."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

SCHEMA_EPIC_BUGFIX_QUEUE = "epic-bugfix-queue/v1"
BUGFIX_QUEUE_ITEM_CLASSES = frozenset(
    {"suite_red", "ac_gap", "leftover", "orphan_ref", "prior_open", "behavior_smoke"}
)
BUGFIX_QUEUE_TERMINAL_STATUSES = frozenset({"done", "cancelled"})
_FULL_VERIFY_RE = re.compile(
    r"(?:^|\s)(?:timeout\s+\S+\s+)?(?:bin/pytest|\.venv/bin/pytest)\s+-q\s+--tb=line(?:\s|$)"
)


def _non_empty(value: object) -> object:
    if isinstance(value, str):
        value = value.strip()
        if not value:
            raise ValueError("field cannot be empty")
    return value


class BugfixVerification(BaseModel):
    status: Literal["pending", "running", "pass", "fail"] = "pending"
    command: str = "bin/pytest -q --tb=line"
    last_run_at: str | None = None
    evidence: str | None = None

    model_config = {"extra": "forbid"}

    _validate_command = field_validator("command", mode="before")(_non_empty)

    @model_validator(mode="after")
    def _validate_full_suite_evidence(self) -> "BugfixVerification":
        if not _FULL_VERIFY_RE.search(self.command):
            raise ValueError("verification.command must be the full repository suite")
        if self.status == "pass":
            if not str(self.evidence or "").strip():
                raise ValueError("verification pass requires evidence")
            if not str(self.last_run_at or "").strip():
                raise ValueError("verification pass requires last_run_at")
        return self


class BugfixQueueItem(BaseModel):
    id: str
    status: Literal["open", "in_progress", "done", "blocked", "cancelled"] = "open"
    class_: Literal[
        "suite_red", "ac_gap", "leftover", "orphan_ref", "prior_open", "behavior_smoke"
    ] = Field(alias="class")
    title: str
    blocker_ref: str
    fix_plan_ref: str
    targets: list[str] = Field(default_factory=list)
    verify: str
    evidence: str | None = None
    done_at: str | None = None
    notes: str = ""

    model_config = {"populate_by_name": True, "extra": "forbid"}

    _validate_strings = field_validator(
        "id", "title", "blocker_ref", "fix_plan_ref", "verify", mode="before"
    )(_non_empty)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not re.fullmatch(r"BF-\d{3,}", value):
            raise ValueError(f"invalid bugfix item id: {value!r}")
        return value

    @field_validator("targets", mode="before")
    @classmethod
    def _normalize_targets(cls, value: object) -> object:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("targets must be a list")
        return [str(item).strip() for item in value if str(item).strip()]

    @model_validator(mode="after")
    def _validate_item_contract(self) -> "BugfixQueueItem":
        if _FULL_VERIFY_RE.search(self.verify):
            raise ValueError(f"item.verify must be targeted, got full suite: {self.verify!r}")
        if self.status == "done":
            if not str(self.evidence or "").strip():
                raise ValueError(f"done item {self.id} requires evidence")
            if not str(self.done_at or "").strip():
                raise ValueError(f"done item {self.id} requires done_at")
        if self.status == "blocked" and "NEED_HUMAN" not in self.notes.upper():
            raise ValueError(f"blocked item {self.id} requires NEED_HUMAN in notes")
        if self.status == "cancelled" and not self.notes.strip():
            raise ValueError(f"cancelled item {self.id} requires a reason in notes")
        return self


class EpicBugfixQueue(BaseModel):
    schema_version: str = Field(alias="schema", default=SCHEMA_EPIC_BUGFIX_QUEUE)
    epic_id: str
    role: Literal["back", "front", "integration"]
    source_qa: str
    checklist_sha256: str
    created_at: str
    updated_at: str
    current_id: str | None = None
    verification: BugfixVerification = Field(default_factory=BugfixVerification)
    items: list[BugfixQueueItem] = Field(default_factory=list)

    model_config = {"populate_by_name": True, "extra": "forbid"}

    _validate_strings = field_validator(
        "schema_version", "epic_id", "source_qa", "checklist_sha256", "created_at", "updated_at", mode="before"
    )(_non_empty)

    @field_validator("schema_version")
    @classmethod
    def _validate_schema(cls, value: str) -> str:
        if value != SCHEMA_EPIC_BUGFIX_QUEUE:
            raise ValueError(f"unsupported bugfix queue schema: {value!r}")
        return value

    @model_validator(mode="after")
    def _validate_queue_invariants(self) -> "EpicBugfixQueue":
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("bugfix queue item ids must be unique")
        blocker_refs = [item.blocker_ref for item in self.items]
        if len(blocker_refs) != len(set(blocker_refs)):
            raise ValueError("bugfix queue blocker_ref values must be unique")
        in_progress = [item.id for item in self.items if item.status == "in_progress"]
        if len(in_progress) > 1:
            raise ValueError("bugfix queue allows at most one in_progress item")
        active = [item.id for item in self.items if item.status in {"open", "in_progress"}]
        if self.current_id != (active[0] if active else None):
            raise ValueError(
                f"current_id must point to first open/in_progress item, got {self.current_id!r}"
            )
        return self


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "BUGFIX_QUEUE_ITEM_CLASSES",
    "BUGFIX_QUEUE_TERMINAL_STATUSES",
    "BugfixQueueItem",
    "BugfixVerification",
    "EpicBugfixQueue",
    "SCHEMA_EPIC_BUGFIX_QUEUE",
]
