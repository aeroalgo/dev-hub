"""pydantic models for loop/mb_load."""

from typing import Literal
from pydantic import BaseModel, Field

from loop.mb_finish.schemas import LoadNowItem, LoopHandoffMeta

SCHEMA_LOOP_MB_LOAD = "mb-load-result/v1"



class MbLoadFile(BaseModel):
    path: str
    content: str
    size_bytes: int
    sha256: str
    truncated: bool = False


class MbLoadRequest(BaseModel):
    schema: Literal["mb-load-request/v1"] = "mb-load-request/v1"
    cwd: str = "."
    plan_section: str | None = None
    max_file_bytes: int = 256 * 1024


class MbLoadResult(BaseModel):
    schema: Literal["mb-load-result/v1"] = "mb-load-result/v1"
    ok: bool
    mb_root: str | None = None
    workflow_pack: str | None = None
    diagnostic_codes: list[str] = Field(default_factory=list)
    shape_errors: list[str] = Field(default_factory=list)
    meta: LoopHandoffMeta | None = None
    load_now: list[LoadNowItem] = Field(default_factory=list)
    files: list[MbLoadFile] = Field(default_factory=list)
    forbidden_skipped: list[str] = Field(default_factory=list)
    fingerprint: str | None = None
