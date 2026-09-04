"""Pydantic v2 schemas for workflow pack registry and resolution."""
from __future__ import annotations

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class WorkflowPack(BaseModel):
    """Workflow pack definition."""
    model_config = ConfigDict(extra="forbid")

    id: str
    roles: List[str]
    command_prefixes: List[str]
    phase_registry: str
    memory_bank: str
    rules_root: str
    artifact_layout: Literal["software-epic-v1"] = "software-epic-v1"
    description: str = ""


class WorkflowPackRegistry(BaseModel):
    """Workflow pack registry definition."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_: Literal["workflow-pack-registry/v1"] = Field(alias="schema", default="workflow-pack-registry/v1")
    default: str
    packs: Dict[str, WorkflowPack]


class PackResolveResult(BaseModel):
    """Result of workflow pack resolution."""
    model_config = ConfigDict(extra="forbid")

    ok: bool
    pack_id: str = ""
    pack: Optional[WorkflowPack] = None
    diagnostic_codes: List[str] = Field(default_factory=list)
