"""Pydantic schema for board card metadata (mb-board-card/v1)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BoardCardMetadata(BaseModel):
    """Pydantic model for card metadata footer (mb-board-card/v1)."""

    model_config = ConfigDict(extra="ignore")

    schema_version: Literal["mb-board-card/v1"] = Field(
        default="mb-board-card/v1", alias="schema"
    )
    card_kind: Literal["step", "gate", "epic"]
    project_root: str
    workspace_id: str
    role: str
    sync_generation: int

    # Step card fields
    epic_id: str | None = None
    step_id: str | None = None
    decompose_rel: str | None = None
    phase: str | None = None
    hub_dev: str | None = None

    # Gate card fields
    gate_phase: str | None = None
    reason_code: str | None = None

    # Epic card fields
    next_command: str | None = None
    next_step_id: str | None = None
    progress_summary: str | None = None
    roadmap_rank: int | None = None
