"""Lean roadmap queue helpers — mark done + next epic after CONTEXT_SYNC."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .index import normalize_role, plan_path, qa_verdict, phase_artifacts


def roadmap_queue_path(project: Path, role: str) -> Path:
    return project / "memory-bank" / normalize_role(role) / "roadmap" / "queue.yaml"


def _load_queue_doc(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError):
        return None
    return payload if isinstance(payload, dict) else None


def _row_refs(row: dict[str, Any]) -> set[str]:
    refs = {
        str(row.get("id") or "").strip(),
        str(row.get("epic_id") or "").strip(),
    }
    plan = str(row.get("plan") or "").strip()
    if plan:
        refs.add(Path(plan).stem.replace("plan-", "", 1))
    return {ref for ref in refs if ref}


def _row_matches(row: dict[str, Any], epic_ref: str) -> bool:
    ref = str(epic_ref or "").strip()
    return bool(ref) and ref in _row_refs(row)


def _epic_slug(row: dict[str, Any]) -> str:
    epic_id = str(row.get("epic_id") or "").strip()
    if epic_id:
        return epic_id
    plan = str(row.get("plan") or "").strip()
    if plan:
        stem = Path(plan).stem
        return stem[5:] if stem.startswith("plan-") else stem
    return str(row.get("id") or "").strip()


def _dump_queue(doc: dict[str, Any], *, role: str, queue: list[dict[str, Any]], done: list[dict[str, Any]]) -> str:
    payload: dict[str, Any] = {
        "version": doc.get("version") or "roadmap-queue/v2",
        "role": role,
        "queue": queue,
        "done": done,
    }
    batches = doc.get("batches")
    if isinstance(batches, dict) and batches:
        payload["batches"] = batches
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)


def cadence_blocks_feature_advance(project: Path, role: str) -> tuple[bool, str]:
    """Optional cadence pause. Lean loop ignores cadence unless LOOP_RESPECT_CADENCE=1."""
    import os

    if os.environ.get("LOOP_RESPECT_CADENCE", "").strip() not in {"1", "true", "yes"}:
        return False, ""
    path = project / "memory-bank" / normalize_role(role) / "roadmap" / "cadence.yaml"
    if not path.is_file():
        return False, ""
    doc = _load_queue_doc(path)
    if doc is None:
        return True, "cadence.yaml unreadable"
    phase = str(doc.get("phase") or "idle").strip().lower() or "idle"
    if phase != "idle":
        return True, f"cadence phase is '{phase}'"
    return False, ""


@dataclass(frozen=True)
class RoadmapAdvance:
    marked: bool
    already_done: bool
    skipped: str | None
    queue_path: Path | None
    queue_body: str | None
    next_epic_id: str | None
    next_kind: str | None
    complete: bool
    blocked_reason: str | None = None


def prepare_advance_after_context_sync(
    project: Path,
    *,
    role: str,
    epic_id: str,
) -> RoadmapAdvance:
    """Mark current epic done (QA pass + context-sync required) and select next queue head."""
    role_key = normalize_role(role)
    qpath = roadmap_queue_path(project, role_key)
    doc = _load_queue_doc(qpath)
    if doc is None:
        return RoadmapAdvance(
            marked=False,
            already_done=False,
            skipped="no_queue",
            queue_path=None,
            queue_body=None,
            next_epic_id=None,
            next_kind=None,
            complete=True,
        )

    qa_artifacts = phase_artifacts(project, role_key, epic_id, "qa")
    if not qa_artifacts:
        raise ValueError("qa_artifact_missing")
    verdict = qa_verdict(qa_artifacts[-1])
    if verdict not in {"pass", "passed", "complete", "completed"}:
        raise ValueError(f"qa_fail_blocks_advance: latest QA verdict is {verdict!r}")
    if not phase_artifacts(project, role_key, epic_id, "context-sync"):
        raise ValueError("context_sync_missing_blocks_advance")

    queue = [row for row in (doc.get("queue") or []) if isinstance(row, dict)]
    done = [row for row in (doc.get("done") or []) if isinstance(row, dict)]

    already = any(_row_matches(row, epic_id) for row in done)
    marked = False
    skipped: str | None = None
    if already:
        skipped = "already_done"
    else:
        hit = next((i for i, row in enumerate(queue) if _row_matches(row, epic_id)), None)
        if hit is None:
            skipped = "not_in_queue"
        else:
            row = queue.pop(hit)
            done_row = {
                "id": row.get("id") or epic_id,
                "epic_id": row.get("epic_id") or _epic_slug(row) or epic_id,
                "kind": row.get("kind") or "feature",
                "plan": row.get("plan") or f"plan-{epic_id}.md",
            }
            if row.get("batch"):
                done_row["batch"] = row["batch"]
            if row.get("deps") is not None:
                done_row["deps"] = row.get("deps") or []
            done.append(done_row)
            marked = True

    body = _dump_queue(doc, role=str(doc.get("role") or role_key), queue=queue, done=done)

    if not queue:
        return RoadmapAdvance(
            marked=marked,
            already_done=already,
            skipped=skipped,
            queue_path=qpath,
            queue_body=body if marked else None,
            next_epic_id=None,
            next_kind=None,
            complete=True,
        )

    blocked, blocked_reason = cadence_blocks_feature_advance(project, role_key)
    if blocked:
        return RoadmapAdvance(
            marked=marked,
            already_done=already,
            skipped=skipped,
            queue_path=qpath,
            queue_body=body if marked else None,
            next_epic_id=None,
            next_kind=None,
            complete=True,
            blocked_reason=blocked_reason,
        )

    head = queue[0]
    next_id = _epic_slug(head)
    next_kind = str(head.get("kind") or "feature").strip().lower() or "feature"
    if not next_id:
        return RoadmapAdvance(
            marked=marked,
            already_done=already,
            skipped=skipped,
            queue_path=qpath,
            queue_body=body if marked else None,
            next_epic_id=None,
            next_kind=None,
            complete=True,
            blocked_reason="next_queue_row_missing_epic_id",
        )
    if not plan_path(project, role_key, next_id).is_file():
        raise ValueError(
            f"next_epic_plan_missing: memory-bank/{role_key}/plan/{next_id}/md/plan.md"
        )

    return RoadmapAdvance(
        marked=marked,
        already_done=already,
        skipped=skipped,
        queue_path=qpath,
        queue_body=body if marked else None,
        next_epic_id=next_id,
        next_kind=next_kind,
        complete=False,
        blocked_reason=None,
    )
