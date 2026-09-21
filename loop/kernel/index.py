from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .store import FileMutation


@dataclass(frozen=True)
class Step:
    step_id: str
    status: str
    title: str
    shard: str | None


@dataclass(frozen=True)
class Queue:
    path: Path
    role: str
    epic_id: str
    steps: tuple[Step, ...]

    @property
    def pending(self) -> tuple[Step, ...]:
        return tuple(step for step in self.steps if step.status not in {"completed", "done"})


def normalize_role(role: str) -> str:
    value = str(role or "").strip().lower()
    if value == "integ":
        value = "integration"
    if value not in {"back", "front", "integration"}:
        raise ValueError(f"unsupported role: {role!r}")
    return value


def index_path(project: Path, role: str, epic_id: str) -> Path:
    if not epic_id or Path(epic_id).name != epic_id:
        raise ValueError(f"invalid epic id: {epic_id!r}")
    return project / "memory-bank" / normalize_role(role) / "plan" / epic_id / "yaml" / "decompose-index.yaml"


def load_queue(project: Path, role: str, epic_id: str) -> Queue:
    path = index_path(project, role, epic_id)
    if not path.is_file():
        raise FileNotFoundError(f"canonical decompose index missing: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict) or not isinstance(payload.get("steps"), list):
        raise ValueError(f"invalid decompose index: {path}")
    steps: list[Step] = []
    for raw in payload["steps"]:
        if not isinstance(raw, dict):
            raise ValueError(f"invalid step entry in {path}")
        step_id = str(raw.get("id") or raw.get("step_id") or "").strip()
        if not step_id:
            raise ValueError(f"step without id in {path}")
        steps.append(
            Step(
                step_id=step_id,
                status=str(raw.get("status") or "pending").lower(),
                title=str(raw.get("title") or step_id),
                shard=str(raw.get("file") or raw.get("shard") or "") or None,
            )
        )
    return Queue(path=path, role=normalize_role(role), epic_id=epic_id, steps=tuple(steps))


def validate_decompose_tree(project: Path, role: str, epic_id: str) -> Queue:
    queue = load_queue(project, role, epic_id)
    payload = yaml.safe_load(queue.path.read_text(encoding="utf-8")) or {}
    if payload.get("schema") != "epic-decompose-index/v1":
        raise ValueError(f"invalid decompose index schema: {queue.path}")
    if str(payload.get("plan_id") or "") != epic_id:
        raise ValueError(f"decompose index plan_id mismatch: expected {epic_id}, got {payload.get('plan_id')!r}")
    if not queue.steps:
        raise ValueError(f"decompose index has no steps: {queue.path}")

    expected_role = normalize_role(role)
    steps_root = (queue.path.parent / "steps").resolve()
    seen: set[str] = set()
    required_step_fields = {
        "schema",
        "role",
        "step_id",
        "plan_id",
        "title",
        "next_phase",
        "goal",
        "plan_contract",
        "context",
        "as_built",
        "delta",
        "deletes",
        "out_of_scope",
        "skills",
        "checkpoints",
        "verify",
        "tdd",
    }
    for position, raw in enumerate(payload["steps"]):
        missing_index_fields = sorted({"id", "file", "title", "next_phase", "status"}.difference(raw))
        if missing_index_fields:
            raise ValueError(f"decompose index step missing fields {missing_index_fields}: {queue.path}")
        step_id = str(raw.get("id") or raw.get("step_id") or "").strip()
        if step_id in seen:
            raise ValueError(f"duplicate decompose step: {step_id}")
        seen.add(step_id)
        file_ref = str(raw.get("file") or "").strip()
        if not file_ref:
            raise ValueError(f"decompose step {step_id!r} has no file")
        shard = shard_path(project, queue, queue.steps[position])
        if shard is None or not shard.is_file():
            raise FileNotFoundError(f"decompose shard missing: {file_ref} ({queue.path})")
        if shard.resolve().parent != steps_root:
            raise ValueError(f"decompose shard outside canonical steps directory: {shard}")
        shard_payload = yaml.safe_load(shard.read_text(encoding="utf-8")) or {}
        if not isinstance(shard_payload, dict):
            raise ValueError(f"invalid decompose shard: {shard}")
        missing = sorted(required_step_fields.difference(shard_payload))
        if missing:
            raise ValueError(f"decompose shard missing fields {missing}: {shard}")
        if shard_payload.get("schema") != "epic-decompose/v1":
            raise ValueError(f"invalid decompose shard schema: {shard}")
        if normalize_role(str(shard_payload.get("role") or "")) != expected_role:
            raise ValueError(f"decompose shard role mismatch: {shard}")
        if str(shard_payload.get("step_id") or "") != step_id:
            raise ValueError(f"decompose shard step_id mismatch: {shard}")
        if str(shard_payload.get("plan_id") or "") != epic_id:
            raise ValueError(f"decompose shard plan_id mismatch: {shard}")
        for field in ("as_built", "delta", "deletes", "out_of_scope", "checkpoints", "verify", "tdd"):
            if not isinstance(shard_payload.get(field), list):
                raise ValueError(f"decompose shard field {field!r} must be a list: {shard}")
        for field in ("plan_contract", "context", "skills"):
            if not isinstance(shard_payload.get(field), dict):
                raise ValueError(f"decompose shard field {field!r} must be a mapping: {shard}")
    return queue


def prepare_step_status(queue: Queue, step_id: str, status: str) -> FileMutation:
    payload = yaml.safe_load(queue.path.read_text(encoding="utf-8")) or {}
    changed = False
    for raw in payload.get("steps", []):
        if str(raw.get("id") or raw.get("step_id") or "") == step_id:
            raw["status"] = status
            changed = True
            break
    if not changed:
        raise ValueError(f"step {step_id!r} not found in {queue.path}")
    current = queue.path.read_text(encoding="utf-8")
    content = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    expected_hash = "sha256:" + hashlib.sha256(current.encode("utf-8")).hexdigest()
    return FileMutation(queue.path.resolve(), content, expected_hash)


def shard_path(project: Path, queue: Queue, step: Step) -> Path | None:
    if not step.shard:
        return None
    raw = Path(step.shard)
    if raw.is_absolute():
        return raw
    candidates = (
        queue.path.parent / raw,
        queue.path.parent / "steps" / raw.name,
        project / "memory-bank" / queue.role / "implement" / queue.epic_id / raw.name,
    )
    return next((candidate for candidate in candidates if candidate.is_file()), candidates[0])


def phase_artifacts(project: Path, role: str, epic_id: str, kind: str) -> list[Path]:
    root = project / "memory-bank" / normalize_role(role) / kind / epic_id
    return sorted(root.glob("*.yaml")) if root.is_dir() else []


def qa_verdict(path: Path) -> str | None:
    try:
        payload: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    return str(payload.get("verdict") or payload.get("status") or "").lower() or None
