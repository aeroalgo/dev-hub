"""Roadmap queue canon — parse machine YAML, pick next epic, smart-arm entry."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
if str(HOOKS) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(HOOKS))

from epic import (  # noqa: E402
    arm_active_context_from_decompose,
    atomic_write_text,
    find_next_decompose_step_from_queue,
    load_decompose_steps_fail_closed,
    load_epic_state,
    post_implement_phase,
    save_epic_state,
)
from epic.core import active_context_path, checkpoint_lock_path, checkpoint_path, load_checkpoint  # noqa: E402
from epic_paths import epic_id_from_decompose_path  # noqa: E402
from _lib import merged_project_env_map  # noqa: E402
from analyze_gate import analyze_required_before_implement  # noqa: E402

QUEUE_VERSION = "roadmap-queue/v1"
DEFAULT_ROADMAP = "memory-bank/back/plan/roadmap-epics.md"
DEFAULT_QUEUE = "memory-bank/back/plan/roadmap-epics.queue.yaml"


def queue_rel_from_roadmap(roadmap_rel: str) -> str:
    """Sibling machine file: roadmap-foo-epics.md → roadmap-foo-epics.queue.yaml."""
    rel = str(roadmap_rel).replace("\\", "/")
    if rel.endswith(".queue.yaml"):
        return rel
    if rel.endswith(".md"):
        return rel[: -len(".md")] + ".queue.yaml"
    return rel + ".queue.yaml"


def epic_chain_roadmap_enabled(cwd: str | Path | None = None) -> bool:
    raw = os.environ.get("EPIC_CHAIN_ROADMAP")
    if raw is None:
        raw = merged_project_env_map(cwd).get("EPIC_CHAIN_ROADMAP", "0")
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _validate_queue_doc(data: Any, *, path: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {
            "ok": False,
            "error": "queue_yaml_invalid",
            "reason": "queue root must be a mapping",
            "path": path,
        }
    version = str(data.get("version") or "")
    if version != QUEUE_VERSION:
        return {
            "ok": False,
            "error": "queue_version_mismatch",
            "reason": f"expected {QUEUE_VERSION}, got {version!r}",
            "path": path,
        }
    role = str(data.get("role") or "back").strip().lower()
    if role not in {"back", "front", "integration"}:
        return {
            "ok": False,
            "error": "queue_yaml_invalid",
            "reason": f"unsupported role: {role!r}",
            "path": path,
        }
    raw_queue = data.get("queue")
    if not isinstance(raw_queue, list) or not raw_queue:
        return {
            "ok": False,
            "error": "queue_yaml_invalid",
            "reason": "queue must be a non-empty list",
            "path": path,
        }
    queue: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, item in enumerate(raw_queue):
        if not isinstance(item, dict):
            return {
                "ok": False,
                "error": "queue_yaml_invalid",
                "reason": f"queue[{i}] must be a mapping",
                "path": path,
            }
        epic_id = str(item.get("id") or "").strip()
        plan = str(item.get("plan") or "").strip()
        deps_raw = item.get("deps") if "deps" in item else []
        if not epic_id or not plan:
            return {
                "ok": False,
                "error": "queue_yaml_invalid",
                "reason": f"queue[{i}] requires id and plan",
                "path": path,
            }
        if epic_id in seen:
            return {
                "ok": False,
                "error": "queue_yaml_invalid",
                "reason": f"duplicate epic id: {epic_id}",
                "path": path,
            }
        if not isinstance(deps_raw, list):
            return {
                "ok": False,
                "error": "queue_yaml_invalid",
                "reason": f"queue[{i}].deps must be a list",
                "path": path,
            }
        deps = [str(d).strip() for d in deps_raw if str(d).strip()]
        seen.add(epic_id)
        queue.append({"id": epic_id, "plan": plan, "deps": deps})
    roadmap = str(data.get("roadmap") or data.get("path") or "").strip()
    return {
        "ok": True,
        "version": version,
        "role": role,
        "path": path,
        "roadmap": roadmap or None,
        "queue": queue,
    }


def parse_roadmap_queue(
    cwd: str | Path,
    *,
    queue_rel: str | None = None,
    roadmap_rel: str | None = None,
) -> dict[str, Any]:
    """Parse sibling `.queue.yaml` (machine canon). Fail-closed on errors.

    Prefers ``queue_rel``. If only ``roadmap_rel`` is given, loads
    ``roadmap-….md`` → ``roadmap-….queue.yaml``. Default: ``DEFAULT_QUEUE``.
    """
    root = Path(cwd)
    if queue_rel:
        rel = queue_rel
    elif roadmap_rel:
        rel = queue_rel_from_roadmap(roadmap_rel)
    else:
        rel = DEFAULT_QUEUE
    path = root / rel
    if not path.is_file():
        return {
            "ok": False,
            "error": "queue_yaml_missing",
            "reason": f"queue yaml not found: {rel}",
            "path": rel,
        }
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return {
            "ok": False,
            "error": "queue_yaml_invalid",
            "reason": f"yaml parse error: {exc}",
            "path": rel,
        }
    return _validate_queue_doc(data, path=rel)


def find_decompose_index(cwd: str | Path, role: str, epic_id: str) -> Path | None:
    root = Path(cwd)
    plan_dir = root / "memory-bank" / role / "plan"
    if not plan_dir.is_dir():
        return None
    exact = plan_dir / f"decompose-{epic_id}" / "index.yaml"
    if exact.is_file():
        return exact
    md_exact = plan_dir / f"decompose-{epic_id}" / "index.md"
    if md_exact.is_file():
        return md_exact
    matches = sorted(plan_dir.glob(f"decompose-{epic_id}-*"))
    for d in matches:
        if not d.is_dir():
            continue
        y = d / "index.yaml"
        if y.is_file():
            return y
        m = d / "index.md"
        if m.is_file():
            return m
    return None


def load_steps_for_index(cwd: str | Path, idx: Path) -> dict[str, Any]:
    """Load decompose steps; support yaml-only indexes (no index.md yet)."""
    root = Path(cwd)
    from epic_index import load_index_yaml, steps_from_doc

    if idx.name == "index.yaml" and idx.is_file():
        md = idx.with_name("index.md")
        if md.is_file():
            try:
                rel = md.relative_to(root).as_posix()
            except ValueError:
                rel = str(md)
            return load_decompose_steps_fail_closed(cwd, rel)
        doc = load_index_yaml(idx) or {}
        return {"ok": True, "steps": steps_from_doc(doc), "source": "yaml"}
    try:
        rel = idx.relative_to(root).as_posix()
    except ValueError:
        rel = str(idx)
    return load_decompose_steps_fail_closed(cwd, rel)


def plan_path(cwd: str | Path, role: str, plan_name: str) -> Path:
    return Path(cwd) / "memory-bank" / role / "plan" / plan_name


def resolve_epic_slug(cwd: str | Path, role: str, queue_id: str) -> str:
    """Map queue id (T-005) to artifact epic slug (T-005-docker-linux-runtime)."""
    idx = find_decompose_index(cwd, role, queue_id)
    if idx is not None:
        slug = epic_id_from_decompose_path(str(idx))
        if slug:
            return slug
    root = Path(cwd)
    refl_dir = root / "memory-bank" / role / "reflection"
    if refl_dir.is_dir():
        exact = refl_dir / f"reflection-{queue_id}.md"
        if exact.is_file():
            return queue_id
        hits = sorted(refl_dir.glob(f"reflection-{queue_id}-*.md"))
        if hits:
            name = hits[0].name
            return name[len("reflection-") : -len(".md")]
    qa_dir = root / "memory-bank" / role / "qa"
    if qa_dir.is_dir():
        if (qa_dir / queue_id).is_dir():
            return queue_id
        hits = sorted(
            p for p in qa_dir.iterdir() if p.is_dir() and p.name.startswith(f"{queue_id}-")
        )
        if hits:
            return hits[0].name
    return queue_id


def is_epic_done(cwd: str | Path, role: str, epic_id: str) -> bool:
    slug = resolve_epic_slug(cwd, role, epic_id)
    phase, _qa, _refl = post_implement_phase(cwd, role, slug)
    if phase == "DONE":
        return True
    idx = find_decompose_index(cwd, role, epic_id)
    if idx is None:
        return False
    loaded = load_steps_for_index(cwd, idx)
    if not loaded.get("ok"):
        return False
    steps = loaded.get("steps") or []
    if not steps:
        return False
    if find_next_decompose_step_from_queue(steps) is not None:
        return False
    phase2, _qa2, _refl2 = post_implement_phase(cwd, role, slug)
    return phase2 == "DONE"


def resolve_entry(
    cwd: str | Path,
    *,
    role: str,
    epic_id: str,
    plan_name: str,
) -> dict[str, Any]:
    """Smart entry: DECOMPOSE / ANALYZE / IMPLEMENT|CREATIVE / QA / REFLECT / done."""
    root = Path(cwd)
    slug = resolve_epic_slug(root, role, epic_id)
    plan = plan_path(root, role, plan_name)
    if not plan.is_file():
        return {
            "ok": False,
            "halt": True,
            "stop": f"NEED_HUMAN: no_plan for {epic_id}",
            "reason": f"plan missing: {plan.as_posix()}",
            "epic": slug,
            "queue_id": epic_id,
            "phase": None,
        }
    idx = find_decompose_index(root, role, epic_id)
    if idx is None:
        return {
            "ok": True,
            "epic": slug,
            "queue_id": epic_id,
            "phase": "DECOMPOSE",
            "plan": plan.relative_to(root).as_posix(),
            "decompose": None,
        }
    loaded = load_steps_for_index(root, idx)
    if not loaded.get("ok"):
        return {
            "ok": False,
            "halt": True,
            "stop": f"NEED_HUMAN: index_invalid for {epic_id}",
            "reason": loaded.get("reason") or loaded.get("error") or "index invalid",
            "epic": slug,
            "queue_id": epic_id,
            "phase": None,
        }
    steps = loaded.get("steps") or []
    next_step = find_next_decompose_step_from_queue(steps)
    decomp_rel = idx.relative_to(root).as_posix()
    if next_step is not None:
        gate = analyze_required_before_implement(
            root, role, slug, steps, index_path=idx
        )
        plan_rel = plan.relative_to(root).as_posix()
        if gate.get("required"):
            return {
                "ok": True,
                "epic": slug,
                "queue_id": epic_id,
                "phase": "ANALYZE",
                "plan": plan_rel,
                "decompose": decomp_rel,
                "step_id": next_step.get("step_id"),
                "analyze_reason": gate.get("reason"),
                "analyze_path": gate.get("analyze_path"),
                "critical_count": gate.get("critical_count"),
            }
        return {
            "ok": True,
            "epic": slug,
            "queue_id": epic_id,
            "phase": "IMPLEMENT",
            "plan": plan_rel,
            "decompose": decomp_rel,
            "step_id": next_step.get("step_id"),
        }
    phase, qa, refl = post_implement_phase(root, role, slug)
    if phase == "DONE":
        return {
            "ok": True,
            "epic": slug,
            "queue_id": epic_id,
            "phase": "DONE",
            "plan": plan.relative_to(root).as_posix(),
            "decompose": decomp_rel,
            "done": True,
        }
    return {
        "ok": True,
        "epic": slug,
        "queue_id": epic_id,
        "phase": phase,
        "plan": plan.relative_to(root).as_posix(),
        "decompose": decomp_rel,
        "qa_path": str(qa) if qa else None,
        "reflection_path": str(refl) if refl else None,
    }


def select_next_epic(
    cwd: str | Path,
    *,
    queue_rel: str | None = None,
    roadmap_rel: str | None = None,
    skip_epic: str | None = None,
) -> dict[str, Any]:
    """First not-done epic with hard deps satisfied."""
    parsed = parse_roadmap_queue(
        cwd, queue_rel=queue_rel, roadmap_rel=roadmap_rel
    )
    if not parsed.get("ok"):
        return parsed
    role = parsed["role"]
    queue = parsed["queue"]
    done_ids: set[str] = set()
    for item in queue:
        if is_epic_done(cwd, role, item["id"]):
            done_ids.add(item["id"])
    if skip_epic:
        for item in queue:
            slug = resolve_epic_slug(cwd, role, item["id"])
            if (
                item["id"] == skip_epic
                or slug == skip_epic
                or str(skip_epic).startswith(item["id"] + "-")
            ):
                done_ids.add(item["id"])
    blocked: list[dict[str, Any]] = []
    for item in queue:
        epic_id = item["id"]
        if epic_id in done_ids:
            continue
        missing = [d for d in item["deps"] if d not in done_ids]
        if missing:
            blocked.append({"id": epic_id, "missing_deps": missing})
            continue
        entry = resolve_entry(
            cwd, role=role, epic_id=epic_id, plan_name=item["plan"]
        )
        if entry.get("done") or entry.get("phase") == "DONE":
            done_ids.add(epic_id)
            continue
        if not entry.get("ok"):
            return entry
        return {
            "ok": True,
            "role": role,
            "item": item,
            "entry": entry,
            "done_ids": sorted(done_ids),
            "blocked": blocked,
            "path": parsed["path"],
        }
    if blocked and not any(
        item["id"] not in done_ids
        and item["id"] not in {b["id"] for b in blocked}
        for item in queue
    ):
        return {
            "ok": False,
            "halt": True,
            "stop": "NEED_HUMAN: roadmap_deps_blocked",
            "reason": "remaining epics blocked by unmet hard deps",
            "blocked": blocked,
            "done_ids": sorted(done_ids),
        }
    return {
        "ok": True,
        "complete": True,
        "stop": "ROADMAP_DONE",
        "reason": "all roadmap epics done",
        "done_ids": sorted(done_ids),
        "blocked": blocked,
        "role": role,
        "path": parsed["path"],
    }


def _clear_checkpoint(cwd: Path) -> None:
    from epic import clear_runner_checkpoint

    clear_runner_checkpoint(cwd)


def _arm_analyze_context(
    cwd: Path,
    *,
    role: str,
    epic_id: str,
    plan_rel: str,
    decompose_rel: str,
    analyze_reason: str,
) -> dict[str, Any]:
    from epic_paths import is_reserved_role_epic_id

    if is_reserved_role_epic_id(epic_id):
        return {
            "ok": False,
            "armed": False,
            "reason": (
                f"epic_id must not be a role slug: {epic_id!r} "
                "(forbidden: back|front|integration|integ)"
            ),
            "diagnostic_code": "epic_id_reserved",
            "epic": epic_id,
        }
    if role == "integration":
        role_u = "INTEG"
    elif role == "front":
        role_u = "FRONT"
    else:
        role_u = "BACK"
    plan_name = Path(plan_rel).name
    plan_link = plan_rel.removeprefix("memory-bank/")
    decomp_yaml = decompose_rel
    if decomp_yaml.endswith("index.md"):
        decomp_yaml = decomp_yaml[: -len("index.md")] + "index.yaml"
    decomp_link = decomp_yaml.removeprefix("memory-bank/")
    decomp_dir = Path(decompose_rel).parent.name
    body = (
        f"## load_now\n"
        f"- [{plan_name}]({plan_link})\n"
        f"- [`{decomp_dir}/index.yaml`]({decomp_link})\n"
        f"\n"
        f"## Handoff {role_u} ANALYZE — {epic_id}\n"
        f"- **Эпик:** {epic_id}\n"
        f"- **Статус:** PENDING ANALYZE (pre-IMPLEMENT gate)\n"
        f"- **Reason:** {analyze_reason}\n"
        f"- **Дальше:**\n"
        f"  - `{role_u} ANALYZE` → `memory-bank/{role}/analyze/{epic_id}/analyze-*.yaml`\n"
        f"  - При `critical_count > 0`: fix plan/decompose → `@analyze-verify` → "
        f"re-ANALYZE или fix до `critical_count=0`\n"
        f"  - Loop откроет IMPLEMENT когда gate pass\n"
        f"\n"
        f"## done\n"
        f"- Roadmap advance: armed ANALYZE for {epic_id}.\n"
    )
    _clear_checkpoint(cwd)
    atomic_write_text(active_context_path(cwd), body)
    st = load_epic_state(cwd)
    st["armed_epic"] = epic_id
    st["armed_decompose"] = decomp_yaml
    st["armed_step"] = "ANALYZE"
    st["role"] = role_u
    st["active"] = True
    st["status"] = "armed"
    st["halt_reason"] = None
    st["pending_fingerprint_before"] = None
    save_epic_state(cwd, st)
    return {
        "ok": True,
        "armed": True,
        "complete": False,
        "epic": epic_id,
        "phase": "ANALYZE",
        "plan": plan_rel,
        "decompose": decompose_rel,
        "role": role_u,
        "analyze_reason": analyze_reason,
    }


def _arm_decompose_context(
    cwd: Path,
    *,
    role: str,
    epic_id: str,
    plan_rel: str,
) -> dict[str, Any]:
    from epic_paths import is_reserved_role_epic_id

    if is_reserved_role_epic_id(epic_id):
        return {
            "ok": False,
            "armed": False,
            "reason": (
                f"epic_id must not be a role slug: {epic_id!r} "
                "(forbidden: back|front|integration|integ)"
            ),
            "diagnostic_code": "epic_id_reserved",
            "epic": epic_id,
        }
    if role == "integration":
        role_u = "INTEG"
    elif role == "front":
        role_u = "FRONT"
    else:
        role_u = "BACK"
    plan_name = Path(plan_rel).name
    link = plan_rel.removeprefix("memory-bank/")
    body = (
        f"## load_now\n"
        f"- [{plan_name}]({link})\n"
        f"\n"
        f"## Handoff {role_u} DECOMPOSE — {epic_id}\n"
        f"- **Эпик:** {epic_id}\n"
        f"- **Статус:** PENDING DECOMPOSE\n"
        f"- **Дальше:**\n"
        f"  - Создать `memory-bank/{role}/plan/decompose-{epic_id}/` "
        f"(`index.yaml` + `index.md` + sNN shards) по плану.\n"
        f"\n"
        f"## done\n"
        f"- Roadmap advance: armed DECOMPOSE for {epic_id}.\n"
    )
    _clear_checkpoint(cwd)
    atomic_write_text(active_context_path(cwd), body)
    st = load_epic_state(cwd)
    st["armed_epic"] = epic_id
    st["armed_decompose"] = None
    st["armed_step"] = "DECOMPOSE"
    st["role"] = role_u
    st["active"] = True
    st["status"] = "armed"
    st["halt_reason"] = None
    st["pending_fingerprint_before"] = None
    save_epic_state(cwd, st)
    return {
        "ok": True,
        "armed": True,
        "complete": False,
        "epic": epic_id,
        "phase": "DECOMPOSE",
        "plan": plan_rel,
        "role": role_u,
    }


def arm_roadmap_entry(cwd: str | Path, selection: dict[str, Any]) -> dict[str, Any]:
    """Apply smart entry: rewrite activeContext + epic state."""
    root = Path(cwd)
    role = selection["role"]
    entry = selection["entry"]
    epic_id = entry["epic"]
    phase = entry["phase"]
    if phase == "DECOMPOSE":
        return _arm_decompose_context(
            root,
            role=role,
            epic_id=entry.get("queue_id") or epic_id,
            plan_rel=entry["plan"],
        )
    if phase == "ANALYZE":
        decompose = entry.get("decompose")
        if not decompose:
            return {
                "ok": False,
                "armed": False,
                "reason": "missing decompose for ANALYZE",
                "epic": epic_id,
            }
        return _arm_analyze_context(
            root,
            role=role,
            epic_id=entry.get("queue_id") or epic_id,
            plan_rel=entry["plan"],
            decompose_rel=decompose,
            analyze_reason=str(entry.get("analyze_reason") or "analyze_required"),
        )
    decompose = entry.get("decompose")
    if not decompose:
        return {
            "ok": False,
            "armed": False,
            "reason": f"missing decompose for phase={phase}",
            "epic": epic_id,
        }
    decomp_path = root / decompose
    # arm_active_context_from_decompose resolves via index.md
    if decomp_path.name == "index.yaml":
        md = decomp_path.with_name("index.md")
        if not md.is_file():
            md.write_text(
                f"# Decompose {epic_id}\n\n"
                f"| step_id | title | status |\n"
                f"| :--- | :--- | :--- |\n",
                encoding="utf-8",
            )
        try:
            decompose = md.relative_to(root).as_posix()
        except ValueError:
            decompose = str(md)
    elif decomp_path.is_dir():
        md = decomp_path / "index.md"
        if not md.is_file():
            md.write_text(f"# Decompose {epic_id}\n", encoding="utf-8")
        try:
            decompose = decomp_path.relative_to(root).as_posix()
        except ValueError:
            decompose = str(decomp_path)
    out = arm_active_context_from_decompose(root, decompose)
    if not out.get("ok"):
        return {
            "ok": False,
            "armed": False,
            "epic": epic_id,
            "phase": phase,
            "reason": out.get("error") or out.get("reason") or "arm failed",
            "arm": out,
        }
    if out.get("complete"):
        return {
            "ok": True,
            "armed": False,
            "complete": True,
            "epic": epic_id,
            "phase": "DONE",
            "stop": "EPIC_DONE",
            "arm": out,
        }
    st = load_epic_state(root)
    st["armed_epic"] = epic_id
    st["active"] = True
    st["status"] = "armed"
    st["halt_reason"] = None
    save_epic_state(root, st)
    return {
        "ok": True,
        "armed": True,
        "complete": False,
        "epic": epic_id,
        "phase": out.get("phase") or phase,
        "step_id": out.get("step_id"),
        "decompose": decompose,
        "role": out.get("role"),
        "arm": out,
    }


def roadmap_advance(
    cwd: str | Path,
    *,
    queue_rel: str | None = None,
    roadmap_rel: str | None = None,
    skip_epic: str | None = None,
) -> dict[str, Any]:
    """Select and arm the next roadmap epic (opt-in chain after EPIC_DONE)."""
    if skip_epic is None:
        st = load_epic_state(cwd)
        skip_epic = (st.get("armed_epic") or "").strip() or None
    selected = select_next_epic(
        cwd,
        queue_rel=queue_rel,
        roadmap_rel=roadmap_rel,
        skip_epic=skip_epic,
    )
    if selected.get("complete"):
        return {
            "ok": True,
            "armed": False,
            "complete": True,
            "stop": "ROADMAP_DONE",
            "reason": selected.get("reason"),
            "done_ids": selected.get("done_ids"),
        }
    if not selected.get("ok"):
        return {
            "ok": False,
            "armed": False,
            "complete": False,
            "halt": bool(selected.get("halt")),
            "stop": selected.get("stop"),
            "reason": selected.get("reason") or selected.get("error"),
            "error": selected.get("error"),
            "blocked": selected.get("blocked"),
        }
    armed = arm_roadmap_entry(cwd, selected)
    armed["done_ids"] = selected.get("done_ids")
    armed["blocked"] = selected.get("blocked")
    armed["path"] = selected.get("path")
    return armed


CANON_QUEUE_BASENAME = "roadmap-epics.queue.yaml"
CANON_MD_BASENAME = "roadmap-epics.md"

ROLE_PLAN_DIRS: dict[str, str] = {
    "back": "memory-bank/back/plan",
    "front": "memory-bank/front/plan",
    "integration": "memory-bank/integration/plan",
}


def canon_queue_rel(role: str = "back") -> str:
    role_key = str(role or "back").strip().lower()
    base = ROLE_PLAN_DIRS.get(role_key) or ROLE_PLAN_DIRS["back"]
    return f"{base}/{CANON_QUEUE_BASENAME}"


def canon_md_rel(role: str = "back") -> str:
    role_key = str(role or "back").strip().lower()
    base = ROLE_PLAN_DIRS.get(role_key) or ROLE_PLAN_DIRS["back"]
    return f"{base}/{CANON_MD_BASENAME}"


def is_source_queue_name(name: str) -> bool:
    if name == CANON_QUEUE_BASENAME:
        return False
    return name.startswith("roadmap-") and name.endswith("-epics.queue.yaml")


def discover_source_queues(cwd: str | Path, role: str = "back") -> list[Path]:
    role_key = str(role or "back").strip().lower()
    plan_rel = ROLE_PLAN_DIRS.get(role_key)
    if not plan_rel:
        return []
    plan_dir = Path(cwd) / plan_rel
    if not plan_dir.is_dir():
        return []
    found = [
        p
        for p in plan_dir.iterdir()
        if p.is_file() and is_source_queue_name(p.name)
    ]
    return sorted(found, key=lambda p: (p.stat().st_mtime_ns, p.name))


def _dump_queue_yaml(
    *,
    role: str,
    roadmap_rel: str,
    queue: list[dict[str, Any]],
) -> str:
    lines = [
        f"version: {QUEUE_VERSION}",
        f"role: {role}",
        f"roadmap: {roadmap_rel}",
        "queue:",
    ]
    for item in queue:
        deps = item.get("deps") or []
        deps_s = "[" + ", ".join(str(d) for d in deps) + "]"
        lines.append(f"  - id: {item['id']}")
        lines.append(f"    plan: {item['plan']}")
        lines.append(f"    deps: {deps_s}")
    return "\n".join(lines) + "\n"


def _render_merged_roadmap_md(
    *,
    role: str,
    queue: list[dict[str, Any]],
    sources: list[str],
    skipped_done: list[str],
    queue_rel: str,
) -> str:
    role_u = {"back": "BACK", "front": "FRONT", "integration": "INTEG"}.get(
        role, role.upper()
    )
    qname = Path(queue_rel).name
    rows = []
    for i, item in enumerate(queue, start=1):
        deps = item.get("deps") or []
        deps_s = ", ".join(deps) if deps else "—"
        rows.append(
            f"| {i} | {item['id']} | [{item['plan']}]({item['plan']}) | {deps_s} |"
        )
    src_lines = "\n".join(f"- `{s}`" for s in sources) if sources else "- (нет slug-источников)"
    done_lines = (
        "\n".join(f"- `{d}`" for d in skipped_done) if skipped_done else "- (нет)"
    )
    return (
        f"# Roadmap: active epics (merged canon)\n\n"
        f"**Роль:** {role_u}\n"
        f"**Назначение:** единая очередь для loop (`EPIC_CHAIN_ROADMAP` / `roadmap-advance`).\n"
        f"**Machine queue:** [`{qname}`]({qname})\n"
        f"**Команда:** `{role_u} ROADMAP MERGE`\n\n"
        f"Slug-roadmap (`roadmap-<slug>-epics.*`) — источники; этот файл — канон.\n\n"
        f"---\n\n"
        f"## Источники\n\n"
        f"{src_lines}\n\n"
        f"## Пропущены (done)\n\n"
        f"{done_lines}\n\n"
        f"## Очередь\n\n"
        f"| # | ID | План | Hard deps |\n"
        f"|---|----|------|-----------|\n"
        + "\n".join(rows)
        + "\n\n"
        f"## Handoff\n\n"
        f"- Loop читает **только** `{qname}` (default path).\n"
        f"- `{role_u} PLAN` **сам** вызывает `roadmap-merge` в той же сессии "
        f"(не отдельный next `{role_u} ROADMAP MERGE`).\n"
        f"- Next: `{role_u} DECOMPOSE` первого id из queue.\n"
        f"- Ручной `{role_u} ROADMAP MERGE` — только если канон устарел без PLAN.\n"
    )


def _topo_merge_order(
    items: dict[str, dict[str, Any]],
    preferred: list[str],
) -> dict[str, Any]:
    ids = set(items)
    pref = [i for i in preferred if i in ids]
    for i in items:
        if i not in pref:
            pref.append(i)
    rank = {eid: n for n, eid in enumerate(pref)}
    remaining = set(ids)
    indeg = {
        eid: sum(1 for d in (items[eid].get("deps") or []) if d in remaining)
        for eid in remaining
    }
    ordered: list[str] = []
    while remaining:
        ready = [eid for eid in remaining if indeg.get(eid, 0) == 0]
        if not ready:
            cycle = sorted(remaining, key=lambda x: rank.get(x, 10**9))
            return {
                "ok": False,
                "error": "roadmap_merge_cycle",
                "reason": f"hard-deps cycle among: {', '.join(cycle)}",
                "cycle": cycle,
            }
        ready.sort(key=lambda x: rank.get(x, 10**9))
        pick = ready[0]
        ordered.append(pick)
        remaining.remove(pick)
        for eid in remaining:
            deps = items[eid].get("deps") or []
            if pick in deps:
                indeg[eid] = max(0, indeg.get(eid, 0) - 1)
    return {"ok": True, "order": ordered}


def roadmap_merge(
    cwd: str | Path,
    *,
    role: str = "back",
    dry_run: bool = False,
    write_md: bool = True,
) -> dict[str, Any]:
    """Merge slug roadmap queues into loop canon roadmap-epics.queue.yaml."""
    root = Path(cwd)
    role_key = str(role or "back").strip().lower()
    if role_key not in ROLE_PLAN_DIRS:
        return {
            "ok": False,
            "error": "roadmap_merge_bad_role",
            "reason": f"unsupported role: {role_key!r}",
        }
    plan_rel = ROLE_PLAN_DIRS[role_key]
    queue_rel = canon_queue_rel(role_key)
    md_rel = canon_md_rel(role_key)
    sources = discover_source_queues(root, role_key)

    by_id: dict[str, dict[str, Any]] = {}
    source_of: dict[str, str] = {}
    preferred: list[str] = []
    conflicts: list[dict[str, Any]] = []
    source_rels: list[str] = []

    existing = parse_roadmap_queue(root, queue_rel=queue_rel)
    if existing.get("ok"):
        for item in existing["queue"]:
            eid = item["id"]
            by_id[eid] = {
                "id": eid,
                "plan": item["plan"],
                "deps": list(item.get("deps") or []),
            }
            source_of[eid] = queue_rel
            preferred.append(eid)

    for src in sources:
        try:
            rel = src.relative_to(root).as_posix()
        except ValueError:
            rel = str(src)
        source_rels.append(rel)
        parsed = parse_roadmap_queue(root, queue_rel=rel)
        if not parsed.get("ok"):
            return {
                "ok": False,
                "error": parsed.get("error") or "queue_yaml_invalid",
                "reason": parsed.get("reason") or f"invalid source: {rel}",
                "path": rel,
            }
        if parsed.get("role") and parsed["role"] != role_key:
            return {
                "ok": False,
                "error": "roadmap_merge_role_mismatch",
                "reason": (
                    f"source {rel} role={parsed['role']!r} != merge role={role_key!r}"
                ),
                "path": rel,
            }
        for item in parsed["queue"]:
            eid = item["id"]
            plan = item["plan"]
            deps = list(item.get("deps") or [])
            if eid in by_id:
                prev = by_id[eid]
                if prev["plan"] != plan:
                    conflicts.append(
                        {
                            "id": eid,
                            "plans": [prev["plan"], plan],
                            "sources": [source_of.get(eid), rel],
                        }
                    )
                    continue
                merged_deps: list[str] = []
                for d in list(prev.get("deps") or []) + deps:
                    if d and d not in merged_deps:
                        merged_deps.append(d)
                prev["deps"] = merged_deps
            else:
                by_id[eid] = {"id": eid, "plan": plan, "deps": deps}
                source_of[eid] = rel
            if eid not in preferred:
                preferred.append(eid)

    if conflicts:
        return {
            "ok": False,
            "error": "roadmap_merge_plan_conflict",
            "reason": "same epic id with different plan paths",
            "conflicts": conflicts,
        }

    if not by_id and not sources and not existing.get("ok"):
        return {
            "ok": False,
            "error": "roadmap_merge_empty",
            "reason": (
                f"no source queues under {plan_rel} and no existing {queue_rel}"
            ),
        }

    skipped_done: list[str] = []
    active: dict[str, dict[str, Any]] = {}
    for eid, item in by_id.items():
        if is_epic_done(root, role_key, eid):
            skipped_done.append(eid)
            continue
        active[eid] = item

    if not active:
        if dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "role": role_key,
                "queue": [],
                "skipped_done": skipped_done,
                "sources": source_rels,
                "path": queue_rel,
                "md_path": md_rel,
                "reason": "all epics done; would write empty-fail",
                "would_fail": "roadmap_merge_no_active",
            }
        return {
            "ok": False,
            "error": "roadmap_merge_no_active",
            "reason": "no active epics left after filtering done",
            "skipped_done": skipped_done,
            "sources": source_rels,
        }

    done_set = set(skipped_done)
    unknown_deps: list[dict[str, str]] = []
    for eid, item in active.items():
        norm: list[str] = []
        for d in item.get("deps") or []:
            if d in done_set:
                continue
            if d not in active:
                unknown_deps.append({"id": eid, "dep": d})
                continue
            if d not in norm:
                norm.append(d)
        item["deps"] = norm
    if unknown_deps:
        return {
            "ok": False,
            "error": "roadmap_merge_unknown_deps",
            "reason": "hard deps reference ids not in active merge set",
            "unknown_deps": unknown_deps,
        }

    topo = _topo_merge_order(active, preferred)
    if not topo.get("ok"):
        return topo
    ordered = [
        {
            "id": eid,
            "plan": active[eid]["plan"],
            "deps": list(active[eid].get("deps") or []),
        }
        for eid in topo["order"]
    ]

    body = _dump_queue_yaml(role=role_key, roadmap_rel=md_rel, queue=ordered)
    md_body = _render_merged_roadmap_md(
        role=role_key,
        queue=ordered,
        sources=source_rels,
        skipped_done=skipped_done,
        queue_rel=queue_rel,
    )
    out: dict[str, Any] = {
        "ok": True,
        "role": role_key,
        "path": queue_rel,
        "md_path": md_rel,
        "sources": source_rels,
        "skipped_done": skipped_done,
        "queue": ordered,
        "ids": [x["id"] for x in ordered],
        "dry_run": bool(dry_run),
        "written": False,
    }
    if dry_run:
        out["queue_yaml"] = body
        out["roadmap_md"] = md_body
        return out

    qpath = root / queue_rel
    qpath.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(qpath, body)
    out["written"] = True
    if write_md:
        atomic_write_text(root / md_rel, md_body)
        out["md_written"] = True
    else:
        out["md_written"] = False
    return out
