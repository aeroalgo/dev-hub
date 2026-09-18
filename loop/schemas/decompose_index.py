from pydantic import BaseModel, Field, field_validator

from typing import List


class DecomposeStep(BaseModel):
    id: str
    file: str
    title: str = ""
    next_phase: str = ""
    status: str = "pending"
    implement: str | None = None
    depends_on: List[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}

    @field_validator("id", "file", "title", "next_phase", "status", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> str:
        return str(value or "").strip()

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not value or not value[:1].lower() in {"s", "e", "r", "a"}:
            raise ValueError("step id must start with s/e/r/a")
        return value


class DecomposeIndex(BaseModel):
    schema: str = Field(alias="schema")
    plan_id: str
    steps: List[DecomposeStep]

    model_config = {"populate_by_name": True, "extra": "allow"}

    @field_validator("schema")
    @classmethod
    def _validate_schema(cls, value: str) -> str:
        if value != "epic-decompose-index/v1":
            raise ValueError(f"unsupported decompose index schema: {value!r}")
        return value
