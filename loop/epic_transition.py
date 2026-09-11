"""Transition Engine public API for T-HUB-029 and T-HUB-088.

Public contract:
  resolve_next(cwd, epic_id, role) -> EpicNextAction
  arm_phase(cwd, epic_id, phase, role, **kwargs) -> dict
  arm_epic(cwd, epic_id, *, role="back", require_plan=True, dsh_preset=None) -> dict
  promote_if_ready(cwd, epic_id, role) -> dict | None
  load_phase_registry(*, pack_id=None, cwd=None) -> dict
  get_phase_config(phase: str, *, pack_id=None, cwd=None) -> dict
  get_verify_agent(phase: str, *, pack_id=None, cwd=None) -> str | None
  get_dsh_preset(phase: str, *, pack_id=None, cwd=None) -> str | None
  _legacy_warn(caller_name) -> None
"""
from __future__ import annotations
import os
import re
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
_COMPOSITE_PHASE_BASES = {
    "PLAN REFACTOR": "PLAN",
}
_ARM_EPIC_KWARGS = frozenset({"require_plan", "dsh_preset"})
_LOOP_HANDOFF_SCHEMA = "loop-handoff/v1"
_LOOP_HANDOFF_SCHEMA_LINE = f"schema: {_LOOP_HANDOFF_SCHEMA}"


