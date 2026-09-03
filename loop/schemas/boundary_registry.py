"""boundary_registry — schema_id to pydantic model mapping for loop boundaries."""

from __future__ import annotations

from typing import Any, Type

from pydantic import BaseModel

from loop.mb_load.schemas import MbLoadResult, SCHEMA_LOOP_MB_LOAD
from loop.schemas.gate_verdict import GateVerdictRecord, SCHEMA_LOOP_GATE_VERDICT
from loop.schemas.repair_result import RepairResultRecord, SCHEMA_LOOP_REPAIR_RESULT
from loop.schemas.validate_result import ValidateResult, SCHEMA_LOOP_VALIDATE_RESULT

BOUNDARY_REGISTRY: dict[str, Type[BaseModel]] = {
    SCHEMA_LOOP_MB_LOAD: MbLoadResult,
    SCHEMA_LOOP_GATE_VERDICT: GateVerdictRecord,
    SCHEMA_LOOP_REPAIR_RESULT: RepairResultRecord,
    SCHEMA_LOOP_VALIDATE_RESULT: ValidateResult,
}

__all__ = [
    "BOUNDARY_REGISTRY",
    "SCHEMA_LOOP_MB_LOAD",
    "SCHEMA_LOOP_GATE_VERDICT",
    "SCHEMA_LOOP_REPAIR_RESULT",
    "SCHEMA_LOOP_VALIDATE_RESULT",
]
