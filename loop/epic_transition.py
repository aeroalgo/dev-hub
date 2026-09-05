"""Transition Engine public API for T-HUB-029.

Public contract:
  resolve_next(cwd, epic_id, role) -> EpicNextAction
  arm_phase(cwd, epic_id, phase, role, **kwargs) -> dict
  promote_if_ready(cwd, epic_id, role) -> dict | None
  load_phase_registry(*, pack_id=None, cwd=None) -> dict
  get_phase_config(phase: str, *, pack_id=None, cwd=None) -> dict
  get_verify_agent(phase: str, *, pack_id=None, cwd=None) -> str | None
  get_dsh_preset(phase: str, *, pack_id=None, cwd=None) -> str | None
  _legacy_warn(caller_name) -> None
"""
from __future__ import annotations
import os
import sys
import warnings
from pathlib import Path
from typing import Any
import yaml

from loop.board_sync.epic_resolver import EpicNextAction, resolve_epic_next_action


def gates_from_phase(
    phase: object,
    *,
    pack: object | None = None,
    pack_id: str | None = None,
    cwd: Path | str | None = None,
) -> dict[str, Any]:
    """Expose gates_from_phase in epic_transition for convenience."""
    from epic.core import gates_from_phase as _gates_from_phase

    return _gates_from_phase(phase, pack=pack, pack_id=pack_id, cwd=cwd)


_HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
if str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))

_LOOP = Path(__file__).resolve().parent
if str(_LOOP) not in sys.path:
    sys.path.insert(0, str(_LOOP))

_PROMOTABLE_PHASES = frozenset({"DECOMPOSE", "ANALYZE"})
_POST_IMPLEMENT_ARMED = frozenset({"AUDIT", "QA", "BUGFIX", "DONE"})
_PHASE_REGISTRY_CACHE: dict[str, dict[str, Any]] = {}


def normalize_registry_phase(phase: str, pack: Any = None) -> str:
    """Map role-prefixed phase labels to registry keys (BACK IMPLEMENT → IMPLEMENT).

    If pack (WorkflowPack) is provided, uses pack.command_prefixes.
    Otherwise, if pack is None, falls back to resolving default software pack or empty.
    """
    normalized = str(phase or "").strip().upper()
    if pack is not None and hasattr(pack, "command_prefixes"):
        prefixes = [p.rstrip().upper() + " " for p in pack.command_prefixes]
    else:
        try:
            from loop.workflow.registry import load_registry, get_pack
            reg = load_registry()
            default_pack = get_pack(reg, reg.default)
            prefixes = [p.rstrip().upper() + " " for p in default_pack.command_prefixes] if default_pack else []
        except Exception:
            prefixes = []

    for prefix in prefixes:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :].strip()
            break
    return normalized


def load_phase_registry(
    *,
    pack_id: str | None = None,
    cwd: Path | str | None = None,
) -> dict[str, Any]:
    """Load canonical phase registry yaml and cache in module state."""
    global _PHASE_REGISTRY_CACHE

    if pack_id is None:
        raise TypeError("load_phase_registry requires pack_id: fail-closed")

    cache_key = f"pack:{pack_id}"
    from loop.workflow.registry import load_registry, get_pack
    try:
        reg = load_registry()
        pack = get_pack(reg, pack_id)
    except Exception as err:
        raise ValueError(f"Failed to resolve pack {pack_id!r}: {err}") from err

    if pack is None:
        raise ValueError(f"Workflow pack not found: {pack_id!r} (pack_path_missing)")

    cwd_path = Path(cwd).resolve() if cwd is not None else Path.cwd().resolve()
    resolved_path = cwd_path / pack.phase_registry
    cache_key = f"pack:{pack_id}:{str(cwd_path)}"

    if cache_key in _PHASE_REGISTRY_CACHE:
        return _PHASE_REGISTRY_CACHE[cache_key]

    if not resolved_path.exists():
        raise ValueError(f"Phase registry yaml file not found: {resolved_path} (pack_path_missing)")

    try:
        data = yaml.safe_load(resolved_path.read_text(encoding="utf-8"))
    except Exception as err:
        raise ValueError(f"Invalid YAML in phase registry at {resolved_path}: {err}") from err

    if not isinstance(data, dict) or "phases" not in data:
        raise ValueError(f"Invalid phase registry schema at {resolved_path}: missing 'phases' key")

    _PHASE_REGISTRY_CACHE[cache_key] = data
    return data


