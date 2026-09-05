"""Pack layout resolver and ArtifactLayout definitions."""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional, Union

from loop.workflow.registry import resolve_workflow_pack
from loop.workflow.schemas import WorkflowPack


class PackLayoutError(Exception):
    """Raised when pack layout or manifest resolution fails."""
    pass


class ArtifactLayout(str, Enum):
    """Artifact layout schemes supported by workflow packs."""
    software_epic_v1 = "software-epic-v1"
    production_epic_v1 = "production-epic-v1"


def resolve_mb_root(
    cwd: Optional[Union[Path, str]] = None,
    pack: Optional[WorkflowPack] = None,
    hub_root: Optional[Union[Path, str]] = None,
) -> Path:
    """Resolve memory-bank root directory for the active workflow pack.

    Fail-closed: raises PackLayoutError if manifest/pack resolution fails.
    For software-epic-v1, returns cwd / pack.memory_bank (e.g. cwd / 'memory-bank').
    """
    cwd_path = Path(cwd).resolve() if cwd is not None else Path.cwd().resolve()

    if pack is None:
        res = resolve_workflow_pack(cwd=cwd_path, hub_root=hub_root)
        if not res.ok or res.pack is None:
            codes = ", ".join(res.diagnostic_codes) if res.diagnostic_codes else "unknown"
            raise PackLayoutError(
                f"Failed to resolve workflow pack for cwd={cwd_path} (pack_id={res.pack_id!r}, diagnostics={codes})"
            )
        pack = res.pack

    # Dispatch based on artifact_layout / pack configuration
    layout = pack.artifact_layout
    if layout in (
        ArtifactLayout.software_epic_v1.value,
        ArtifactLayout.production_epic_v1.value,
        "software-epic-v1",
        "production-epic-v1",
    ):
        return cwd_path / pack.memory_bank
    raise PackLayoutError(f"Unsupported artifact layout: {layout!r}")


def resolve_active_context(cwd: Path | str | None = None, *, pack: WorkflowPack | None = None) -> Path:
    """Canonical activeContext path for the selected pack."""
    return resolve_mb_root(cwd=cwd, pack=pack) / "activeContext.md"


def resolve_role_root(pack: WorkflowPack, role: str, *, cwd: Path | str | None = None) -> Path:
    """Resolve a declared role under its pack root; reject unknown roles."""
    normalized = "integration" if role.lower() == "integ" else role.lower()
    if normalized not in pack.roles:
        raise PackLayoutError(f"Role {role!r} is not declared by pack {pack.id!r}")
    return resolve_mb_root(cwd=cwd, pack=pack) / normalized


def pack_diagnostics(cwd: Path | str) -> dict[str, str | None]:
    """CLI metadata; an unresolved pack stays explicit, never defaults silently."""
    result = resolve_workflow_pack(cwd=cwd)
    return {
        "workflow_pack": result.pack_id or None,
        "mb_root": str(resolve_mb_root(cwd=cwd, pack=result.pack)) if result.ok and result.pack else None,
    }
