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
    artifact_layout: Literal["software-epic-v1", "production-epic-v1"] = "software-epic-v1"
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


class IntentPipelineStep(BaseModel):
    """Pipeline step within an intent route."""
    model_config = ConfigDict(extra="forbid")

    command: str
    gate: Literal["auto", "approval"] = "auto"


class IntentRoute(BaseModel):
    """Intent route definition mapping intent to pack and phase pipeline."""
    model_config = ConfigDict(extra="forbid")

    pack: str
    pipeline: List[IntentPipelineStep] = Field(default_factory=list)


class IntentRoutingTable(BaseModel):
    """Workflow intent routing table definition."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_: Literal["workflow-intent-routing/v1"] = Field(alias="schema", default="workflow-intent-routing/v1")
    intents: Dict[str, IntentRoute]

