"""Preflight checks for workflow pack configuration and paths."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, List, Optional

from loop.workflow.registry import resolve_workflow_pack


_WORKFLOW_PACK_ERROR = "workflow_pack_check_error"


def check_workflow_pack(
    cwd: Optional[Path | str] = None,
    hub_root: Optional[Path | str] = None,
) -> List[str]:
    """Run >=4 preflight checks on workflow pack configuration and environment.

    Checks:
    1. Workflow pack resolve ok (via resolve_workflow_pack)
    2. Phase registry file exists and is a file
    3. Rules root directory exists and is a directory
    4. Memory-bank root directory exists and is writable

    Returns a list of diagnostic code strings. Empty list indicates all checks passed.
    """
    try:
        cwd_path = Path(cwd).resolve() if cwd is not None else Path.cwd().resolve()
        res = resolve_workflow_pack(cwd=cwd_path, hub_root=hub_root)

        diagnostic_codes: List[str] = []

        # Check 1: Resolve ok
        if not res.ok or res.pack is None:
            if res.diagnostic_codes:
                for code in res.diagnostic_codes:
                    if code not in diagnostic_codes:
                        diagnostic_codes.append(code)
            else:
                diagnostic_codes.append("pack_resolve_failed")
            return diagnostic_codes

        pack = res.pack

        # Check 2: Phase registry file exists
        phase_reg_path = cwd_path / pack.phase_registry
        if not phase_reg_path.is_file():
            diagnostic_codes.append("pack_phase_registry_missing")

        # Check 3: Rules root directory exists
        rules_root_path = cwd_path / pack.rules_root
        if not rules_root_path.is_dir():
            diagnostic_codes.append("pack_rules_missing")

        # Check 4: Memory-bank root exists and is writable
        mb_path = cwd_path / pack.memory_bank
        if not mb_path.exists():
            diagnostic_codes.append("mb_root_missing")
        elif not mb_path.is_dir():
            diagnostic_codes.append("mb_root_not_dir")
        elif not os.access(mb_path, os.W_OK):
            diagnostic_codes.append("mb_root_not_writable")

        return diagnostic_codes
    except Exception:
        return [_WORKFLOW_PACK_ERROR]


def run_doctor_workflow_pack(
    cwd: Optional[Path | str] = None,
    hub_root: Optional[Path | str] = None,
    format: str = "json",
) -> int:
    """CLI entrypoint for doctor workflow-pack.

    Prints JSON result with status, pack_id, and diagnostic codes.
    Returns 0 on success, 1 on failure.
    """
    try:
        cwd_path = Path(cwd).resolve() if cwd is not None else Path.cwd().resolve()
        codes = check_workflow_pack(cwd=cwd_path, hub_root=hub_root)
        res = resolve_workflow_pack(cwd=cwd_path, hub_root=hub_root)
        pack_id = res.pack_id if res.pack_id else ""
    except Exception:
        codes = [_WORKFLOW_PACK_ERROR]
        pack_id = ""

    ok = len(codes) == 0
    out: dict[str, Any] = {
        "ok": ok,
        "pack_id": pack_id,
        "diagnostic_codes": codes,
    }

    try:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    except Exception:
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(run_doctor_workflow_pack())