def _arm_epic_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Keep only kwargs accepted by arm_epic (drop decompose_rel/env/…)."""
    return {k: v for k, v in kwargs.items() if k in _ARM_EPIC_KWARGS}


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
    return _COMPOSITE_PHASE_BASES.get(normalized, normalized)


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

def _arm_post_implement(
    cwd: str | Path,
    *,
    epic_id: str,
    role: str,
    phase: str,
) -> dict[str, Any]:
    """Arm activeContext for post-implement phases (AUDIT, QA, BUGFIX)."""
    cwd_p = Path(cwd).resolve()
    from epic.core import (
        _write_active_context_or_lock,
        active_context_path,
        build_post_implement_active_context,
        clear_runner_checkpoint,
        find_qa_pass_artifact,
        load_epic_state,
        save_epic_state,
    )
    from epic_paths import find_decompose_index_path

    try:
        from loop.paths.pack_layout import resolve_mb_root
        mb_root = resolve_mb_root(cwd=cwd_p)
        mb_root_name = mb_root.name
    except Exception:
        mb_root_name = "memory-bank"

    qa_p = find_qa_pass_artifact(cwd_p, role, epic_id)
    resolved_idx = find_decompose_index_path(cwd_p, role, epic_id)
    if resolved_idx is not None:
        rel_idx = resolved_idx.relative_to(cwd_p).as_posix()
    else:
        from loop.paths.epic_layout import EpicLayoutKind, resolve as layout_resolve

        rel_idx = layout_resolve(
            role,
            epic_id,
            EpicLayoutKind.DECOMPOSE_INDEX_YAML,
            project_root=cwd_p,
        ).relative_to(cwd_p).as_posix()
    rel_md = rel_idx.removesuffix(".yaml") + ".md" if rel_idx.endswith(".yaml") else rel_idx
    link = rel_idx.removeprefix(f"{mb_root_name}/").removeprefix("memory-bank/")
    hub_rel = f"{mb_root_name}/hub/plan/plan-{epic_id}.md"
    role_u = {"back": "BACK", "front": "FRONT", "integration": "INTEG", "integ": "INTEG"}.get(
        str(role or "back").lower(), str(role or "BACK").upper()
    )
    body = build_post_implement_active_context(
        role=role_u,
        role_dir=role,
        epic_id=epic_id,
        tracker_rel=rel_idx,
        tracker_link=link,
        index_rel=rel_md,
        hub_rel=hub_rel if (cwd_p / hub_rel).is_file() else None,
        phase=phase,
        qa_path=qa_p if qa_p and qa_p.is_file() else None,
        cwd=cwd_p,
    )
    locked = _write_active_context_or_lock(active_context_path(cwd_p), body, epic_id=epic_id)
    if locked:
        return locked
    clear_runner_checkpoint(cwd_p)
    st = load_epic_state(cwd_p)
    st["active"] = True
    st["status"] = "armed"
    st["halt_reason"] = None
    st["armed_epic"] = epic_id
    st["armed_decompose"] = rel_idx
    st["armed_step"] = phase
    st["phase"] = phase
    st["role"] = role_u
    st["pending_fingerprint_before"] = None
    save_epic_state(cwd_p, st)
    return {
        "ok": True,
        "complete": False,
        "phase": phase,
        "epic_id": epic_id,
        "role": role_u,
        "step_id": phase,
        "status": "pending",
        "index": rel_idx,
        "active_context": str(active_context_path(cwd_p).relative_to(cwd_p)),
        "qa_path": str(qa_p.relative_to(cwd_p)) if qa_p and qa_p.is_file() else None,
    }


def _arm_done(
    cwd: str | Path,
    *,
    epic_id: str,
    role: str,
    dsh_preset: str | None = None,
) -> dict[str, Any]:
    """Arm DONE state."""
    cwd_p = Path(cwd).resolve()
    from epic.core import load_epic_state, save_epic_state
    st = load_epic_state(cwd_p)
    st["active"] = False
    st["status"] = "complete"
    st["halt_reason"] = None
    save_epic_state(cwd_p, st)
    res = {
        "ok": True,
        "complete": True,
        "stop": "EPIC_DONE",
        "phase": "DONE",
        "epic_id": epic_id,
        "role": role,
    }
    if dsh_preset:
        res["dsh_preset"] = dsh_preset
    return res


def _arm_from_decompose(
    cwd: str | Path,
    decompose: str,
) -> dict[str, Any]:
    from epic.core import (
        _decompose_index_path,
        _decompose_step_shards_dir,
        _render_loop_active_context,
        _resolve_href,
        _role_dir_from_index_path,
        _step_needs_creative,
        _write_active_context_or_lock,
        active_context_path,
        build_post_implement_active_context,
        clear_runner_checkpoint,
        effective_phase,
        find_next_decompose_step_from_queue,
        index_yaml_path,
        is_reserved_role_epic_id,
        load_decompose_steps_fail_closed,
        load_epic_state,
        post_implement_handoff_violates_epic_done,
        post_implement_phase,
        save_epic_state,
    )
    from epic_paths import epic_id_from_decompose_path
    """Overwrite activeContext from decompose index — ignore prior epic cursor.

    Used when human launches ``./loop/loop.sh decompose-<epic> …`` so the model
    starts on the chosen epic's next pending/active step even if activeContext
    still points at another epic or carries BLOCKED/NEED_HUMAN from it.
    """

    if decompose is None or not isinstance(decompose, (str, Path)):
        return {
            "ok": False,
            "error": f"invalid_arg: expected str/Path, got {type(decompose).__name__}",
        }
    cwd_p = Path(cwd)
    idx = _decompose_index_path(cwd_p, decompose)
    ypath = index_yaml_path(idx) if idx is not None else None
    if idx is None or (
        not idx.is_file() and not (ypath is not None and ypath.is_file())
    ):
        return {
            "ok": False,
            "error": f"decompose index not found: {decompose!r}",
        }

    loaded = load_decompose_steps_fail_closed(cwd_p, str(idx))
    if not loaded["ok"]:
        return loaded
    steps = loaded["steps"]
    # steps are loaded directly from YAML canon
    queue_src = loaded["source"]
    epic_id = epic_id_from_decompose_path(
        str(idx.relative_to(cwd_p)) if idx.is_relative_to(cwd_p) else str(idx)
    ) or epic_id_from_decompose_path(decompose)
    if is_reserved_role_epic_id(epic_id):
        return {
            "ok": False,
            "error": (
                f"epic_id must not be a role slug: {epic_id!r} "
                "(forbidden: back|front|integration|integ)"
            ),
            "diagnostic_code": "epic_id_reserved",
            "epic_id": epic_id,
        }
    role, role_dir = _role_dir_from_index_path(idx, cwd_p)
    index_rel = (
        str(idx.relative_to(cwd_p)).replace("\\", "/")
        if idx.is_relative_to(cwd_p)
        else str(idx)
    )
    ypath = index_yaml_path(idx)
    yaml_rel = (
        str(ypath.relative_to(cwd_p)).replace("\\", "/")
        if ypath.is_file() and ypath.is_relative_to(cwd_p)
        else (str(ypath) if ypath.is_file() else "")
    )
    tracker_rel = yaml_rel or index_rel
    tracker_link = tracker_rel.removeprefix("memory-bank/")

    step = find_next_decompose_step_from_queue(steps)
    if step is None:
        phase, qa_p, _ = post_implement_phase(cwd_p, role_dir, epic_id or "")
        body = build_post_implement_active_context(
            role=role,
            role_dir=role_dir,
            epic_id=epic_id or "unknown",
            tracker_rel=tracker_rel,
            tracker_link=tracker_link,
            index_rel=index_rel,
            hub_rel=None,
            phase=phase,
            qa_path=qa_p,
            cwd=cwd_p,
        )
        if post_implement_handoff_violates_epic_done(phase, body):
            return {
                "ok": False,
                "error": (
                    f"invariant: post-implement Handoff for phase={phase} "
                    "must not contain EPIC_DONE"
                ),
                "phase": phase,
                "epic_id": epic_id,
            }
        locked = _write_active_context_or_lock(active_context_path(cwd_p), body, epic_id=epic_id)
        if locked:
            return locked
        cleared = clear_runner_checkpoint(cwd_p)
        if not cleared.get("ok"):
            return {
                "ok": False,
                "error": "failed to clear runner checkpoint after arm",
                "diagnostic_code": cleared.get("diagnostic_code"),
                "checkpoint_clear": cleared,
                "epic_id": epic_id,
                "phase": phase,
            }
        st = load_epic_state(cwd_p)
        st["armed_epic"] = epic_id
        st["armed_decompose"] = tracker_rel
        st["armed_step"] = None
        st["role"] = role
        st["pending_fingerprint_before"] = None
        if phase == "DONE":
            st["active"] = False
            st["status"] = "complete"
            st["halt_reason"] = None
            save_epic_state(cwd_p, st)
            return {
                "ok": True,
                "complete": True,
                "stop": "EPIC_DONE",
                "phase": phase,
                "epic_id": epic_id,
                "role": role,
                "index": tracker_rel,
                "queue_source": queue_src,
                "active_context": str(active_context_path(cwd_p).relative_to(cwd_p)),
            }
        st["active"] = True
        st["status"] = "armed"
        st["halt_reason"] = None
        st["armed_step"] = phase
        save_epic_state(cwd_p, st)
        return {
            "ok": True,
            "complete": False,
            "stop": None,
            "phase": phase,
            "epic_id": epic_id,
            "role": role,
            "step_id": phase,
            "status": "pending",
            "index": tracker_rel,
            "queue_source": queue_src,
            "active_context": str(active_context_path(cwd_p).relative_to(cwd_p)),
            "qa_path": str(qa_p.relative_to(cwd_p)) if qa_p else None,
        }

    shard_rel = _resolve_href(_decompose_step_shards_dir(idx), step["shard_href"], cwd_p)
    if not shard_rel:
        steps_dir = _decompose_step_shards_dir(idx)
        guess = steps_dir / f"{step['step_id']}.yaml"
        if not guess.is_file():
            hits = sorted(steps_dir.glob(f"{step['step_id']}-*.yaml"))
            guess = hits[0] if hits else guess
        if guess.is_file():
            shard_rel = guess.relative_to(cwd_p).as_posix()
        else:
            return {
                "ok": False,
                "error": (
                    f"work shard for {step['step_id']} not found under {steps_dir}"
                ),
                "step_id": step["step_id"],
            }

    phase = effective_phase(
        role=role,
        next_phase=step["next_phase"],
        needs_creative=_step_needs_creative(cwd_p, idx, step),
    )
    title = step["title"] or step["step_id"]
    yaml_for_load = (
        tracker_rel if tracker_rel.endswith(".yaml") else yaml_rel or tracker_rel
    )
    shard_link = shard_rel.removeprefix("memory-bank/")
    yaml_link = yaml_for_load.removeprefix("memory-bank/")
    done_items: list[str] = []
    completed = [s["id"] for s in steps if s.get("status") in {"completed", "done"}]
    if completed:
        done_items.append(
            f"{completed[0]}–{completed[-1]} completed в `{tracker_link}` "
            f"({len(completed)} шагов)"
        )

    body = _render_loop_active_context(
        role=role,
        mode=phase,
        epic_id=epic_id or "unknown",
        step_id=step["step_id"],
        load_now=[
            (
                shard_link,
                f"текущий work shard ({phase} {step['step_id']})",
            ),
            (
                yaml_link,
                "очередь/status (canon=yaml)",
            ),
        ],
        custom_lines=[
            f"- **Эпик:** {epic_id} ({role}); armed из `{tracker_link}` "
            f"(прошлый activeContext игнорирован).",
            f"- **Текущий шаг:** {step['step_id']} — {title} "
            f"(status={step['status']} в index.yaml).",
            f"- **Команда:** `{phase} @{step['step_id']}`",
        ],
        next_hint=(
            "выполнить atomic шаг → FINISH "
            "(seed-implement → flush cp → suite → evidence in_progress → "
            "validate-step → Handoff → @verify → finalize-step)"
        ),
        done=done_items,
    )
    locked = _write_active_context_or_lock(active_context_path(cwd_p), body, epic_id=epic_id)
    if locked:
        return locked

    # Arm always rewrites activeContext. Drop runner checkpoint unconditionally —
    # same-step re-arm still changes context_fingerprint and would halt prepare with
    # checkpoint_projection_conflict if a prior committed/prepared checkpoint remains.
    cleared = clear_runner_checkpoint(cwd_p)
    if not cleared.get("ok"):
        return {
            "ok": False,
            "error": "failed to clear runner checkpoint after arm",
            "diagnostic_code": cleared.get("diagnostic_code"),
            "checkpoint_clear": cleared,
            "epic_id": epic_id,
            "step_id": step["step_id"],
        }

    st = load_epic_state(cwd_p)
    st["active"] = True
    st["status"] = "armed"
    st["halt_reason"] = None
    st["armed_epic"] = epic_id
    st["armed_decompose"] = tracker_rel
    st["armed_step"] = step["step_id"]
    st["phase"] = phase
    st["role"] = role
    st["pending_fingerprint_before"] = None
    save_epic_state(cwd_p, st)

    return {
        "ok": True,
        "complete": False,
        "epic_id": epic_id,
        "role": role,
        "step_id": step["step_id"],
        "status": step["status"],
        "phase": phase,
        "work_shard": shard_rel,
        "index": tracker_rel,
        "index_md": index_rel,
        "queue_source": queue_src,
        "implement_hub": None,
        "active_context": str(active_context_path(cwd_p).relative_to(cwd_p)),
        "checkpoint_cleared": True,
    }


def _arm_pre_implement(
    cwd: str | Path,
    *,
    epic_id: str,
    role: str,
    phase: str,
    target_rel: str | None,
    decompose_rel: str | None = None,
) -> dict[str, Any]:
    """Arm activeContext for pre-implement phases (PLAN, DECOMPOSE, CLARIFY, ANALYZE)."""
    from epic.core import (
        _LOOP_HANDOFF_SCHEMA_LINE,
        _write_active_context_or_lock,
        active_context_path,
        clear_runner_checkpoint,
        load_epic_state,
        save_epic_state,
    )

    cwd_p = Path(cwd)
    role_key = str(role or "back").lower()
    from epic_paths import epic_id_from_plan_path, find_plan_md_path

    resolved_plan = find_plan_md_path(cwd_p, role_key, epic_id)
    if resolved_plan is not None:
        full_id = epic_id_from_plan_path(resolved_plan)
        if full_id:
            epic_id = full_id

    phase_u = str(phase or "").upper()
    role_u = str(role or "back").upper()
    if target_rel:
        pass
    elif resolved_plan is not None:
        try:
            target_rel = resolved_plan.relative_to(cwd_p).as_posix()
        except ValueError:
            target_rel = str(resolved_plan).replace("\\", "/")
    else:
        from loop.paths.epic_layout import EpicLayoutKind, resolve as layout_resolve

        target_rel = layout_resolve(
            role_key, epic_id, EpicLayoutKind.PLAN_MD, project_root=cwd_p
        ).relative_to(cwd_p).as_posix()
    link = target_rel.removeprefix("memory-bank/")
    next_cmd = f"{role_u} {phase_u}"
    load_now = (
        f"1. [{Path(target_rel).name}]({link}) — source plan/artifact for pre-implement phase {phase_u}.\n"
    )
    armed_decompose: str | None = None
    if phase_u == "ANALYZE" and decompose_rel:
        decomp_yaml = decompose_rel
        if decomp_yaml.endswith("/md/decompose-index.md"):
            decomp_yaml = decomp_yaml[: -len("/md/decompose-index.md")] + "/yaml/decompose-index.yaml"
        elif decomp_yaml.endswith("decompose-index.md"):
            decomp_yaml = decomp_yaml[: -len("decompose-index.md")] + "decompose-index.yaml"
        elif decomp_yaml.endswith("index.md"):
            decomp_yaml = decomp_yaml[: -len("index.md")] + "index.yaml"
        decomp_link = decomp_yaml.removeprefix("memory-bank/")
        decomp_path = Path(decompose_rel)
        if decomp_path.name in {"decompose-index.yaml", "decompose-index.md"}:
            decomp_label = decomp_path.name
        elif decomp_path.suffix.lower() in {".yaml", ".yml", ".md"}:
            decomp_label = f"{decomp_path.parent.name}/{decomp_path.name}"
        else:
            decomp_label = f"{decomp_path.name}/index.yaml"
        load_now += (
            f"2. [`{decomp_label}`]({decomp_link}) — decompose index for ANALYZE gate.\n"
        )
        armed_decompose = decomp_yaml
    elif phase_u == "DECOMPOSE":
        from epic_paths import find_decompose_index_path
        from loop.paths.epic_layout import EpicLayoutKind, resolve as layout_resolve

        rule_dir = {
            "back": "back_developer",
            "front": "front_developer",
            "integration": "integration_developer",
        }.get(role_key, f"{role_key}_developer")
        idx = find_decompose_index_path(cwd_p, role_key, epic_id)
        v2_yaml = layout_resolve(
            role_key, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=cwd_p
        )
        v2_md = layout_resolve(
            role_key, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_MD, project_root=cwd_p
        )
        if idx and idx.is_file():
            decomp_yaml = idx.relative_to(cwd_p).as_posix()
            if idx.name in {"decompose-index.md", "index.md"}:
                sibling_yaml = idx.with_name(
                    "decompose-index.yaml" if idx.name == "decompose-index.md" else "index.yaml"
                )
                if sibling_yaml.is_file():
                    decomp_yaml = sibling_yaml.relative_to(cwd_p).as_posix()
                elif idx.name == "decompose-index.md":
                    decomp_yaml = v2_yaml.relative_to(cwd_p).as_posix()
        else:
            decomp_yaml = v2_yaml.relative_to(cwd_p).as_posix()
        decomp_link = decomp_yaml.removeprefix("memory-bank/")
        decomp_md_link = v2_md.relative_to(cwd_p).as_posix().removeprefix("memory-bank/")
        load_now += (
            f"2. `.cursor/templates/decompose/` — epic-step.yaml + index.md "
            f"(layout v2: md/decompose-index.md + yaml/decompose-index.yaml + yaml/steps/sNN-<slug>.yaml).\n"
            f"3. `.cursor/rules/{rule_dir}/workflow-decompose.mdc` — §Maximal detail + §Replacement cleanup.\n"
            f"4. Target decompose: [`decompose-index.yaml`]({decomp_link}) "
            f"(layout v2: `{decomp_md_link}` + `{decomp_link}` + `yaml/steps/sNN-<slug>.yaml`).\n"
        )
        armed_decompose = decomp_yaml if idx and idx.is_file() else None
    body = (
        f"---\n{_LOOP_HANDOFF_SCHEMA_LINE} # handoff\nrole: {role_u}\nmode: {phase_u}\nepic_id: {epic_id}\nstep_id: {phase_u}\n---\n\n"
        f"## load_now\n{load_now}\n"
        f"## Handoff {phase_u}\n"
        f"- # epic_id: {epic_id} — NOT short queue id\n"
        f"- **Эпик:** {epic_id} ({role_u}).\n"
        f"- **Режим/шаг:** `{next_cmd}`.\n"
        f"- **Дальше:** выполнить `{next_cmd}`.\n"
    )
    locked = _write_active_context_or_lock(active_context_path(cwd_p), body, epic_id=epic_id)
    if locked:
        return locked
    clear_runner_checkpoint(cwd_p)
    st = load_epic_state(cwd_p)
    st["active"] = True
    st["status"] = "armed"
    st["halt_reason"] = None
    st["armed_epic"] = epic_id
    st["armed_decompose"] = armed_decompose
    st["armed_step"] = phase_u
    st["phase"] = phase_u
    st["role"] = role
    st["pending_fingerprint_before"] = None
    save_epic_state(cwd_p, st)
    return {
        "ok": True,
        "complete": False,
        "phase": phase_u,
        "epic_id": epic_id,
        "role": role,
        "step_id": phase_u,
        "target_rel": target_rel,
        "active_context": str(active_context_path(cwd_p).relative_to(cwd_p)),
    }


def _legacy_mock_intercept(func_name: str, *args: Any, **kwargs: Any) -> tuple[bool, Any]:
    """Honor mock if a legacy test replaced a symbol on epic.core or epic."""
    try:
        import unittest.mock
        for mod_name in ("epic.core", "epic"):
            mod = sys.modules.get(mod_name)
            if mod is not None:
                fn = getattr(mod, func_name, None)
                if fn is not None and (
                    isinstance(fn, (unittest.mock.Mock, unittest.mock.MagicMock))
                    or getattr(fn, "__module__", "") not in ("epic.core", "epic", "harness.hooks.epic.core")
                    or getattr(fn, "__name__", "") != func_name
                ):
                    return True, fn(*args, **kwargs)
    except Exception as exc:
        raise exc
    return False, None


def arm_epic(
    cwd: str | Path,
    epic_id: str,
    *,
    role: str = "back",
    require_plan: bool = True,
    dsh_preset: str | None = None,
) -> dict[str, Any]:
    """Arm activeContext for epic via resolver (pre-implement / implement / post-implement)."""
    is_mock, mock_val = _legacy_mock_intercept(
        "arm_epic",
        cwd,
        epic_id,
        role=role,
        require_plan=require_plan,
        dsh_preset=dsh_preset,
    )
    if is_mock:
        return mock_val

    cwd_p = Path(cwd).resolve()
    from loop.board_sync.epic_resolver import resolve_epic_next_action

    action = resolve_epic_next_action(cwd_p, role, epic_id, require_plan=require_plan)
    phase = (action.phase or "").upper()
    if phase == "DONE":
        if action.decompose_rel:
            return arm_phase(cwd_p, epic_id, "IMPLEMENT", role, decompose_rel=action.decompose_rel)
        return {
            "ok": True,
            "complete": True,
            "stop": "EPIC_DONE",
            "phase": "DONE",
            "epic_id": epic_id,
            "role": role,
            **({"dsh_preset": dsh_preset} if dsh_preset else {}),
        }
    if phase in {"PLAN", "DECOMPOSE", "CLARIFY", "ANALYZE", "CREATIVE"}:
        return arm_phase(
            cwd_p,
            epic_id,
            phase,
            role,
            target_rel=action.plan_rel,
            decompose_rel=action.decompose_rel if phase == "ANALYZE" else None,
        )
    if phase == "IMPLEMENT":
        if not action.decompose_rel:
            return {
                "ok": False,
                "error": f"cannot arm epic {epic_id} in phase {phase} without decompose index",
            }
        if os.environ.get("EPIC_CONVERGENCE_CHECK") == "1":
            try:
                from epic.core import run_convergence_checks, logger
                findings = run_convergence_checks(cwd_p, epic_id)
                for f in findings:
                    if str(f.severity).upper() in {"HIGH", "CRITICAL"}:
                        logger.warning(
                            f"[convergence] {f.severity} finding in epic {epic_id}: {f.category} - {f.message}"
                        )
            except Exception as exc:
                pass
        return arm_phase(cwd_p, epic_id, "IMPLEMENT", role, decompose_rel=action.decompose_rel)
    if phase in {"AUDIT", "QA", "BUGFIX"}:
        return arm_phase(cwd_p, epic_id, phase, role, decompose_rel=action.decompose_rel)
    return {
        "ok": False,
        "error": f"unhandled phase {phase} for epic {epic_id}",
    }

def arm_phase(
    cwd: Path | str,
    epic_id: str,
    phase: str,
    role: str,
    *,
    pack_id: str | None = None,
    **kwargs: Any,
) -> dict:
    """Arm an epic phase context by executing canonical phase transition."""
    from _lib import ActiveContextLocked, resolve_runtime_config
    from loop.workflow.resolve import full_resolve
    from epic.core import active_context_path, load_epic_state

    cwd_p = Path(cwd).resolve()
    st_before = load_epic_state(cwd_p)
    last_finished = str(st_before.get("last_finished_step") or "").strip().lower()
    last_finished_epic = str(
        st_before.get("last_finished_epic") or st_before.get("armed_epic") or ""
    ).strip()

    if pack_id is None:
        try:
            resolve_res = full_resolve(cwd_p)
            pack_id = resolve_res.pack.id
        except Exception:
            pack_id = None

    runtime_cfg = resolve_runtime_config(cwd_p)
    epic_runtime = kwargs.get("epic_runtime") or runtime_cfg.epic_runtime
    if epic_runtime == "dsh":
        phase_config = get_phase_config(phase, pack_id=pack_id, cwd=cwd_p)
        dsh_preset = phase_config.get("dsh_preset")
        if dsh_preset is None:
            raise ValueError(f"no DSH preset for phase {phase!r}: fail-closed")
        kwargs["dsh_preset"] = dsh_preset

    phase_u = (phase or "").upper()
    lifecycle_phase_u = normalize_registry_phase(phase_u)
    decompose_rel = kwargs.get("decompose") or kwargs.get("decompose_rel")

    env = kwargs.get("env") or os.environ
    if phase_u in ("IMPLEMENT", "TASK", "REFACTOR", "BUGFIX") and env.get("EPIC_PARALLEL_SNN") == "1":
        from loop.parallel.orchestrator import run_parallel_wave
        from loop.paths.epic_layout import resolve, EpicLayoutKind
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
        # Legacy test mock intercept
        if lifecycle_phase_u in ("PLAN", "CLARIFY", "ANALYZE", "CREATIVE"):
            is_mock, mock_val = _legacy_mock_intercept(
                "arm_pre_implement_context",
                cwd_p,
                epic_id=epic_id,
                role=role,
                phase=lifecycle_phase_u,
                target_rel=kwargs.get("target_rel") or kwargs.get("plan_rel"),
                decompose_rel=decompose_rel,
            )
            if is_mock:
                res = mock_val
            else:
                target_rel = kwargs.get("target_rel") or kwargs.get("plan_rel")
                res = _arm_pre_implement(
                    cwd_p,
                    epic_id=epic_id,
                    role=role,
                    phase=lifecycle_phase_u,
                    target_rel=target_rel,
                    decompose_rel=decompose_rel,
                )
        elif lifecycle_phase_u == "DECOMPOSE":
            if decompose_rel:
                is_mock, mock_val = _legacy_mock_intercept(
                    "arm_active_context_from_decompose", cwd_p, decompose_rel
                )
                if is_mock:
                    res = mock_val
                else:
                    res = _arm_from_decompose(cwd_p, decompose_rel)
            else:
                is_mock, mock_val = _legacy_mock_intercept(
                    "arm_pre_implement_context",
                    cwd_p,
                    epic_id=epic_id,
                    role=role,
                    phase=lifecycle_phase_u,
                    target_rel=kwargs.get("target_rel") or kwargs.get("plan_rel"),
                    decompose_rel=decompose_rel,
                )
                if is_mock:
                    res = mock_val
                else:
                    target_rel = kwargs.get("target_rel") or kwargs.get("plan_rel")
                    res = _arm_pre_implement(
                        cwd_p,
                        epic_id=epic_id,
                        role=role,
                        phase=lifecycle_phase_u,
                        target_rel=target_rel,
                        decompose_rel=decompose_rel,
                    )
        elif lifecycle_phase_u in ("IMPLEMENT", "TASK", "REFACTOR"):
            if decompose_rel:
                is_mock, mock_val = _legacy_mock_intercept(
                    "arm_active_context_from_decompose", cwd_p, decompose_rel
                )
                if is_mock:
                    res = mock_val
                else:
                    res = _arm_from_decompose(cwd_p, decompose_rel)
            else:
                res = arm_epic(cwd_p, epic_id, role=role, **_arm_epic_kwargs(kwargs))
        elif lifecycle_phase_u in ("AUDIT", "QA", "BUGFIX"):
            if decompose_rel:
                is_mock, mock_val = _legacy_mock_intercept(
                    "arm_active_context_from_decompose", cwd_p, decompose_rel
                )
                if is_mock:
                    res = mock_val
                else:
                    res = _arm_from_decompose(cwd_p, decompose_rel)
            else:
                res = _arm_post_implement(
                    cwd_p,
                    epic_id=epic_id,
                    role=role,
                    phase=lifecycle_phase_u,
                )
        elif lifecycle_phase_u == "DONE":
            if decompose_rel:
                res = _arm_from_decompose(cwd_p, decompose_rel)
            else:
                res = _arm_done(
                    cwd_p,
                    epic_id=epic_id,
                    role=role,
                    dsh_preset=kwargs.get("dsh_preset"),
                )
        else:
            is_mock, mock_val = _legacy_mock_intercept("arm_epic", cwd_p, epic_id, role=role, **_arm_epic_kwargs(kwargs))
            if is_mock:
                res = mock_val
            else:
                res = arm_epic(cwd_p, epic_id, role=role, **_arm_epic_kwargs(kwargs))
    except ActiveContextLocked as exc:
        return {
            "ok": False,
            "diagnostic_code": "runner_owns_active_context",
            "epic_id": epic_id,
            "phase": phase_u,
        }

    if isinstance(res, dict):
        if "armed_step" not in res:
            res["armed_step"] = res.get("step_id")
        if "handoff" not in res:
            res["handoff"] = res.get("active_context") or str(active_context_path(cwd_p).relative_to(cwd_p))
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

            st_after = _load(cwd_p)
            if st_after.get("last_finished_step") or st_after.get("last_finished_epic"):
                st_after["last_finished_step"] = None
                st_after["last_finished_epic"] = None
                st_after["armed_after_finish"] = None
                _save(cwd_p, st_after)
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

    # ANALYZE → IMPLEMENT is a gate transition.  An artifact or a manually
    # edited activeContext cannot substitute for a fresh receipt bound to the
    # current projection.
    if armed_step == "ANALYZE":
        # A manually edited IMPLEMENT handoff is handled by prepare_session,
        # which re-arms ANALYZE after rejecting the missing/stale receipt.  Do
        # not turn that drift into an implicit promotion here.
        active_context = cwd_p / "memory-bank" / "activeContext.md"
        try:
            active_text = active_context.read_text(encoding="utf-8", errors="replace")
        except OSError:
            active_text = ""
        if re.search(r"(?im)^\s*mode:\s*IMPLEMENT\b", active_text) or re.search(
            r"(?im)^##\s*Handoff\s+(?:BACK|FRONT|INTEG(?:RATION)?)\s+IMPLEMENT\b",
            active_text,
        ):
            return None
        from loop.session_finalize import analyze_promotion_requires_bound_receipt

        # Arrival at ANALYZE after DECOMPOSE must not fail-closed on a stale
        # foreign receipt (e.g. previous epic BUGFIX). Bound receipt is required
        # only after ANALYZE itself finished.
        if analyze_promotion_requires_bound_receipt(st):
            evidence = st.get("last_verify_evidence") or st.get("last_verify_receipt")
            if not evidence:
                return {
                    "ok": False,
                    "error": "ANALYZE promotion requires verifier receipt",
                    "diagnostic_code": "gate_evidence_missing",
                }
            try:
                from epic.core import gate_evidence_matches
                matched, diagnostic = gate_evidence_matches(cwd_p, evidence)
            except Exception as exc:
                return {
                    "ok": False,
                    "error": f"ANALYZE promotion gate validation failed: {exc}",
                    "diagnostic_code": "gate_evidence_invalid",
                }
            if not matched:
                return {
                    "ok": False,
                    "error": f"ANALYZE promotion rejected: {diagnostic}",
                    "diagnostic_code": diagnostic,
                }

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

    from loop.decompose_gate import decompose_shards_diagnostic, decompose_verify_pass_ready

    shard_diagnostic = decompose_shards_diagnostic(idx_path, steps)
    if shard_diagnostic:
        # This is deliberately checked before analyze_gate: an analyze
        # artifact cannot promote an incomplete decompose graph.
        return None

    if armed_step == "DECOMPOSE":
        verify = decompose_verify_pass_ready(cwd_p, st)
        if not verify.get("ok"):
            # Stay on DECOMPOSE (repair exhausted / prepare retry). Do not
            # fail-closed halt prepare — return None so the same phase reruns.
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
