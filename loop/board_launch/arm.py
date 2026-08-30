"""Arm the product loop from a validated board launch card."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loop.context_loop import arm_session

from loop.board_sync.card_model import CardKind

from .loop_argv import BridgeConfig
from .metadata import LaunchCard


class StepMismatchError(RuntimeError):
    """Raised when the armed step differs from the board card step."""

    diagnostic_code = "step_mismatch"


class RoadmapAdvanceDeniedError(RuntimeError):
    """Raised when a roadmap gate lacks explicit permission to advance."""

    diagnostic_code = "roadmap_advance_denied"


@dataclass(frozen=True, slots=True)
class ArmResult:
    """Normalized result returned after a successful arm operation."""

    step_id: str
    armed_epic: str
    ok: bool = True


def arm_from_card(
    launch_card: LaunchCard,
    cwd_override: str | Path | None = None,
    config: BridgeConfig | None = None,
) -> ArmResult:
    """Arm the product loop and enforce card-specific launch invariants."""
    if not isinstance(launch_card, LaunchCard):
        raise TypeError("launch_card must be a LaunchCard")

    is_roadmap = (
        launch_card.card_kind is CardKind.GATE
        and (launch_card.gate_phase or "").upper() == "ROADMAP"
    )
    if is_roadmap and (
        config is None
        or not config.is_enabled()
        or not config.allows_roadmap_advance()
        or not _has_explicit_epic(launch_card)
    ):
        raise RoadmapAdvanceDeniedError(
            "ROADMAP gate requires enabled bridge, explicit allowRoadmapAdvance, and epic metadata"
        )

    target = _explicit_roadmap_target(launch_card) if is_roadmap else launch_card.decompose_rel
    if not isinstance(target, str) or not target.strip():
        raise ValueError("launch card is missing an arm target")

    project_root = Path(cwd_override) if cwd_override is not None else Path(launch_card.project_root)
    armed = arm_session(project_root, target)
    if not armed.get("ok"):
        error = armed.get("error") or armed.get("reason") or "arm failed"
        raise RuntimeError(str(error))

    step_id = str(armed.get("step_id") or "")
    armed_epic = str(armed.get("epic_id") or "")
    if launch_card.card_kind is CardKind.STEP and step_id != launch_card.step_id:
        raise StepMismatchError(
            f"armed step {step_id!r} does not match card step {launch_card.step_id!r}"
        )
    if not step_id or not armed_epic:
        raise RuntimeError("arm response is missing step_id or epic_id")

    return ArmResult(step_id=step_id, armed_epic=armed_epic, ok=True)


def _explicit_roadmap_target(launch_card: LaunchCard) -> str:
    """Return the validated explicit roadmap epic/decompose target."""
    raw = launch_card.raw
    for key in ("explicit_epic", "epic_id", "next_epic_id"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise RoadmapAdvanceDeniedError("ROADMAP gate requires explicit epic metadata")


def _has_explicit_epic(launch_card: LaunchCard) -> bool:
    """Return whether the card explicitly authorizes a roadmap epic."""
    try:
        _explicit_roadmap_target(launch_card)
    except RoadmapAdvanceDeniedError:
        return False
    return True