def get_phase_config(
    phase: str,
    *,
    pack_id: str | None = None,
    cwd: Path | str | None = None,
) -> dict[str, Any]:
    """Lookup phase config from registry; unknown phase raises ValueError fail-closed."""
    from loop.workflow.resolve import full_resolve
    from loop.workflow.registry import load_registry, get_pack

    resolved_pack = None
    hub_root_path = Path(__file__).resolve().parent.parent
    if pack_id is not None:
        reg_obj = load_registry()
        resolved_pack = get_pack(reg_obj, pack_id)
        try:
            registry = load_phase_registry(pack_id=pack_id, cwd=cwd)
        except Exception:
            registry = load_phase_registry(pack_id=pack_id, cwd=hub_root_path)
    else:
        resolve_res = full_resolve(cwd)
        resolved_pack = resolve_res.pack
        try:
            registry = load_phase_registry(pack_id=resolved_pack.id, cwd=cwd)
        except Exception:
            registry = load_phase_registry(pack_id=resolved_pack.id, cwd=hub_root_path)

    phases = registry.get("phases", {})
    normalized_phase = normalize_registry_phase(phase, resolved_pack)
    if normalized_phase not in phases:
        raise ValueError(f"unknown phase {phase!r}: fail-closed")
    return phases[normalized_phase]


def get_verify_agent(
    phase: str,
    *,
    pack_id: str | None = None,
    cwd: Path | str | None = None,
) -> str | None:
    """Lookup verify_agent for a phase from registry; unknown phase raises ValueError fail-closed."""
    cfg = get_phase_config(phase, pack_id=pack_id, cwd=cwd)
    return cfg.get("verify_agent")


def get_dsh_preset(
    phase: str,
    *,
    pack_id: str | None = None,
    cwd: Path | str | None = None,
) -> str | None:
    """Lookup dsh_preset for a phase from registry; unknown phase raises ValueError fail-closed."""
    cfg = get_phase_config(phase, pack_id=pack_id, cwd=cwd)
    return cfg.get("dsh_preset")


def resolve_next(cwd: Path | str, epic_id: str, role: str) -> EpicNextAction:
    """Delegate to resolve_epic_next_action — single entry point for next-action lookup."""
    return resolve_epic_next_action(cwd, role, epic_id)


