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
    arm_epic,
    atomic_write_text,
    find_next_decompose_step_from_queue,
    load_decompose_steps_fail_closed,
    load_epic_state,
    post_implement_phase,
)
from epic.core import active_context_path, checkpoint_lock_path, checkpoint_path, load_checkpoint  # noqa: E402
from epic_paths import epic_id_from_decompose_path  # noqa: E402
from _lib import merged_project_env_map  # noqa: E402
from analyze_gate import analyze_required_before_implement  # noqa: E402

QUEUE_VERSION_V1 = "roadmap-queue/v1"
QUEUE_VERSION = "roadmap-queue/v2"
SUPPORTED_QUEUE_VERSIONS = {QUEUE_VERSION_V1, QUEUE_VERSION}

# Layout v2 SoT (yaml-only; no sibling .md)
DEFAULT_QUEUE = "memory-bank/back/roadmap/queue.yaml"
# Deprecated aliases (migration / old docs)
DEFAULT_ROADMAP = "memory-bank/back/roadmap/queue.yaml"
LEGACY_DEFAULT_QUEUE = "memory-bank/back/plan/roadmap-epics.queue.yaml"


def queue_rel_from_roadmap(roadmap_rel: str) -> str:
    """Map legacy roadmap path to machine queue.

    - ``…/roadmap/queue.yaml`` stays
    - ``…/plan/roadmap-foo-epics.md`` → ``…/plan/roadmap-foo-epics.queue.yaml`` (legacy)
    - bare ``…/roadmap`` → ``…/roadmap/queue.yaml``
    """
    rel = str(roadmap_rel).replace("\\", "/")
    if rel.endswith("/queue.yaml") or rel.endswith("queue.yaml"):
        return rel if rel.endswith(".yaml") else f"{rel.rstrip('/')}/queue.yaml"
    if rel.endswith(".queue.yaml"):
        return rel
    if rel.endswith(".md"):
        return rel[: -len(".md")] + ".queue.yaml"
    if rel.rstrip("/").endswith("/roadmap"):
        return f"{rel.rstrip('/')}/queue.yaml"
    return rel + ".queue.yaml"


def epic_chain_roadmap_enabled(cwd: str | Path | None = None) -> bool:
    raw = os.environ.get("EPIC_CHAIN_ROADMAP")
    if raw is None:
        raw = merged_project_env_map(cwd).get("EPIC_CHAIN_ROADMAP", "0")
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_queue_item(item: dict[str, Any], *, index: int, path: str) -> dict[str, Any]:
    """Normalize one queue/done row: require id + (epic_id|plan)."""
    if not isinstance(item, dict):
        return {
            "ok": False,
            "error": "queue_yaml_invalid",
            "reason": f"queue[{index}] must be a mapping",
            "path": path,
        }
    qid = str(item.get("id") or "").strip()
    epic_fs = str(item.get("epic_id") or "").strip()
    plan = str(item.get("plan") or "").strip()
    if not epic_fs and plan:
        epic_fs = plan_stem_from_name(plan)
    if not plan and epic_fs:
        plan = f"plan-{epic_fs}.md"
    deps_raw = item.get("deps") if "deps" in item else []
    if not qid or (not plan and not epic_fs):
        return {
            "ok": False,
            "error": "queue_yaml_invalid",
            "reason": f"queue[{index}] requires id and epic_id|plan",
            "path": path,
        }
    if not isinstance(deps_raw, list):
        return {
            "ok": False,
            "error": "queue_yaml_invalid",
            "reason": f"queue[{index}].deps must be a list",
            "path": path,
        }
    deps = [str(d).strip() for d in deps_raw if str(d).strip()]
    batch = str(item.get("batch") or "").strip() or None
    out: dict[str, Any] = {
        "ok": True,
        "id": qid,
        "plan": plan or f"plan-{epic_fs}.md",
        "epic_id": epic_fs or plan_stem_from_name(plan),
        "deps": deps,
    }
    if batch:
        out["batch"] = batch
    return out


