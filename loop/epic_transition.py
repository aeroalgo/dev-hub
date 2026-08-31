"""Transition Engine public API for T-HUB-029.

Public contract:
  resolve_next(cwd, epic_id, role) -> EpicNextAction
  arm_phase(cwd, epic_id, phase, role, **kwargs) -> dict
  promote_if_ready(cwd, epic_id, role) -> dict | None
  load_phase_registry(registry_path=None) -> dict
  get_phase_config(phase: str) -> dict
  get_verify_agent(phase: str) -> str | None
  get_dsh_preset(phase: str) -> str | None
  _legacy_warn(caller_name) -> None
"""
from __future__ import annotations
import sys
import warnings
from pathlib import Path
from typing import Any
import yaml

from loop.board_sync.epic_resolver import EpicNextAction, resolve_epic_next_action

_HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
if str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))

_LOOP = Path(__file__).resolve().parent
if str(_LOOP) not in sys.path:
    sys.path.insert(0, str(_LOOP))

_PROMOTABLE_PHASES = frozenset({"DECOMPOSE", "ANALYZE"})
_ROLE_PREFIXES = ("BACK ", "FRONT ", "INTEG ", "INTEGRATION ")
_PHASE_REGISTRY_CACHE: dict[str, Any] | None = None
_DEFAULT_REGISTRY_PATH = _LOOP / "schemas" / "phase_registry.yaml"


def normalize_registry_phase(phase: str) -> str:
    """Map role-prefixed phase labels to registry keys (BACK IMPLEMENT → IMPLEMENT)."""
    normalized = str(phase or "").strip().upper()
    for prefix in _ROLE_PREFIXES:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :].strip()
            break
    return normalized


def load_phase_registry(registry_path: Path | str | None = None) -> dict[str, Any]:
    """Load canonical phase registry yaml and cache in module state."""
    global _PHASE_REGISTRY_CACHE
    path = Path(registry_path) if registry_path else _DEFAULT_REGISTRY_PATH
    if registry_path is None and _PHASE_REGISTRY_CACHE is not None:
        return _PHASE_REGISTRY_CACHE

    if not path.exists():
        raise ValueError(f"Phase registry yaml file not found: {path}")

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as err:
        raise ValueError(f"Invalid YAML in phase registry at {path}: {err}") from err

    if not isinstance(data, dict) or "phases" not in data:
        raise ValueError(f"Invalid phase registry schema at {path}: missing 'phases' key")

    if registry_path is None:
        _PHASE_REGISTRY_CACHE = data
    return data


def get_phase_config(phase: str, registry_path: Path | str | None = None) -> dict[str, Any]:
    """Lookup phase config from registry; unknown phase raises ValueError fail-closed."""
    registry = load_phase_registry(registry_path)
    phases = registry.get("phases", {})
    normalized_phase = normalize_registry_phase(phase)
    if normalized_phase not in phases:
        raise ValueError(f"unknown phase {phase!r}: fail-closed")
    return phases[normalized_phase]


def get_verify_agent(phase: str, registry_path: Path | str | None = None) -> str | None:
    """Lookup verify_agent for a phase from registry; unknown phase raises ValueError fail-closed."""
    cfg = get_phase_config(phase, registry_path=registry_path)
    return cfg.get("verify_agent")


def get_dsh_preset(phase: str, registry_path: Path | str | None = None) -> str | None:
    """Lookup dsh_preset for a phase from registry; unknown phase raises ValueError fail-closed."""
    cfg = get_phase_config(phase, registry_path=registry_path)
    return cfg.get("dsh_preset")


def resolve_next(cwd: Path | str, epic_id: str, role: str) -> EpicNextAction:
    """Delegate to resolve_epic_next_action — single entry point for next-action lookup."""
    return resolve_epic_next_action(cwd, role, epic_id)


