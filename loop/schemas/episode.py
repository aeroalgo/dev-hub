"""Pydantic schema for loop episode package manifest (loop-episode/v1)."""

from __future__ import annotations

import warnings
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator

warnings.filterwarnings("ignore", message=".*shadows an attribute in parent.*")

EPISODE_SCHEMA = "loop-episode/v1"


class EpisodeManifest(BaseModel):
    """Schema for EpisodeManifest persistence in runtime/episodes/."""

    model_config = {"protected_namespaces": (), "extra": "allow"}

    schema: Literal["loop-episode/v1"] = "loop-episode/v1"
    episode_id: str = Field(min_length=1)
    started_at: str = Field(min_length=1)
    ended_at: str | None = None
    epic_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    armed_step: str = Field(min_length=1)
    sNN: str | None = None
    prompt_hash: str | None = None
    fingerprint_before: str | None = None
    fingerprint_after: str | None = None
    decide: str | None = None
    halt_reason: str | None = None
    incident_ids: list[str] = Field(default_factory=list)
    event_seq_range: list[int] = Field(default_factory=list)
    load_now_paths: list[str] = Field(default_factory=list)
    load_now_sha256: list[str] = Field(default_factory=list)
    artifact_refs: dict[str, str] = Field(default_factory=dict)

    @field_validator("schema", mode="before")
    @classmethod
    def _validate_schema(cls, v: Any) -> str:
        if v != EPISODE_SCHEMA:
            raise ValueError(f"invalid schema version: {v}")
        return str(v)
