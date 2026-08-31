"""Tier-0 incident auto-repair orchestrator."""
from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from epic_paths import epic_dir

from loop.incidents.events import emit_incident_resolved, emit_repair_applied
from loop.incidents.metrics import increment_counter
from loop.incidents.registry import get_chain, resolve_callable
from loop.incidents.schema import IncidentRecord
from loop.incidents.store import resolve_incident

logger = logging.getLogger(__name__)


@dataclass
class Tier0Result:
    attempted: bool
    resolved: bool
    repair_exhausted: bool
    diagnostic_code: str
    repair_action: str | None = None
    details: dict[str, Any] | None = None


def _call_with_args(func: Any, cwd: str | Path, decompose_path: str | Path | None = None) -> Any:
    sig = inspect.signature(func)
    kwargs: dict[str, Any] = {}
    params = sig.parameters
    if "cwd" in params:
        kwargs["cwd"] = cwd
    if "decompose" in params and decompose_path:
        kwargs["decompose"] = decompose_path
    if not kwargs:
        return func()
    if len(kwargs) == 1 and "cwd" in kwargs:
        return func(cwd)
    return func(**kwargs)


def run_tier0_for_incident(
    cwd: str | Path,
    incident: IncidentRecord,
    registry_path: str | Path | None = None,
    decompose_path: str | Path | None = None,
) -> Tier0Result:
    """Execute Tier-0 repair chain for an incident and update incident status if resolved."""
    diagnostic_codes = incident.diagnostic_codes
    if not diagnostic_codes:
        return Tier0Result(
            attempted=False,
            resolved=False,
            repair_exhausted=False,
            diagnostic_code="",
        )

    code = diagnostic_codes[0]
    chain = get_chain(code, registry_path=registry_path)

    if not chain:
        logger.info("No repair chain for diagnostic code: %s", code)
        return Tier0Result(
            attempted=False,
            resolved=False,
            repair_exhausted=False,
            diagnostic_code=code,
        )

    for step in chain:
        repair_func = resolve_callable(step.repair_fn)
        if repair_func is None:
            logger.warning("Could not resolve repair_fn: %s", step.repair_fn)
            return Tier0Result(
                attempted=True,
                resolved=False,
                repair_exhausted=True,
                diagnostic_code=code,
            )

        attempts = 0
        while attempts < step.max_attempts:
            attempts += 1
            increment_counter(epic_dir(cwd), "tier0_attempts")
            logger.info(
                "Running repair %s for %s (attempt %d/%d)",
                step.repair_fn,
                code,
                attempts,
                step.max_attempts,
            )
            try:
                res = _call_with_args(repair_func, cwd, decompose_path)
            except Exception as e:
                logger.error("Repair function %s raised: %s", step.repair_fn, e)
                res = {"repaired": False, "error": str(e)}

            # Verification
            is_resolved = False
            if step.verify_fn:
                verify_func = resolve_callable(step.verify_fn)
                if verify_func:
                    try:
                        v_res = _call_with_args(verify_func, cwd, decompose_path)
                        if isinstance(v_res, list):
                            is_resolved = len(v_res) == 0
                        elif isinstance(v_res, bool):
                            is_resolved = v_res
                        elif isinstance(v_res, dict):
                            is_resolved = v_res.get("valid", True) and not v_res.get("errors")
                        else:
                            is_resolved = bool(v_res)
                    except Exception as ve:
                        logger.error("Verify function %s raised: %s", step.verify_fn, ve)
                        is_resolved = False
                else:
                    is_resolved = bool(res and isinstance(res, dict) and (res.get("repaired") or res.get("ok")))
            else:
                is_resolved = bool(res and isinstance(res, dict) and (res.get("repaired") or res.get("ok")))

            if is_resolved:
                logger.info("Incident %s (%s) resolved by Tier-0 repair %s", incident.incident_id, code, step.repair_fn)
                resolve_incident(
                    epic_dir(cwd),
                    incident.incident_id,
                    resolution_tier="tier0",
                    resolution_action=step.repair_fn,
                )
                increment_counter(epic_dir(cwd), "tier0_success")
                emit_repair_applied(
                    cwd,
                    epic_id=incident.epic_id,
                    metadata={
                        "repair_fn": step.repair_fn,
                        "diagnostic_code": code,
                        "incident_id": incident.incident_id,
                    },
                )
                emit_incident_resolved(
                    cwd,
                    epic_id=incident.epic_id,
                    metadata={
                        "resolution_tier": "tier0",
                        "resolution_action": step.repair_fn,
                        "incident_id": incident.incident_id,
                        "diagnostic_code": code,
                    },
                )
                return Tier0Result(
                    attempted=True,
                    resolved=True,
                    repair_exhausted=False,
                    diagnostic_code=code,
                    repair_action=step.repair_fn,
                    details=res if isinstance(res, dict) else {"result": res},
                )
            else:
                increment_counter(epic_dir(cwd), "tier0_fail")

    # If all attempts failed or max_attempts reached without resolution
    logger.warning("Tier-0 repairs exhausted for incident %s (%s)", incident.incident_id, code)
    return Tier0Result(
        attempted=True,
        resolved=False,
        repair_exhausted=True,
        diagnostic_code=code,
    )
