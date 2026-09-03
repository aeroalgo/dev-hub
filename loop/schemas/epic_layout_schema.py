"""Pydantic schema and kinds for epic-layout/v2."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class EpicLayoutKind(str, Enum):
    PLAN_MD = "plan_md"
    PLAN_YAML = "plan_yaml"
    DECOMPOSE_INDEX_MD = "decompose_index_md"
    DECOMPOSE_INDEX_YAML = "decompose_index_yaml"
    DECOMPOSE_STEP = "decompose_step"
    IMPLEMENT_STEP = "implement_step"
    QA_YAML = "qa_yaml"
    ANALYZE_YAML = "analyze_yaml"
    AUDIT_YAML = "audit_yaml"


class EpicLayoutResolveRequest(BaseModel):
    role: str = "back"
    plan_id: str
    kind: EpicLayoutKind
    step_id: Optional[str] = None
    step_slug: Optional[str] = None
    ext: Optional[str] = None
