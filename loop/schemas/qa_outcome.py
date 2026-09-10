"""loop-qa-outcome/v1 — deterministic QA classifier contract."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

SCHEMA_LOOP_QA_OUTCOME = "loop-qa-outcome/v1"

QaOutcomeKind = Literal[
    "suite_red",
    "plan_mismatch",
    "ac_gap",
    "transport_broken",
    "all_green",
]

QaNextAction = Literal[
    "bugfix",
    "verify_qa",
    "retry_spawn",
    "need_human",
    "done",
]

QaSuiteScope = Literal["full", "targeted"]


class QaOutcome(BaseModel):
    """Machine SoT for one QA decision (runner/agent must not invent dual paths)."""

    schema_version: str = Field(alias="schema", default=SCHEMA_LOOP_QA_OUTCOME)
    kind: QaOutcomeKind
    next_action: QaNextAction
    suite_scope: QaSuiteScope = "full"
    suite_command: str = "bin/pytest -q --tb=line"
    reasons: list[str] = Field(default_factory=list)
    changed_paths: list[str] = Field(default_factory=list)
    epic_id: str = ""
    transport_retries: int = 0

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("schema_version")
    @classmethod
    def _schema_id(cls, value: str) -> str:
        if value != SCHEMA_LOOP_QA_OUTCOME:
            raise ValueError(f"unsupported qa outcome schema: {value!r}")
        return value


class QaSignals(BaseModel):
    """Inputs for classify_qa_outcome — no free-text enum coercion."""

    model_config = {"extra": "forbid"}

    suite_ok: bool | None = None
    suite_is_full: bool = True
    plan_mismatch: bool = False
    ac_gap: bool = False
    transport_broken: bool = False
    transport_retries: int = 0
    verify_verdict: Literal["PASS", "FAIL", "BLOCKED"] | None = None
    suite_scope: QaSuiteScope = "full"
    suite_command: str = "bin/pytest -q --tb=line"
    changed_paths: list[str] = Field(default_factory=list)
    epic_id: str = ""
