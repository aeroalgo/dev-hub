"""Workflow pack path validation and full resolution helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from loop.workflow.registry import resolve_workflow_pack
from loop.workflow.schemas import PackResolveResult


def validate_pack_paths(result: PackResolveResult, cwd: Optional[Path | str] = None) -> PackResolveResult:
    """Validate that phase_registry file and memory_bank dir exist relative to PROJECT_ROOT / cwd.

    If ok is True but any path is missing, marks ok=False and adds 'pack_path_missing' to diagnostic_codes.
    """
    if not result.ok or result.pack is None:
        return result

    cwd_path = Path(cwd).resolve() if cwd is not None else Path.cwd().resolve()
    pack = result.pack

    phase_reg_path = cwd_path / pack.phase_registry
    mb_path = cwd_path / pack.memory_bank

    missing = False
    if not phase_reg_path.is_file():
        missing = True
    if not mb_path.is_dir():
        missing = True

    if missing:
        diagnostic_codes = list(result.diagnostic_codes)
        if "pack_path_missing" not in diagnostic_codes:
            diagnostic_codes.append("pack_path_missing")
        return PackResolveResult(
            ok=False,
            pack_id=result.pack_id,
            pack=result.pack,
            diagnostic_codes=diagnostic_codes,
        )

    return result


def full_resolve(cwd: Optional[Path | str] = None, hub_root: Optional[Path | str] = None) -> PackResolveResult:
    """Full workflow pack resolution including path validation against cwd / project root.

    Combines resolve_workflow_pack (precedence & registry lookup) with validate_pack_paths.
    """
    cwd_path = Path(cwd).resolve() if cwd is not None else Path.cwd().resolve()
    res = resolve_workflow_pack(cwd=cwd_path, hub_root=hub_root)
    return validate_pack_paths(res, cwd=cwd_path)
