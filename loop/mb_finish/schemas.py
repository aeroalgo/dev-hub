"""pydantic models for loop/mb_finish."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from loop.schemas.handoff import LoopHandoffFrontmatter, LoopHandoffRole, SCHEMA_LOOP_HANDOFF


class LoadNowItem(BaseModel):
    path: str
    description: str

    def render(self, index: int) -> str:
        return f"{index}. [{self.path}]({self.path}) — {self.description}."


class LoopHandoffMeta(LoopHandoffFrontmatter):
    pass


class HandoffBody(BaseModel):
    mode: str
    next_hint: str | None = None
    epic_id: str | None = None
    step_id: str | None = None
    custom_lines: list[str] = Field(default_factory=list)

    @field_validator("mode", mode="before")
    @classmethod
    def _mode_upper(cls, value: str) -> str:
        if isinstance(value, str):
            return value.upper()
        return value


class MbFinishRequest(BaseModel):
    phase: str
    step_id: str
    done_summary: str
    cwd: str = "."


class MbFinishResult(BaseModel):
    ok: bool
    mb_root: str | None = None
    workflow_pack: str | None = None
    diagnostic_codes: list[str] = Field(default_factory=list)
    shape_errors: list[str] = Field(default_factory=list)
    active_context: str | None = None
    finished_step: str | None = None
    next_step: str | None = None
    next_phase: str | None = None
    epic_done: bool | None = None

