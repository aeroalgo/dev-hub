"""Preflight checks for workflow pack configuration and paths."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, List, Optional

import loop.workflow.pack_graph as pack_graph
from loop.workflow.registry import load_registry, resolve_workflow_pack


_WORKFLOW_PACK_ERROR = "workflow_pack_check_error"


def check_workflow_pack(
    cwd: Optional[Path | str] = None,
    hub_root: Optional[Path | str] = None,
    pack_id: Optional[str] = None,
) -> List[str]:
    """Run preflight checks on executable workflow pack graph.

    Returns a list of diagnostic code strings. Empty list indicates all checks passed.
    """
    try:
        if pack_id is None:
            resolved = resolve_workflow_pack(cwd=cwd, hub_root=hub_root)
            if not resolved.ok or resolved.pack is None:
                return list(resolved.diagnostic_codes) or [_WORKFLOW_PACK_ERROR]
            res = pack_graph.check_pack_graph(pack_or_id=resolved.pack, cwd=cwd, hub_root=hub_root)
        else:
            res = pack_graph.check_pack_graph(pack_or_id=pack_id, cwd=cwd, hub_root=hub_root)
        return list(res.diagnostic_codes)
    except Exception:
        return [_WORKFLOW_PACK_ERROR]


def run_doctor_workflow_pack(
    cwd: Optional[Path | str] = None,
    hub_root: Optional[Path | str] = None,
    pack_id: Optional[str] = None,
    format: str = "json",
) -> int:
    """CLI entrypoint for doctor workflow-pack.

    Prints JSON result with status, pack_id, and diagnostic codes.
    Returns 0 on success, 1 on failure.
    """
    try:
        cwd_path = Path(cwd).resolve() if cwd is not None else Path.cwd().resolve()
        hub_root_path = Path(hub_root).resolve() if hub_root is not None else None

        if pack_id is None:
            resolved = resolve_workflow_pack(cwd=cwd_path, hub_root=hub_root_path)
            if not resolved.ok or resolved.pack is None:
                codes = list(resolved.diagnostic_codes) or [_WORKFLOW_PACK_ERROR]
                resolved_pack_id = resolved.pack_id
            else:
                res = pack_graph.check_pack_graph(pack_or_id=resolved.pack, cwd=cwd_path, hub_root=hub_root_path)
                codes = list(res.diagnostic_codes)
                resolved_pack_id = res.pack_id
        else:
            res = pack_graph.check_pack_graph(pack_or_id=pack_id, cwd=cwd_path, hub_root=hub_root_path)
            codes = list(res.diagnostic_codes)
            resolved_pack_id = res.pack_id
    except Exception:
        codes = [_WORKFLOW_PACK_ERROR]
        resolved_pack_id = pack_id or ""

    ok = len(codes) == 0
    out: dict[str, Any] = {
        "ok": ok,
        "pack_id": resolved_pack_id,
        "diagnostic_codes": codes,
    }

    try:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    except Exception:
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(run_doctor_workflow_pack())
