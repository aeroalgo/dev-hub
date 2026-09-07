"""Registry loader and models for bundled stack profiles."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field
import yaml

from loop.stack_profiles.schemas import CapabilityName, ProfileName


class ProfileCapabilityDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    argv: Optional[List[str]] = None
    argv_template: Optional[List[str]] = None
    script_key: Optional[str] = None
    append_selector: bool = False
    timeout_seconds: int = 300
    requirements: List[str] = Field(default_factory=list)


class ProfileDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str
    required_executables: List[str] = Field(default_factory=list)
    default_scripts: Optional[Dict[str, str]] = None
    capabilities: Dict[CapabilityName, ProfileCapabilityDef]


class StackProfileRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["stack-profile-registry/v1"] = Field(alias="schema")
    version: int = 1
    profiles: Dict[ProfileName, ProfileDef]


@lru_cache(maxsize=1)
def get_bundled_registry() -> StackProfileRegistry:
    """Load and validate the bundled stack profile registry YAML."""
    registry_path = Path(__file__).parent / "registry.yaml"
    if not registry_path.is_file():
        raise FileNotFoundError(f"Bundled registry not found at {registry_path}")

    with open(registry_path, "r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f)

    return StackProfileRegistry.model_validate(raw_data)
