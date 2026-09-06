"""Workflow pack command router: maps raw commands to normalized phases and rules mdc paths."""
from __future__ import annotations

import functools
from pathlib import Path
from typing import List, Optional, Union
import yaml

from loop.workflow.schemas import CommandRoute, IntentRoutingTable, WorkflowPack

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



_ROLE_SUBDIR_MAP = {
    "back": "back_developer",
    "front": "front_developer",
    "integ": "integration_developer",
    "integration": "integration_developer",
}


def route_command(pack: WorkflowPack, raw_command: str, hub_root: Optional[Union[Path, str]] = None) -> CommandRoute:
    """Route raw_command via pack.command_prefixes to canonical phase and relative rules MDC path.

    1. Normalizes raw_command via pack.command_prefixes (matching prefix determines role).
    2. Resolves rules_mdc_rel:
       - If {rules_root}/workflow-{phase_lower}.mdc exists, use flat layout: {rules_root}/workflow-{phase_lower}.mdc.
       - Else if {rules_root}/{role_subdir}/workflow-{phase_lower}.mdc exists or role_subdir layout is used:
         {rules_root}/{role_subdir}/workflow-{phase_lower}.mdc.
    3. Verifies existence against hub_root (if hub_root provided or defaults to project root).
       If target rules file does not exist, marks ok=False and diagnostic_codes=['pack_route_missing'].
    4. If no prefix matches, normalized_phase is the uppercase raw command stripped, and rules_mdc_rel is None.
    """
    if hub_root is None:
        hub_root_path = Path(__file__).resolve().parent.parent.parent
    else:
        hub_root_path = Path(hub_root).resolve()

    raw_str = str(raw_command or "").strip()
    if not raw_str:
        return CommandRoute(ok=True, normalized_phase="", rules_mdc_rel=None, diagnostic_codes=[])

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
            ok=True,
            normalized_phase=normalized_phase or raw_str.upper(),
            rules_mdc_rel=None,
            diagnostic_codes=[],
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

    role_subdir = _ROLE_SUBDIR_MAP.get(role.strip().lower())
    rules_root = str(pack.rules_root or "").rstrip("/")
    phase_lower = normalized_phase.lower()

    # Check candidates on disk
    flat_rel = f"{rules_root}/workflow-{phase_lower}.mdc" if rules_root else f"workflow-{phase_lower}.mdc"
    role_rel = (
        f"{rules_root}/{role_subdir}/workflow-{phase_lower}.mdc"
        if rules_root and role_subdir
        else None
    )

    if (hub_root_path / flat_rel).is_file():
        rules_mdc_rel = flat_rel
    elif role_rel and (hub_root_path / role_rel).is_file():
        rules_mdc_rel = role_rel
    else:
        # Keep missing routes on the canonical flat path; known role layouts remain supported.
        if role_rel and rules_root and (hub_root_path / rules_root / role_subdir).is_dir():
            rules_mdc_rel = role_rel
        else:
            rules_mdc_rel = flat_rel

    file_exists = (hub_root_path / rules_mdc_rel).is_file() if rules_mdc_rel else False
    if not file_exists:
        return CommandRoute(
            ok=False,
            normalized_phase=normalized_phase,
            rules_mdc_rel=rules_mdc_rel,
            diagnostic_codes=["pack_route_missing"],
        )

    return CommandRoute(
        ok=True,
        normalized_phase=normalized_phase,
        rules_mdc_rel=rules_mdc_rel,
        diagnostic_codes=[],
    )