def _validate_queue_doc(data: Any, *, path: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {
            "ok": False,
            "error": "queue_yaml_invalid",
            "reason": "queue root must be a mapping",
            "path": path,
        }
    version = str(data.get("version") or "")
    if version not in SUPPORTED_QUEUE_VERSIONS:
        return {
            "ok": False,
            "error": "queue_version_mismatch",
            "reason": f"expected one of {sorted(SUPPORTED_QUEUE_VERSIONS)}, got {version!r}",
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
    if not isinstance(raw_queue, list):
        return {
            "ok": False,
            "error": "queue_yaml_invalid",
            "reason": "queue must be a list",
            "path": path,
        }
    if version == QUEUE_VERSION_V1 and not raw_queue:
        return {
            "ok": False,
            "error": "queue_yaml_invalid",
            "reason": "queue must be a non-empty list",
            "path": path,
        }
    queue: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, item in enumerate(raw_queue):
        norm = _normalize_queue_item(item if isinstance(item, dict) else {}, index=i, path=path)
        if not norm.get("ok"):
            return norm
        epic_id = norm["id"]
        if epic_id in seen:
            return {
                "ok": False,
                "error": "queue_yaml_invalid",
                "reason": f"duplicate epic id: {epic_id}",
                "path": path,
            }
        seen.add(epic_id)
        row = {"id": epic_id, "plan": norm["plan"], "deps": norm["deps"], "epic_id": norm["epic_id"]}
        if norm.get("batch"):
            row["batch"] = norm["batch"]
        queue.append(row)

    done: list[dict[str, Any]] = []
    raw_done = data.get("done")
    if raw_done is not None:
        if not isinstance(raw_done, list):
            return {
                "ok": False,
                "error": "queue_yaml_invalid",
                "reason": "done must be a list",
                "path": path,
            }
        for i, item in enumerate(raw_done):
            if not isinstance(item, dict):
                return {
                    "ok": False,
                    "error": "queue_yaml_invalid",
                    "reason": f"done[{i}] must be a mapping",
                    "path": path,
                }
            norm = _normalize_queue_item(item, index=i, path=path)
            if not norm.get("ok"):
                return {
                    "ok": False,
                    "error": "queue_yaml_invalid",
                    "reason": f"done[{i}]: {norm.get('reason')}",
                    "path": path,
                }
            row = {
                "id": norm["id"],
                "plan": norm["plan"],
                "deps": norm["deps"],
                "epic_id": norm["epic_id"],
            }
            if norm.get("batch"):
                row["batch"] = norm["batch"]
            done.append(row)

    batches = data.get("batches") if isinstance(data.get("batches"), dict) else {}
    roadmap = str(data.get("roadmap") or data.get("path") or "").strip()
    return {
        "ok": True,
        "version": version,
        "role": role,
        "path": path,
        "roadmap": roadmap or None,
        "queue": queue,
        "done": done,
        "batches": batches,
    }


def parse_roadmap_queue(
    cwd: str | Path,
    *,
    queue_rel: str | None = None,
    roadmap_rel: str | None = None,
) -> dict[str, Any]:
    """Parse machine queue YAML. Fail-closed on errors.

    Prefers ``queue_rel``. Default: ``DEFAULT_QUEUE``
    (``memory-bank/<role>/roadmap/queue.yaml``). If default missing, tries
    legacy ``plan/roadmap-epics.queue.yaml`` once (migration window).
    """
    root = Path(cwd)
    if queue_rel:
        rel = queue_rel
    elif roadmap_rel:
        rel = queue_rel_from_roadmap(roadmap_rel)
    else:
        rel = DEFAULT_QUEUE
    path = root / rel
    if not path.is_file() and not queue_rel and not roadmap_rel:
        legacy = root / LEGACY_DEFAULT_QUEUE
        if legacy.is_file():
            rel = LEGACY_DEFAULT_QUEUE
            path = legacy
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
    from epic_paths import find_decompose_index_path

    return find_decompose_index_path(cwd, role, epic_id)


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
    """Resolve plan file: flat v1 ``plan-*.md`` or layout v2 ``{slug}/md/plan.md``."""
    root = Path(cwd)
    role_dir = str(role or "back").strip().lower()
    if role_dir == "integ":
        role_dir = "integration"
    flat = root / "memory-bank" / role_dir / "plan" / plan_name
    if flat.is_file():
        return flat
    stem = plan_stem_from_name(plan_name)
    if stem:
        v2 = root / "memory-bank" / role_dir / "plan" / stem / "md" / "plan.md"
        if v2.is_file():
            return v2
        try:
            from loop.paths.epic_layout import EpicLayoutKind, resolve

            resolved = resolve(
                role_dir, stem, EpicLayoutKind.PLAN_MD, project_root=root
            )
            if resolved.is_file():
                return resolved
            return resolved
        except Exception:
            return v2
    return flat


def plan_stem_from_name(plan_name: str) -> str:
    """Stem of plan-*.md without plan- prefix (FS epic_id with descriptive slug)."""
    name = Path(str(plan_name or "").strip().replace("\\", "/")).name
    if name.startswith("plan-"):
        name = name[len("plan-") :]
    if name.endswith(".md"):
        name = name[: -len(".md")]
    return name.strip()


def resolve_epic_slug(
    cwd: str | Path,
    role: str,
    queue_id: str,
    plan_name: str | None = None,
) -> str:
    """Map queue id (T-HUB-023) to artifact epic slug (T-HUB-023-hooks-llm-fallbacks).

    Source of truth for FS folders: plan file stem (queue ``plan:`` field or
    ``plan-{queue_id}[-slug].md`` on disk). Short queue id alone is only a
    fallback when no plan / decompose / reflection / qa artifact exists.
    """
    if plan_name:
        stem = plan_stem_from_name(plan_name)
        if stem:
            return stem
    root = Path(cwd)
    plan_dir = root / "memory-bank" / role / "plan"
    if plan_dir.is_dir():
        exact_plan = plan_dir / f"plan-{queue_id}.md"
        slugged = sorted(plan_dir.glob(f"plan-{queue_id}-*.md"))
        if slugged:
            return plan_stem_from_name(slugged[0].name)
        if exact_plan.is_file():
            return queue_id
    idx = find_decompose_index(cwd, role, queue_id)
    if idx is not None:
        slug = epic_id_from_decompose_path(str(idx))
        if slug:
            return slug
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


def _queue_row_matches(
    cwd: str | Path,
    role: str,
    item: dict[str, Any],
    epic_ref: str,
) -> bool:
    """Match short queue id, epic_id slug, or armed_epic full id."""
    ref = str(epic_ref or "").strip()
    if not ref:
        return False
    qid = str(item.get("id") or "").strip()
    if qid and (qid == ref or ref.startswith(qid + "-")):
        return True
    epic_fs = str(item.get("epic_id") or "").strip()
    if epic_fs and epic_fs == ref:
        return True
    if qid:
        slug = resolve_epic_slug(cwd, role, qid)
        if slug == ref:
            return True
    return False


def mark_queue_epic_done(
    cwd: str | Path,
    epic_id: str,
    *,
    role: str | None = None,
    queue_rel: str | None = None,
    require_done: bool = False,
) -> dict[str, Any]:
    """Move one epic from ``queue:`` → ``done:`` in roadmap/queue.yaml.

    Not per-session: only on epic completion. Idempotent if already in ``done:``.
    Missing from both lists → ``ok: true, skipped: not_in_queue`` (ad-hoc epics).
    """
    root = Path(cwd)
    ref = str(epic_id or "").strip()
    if not ref:
        return {
            "ok": False,
            "error": "mark_queue_epic_missing_id",
            "reason": "epic_id required",
        }
    role_key = str(role or "back").strip().lower() or "back"
    qrel = queue_rel or canon_queue_rel(role_key)
    parsed = parse_roadmap_queue(root, queue_rel=qrel)
    if not parsed.get("ok"):
        return {
            "ok": False,
            "error": parsed.get("error") or "queue_parse_failed",
            "reason": parsed.get("reason") or parsed.get("error"),
            "path": parsed.get("path") or qrel,
        }
    role_key = str(parsed.get("role") or role_key).strip().lower()
    queue = list(parsed.get("queue") or [])
    done = list(parsed.get("done") or [])
    batches = dict(parsed.get("batches") or {})

    for row in done:
        if _queue_row_matches(root, role_key, row, ref):
            return {
                "ok": True,
                "written": False,
                "already_done": True,
                "id": row["id"],
                "epic_id": row.get("epic_id"),
                "path": parsed["path"],
            }

    hit_idx: int | None = None
    for i, row in enumerate(queue):
        if _queue_row_matches(root, role_key, row, ref):
            hit_idx = i
            break
    if hit_idx is None:
        return {
            "ok": True,
            "written": False,
            "skipped": "not_in_queue",
            "epic_ref": ref,
            "path": parsed["path"],
        }

    row = queue.pop(hit_idx)
    if require_done and not is_epic_done(root, role_key, row["id"]):
        return {
            "ok": False,
            "error": "mark_queue_epic_not_done",
            "reason": f"epic {row['id']} is not DONE (QA+REFLECT gate)",
            "id": row["id"],
            "path": parsed["path"],
        }

    done_row: dict[str, Any] = {
        "id": row["id"],
        "epic_id": row.get("epic_id") or plan_stem_from_name(row.get("plan") or ""),
        "plan": row.get("plan") or f"plan-{row['id']}.md",
        "deps": [],
    }
    if row.get("batch"):
        done_row["batch"] = row["batch"]
    done.append(done_row)

    body = _dump_queue_yaml(
        role=role_key,
        queue=queue,
        done=done,
        batches=batches or None,
    )
    qpath = root / parsed["path"]
    qpath.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(qpath, body)
    return {
        "ok": True,
        "written": True,
        "already_done": False,
        "id": done_row["id"],
        "epic_id": done_row.get("epic_id"),
        "path": parsed["path"],
        "queue_remaining": [x["id"] for x in queue],
    }


def resolve_entry(
    cwd: str | Path,
    *,
    role: str,
    epic_id: str,
    plan_name: str,
) -> dict[str, Any]:
    """Smart entry: DECOMPOSE / ANALYZE / IMPLEMENT|CREATIVE / QA / done."""
    root = Path(cwd)
    slug = resolve_epic_slug(root, role, epic_id, plan_name=plan_name)
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
    idx = find_decompose_index(root, role, slug)
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
    phase, qa, _refl = post_implement_phase(root, role, slug)
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
    for item in parsed.get("done") or []:
        qid = str(item.get("id") or "").strip()
        if qid:
            done_ids.add(qid)
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
        for item in parsed.get("done") or []:
            if _queue_row_matches(cwd, role, item, skip_epic):
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
            cwd,
            role=role,
            epic_id=epic_id,
            plan_name=item.get("plan") or item.get("epic_id") or "",
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


def arm_roadmap_entry(cwd: str | Path, selection: dict[str, Any]) -> dict[str, Any]:
    """Plan-centric arm: delegate phase selection to arm_epic + resolver."""
    root = Path(cwd)
    role = selection["role"]
    entry = selection["entry"]
    slug = entry.get("epic") or entry.get("queue_id")
    out = arm_epic(root, slug, role=role)
    if not out.get("ok"):
        return {
            "ok": False,
            "armed": False,
            "epic": slug,
            "phase": entry.get("phase"),
            "reason": out.get("error") or out.get("reason") or "arm failed",
            "arm": out,
        }
    if out.get("complete"):
        return {
            "ok": True,
            "armed": False,
            "complete": True,
            "epic": slug,
            "phase": "DONE",
            "stop": "EPIC_DONE",
            "arm": out,
        }
    try:
        from loop.epic_transition import promote_if_ready

        promoted = promote_if_ready(root, slug, role)
        if isinstance(promoted, dict) and promoted.get("ok"):
            out = promoted
    except Exception:
        pass
    phase = str(out.get("phase") or entry.get("phase") or "")
    if phase.endswith(" IMPLEMENT"):
        phase = "IMPLEMENT"
    decompose = out.get("index") or out.get("decompose") or entry.get("decompose")
    res = {
        "ok": True,
        "armed": True,
        "complete": False,
        "epic": slug,
        "phase": phase,
        "step_id": out.get("step_id"),
        "decompose": decompose,
        "role": out.get("role") or role,
        "plan": entry.get("plan"),
        "arm": out,
    }
    if "promoted_from" in out:
        res["promoted_from"] = out["promoted_from"]
    return res


def roadmap_advance(
    cwd: str | Path,
    *,
    queue_rel: str | None = None,
    roadmap_rel: str | None = None,
    skip_epic: str | None = None,
) -> dict[str, Any]:
    """Select and arm the next roadmap epic (opt-in chain after EPIC_DONE)."""
    st = load_epic_state(cwd)
    if skip_epic is None:
        skip_epic = (st.get("armed_epic") or "").strip() or None
    marked: dict[str, Any] | None = None
    if skip_epic:
        role_hint = (
            str(st.get("armed_role") or st.get("role") or "back").strip().lower()
            or "back"
        )
        marked = mark_queue_epic_done(
            cwd,
            skip_epic,
            role=role_hint,
            queue_rel=queue_rel,
            require_done=False,
        )
        if marked.get("ok") is False and marked.get("error") in {
            "queue_version_mismatch",
            "queue_yaml_invalid",
        }:
            return {
                "ok": False,
                "armed": False,
                "complete": False,
                "halt": True,
                "stop": f"NEED_HUMAN: {marked.get('error')}",
                "reason": marked.get("reason"),
                "mark_done": marked,
            }
    selected = select_next_epic(
        cwd,
        queue_rel=queue_rel,
        roadmap_rel=roadmap_rel,
        skip_epic=skip_epic,
    )
    if selected.get("complete"):
        out_done = {
            "ok": True,
            "armed": False,
            "complete": True,
            "stop": "ROADMAP_DONE",
            "reason": selected.get("reason"),
            "done_ids": selected.get("done_ids"),
        }
        if marked is not None:
            out_done["mark_done"] = marked
        return out_done
    if not selected.get("ok"):
        out_bad = {
            "ok": False,
            "armed": False,
            "complete": False,
            "halt": bool(selected.get("halt")),
            "stop": selected.get("stop"),
            "reason": selected.get("reason") or selected.get("error"),
            "error": selected.get("error"),
            "blocked": selected.get("blocked"),
        }
        if marked is not None:
            out_bad["mark_done"] = marked
        return out_bad
    armed = arm_roadmap_entry(cwd, selected)
    armed["done_ids"] = selected.get("done_ids")
    armed["blocked"] = selected.get("blocked")
    armed["path"] = selected.get("path")
    if marked is not None:
        armed["mark_done"] = marked
    return armed


CANON_QUEUE_BASENAME = "queue.yaml"
CANON_MD_BASENAME = "roadmap-epics.md"  # deprecated; never written by default

ROLE_ROADMAP_DIRS: dict[str, str] = {
    "back": "memory-bank/back/roadmap",
    "front": "memory-bank/front/roadmap",
    "integration": "memory-bank/integration/roadmap",
}

# Legacy plan-dir (slug sources during migration)
ROLE_PLAN_DIRS: dict[str, str] = {
    "back": "memory-bank/back/plan",
    "front": "memory-bank/front/plan",
    "integration": "memory-bank/integration/plan",
}


def canon_queue_rel(role: str = "back") -> str:
    role_key = str(role or "back").strip().lower()
    base = ROLE_ROADMAP_DIRS.get(role_key) or ROLE_ROADMAP_DIRS["back"]
    return f"{base}/{CANON_QUEUE_BASENAME}"


def canon_md_rel(role: str = "back") -> str:
    """Deprecated md mirror path (not written). Kept for API compat."""
    role_key = str(role or "back").strip().lower()
    base = ROLE_ROADMAP_DIRS.get(role_key) or ROLE_ROADMAP_DIRS["back"]
    return f"{base}/{CANON_MD_BASENAME}"


def is_source_queue_name(name: str) -> bool:
    if name in {CANON_QUEUE_BASENAME, "roadmap-epics.queue.yaml"}:
        return False
    if name.endswith(".queue.yaml") and name.startswith("roadmap-"):
        return True
    if name.endswith(".yaml") and not name.startswith(".") and name != CANON_QUEUE_BASENAME:
        # batches/<slug>.yaml under roadmap/
        return True
    return False


def discover_source_queues(cwd: str | Path, role: str = "back") -> list[Path]:
    """Discover optional batch/legacy sources (migration + rare ops).

    Prefer ``roadmap/batches/*.yaml``; also scan legacy ``plan/roadmap-*-epics.queue.yaml``.
    Canon ``roadmap/queue.yaml`` is never a source.
    """
    role_key = str(role or "back").strip().lower()
    root = Path(cwd)
    found: list[Path] = []

    road_rel = ROLE_ROADMAP_DIRS.get(role_key)
    if road_rel:
        batches = root / road_rel / "batches"
        if batches.is_dir():
            for p in batches.iterdir():
                if p.is_file() and p.suffix in {".yaml", ".yml"} and p.name != CANON_QUEUE_BASENAME:
                    found.append(p)
        archive = root / road_rel / "archive"
        # archive is provenance only — do not re-merge unless batches empty and no canon
        _ = archive

    plan_rel = ROLE_PLAN_DIRS.get(role_key)
    if plan_rel:
        plan_dir = root / plan_rel
        if plan_dir.is_dir():
            for p in plan_dir.iterdir():
                if (
                    p.is_file()
                    and p.name.startswith("roadmap-")
                    and p.name.endswith("-epics.queue.yaml")
                    and p.name != "roadmap-epics.queue.yaml"
                ):
                    found.append(p)

    return sorted(found, key=lambda p: (p.stat().st_mtime_ns, p.name))


def _dump_queue_yaml(
    *,
    role: str,
    queue: list[dict[str, Any]],
    done: list[dict[str, Any]] | None = None,
    batches: dict[str, Any] | None = None,
    roadmap_rel: str | None = None,
) -> str:
    """Serialize roadmap-queue/v2 (yaml-only SoT)."""
    _ = roadmap_rel
    doc: dict[str, Any] = {
        "version": QUEUE_VERSION,
        "role": role,
        "queue": [],
        "done": [],
    }
    for item in queue:
        row: dict[str, Any] = {
            "id": item["id"],
            "epic_id": item.get("epic_id") or plan_stem_from_name(item.get("plan") or ""),
            "plan": item.get("plan")
            or f"plan-{item.get('epic_id') or item['id']}.md",
            "deps": list(item.get("deps") or []),
        }
        if item.get("batch"):
            row["batch"] = item["batch"]
        doc["queue"].append(row)
    for item in done or []:
        row = {
            "id": item["id"],
            "epic_id": item.get("epic_id") or plan_stem_from_name(item.get("plan") or ""),
        }
        if item.get("plan"):
            row["plan"] = item["plan"]
        if item.get("batch"):
            row["batch"] = item["batch"]
        doc["done"].append(row)
    if batches:
        doc["batches"] = batches
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def _render_merged_roadmap_md(
    *,
    role: str,
    queue: list[dict[str, Any]],
    sources: list[str],
    skipped_done: list[str],
    queue_rel: str,
) -> str:
    """Deprecated — md mirrors are no longer generated. Kept for dry-run preview."""
    role_u = {"back": "BACK", "front": "FRONT", "integration": "INTEG"}.get(
        role, role.upper()
    )
    qname = Path(queue_rel).as_posix()
    rows = []
    for i, item in enumerate(queue, start=1):
        deps = item.get("deps") or []
        deps_s = ", ".join(deps) if deps else "—"
        rows.append(
            f"| {i} | {item['id']} | {item.get('epic_id') or item.get('plan')} | {deps_s} |"
        )
    src_lines = "\n".join(f"- `{s}`" for s in sources) if sources else "- (inline batches only)"
    done_lines = (
        "\n".join(f"- `{d}`" for d in skipped_done) if skipped_done else "- (нет)"
    )
    return (
        f"# Roadmap (deprecated md mirror)\n\n"
        f"**Роль:** {role_u}\n"
        f"**Machine SoT:** `{qname}`\n\n"
        f"## Sources\n\n{src_lines}\n\n"
        f"## Done\n\n{done_lines}\n\n"
        f"## Queue\n\n"
        f"| # | ID | epic_id | Hard deps |\n"
        f"|---|----|---------|-----------|\n"
        + "\n".join(rows)
        + "\n"
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


def _batch_slug_from_source(path: Path) -> str | None:
    name = path.name
    if name.endswith("-epics.queue.yaml") and name.startswith("roadmap-"):
        return name[len("roadmap-") : -len("-epics.queue.yaml")]
    if name.endswith(".yaml"):
        return name[: -len(".yaml")]
    if name.endswith(".yml"):
        return name[: -len(".yml")]
    return None


def roadmap_merge(
    cwd: str | Path,
    *,
    role: str = "back",
    dry_run: bool = False,
    write_md: bool = False,
    archive_sources: bool = True,
) -> dict[str, Any]:
    """Reconcile roadmap SoT: ``memory-bank/<role>/roadmap/queue.yaml``.

    Merges optional batch/legacy sources into one v2 file (queue + done + batches).
    Does **not** write md by default. Legacy plan/ slug queues are archived under
    ``roadmap/archive/`` after successful write.
    """
    root = Path(cwd)
    role_key = str(role or "back").strip().lower()
    if role_key not in ROLE_ROADMAP_DIRS:
        return {
            "ok": False,
            "error": "roadmap_merge_bad_role",
            "reason": f"unsupported role: {role_key!r}",
        }
    road_rel = ROLE_ROADMAP_DIRS[role_key]
    plan_rel = ROLE_PLAN_DIRS[role_key]
    queue_rel = canon_queue_rel(role_key)
    md_rel = canon_md_rel(role_key)
    sources = discover_source_queues(root, role_key)

    by_id: dict[str, dict[str, Any]] = {}
    source_of: dict[str, str] = {}
    preferred: list[str] = []
    conflicts: list[dict[str, Any]] = []
    source_rels: list[str] = []
    batches_meta: dict[str, Any] = {}
    prior_done: list[dict[str, Any]] = []

    existing = parse_roadmap_queue(root, queue_rel=queue_rel)
    if not existing.get("ok"):
        # try legacy canon under plan/
        legacy_rel = f"{plan_rel}/roadmap-epics.queue.yaml"
        existing = parse_roadmap_queue(root, queue_rel=legacy_rel)
    if existing.get("ok"):
        batches_meta = dict(existing.get("batches") or {})
        prior_done = list(existing.get("done") or [])
        for item in existing["queue"]:
            eid = item["id"]
            by_id[eid] = {
                "id": eid,
                "plan": item["plan"],
                "epic_id": item.get("epic_id") or plan_stem_from_name(item["plan"]),
                "deps": list(item.get("deps") or []),
                "batch": item.get("batch"),
            }
            source_of[eid] = existing["path"]
            preferred.append(eid)

    for src in sources:
        try:
            rel = src.relative_to(root).as_posix()
        except ValueError:
            rel = str(src)
        source_rels.append(rel)
        batch_slug = _batch_slug_from_source(src)
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
        if batch_slug and batch_slug not in batches_meta:
            batches_meta[batch_slug] = {"source": rel}
        for item in parsed["queue"]:
            eid = item["id"]
            plan = item["plan"]
            epic_fs = item.get("epic_id") or plan_stem_from_name(plan)
            deps = list(item.get("deps") or [])
            batch = item.get("batch") or batch_slug
            if eid in by_id:
                prev = by_id[eid]
                if prev["plan"] != plan and plan_stem_from_name(prev["plan"]) != epic_fs:
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
                if batch and not prev.get("batch"):
                    prev["batch"] = batch
            else:
                by_id[eid] = {
                    "id": eid,
                    "plan": plan,
                    "epic_id": epic_fs,
                    "deps": deps,
                    "batch": batch,
                }
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
                f"no sources under {road_rel}/batches or {plan_rel} "
                f"and no existing {queue_rel}"
            ),
        }

    skipped_done: list[str] = []
    active: dict[str, dict[str, Any]] = {}
    done_rows: dict[str, dict[str, Any]] = {}
    for row in prior_done:
        done_rows[row["id"]] = row

    for eid, item in by_id.items():
        if is_epic_done(root, role_key, eid):
            skipped_done.append(eid)
            done_rows[eid] = {
                "id": eid,
                "plan": item["plan"],
                "epic_id": item.get("epic_id"),
                "deps": [],
                "batch": item.get("batch"),
            }
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

    done_set = set(done_rows) | set(skipped_done)
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
            "epic_id": active[eid].get("epic_id")
            or plan_stem_from_name(active[eid]["plan"]),
            "deps": list(active[eid].get("deps") or []),
            **(
                {"batch": active[eid]["batch"]}
                if active[eid].get("batch")
                else {}
            ),
        }
        for eid in topo["order"]
    ]
    done_list = [done_rows[k] for k in sorted(done_rows.keys())]

    body = _dump_queue_yaml(
        role=role_key,
        queue=ordered,
        done=done_list,
        batches=batches_meta,
    )
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
        "done": done_list,
        "batches": batches_meta,
        "ids": [x["id"] for x in ordered],
        "dry_run": bool(dry_run),
        "written": False,
        "md_written": False,
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

    if archive_sources and source_rels:
        arch = root / road_rel / "archive"
        arch.mkdir(parents=True, exist_ok=True)
        archived: list[str] = []
        for rel in source_rels:
            src = root / rel
            if not src.is_file():
                continue
            # also move sibling .md if present
            dest = arch / src.name
            if dest.exists():
                dest.unlink()
            src.rename(dest)
            archived.append(dest.relative_to(root).as_posix())
            if rel.endswith(".queue.yaml"):
                md_sib = Path(str(root / rel[: -len(".queue.yaml")]) + ".md")
                if md_sib.is_file():
                    md_dest = arch / md_sib.name
                    if md_dest.exists():
                        md_dest.unlink()
                    md_sib.rename(md_dest)
                    archived.append(md_dest.relative_to(root).as_posix())
        out["archived"] = archived

    # remove legacy canon under plan/ if we wrote new path
    legacy_q = root / plan_rel / "roadmap-epics.queue.yaml"
    legacy_md = root / plan_rel / "roadmap-epics.md"
    removed: list[str] = []
    if legacy_q.is_file() and legacy_q.resolve() != qpath.resolve():
        legacy_q.unlink()
        removed.append(legacy_q.relative_to(root).as_posix())
    if legacy_md.is_file():
        legacy_md.unlink()
        removed.append(legacy_md.relative_to(root).as_posix())
    if removed:
        out["removed_legacy"] = removed
    return out