def arm_phase(
    cwd: Path | str,
    epic_id: str,
    phase: str,
    role: str,
    **kwargs: Any,
) -> dict:
    """Arm an epic phase context by routing to appropriate arm function."""
    from epic.core import arm_active_context_from_decompose, arm_epic, arm_pre_implement_context
    from _lib import resolve_runtime_config

    runtime_cfg = resolve_runtime_config(cwd)
    epic_runtime = kwargs.get("epic_runtime") or runtime_cfg.epic_runtime
    if epic_runtime == "dsh":
        phase_config = get_phase_config(phase)
        dsh_preset = phase_config.get("dsh_preset")
        if dsh_preset is None:
            raise ValueError(f"no DSH preset for phase {phase!r}: fail-closed")
        kwargs["dsh_preset"] = dsh_preset

    phase_u = (phase or "").upper()
    decompose_rel = kwargs.get("decompose") or kwargs.get("decompose_rel")
    if phase_u in ("PLAN", "CLARIFY", "ANALYZE", "CREATIVE"):
        target_rel = kwargs.get("target_rel")
        res = arm_pre_implement_context(
            cwd,
            epic_id=epic_id,
            role=role,
            phase=phase_u,
            target_rel=target_rel,
            decompose_rel=decompose_rel,
        )
    elif phase_u == "DECOMPOSE" or phase_u in ("IMPLEMENT", "TASK", "REFACTOR", "BUGFIX", "QA"):
        if decompose_rel:
            res = arm_active_context_from_decompose(cwd, decompose_rel)
        elif phase_u == "DECOMPOSE":
            target_rel = kwargs.get("target_rel")
            res = arm_pre_implement_context(
                cwd,
                epic_id=epic_id,
                role=role,
                phase=phase_u,
                target_rel=target_rel,
                decompose_rel=decompose_rel,
            )
        else:
            res = arm_epic(cwd, epic_id, role=role, **kwargs)
    else:
        res = arm_epic(cwd, epic_id, role=role, **kwargs)

    if isinstance(res, dict):
        if "armed_step" not in res:
            res["armed_step"] = res.get("step_id")
        if "handoff" not in res:
            res["handoff"] = res.get("active_context") or "memory-bank/activeContext.md"
        if "role" not in res:
            res["role"] = role
    return res


def promote_if_ready(
    cwd: Path | str,
    epic_id: str,
    role: str,
) -> dict | None:
    """Promote epic from a finishable pre-implement phase (DECOMPOSE / ANALYZE).

    DECOMPOSE finish → ANALYZE when gate required, else IMPLEMENT.
    ANALYZE finish (gate pass) → IMPLEMENT first pending sNN.
    """
    from analyze_gate import analyze_required_before_implement
    from epic.core import load_epic_state
    from roadmap_queue import find_decompose_index, load_steps_for_index

    cwd_p = Path(cwd).resolve()
    st = load_epic_state(cwd_p)
    armed_step = str(st.get("armed_step") or "").upper()
    if armed_step not in _PROMOTABLE_PHASES:
        return None

    role_dir = (role or st.get("role") or "back").lower()
    epic = str(epic_id or st.get("armed_epic") or "").strip()
    if not epic:
        return None

    decomp = str(st.get("armed_decompose") or "").strip()
    idx_path: Path | None
    if decomp:
        idx_path = cwd_p / decomp
        if not idx_path.is_file():
            idx_path = None
    else:
        idx_path = None
    if idx_path is None:
        idx_path = find_decompose_index(cwd_p, role_dir, epic)
    if idx_path is None or not idx_path.is_file():
        return None

    loaded = load_steps_for_index(cwd_p, idx_path)
    if not loaded.get("ok"):
        return None
    steps = loaded.get("steps") or []
    if not steps:
        return None

    decompose_rel = (
        str(idx_path.relative_to(cwd_p)).replace("\\", "/")
        if idx_path.is_relative_to(cwd_p)
        else str(idx_path)
    )
    arm_decompose = decompose_rel
    if arm_decompose.endswith("/index.yaml") or arm_decompose.endswith("/index.md"):
        arm_decompose = str(Path(arm_decompose).parent).replace("\\", "/")
    gate = analyze_required_before_implement(
        cwd_p,
        role_dir,
        epic,
        steps,
        index_path=idx_path,
    )

    if armed_step == "DECOMPOSE":
        if gate.get("required"):
            res = arm_phase(
                cwd_p,
                epic,
                "ANALYZE",
                role_dir,
                decompose_rel=arm_decompose,
            )
            reason = "analyze_gate"
        else:
            res = arm_phase(
                cwd_p,
                epic,
                "IMPLEMENT",
                role_dir,
                decompose_rel=arm_decompose,
            )
            reason = "implement_promote"
        if isinstance(res, dict) and res.get("ok"):
            res["promoted_from"] = "DECOMPOSE"
            res["reason"] = reason
            try:
                from epic import _append_event
                if idx_path and idx_path.is_file():
                    _append_event(cwd_p, role_dir, epic, "phase_transition", idx_path)
            except Exception:
                pass
        return res if isinstance(res, dict) and res.get("ok") else None

    if armed_step == "ANALYZE":
        if gate.get("required"):
            return None
        res = arm_phase(
            cwd_p,
            epic,
            "IMPLEMENT",
            role_dir,
            decompose_rel=arm_decompose,
        )
        if isinstance(res, dict) and res.get("ok"):
            res["promoted_from"] = "ANALYZE"
            res["reason"] = "implement_promote"
            try:
                from epic import _append_event
                if idx_path and idx_path.is_file():
                    _append_event(cwd_p, role_dir, epic, "phase_transition", idx_path)
            except Exception:
                pass
        return res if isinstance(res, dict) and res.get("ok") else None

    return None


def _legacy_warn(caller_name: str) -> None:
    """Emit DeprecationWarning for legacy callers replaced by Transition Engine."""
    warnings.warn(
        f"{caller_name!r} is deprecated — use loop.epic_transition instead",
        DeprecationWarning,
        stacklevel=2,
    )
