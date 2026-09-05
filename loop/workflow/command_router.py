"""Workflow pack command router: maps raw commands to normalized phases and rules mdc paths."""
from __future__ import annotations

import functools
from pathlib import Path
from typing import NamedTuple, Optional, Union
import yaml

from loop.workflow.schemas import IntentRoutingTable, WorkflowPack

DEFAULT_INTENT_ROUTING_FILENAME = "intent_routing.yaml"


@functools.lru_cache(maxsize=32)
def load_intent_routing(hub_root: Optional[Union[Path, str]] = None) -> IntentRoutingTable:
    """Load and validate IntentRoutingTable from hub_root/loop/workflow/intent_routing.yaml."""
    if hub_root is None:
        hub_root_path = Path(__file__).resolve().parent.parent.parent
    else:
        hub_root_path = Path(hub_root).resolve()

    routing_path = hub_root_path / "loop" / "workflow" / DEFAULT_INTENT_ROUTING_FILENAME
    if not routing_path.is_file():
        alt_path = hub_root_path / "loop" / DEFAULT_INTENT_ROUTING_FILENAME
        if alt_path.is_file():
            routing_path = alt_path
        else:
            alt_path2 = hub_root_path / DEFAULT_INTENT_ROUTING_FILENAME
            if alt_path2.is_file():
                routing_path = alt_path2

    if not routing_path.is_file():
        raise FileNotFoundError(f"Intent routing file not found: {routing_path}")

    with open(routing_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Malformed YAML in intent routing: expected dict at root, got {type(data)}")

    return IntentRoutingTable.model_validate(data)



class CommandRoute(NamedTuple):
    """Result of routing a raw command against a workflow pack."""
    normalized_phase: str
    rules_mdc_rel: Optional[str]


_ROLE_SUBDIR_MAP = {
    "back": "back_developer",
    "front": "front_developer",
    "integ": "integration_developer",
    "integration": "integration_developer",
}


def _resolve_role_subdir(role: str) -> str:
    role_key = role.strip().lower()
    return _ROLE_SUBDIR_MAP.get(role_key, f"{role_key}_developer" if not role_key.endswith("_developer") else role_key)


def route_command(pack: WorkflowPack, raw_command: str) -> CommandRoute:
    """Route raw_command via pack.command_prefixes to canonical phase and relative rules MDC path.

    1. Normalizes raw_command via pack.command_prefixes (matching prefix determines role).
    2. Resolves rules_mdc_rel = {pack.rules_root}/{role_subdir}/workflow-{phase.lower()}.mdc.
    3. If no prefix matches, normalized_phase is the uppercase raw command stripped, and rules_mdc_rel is None.
    """
    raw_str = str(raw_command or "").strip()
    if not raw_str:
        return CommandRoute(normalized_phase="", rules_mdc_rel=None)

    raw_upper = raw_str.upper()

    # Sort prefixes by length descending for deterministic longest-match
    sorted_prefixes = sorted(pack.command_prefixes, key=lambda p: len(str(p)), reverse=True)

    matched_prefix: Optional[str] = None
    for prefix in sorted_prefixes:
        p_clean = str(prefix).strip().upper()
        p_spaced = p_clean + " "
        if raw_upper.startswith(p_spaced):
            matched_prefix = prefix
            raw_upper = raw_upper[len(p_spaced):].strip()
            break
        elif raw_upper == p_clean:
            matched_prefix = prefix
            raw_upper = ""
            break

    normalized_phase = raw_upper

    if not matched_prefix or not normalized_phase:
        return CommandRoute(
            normalized_phase=normalized_phase or raw_str.upper(),
            rules_mdc_rel=None,
        )

    # Determine role_subdir based on prefix and pack.roles / pack.command_prefixes
    prefix_clean = str(matched_prefix).strip()
    prefix_idx = -1
    for idx, p in enumerate(pack.command_prefixes):
        if str(p).strip().upper() == prefix_clean.upper():
            prefix_idx = idx
            break

    role = prefix_clean.lower()
    if 0 <= prefix_idx < len(pack.roles):
        role = pack.roles[prefix_idx]

    role_subdir = _resolve_role_subdir(role)
    rules_root = str(pack.rules_root or "").rstrip("/")
    phase_lower = normalized_phase.lower()

    rules_mdc_rel = f"{rules_root}/{role_subdir}/workflow-{phase_lower}.mdc" if rules_root else f"{role_subdir}/workflow-{phase_lower}.mdc"

    return CommandRoute(
        normalized_phase=normalized_phase,
        rules_mdc_rel=rules_mdc_rel,
    )
