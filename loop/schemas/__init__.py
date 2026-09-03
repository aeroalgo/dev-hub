"""Typed loop contracts — validate-on-read/write for handoff and gate verdicts."""

from loop.schemas.active_context import (
    handoff_mode_from_text,
    parse_handoff_meta,
    render_with_frontmatter,
    split_frontmatter,
    validate_handoff_frontmatter,
)
from loop.schemas.board import BoardCardMetadata
from loop.schemas.checkpoint import (
    CHECKPOINT_ACTIONS,
    CHECKPOINT_RESUME_POLICIES,
    CHECKPOINT_STAGES,
    CHECKPOINT_STATUSES,
    CheckpointRecord,
)
from loop.schemas.event import EVENT_KINDS, EVENT_SCHEMA, LoopEvent
from loop.schemas.formula import DecomposeFormula, FormulaStep, load_formula
from loop.schemas.gate_verdict import GateVerdictRecord, GateVerdictValue
from loop.schemas.handoff import LoopHandoffFrontmatter, LoopHandoffRole
from loop.schemas.state import DriftCounters, EpicState
from loop.schemas.sunset_inventory import (
    SCHEMA_LOOP_SUNSET_INVENTORY,
    SunsetItem,
    SunsetKind,
    SunsetMark,
    SunsetReport,
)

__all__ = [
    "CHECKPOINT_ACTIONS",
    "CHECKPOINT_RESUME_POLICIES",
    "CHECKPOINT_STAGES",
    "CHECKPOINT_STATUSES",
    "BoardCardMetadata",
    "CheckpointRecord",
    "DecomposeFormula",
    "DriftCounters",
    "EVENT_KINDS",
    "EVENT_SCHEMA",
    "EpicState",
    "FormulaStep",
    "GateVerdictRecord",
    "GateVerdictValue",
    "LoopEvent",
    "LoopHandoffFrontmatter",
    "LoopHandoffRole",
    "SCHEMA_LOOP_SUNSET_INVENTORY",
    "SunsetItem",
    "SunsetKind",
    "SunsetMark",
    "SunsetReport",
    "load_formula",
    "handoff_mode_from_text",
    "parse_handoff_meta",
    "render_with_frontmatter",
    "split_frontmatter",
    "validate_handoff_frontmatter",
]