def arm_phase(
    cwd: Path | str,
    epic_id: str,
    phase: str,
    role: str,
    *,
    pack_id: str | None = None,
    **kwargs: Any,
) -> dict:
    """Arm an epic phase context by routing to appropriate arm function."""
    from epic.core import active_context_path, arm_active_context_from_decompose, arm_epic, arm_pre_implement_context, load_epic_state
    from _lib import ActiveContextLocked, resolve_runtime_config
    from loop.workflow.resolve import full_resolve

    st_before = load_epic_state(cwd)
    last_finished = str(st_before.get("last_finished_step") or "").strip().lower()
    last_finished_epic = str(
        st_before.get("last_finished_epic") or st_before.get("armed_epic") or ""
    ).strip()

    if pack_id is None:
        try:
            resolve_res = full_resolve(cwd)
            pack_id = resolve_res.pack.id
        except Exception:
            pack_id = None

    runtime_cfg = resolve_runtime_config(cwd)
    epic_runtime = kwargs.get("epic_runtime") or runtime_cfg.epic_runtime
    if epic_runtime == "dsh":
        phase_config = get_phase_config(phase, pack_id=pack_id, cwd=cwd)
        dsh_preset = phase_config.get("dsh_preset")
        if dsh_preset is None:
            raise ValueError(f"no DSH preset for phase {phase!r}: fail-closed")
        kwargs["dsh_preset"] = dsh_preset

    phase_u = (phase or "").upper()
    decompose_rel = kwargs.get("decompose") or kwargs.get("decompose_rel")

    env = kwargs.get("env") or os.environ
    if phase_u in ("IMPLEMENT", "TASK", "REFACTOR", "BUGFIX") and env.get("EPIC_PARALLEL_SNN") == "1":
        from loop.parallel.orchestrator import run_parallel_wave
        from loop.paths.epic_layout import resolve, EpicLayoutKind
        cwd_p = Path(cwd).resolve()
        if decompose_rel:
            idx_path = cwd_p / decompose_rel
        else:
            idx_path = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=cwd_p)
            if not idx_path.is_file():
                idx_path = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_MD, project_root=cwd_p)
        if idx_path and idx_path.is_file():
            p_res = run_parallel_wave(epic_id, idx_path, cwd_p, env=env)
            if p_res and p_res.spawned:
                return {
                    "ok": True,
                    "parallel": True,
                    "wave": p_res.wave,
                    "spawned": p_res.spawned,
                    "failed": p_res.failed,
                    "armed_step": "IMPLEMENT",
                    "role": role,
                    "handoff": str(active_context_path(cwd_p).relative_to(cwd_p)),
                }

    try:
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
                kwargs.pop("env", None)
                kwargs.pop("epic_runtime", None)
                res = arm_epic(cwd, epic_id, role=role, **kwargs)
        else:
            kwargs.pop("env", None)
            kwargs.pop("epic_runtime", None)
            res = arm_epic(cwd, epic_id, role=role, **kwargs)
    except ActiveContextLocked as exc:
        return {
            "ok": False,
            "error": str(exc),
            "diagnostic_code": "runner_owns_active_context",
            "epic_id": epic_id,
            "phase": phase_u,
        }

    if isinstance(res, dict):
        if "armed_step" not in res:
            res["armed_step"] = res.get("step_id")
        if "handoff" not in res:
            res["handoff"] = res.get("active_context") or str(active_context_path(Path(cwd).resolve()).relative_to(Path(cwd).resolve()))
        if "role" not in res:
            res["role"] = role

        # Anti-loop: same epic + same step only. Cross-epic phase reuse (DECOMPOSE/PLAN/…) is allowed.
        armed_step_val = str(res.get("armed_step") or res.get("step_id") or "").strip().lower()
        armed_epic_val = str(res.get("epic_id") or epic_id or "").strip()
        same_epic = (not last_finished_epic) or (not armed_epic_val) or (
            last_finished_epic == armed_epic_val
        )
        if (
            same_epic
            and last_finished
            and armed_step_val
            and armed_step_val == last_finished
            and not res.get("complete")
            and not res.get("stop")
        ):
            return {
                "ok": False,
                "error": (
                    f"step_loop_forbidden: next step {armed_step_val} equals last finished step "
                    f"{last_finished} on epic {last_finished_epic or armed_epic_val}"
                ),
                "diagnostic_code": "step_loop_forbidden",
                "diagnostic_codes": ["step_loop_forbidden"],
                "last_finished_step": last_finished,
                "last_finished_epic": last_finished_epic or None,
                "armed_step": armed_step_val,
            }
        if (
            res.get("ok") is not False
            and last_finished_epic
            and armed_epic_val
            and last_finished_epic != armed_epic_val
        ):
            from epic.core import load_epic_state as _load, save_epic_state as _save

            st_after = _load(cwd)
            if st_after.get("last_finished_step") or st_after.get("last_finished_epic"):
                st_after["last_finished_step"] = None
                st_after["last_finished_epic"] = None
                st_after["armed_after_finish"] = None
                _save(cwd, st_after)
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
    from roadmap_queue import load_steps_for_index
    from loop.paths.epic_layout import resolve, EpicLayoutKind

    cwd_p = Path(cwd).resolve()
    st = load_epic_state(cwd_p)
    armed_step = str(st.get("armed_step") or "").upper()

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
        v2_idx = resolve(role_dir, epic, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=cwd_p)
        if v2_idx.is_file():
            idx_path = v2_idx
        else:
            v2_md = resolve(role_dir, epic, EpicLayoutKind.DECOMPOSE_INDEX_MD, project_root=cwd_p)
            if v2_md.is_file():
                idx_path = v2_md
    if idx_path is None or not idx_path.is_file():
        try:
            from roadmap_queue import find_decompose_index
            found = find_decompose_index(cwd_p, role_dir, epic)
            if found and Path(found).is_file():
                idx_path = Path(found)
        except Exception:
            pass
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
    arm_decompose_dir = decompose_rel
    if arm_decompose_dir.endswith(
        ("/index.yaml", "/index.yml", "/index.md")
    ):
        arm_decompose_dir = str(Path(arm_decompose_dir).parent).replace("\\", "/")
    arm_decompose_index = decompose_rel
    if not arm_decompose_index.endswith(
        ("/index.yaml", "/index.yml", "/index.md")
    ):
        yaml_cand = cwd_p / arm_decompose_index / "index.yaml"
        md_cand = cwd_p / arm_decompose_index / "index.md"
        if yaml_cand.is_file():
            arm_decompose_index = str(yaml_cand.relative_to(cwd_p)).replace("\\", "/")
        elif md_cand.is_file():
            arm_decompose_index = str(md_cand.relative_to(cwd_p)).replace("\\", "/")

    pending = [
        s
        for s in steps
        if str(s.get("status") or "").lower() not in {"completed", "done"}
    ]
    if not pending and armed_step not in _POST_IMPLEMENT_ARMED:
        from epic.core import post_implement_phase

        post_phase, _, _ = post_implement_phase(cwd_p, role_dir, epic)
        if post_phase == "AUDIT":
            res = arm_phase(
                cwd_p,
                epic,
                "AUDIT",
                role_dir,
                decompose_rel=arm_decompose_index,
            )
            if isinstance(res, dict) and res.get("ok"):
                res["promoted_from"] = armed_step or "IMPLEMENT"
                res["reason"] = "audit_promote"
                try:
                    from epic import _append_event
                    if idx_path and idx_path.is_file():
                        _append_event(cwd_p, role_dir, epic, "phase_transition", idx_path)
                except Exception:
                    pass
            return res if isinstance(res, dict) and res.get("ok") else None

    if armed_step not in _PROMOTABLE_PHASES:
        return None

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
                decompose_rel=arm_decompose_dir,
            )
            reason = "analyze_gate"
        else:
            res = arm_phase(
                cwd_p,
                epic,
                "IMPLEMENT",
                role_dir,
                decompose_rel=arm_decompose_index,
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
            decompose_rel=arm_decompose_index,
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