def roadmap_upsert_batch(
    cwd: str | Path,
    *,
    role: str,
    batch: str,
    items: list[dict[str, Any]],
    title: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """PLAN helper: append/update epics in single ``roadmap/queue.yaml`` (no slug files)."""
    root = Path(cwd)
    role_key = str(role or "back").strip().lower()
    queue_rel = canon_queue_rel(role_key)
    parsed = parse_roadmap_queue(root, queue_rel=queue_rel)
    by_id: dict[str, dict[str, Any]] = {}
    preferred: list[str] = []
    done_rows: list[dict[str, Any]] = []
    batches: dict[str, Any] = {}
    if parsed.get("ok"):
        for item in parsed["queue"]:
            by_id[item["id"]] = dict(item)
            preferred.append(item["id"])
        done_rows = list(parsed.get("done") or [])
        batches = dict(parsed.get("batches") or {})
    batch_key = str(batch or "").strip()
    if not batch_key:
        return {"ok": False, "error": "roadmap_upsert_bad_batch", "reason": "batch required"}
    meta: dict[str, Any] = dict(batches.get(batch_key) or {})
    if title:
        meta["title"] = title
    if note:
        meta["note"] = note
    batches[batch_key] = meta

    for raw in items:
        norm = _normalize_queue_item(raw if isinstance(raw, dict) else {}, index=0, path=queue_rel)
        if not norm.get("ok"):
            return norm
        row = {
            "id": norm["id"],
            "plan": norm["plan"],
            "epic_id": norm["epic_id"],
            "deps": norm["deps"],
            "batch": batch_key,
        }
        by_id[row["id"]] = row
        if row["id"] not in preferred:
            preferred.append(row["id"])

    # drop done ids from active
    done_ids = {d["id"] for d in done_rows}
    active = {k: v for k, v in by_id.items() if k not in done_ids}
    topo = _topo_merge_order(active, preferred)
    if not topo.get("ok"):
        return topo
    ordered = [active[eid] for eid in topo["order"]]
    body = _dump_queue_yaml(
        role=role_key, queue=ordered, done=done_rows, batches=batches
    )
    qpath = root / queue_rel
    qpath.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(qpath, body)
    return {
        "ok": True,
        "path": queue_rel,
        "ids": [x["id"] for x in ordered],
        "batch": batch_key,
        "written": True,
    }