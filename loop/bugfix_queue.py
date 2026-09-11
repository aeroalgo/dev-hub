"""Read/write and lifecycle operations for epic-bugfix-queue/v1."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

import yaml

from loop.paths.epic_layout import EpicLayoutKind, normalize_role_dir, resolve
from loop.schemas.bugfix_queue import (
    BUGFIX_QUEUE_ITEM_CLASSES,
    BUGFIX_QUEUE_TERMINAL_STATUSES,
    BugfixQueueItem,
    BugfixVerification,
    EpicBugfixQueue,
    utc_now,
)

_PATH_RE = re.compile(
    r"(?<![\w.-])((?:loop|harness|bin|dsh|tests)(?:/[\w.{}-]+)+\.(?:py|sh|md|yaml|yml|toml|json))"
)
_VERIFY_RE = re.compile(r"(?:^|\s)((?:timeout\s+\S+\s+)?bin/pytest\s+[^\n]+)", re.I)
_CLASS_RE = re.compile(r"^([a-z_]+):\s*(.+)$", re.I)


def bugfix_queue_path(cwd: str | Path, role: str, epic_id: str) -> Path:
    role_dir = normalize_role_dir(role)
    if not str(epic_id).strip() or "/" in epic_id or "\\" in epic_id or ".." in epic_id:
        raise ValueError(f"invalid epic_id: {epic_id!r}")
    return resolve(
        role_dir,
        epic_id,
        EpicLayoutKind.BUGFIX_QUEUE_YAML,
        project_root=Path(cwd).resolve(),
    )


def _queue_data(queue: EpicBugfixQueue) -> dict[str, Any]:
    return queue.model_dump(by_alias=True, exclude_none=False)


def load_bugfix_queue(path: str | Path) -> EpicBugfixQueue:
    queue_path = Path(path)
    if not queue_path.is_file():
        raise FileNotFoundError(queue_path)
    raw = yaml.safe_load(queue_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"bugfix queue must be a YAML mapping: {queue_path}")
    return EpicBugfixQueue.model_validate(raw)


def save_bugfix_queue(path: str | Path, queue: EpicBugfixQueue) -> EpicBugfixQueue:
    queue = queue.model_copy(update={"updated_at": utc_now()})
    queue = EpicBugfixQueue.model_validate(_queue_data(queue))
    queue_path = Path(path)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    payload = yaml.safe_dump(_queue_data(queue), allow_unicode=True, sort_keys=False)
    temp = queue_path.with_name(f"{queue_path.name}.tmp")
    temp.write_text(payload, encoding="utf-8")
    temp.replace(queue_path)
    return queue


def _relative(cwd: Path, path: Path) -> str:
    return path.resolve().relative_to(cwd.resolve()).as_posix()


def _qa_lists(qa_artifact: str | Path) -> tuple[dict[str, Any], list[str], list[str]]:
    path = Path(qa_artifact)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"QA artifact must be a YAML mapping: {path}")
    def rows(value: object) -> list[str]:
        result: list[str] = []
        values = value if isinstance(value, list) else []
        for item in values:
            if isinstance(item, dict) and len(item) == 1:
                key, body = next(iter(item.items()))
                item = f"{key}: {body}"
            text = str(item).strip()
            if text:
                result.append(text)
        return result

    blockers = rows(raw.get("blockers"))
    fix_plan = rows(raw.get("fix_plan"))
    if len(blockers) != len(fix_plan):
        raise ValueError("QA blockers and fix_plan must be 1:1")
    return raw, blockers, fix_plan


def _parse_blocker(raw: str) -> tuple[str, str]:
    match = _CLASS_RE.match(raw)
    if not match or match.group(1).lower() not in BUGFIX_QUEUE_ITEM_CLASSES:
        raise ValueError(f"ineligible or unclassified QA blocker: {raw!r}")
    return match.group(1).lower(), match.group(2).strip()


def _targets(*texts: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for match in _PATH_RE.finditer(text):
            value = match.group(1).strip("`\"'.,:;)")
            if value not in seen:
                seen.add(value)
                result.append(value)
    return result


def _targeted_verify(fix_plan: str, targets: list[str], body: str) -> str:
    match = _VERIFY_RE.search(fix_plan)
    if match:
        command = match.group(1).strip().strip("`\"'")
        if not re.search(r"bin/pytest\s+-q\s+--tb=line(?:\s|$)", command):
            return command
    if targets:
        return f"bin/pytest {' '.join(targets)} -q --tb=line"
    return f"targeted evidence required: {body}"


def _next_id(items: Iterable[BugfixQueueItem]) -> str:
    numbers = [int(item.id[3:]) for item in items if re.fullmatch(r"BF-\d+", item.id)]
    return f"BF-{(max(numbers, default=0) + 1):03d}"


def _refresh_current(queue: EpicBugfixQueue) -> EpicBugfixQueue:
    active = [item.id for item in queue.items if item.status in {"open", "in_progress"}]
    return queue.model_copy(update={"current_id": active[0] if active else None})


def _new_items(blockers: list[str], fix_plan: list[str], existing: list[BugfixQueueItem]) -> list[BugfixQueueItem]:
    existing_refs = {item.blocker_ref for item in existing}
    result: list[BugfixQueueItem] = []
    items = list(existing)
    for index, blocker in enumerate(blockers):
        klass, body = _parse_blocker(blocker)
        if blocker in existing_refs:
            continue
        plan = fix_plan[index]
        targets = _targets(blocker, plan)
        item = BugfixQueueItem(
            id=_next_id([*items, *result]),
            status="open",
            **{"class": klass},
            title=body,
            blocker_ref=blocker,
            fix_plan_ref=plan,
            targets=targets,
            verify=_targeted_verify(plan, targets, body),
        )
        result.append(item)
    return result


def seed_or_merge_bugfix_queue(
    cwd: str | Path,
    role: str,
    epic_id: str,
    qa_artifact: str | Path,
) -> tuple[Path, EpicBugfixQueue]:
    root = Path(cwd).resolve()
    qa_path = Path(qa_artifact).resolve()
    raw, blockers, fix_plan = _qa_lists(qa_path)
    checklist_sha = str(raw.get("checklist_sha256") or "").strip()
    if not checklist_sha:
        raise ValueError("QA artifact requires checklist_sha256 for bugfix queue")
    path = bugfix_queue_path(root, role, epic_id)
    existing = load_bugfix_queue(path) if path.is_file() else None
    if existing is not None:
        if existing.epic_id != epic_id or existing.role != normalize_role_dir(role):
            raise ValueError("existing bugfix queue identity does not match QA")
        if existing.checklist_sha256 != checklist_sha:
            raise ValueError("bugfix queue checklist_sha256 drift")
        items = list(existing.items)
        source = _relative(root, qa_path)
        queue = existing.model_copy(update={"source_qa": source, "items": items})
    else:
        source = _relative(root, qa_path)
        queue = EpicBugfixQueue(
            epic_id=epic_id,
            role=normalize_role_dir(role),
            source_qa=source,
            checklist_sha256=checklist_sha,
            created_at=utc_now(),
            updated_at=utc_now(),
            verification=BugfixVerification(),
            items=[],
        )
    additions = _new_items(blockers, fix_plan, list(queue.items))
    updates: dict[str, Any] = {"items": [*queue.items, *additions]}
    if additions:
        updates["verification"] = BugfixVerification(command=queue.verification.command)
    queue = _refresh_current(queue.model_copy(update=updates))
    return path, save_bugfix_queue(path, queue)


def validate_queue_for_qa(
    cwd: str | Path, queue_path: str | Path, qa_artifact: str | Path, epic_id: str, role: str
) -> list[str]:
    root = Path(cwd).resolve()
    try:
        queue = load_bugfix_queue(queue_path)
    except FileNotFoundError:
        return ["bugfix queue missing"]
    except Exception as exc:
        return [f"bugfix queue invalid: {exc}"]
    try:
        raw, blockers, fix_plan = _qa_lists(qa_artifact)
    except Exception as exc:
        return [str(exc)]
    errors: list[str] = []
    if queue.epic_id != epic_id:
        errors.append("bugfix queue epic_id mismatch")
    if queue.role != normalize_role_dir(role):
        errors.append("bugfix queue role mismatch")
    if queue.source_qa != _relative(root, Path(qa_artifact)):
        errors.append("bugfix queue source_qa mismatch")
    if queue.checklist_sha256 != str(raw.get("checklist_sha256") or "").strip():
        errors.append("bugfix queue checklist_sha256 mismatch")
    queue_refs = {item.blocker_ref for item in queue.items}
    for blocker, plan in zip(blockers, fix_plan):
        if blocker not in queue_refs:
            errors.append(f"missing queue item for QA blocker: {blocker}")
        else:
            item = next(item for item in queue.items if item.blocker_ref == blocker)
            if item.fix_plan_ref != plan:
                errors.append(f"fix_plan mismatch for QA blocker: {blocker}")
    return errors


def update_bugfix_item(
    path: str | Path,
    item_id: str,
    status: str,
    *,
    evidence: str | None = None,
    done_at: str | None = None,
    notes: str | None = None,
) -> EpicBugfixQueue:
    queue = load_bugfix_queue(path)
    item_index = next((i for i, item in enumerate(queue.items) if item.id == item_id), None)
    if item_index is None:
        raise ValueError(f"unknown bugfix queue item: {item_id}")
    item = queue.items[item_index]
    first_active = next((candidate for candidate in queue.items if candidate.status in {"open", "in_progress"}), None)
    if status in {"in_progress", "done", "blocked", "cancelled"} and first_active and first_active.id != item_id:
        raise ValueError(f"cannot skip current bugfix queue item {first_active.id}")
    if status == "in_progress" and item.status not in {"open", "in_progress"}:
        raise ValueError(f"cannot start item {item_id} from status {item.status}")
    if status == "done" and item.status != "in_progress":
        raise ValueError(f"item {item_id} must be in_progress before done")
    if status in {"blocked", "cancelled"} and item.status not in {"open", "in_progress"}:
        raise ValueError(f"cannot transition item {item_id} from status {item.status}")
    if status == "done" and not str(evidence or item.evidence or "").strip():
        raise ValueError(f"done item {item_id} requires targeted evidence")
    updates: dict[str, Any] = {"status": status}
    if evidence is not None:
        updates["evidence"] = evidence
    if status == "done":
        updates["done_at"] = done_at or utc_now()
    if notes is not None:
        updates["notes"] = notes
    items = list(queue.items)
    items[item_index] = item.model_copy(update=updates)
    updated = _refresh_current(queue.model_copy(update={"items": items}))
    return save_bugfix_queue(path, updated)


def set_bugfix_verification(
    path: str | Path, status: str, *, evidence: str | None = None, last_run_at: str | None = None
) -> EpicBugfixQueue:
    queue = load_bugfix_queue(path)
    if any(item.status not in BUGFIX_QUEUE_TERMINAL_STATUSES for item in queue.items):
        raise ValueError("full verification is allowed only when bugfix queue items are terminal")
    verification = queue.verification.model_copy(
        update={"status": status, "evidence": evidence, "last_run_at": last_run_at or utc_now()}
    )
    return save_bugfix_queue(path, queue.model_copy(update={"verification": verification}))


def append_gate_repair_items(
    path: str | Path, blockers: list[str], *, source_qa: str | None = None
) -> EpicBugfixQueue:
    queue = load_bugfix_queue(path)
    additions = _new_items(blockers, [f"targeted repair: {item}" for item in blockers], list(queue.items))
    updated = queue.model_copy(
        update={
            "items": [*queue.items, *additions],
            "source_qa": source_qa or queue.source_qa,
            "verification": BugfixVerification(command=queue.verification.command),
        }
    )
    return save_bugfix_queue(path, _refresh_current(updated))


mark_bugfix_item = update_bugfix_item
gate_repair_append = append_gate_repair_items


__all__ = [
    "append_gate_repair_items",
    "bugfix_queue_path",
    "gate_repair_append",
    "load_bugfix_queue",
    "mark_bugfix_item",
    "save_bugfix_queue",
    "seed_or_merge_bugfix_queue",
    "set_bugfix_verification",
    "update_bugfix_item",
    "validate_queue_for_qa",
]
