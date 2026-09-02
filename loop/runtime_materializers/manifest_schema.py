from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
import yaml
from pydantic import BaseModel, Field, ValidationError


class ManifestValidationError(Exception):
    def __init__(self, message: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class ManifestAgent(BaseModel):
    description: str | None = None
    source: str
    runtimes: dict[str, dict[str, Any]] = Field(default_factory=dict)


class ManifestHook(BaseModel):
    source: str
    runtimes: dict[str, dict[str, Any]] = Field(default_factory=dict)


class ManifestInstruction(BaseModel):
    source: str
    runtimes: dict[str, dict[str, Any]] = Field(default_factory=dict)


class HarnessManifest(BaseModel):
    schema_version: Literal["harness-manifest/v1"]
    agents: dict[str, ManifestAgent]
    hooks: dict[str, ManifestHook]
    instructions: dict[str, ManifestInstruction]


def load_manifest(path: str | Path) -> HarnessManifest:
    manifest_path = Path(path)
    if not manifest_path.exists():
        raise ManifestValidationError(f"Manifest file not found: {manifest_path}", exit_code=2)

    try:
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ManifestValidationError(f"Invalid YAML in manifest: {e}", exit_code=2) from e

    if not isinstance(data, dict):
        raise ManifestValidationError("Manifest content must be a mapping", exit_code=2)

    try:
        return HarnessManifest.model_validate(data)
    except ValidationError as e:
        raise ManifestValidationError(f"Manifest validation failed:\n{e}", exit_code=2) from e
