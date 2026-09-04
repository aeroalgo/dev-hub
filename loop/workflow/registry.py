"""Workflow pack registry loader and resolution helpers."""
from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Optional
import yaml
from pydantic import ValidationError

from loop.workflow.schemas import PackResolveResult, WorkflowPack, WorkflowPackRegistry

DEFAULT_REGISTRY_FILENAME = "workflow_pack_registry.yaml"


@functools.lru_cache(maxsize=32)
def load_registry(hub_root: Optional[Path | str] = None) -> WorkflowPackRegistry:
    """Load and validate WorkflowPackRegistry from hub_root/loop/workflow_pack_registry.yaml."""
    if hub_root is None:
        hub_root_path = Path(__file__).resolve().parent.parent.parent
    else:
        hub_root_path = Path(hub_root).resolve()

    registry_path = hub_root_path / "loop" / DEFAULT_REGISTRY_FILENAME
    if not registry_path.is_file():
        # Fallback if registry is directly in hub_root_path
        alt_path = hub_root_path / DEFAULT_REGISTRY_FILENAME
        if alt_path.is_file():
            registry_path = alt_path

    if not registry_path.is_file():
        raise FileNotFoundError(f"Workflow pack registry file not found: {registry_path}")

    with open(registry_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Malformed YAML in workflow pack registry: expected dict at root, got {type(data)}")

    return WorkflowPackRegistry.model_validate(data)


def get_pack(registry: WorkflowPackRegistry, pack_id: str) -> Optional[WorkflowPack]:
    """Retrieve a workflow pack by id from registry, returning None if not found."""
    return registry.packs.get(pack_id)


def _read_project_yaml_pack(cwd: Path) -> Optional[str]:
    """Read workflow_pack field from project.yaml or .dev-hub/project.yaml if present."""
    candidates = [
        cwd / "project.yaml",
        cwd / ".dev-hub" / "project.yaml",
    ]
    for p in candidates:
        if p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict) and "workflow_pack" in data:
                    val = data.get("workflow_pack")
                    if isinstance(val, str) and val.strip():
                        return val.strip()
            except Exception:
                pass
    return None


def resolve_workflow_pack(cwd: Optional[Path | str] = None, hub_root: Optional[Path | str] = None) -> PackResolveResult:
    """Resolve workflow pack following precedence: project.yaml > env > default.

    Env aliases checked: WORKFLOW_PACK, EPIC_WORKFLOW_PACK.
    Fail-closed: unknown pack_id returns ok=False with diagnostic_codes=['invalid_workflow_pack'].
    """
    cwd_path = Path(cwd).resolve() if cwd is not None else Path.cwd().resolve()

    try:
        registry = load_registry(hub_root)
    except Exception:
        return PackResolveResult(
            ok=False,
            pack_id="",
            pack=None,
            diagnostic_codes=["invalid_workflow_pack_registry"],
        )

    # 1. Check project.yaml / .dev-hub/project.yaml
    pack_id = _read_project_yaml_pack(cwd_path)

    # 2. Check environment variables
    if not pack_id:
        env_pack = os.environ.get("WORKFLOW_PACK") or os.environ.get("EPIC_WORKFLOW_PACK")
        if env_pack and env_pack.strip():
            pack_id = env_pack.strip()

    # 3. Fallback to default
    if not pack_id:
        pack_id = registry.default

    pack = get_pack(registry, pack_id)
    if pack is None:
        return PackResolveResult(
            ok=False,
            pack_id=pack_id,
            pack=None,
            diagnostic_codes=["invalid_workflow_pack"],
        )

    return PackResolveResult(
        ok=True,
        pack_id=pack_id,
        pack=pack,
        diagnostic_codes=[],
    )
