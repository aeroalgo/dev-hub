from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .model import Cursor
from .store import LoopPaths

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


BOUNDARY_SCHEMA = "loop-boundary/v1"
READ_TOOLS = frozenset({"read", "readfile", "read_file", "view", "file_read", "open_file", "notebookread", "notebook_read", "cat"})
WRITE_TOOLS = frozenset({"write", "edit", "notebookedit", "notebook_edit", "multiedit", "multi_edit", "apply_patch", "patch", "create_file", "delete_file", "rename_file", "mv", "rm"})
PATH_KEYS = ("file_path", "path", "notebook_path", "file", "filename", "target_path", "target", "uri", "path_to_file", "source_path")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        return dict(default)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"boundary state is unreadable: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"boundary state must be an object: {path}")
    return value


class _StateLock:
    def __init__(self, path: Path, timeout: float = 3.0):
        self.path = path
        self.timeout = timeout
        self.handle = None

    def __enter__(self) -> "_StateLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+", encoding="utf-8")
        if fcntl is not None:
            deadline = time.monotonic() + self.timeout
            while True:
                try:
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except (BlockingIOError, OSError):
                    if time.monotonic() >= deadline:
                        fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
                        break
                    time.sleep(0.01)
        return self

    def __exit__(self, *_: Any) -> None:
        if self.handle is not None:
            if fcntl is not None:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()
            self.handle = None


@dataclass(frozen=True)
class ActorIdentity:
    project_root: str
    root_session_id: str
    invocation_id: str
    provider: str = "codex"
    kind: str = "root"
    parent_invocation_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "root_session_id": self.root_session_id,
            "invocation_id": self.invocation_id,
            "provider": self.provider,
            "kind": self.kind,
            "parent_invocation_id": self.parent_invocation_id,
        }

    def key(self) -> str:
        return hashlib.sha256(json.dumps(self.as_dict(), sort_keys=True).encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class ReadRequest:
    path: str
    actor: ActorIdentity
    interval: tuple[int, int] | None
    content_hash: str | None
    mode: str
    purpose: str | None = None
    exception_reason: str | None = None


@dataclass(frozen=True)
class BoundaryReceipt:
    decision: str
    reason: str
    diagnostic: str
    path: str
    content_hash: str | None
    requested_intervals: list[list[int]] = field(default_factory=list)
    allowed_intervals: list[list[int]] = field(default_factory=list)
    cached_intervals: list[list[int]] = field(default_factory=list)
    actor: dict[str, Any] = field(default_factory=dict)
    sequence: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.decision in {"allowed", "partial", "exception"}

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": BOUNDARY_SCHEMA,
            "decision": self.decision,
            "reason": self.reason,
            "diagnostic": self.diagnostic,
            "path": self.path,
            "content_hash": self.content_hash,
            "requested_intervals": self.requested_intervals,
            "allowed_intervals": self.allowed_intervals,
            "cached_intervals": self.cached_intervals,
            "actor": self.actor,
            "sequence": self.sequence,
            "metadata": self.metadata,
        }


def canonical_path(raw: str | Path, project_root: str | Path) -> Path:
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = Path(project_root).expanduser() / candidate
    return Path(os.path.realpath(str(candidate)))


def content_hash(path: str | Path) -> str | None:
    try:
        candidate = Path(path)
        if not candidate.is_file():
            return None
        return "sha256:" + hashlib.sha256(candidate.read_bytes()).hexdigest()
    except OSError:
        return None


def line_count(path: str | Path) -> int | None:
    try:
        candidate = Path(path)
        if not candidate.is_file():
            return None
        with candidate.open("rb") as handle:
            return max(1, sum(1 for _ in handle))
    except OSError:
        return None


def interval_bytes(path: str | Path, interval: Sequence[int]) -> int:
    try:
        start, end = int(interval[0]), int(interval[1])
        with Path(path).open("rb") as handle:
            return sum(len(line) for line in handle.readlines()[start - 1 : end])
    except (OSError, TypeError, ValueError):
        return 0


def normalize_intervals(intervals: Iterable[Sequence[int]]) -> list[list[int]]:
    values: list[list[int]] = []
    for interval in intervals:
        if len(interval) < 2:
            continue
        try:
            start, end = int(interval[0]), int(interval[1])
        except (TypeError, ValueError):
            continue
        if start >= 1 and end >= start:
            values.append([start, end])
    values.sort()
    merged: list[list[int]] = []
    for start, end in values:
        if not merged or start > merged[-1][1] + 1:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return merged


def subtract_interval(target: Sequence[int], covered: Iterable[Sequence[int]]) -> tuple[list[list[int]], list[list[int]]]:
    start, end = int(target[0]), int(target[1])
    missing: list[list[int]] = []
    present: list[list[int]] = []
    cursor = start
    for cached_start, cached_end in normalize_intervals(covered):
        if cached_end < cursor:
            continue
        if cached_start > end:
            break
        overlap_start, overlap_end = max(cursor, cached_start), min(end, cached_end)
        if overlap_start <= overlap_end:
            if cursor < overlap_start:
                missing.append([cursor, overlap_start - 1])
            present.append([overlap_start, overlap_end])
            cursor = overlap_end + 1
    if cursor <= end:
        missing.append([cursor, end])
    return missing, present


def _tool_name(payload: Mapping[str, Any]) -> str:
    return str(payload.get("tool_name") or payload.get("tool") or payload.get("name") or "").strip().lower()


def _tool_input(payload: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("tool_input", "arguments", "args", "input"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return dict(payload)


def _patch_paths(value: str) -> list[str]:
    paths: list[str] = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        for marker in ("*** Update File: ", "*** Add File: ", "*** Delete File: ", "*** Move to: "):
            if line.startswith(marker):
                path = line[len(marker) :].strip()
                if path and path not in paths:
                    paths.append(path)
    return paths


def paths_from_payload(payload: Mapping[str, Any]) -> list[str]:
    tool_input = _tool_input(payload)
    result: list[str] = []
    for key in PATH_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip() and value.strip() not in result:
            result.append(value.strip())
    for key in ("patch", "diff", "content", "contents", "input"):
        value = tool_input.get(key)
        if isinstance(value, str):
            for path in _patch_paths(value):
                if path not in result:
                    result.append(path)
    return result


def provider_from_payload(payload: Mapping[str, Any]) -> str:
    explicit = payload.get("runtime_provider") or payload.get("provider") or payload.get("runtime")
    if explicit:
        return str(explicit).strip().lower()
    return "claude" if "hookSpecificOutput" in payload or "tool_use_id" in payload else "codex"


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")[:96] or "actor"


def actor_from_payload(payload: Mapping[str, Any], *, project_root: Path, default_session: str | None = None) -> ActorIdentity:
    nested = _tool_input(payload)
    session = str(payload.get("session_id") or payload.get("root_session_id") or payload.get("executor_session_id") or default_session or os.environ.get("LOOP_SESSION_ID") or "session-unknown")
    provider = provider_from_payload(payload)
    parent = payload.get("parent_invocation_id") or nested.get("parent_invocation_id")
    role = payload.get("subagent_type") or payload.get("agent_type") or nested.get("subagent_type")
    kind = str(payload.get("actor_kind") or ("subagent" if role or parent else "root"))
    invocation = payload.get("agent_invocation_id") or payload.get("invocation_id") or payload.get("thread_id") or payload.get("subagent_id") or payload.get("actor_id") or nested.get("agent_invocation_id")
    if not invocation:
        seed = f"{session}:{provider}:{kind}:{role or ''}:{_tool_name(payload)}:{','.join(paths_from_payload(payload))}"
        invocation = "derived-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return ActorIdentity(str(project_root), session, str(invocation), provider, kind, str(parent) if parent else None)


def _request(payload: Mapping[str, Any], *, project_root: Path, session_id: str) -> ReadRequest:
    raw_paths = paths_from_payload(payload)
    if not raw_paths:
        raise ValueError("read operation has no path")
    nested = _tool_input(payload)
    interval: tuple[int, int] | None = None
    if "offset" in nested or "limit" in nested:
        start, limit = int(nested.get("offset") or 1), int(nested.get("limit") or 0)
        if start < 1 or limit < 1:
            raise ValueError("offset and limit must be positive")
        interval = (start, start + limit - 1)
    elif any(key in nested for key in ("start_line", "end_line", "startLine", "endLine")):
        start = int(nested.get("start_line", nested.get("startLine")) or 1)
        raw_end = nested.get("end_line", nested.get("endLine"))
        interval = (start, int(raw_end)) if raw_end is not None else None
    elif isinstance(nested.get("line_interval"), (list, tuple)) and len(nested["line_interval"]) >= 2:
        start, end = int(nested["line_interval"][0] or 1), nested["line_interval"][1]
        interval = (start, int(end)) if end is not None else None
    return ReadRequest(
        raw_paths[0],
        actor_from_payload(payload, project_root=project_root, default_session=session_id),
        interval,
        str(payload["content_hash"]) if payload.get("content_hash") else None,
        str(payload.get("mode") or "IMPLEMENT").upper(),
        str(payload["purpose"]) if payload.get("purpose") else None,
        str(payload["exception_reason"]) if payload.get("exception_reason") else None,
    )


def _is_plan(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return "/plan/" in normalized or normalized.startswith("memory-bank/plan/") or "/memory-bank/plan/" in normalized


def _default_state() -> dict[str, Any]:
    return {
        "schema": BOUNDARY_SCHEMA,
        "scope_key": "",
        "actors": {},
        "touched": {},
        "records": [],
        "sequence": 0,
        "metrics": {"reads": 0, "duplicates": 0, "partials": 0, "invalidations": 0, "denials": 0, "changes": 0},
        "updated_at": _now(),
    }


def _relative(path: Path, project_root: Path) -> str | None:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return None


def is_read_payload(payload: Mapping[str, Any]) -> bool:
    return _tool_name(payload) in READ_TOOLS


def is_write_payload(payload: Mapping[str, Any]) -> bool:
    return _tool_name(payload) in WRITE_TOOLS


class BoundaryService:
    def __init__(self, paths: LoopPaths):
        self.paths = paths

    @property
    def state_path(self) -> Path:
        return self.paths.boundary_state

    @property
    def lock_path(self) -> Path:
        return self.state_path.with_suffix(".lock")

    def _load(self) -> dict[str, Any]:
        data = _load_json(self.state_path, _default_state())
        if data.get("schema") != BOUNDARY_SCHEMA:
            raise ValueError(f"unsupported boundary schema: {data.get('schema')!r}")
        if "cursor" in data:
            raise ValueError("boundary state contains a legacy cursor identity")
        for key, value in _default_state().items():
            if isinstance(value, dict):
                data.setdefault(key, {}).update({missing: item for missing, item in value.items() if missing not in data[key]})
            else:
                data.setdefault(key, value)
        return data

    def _save(self, data: dict[str, Any]) -> None:
        data["updated_at"] = _now()
        _atomic_json(self.state_path, data)

    @staticmethod
    def _scope_key(cursor: Cursor) -> str:
        raw = ":".join(
            (
                cursor.epic_id,
                cursor.role,
                cursor.phase,
                cursor.step_id,
                cursor.session_id,
                str(cursor.phase_epoch),
            )
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _prepare_scope(self, data: dict[str, Any], cursor: Cursor) -> None:
        scope_key = self._scope_key(cursor)
        if data.get("scope_key") != scope_key:
            data["scope_key"] = scope_key
            data["actors"] = {}
            data["touched"] = {}

    def ensure_step(self, cursor: Cursor) -> dict[str, Any]:
        with _StateLock(self.lock_path):
            data = self._load()
            self._prepare_scope(data, cursor)
            self._save(data)
            return data

    def _receipt(self, decision: str, reason: str, diagnostic: str, request: ReadRequest, path: Path, *, content: str | None = None, requested: list[list[int]] | None = None, allowed: list[list[int]] | None = None, cached: list[list[int]] | None = None, sequence: int = 0, metadata: dict[str, Any] | None = None) -> BoundaryReceipt:
        return BoundaryReceipt(decision, reason, diagnostic, str(path), content, requested or [], allowed or [], cached or [], request.actor.as_dict(), sequence, metadata or {})

    def read(self, payload: Mapping[str, Any], cursor: Cursor) -> BoundaryReceipt:
        try:
            request = _request(payload, project_root=self.paths.project, session_id=cursor.session_id)
            target = canonical_path(request.path, self.paths.project)
        except (TypeError, ValueError) as exc:
            actor = actor_from_payload(payload, project_root=self.paths.project, default_session=cursor.session_id)
            return BoundaryReceipt("denied", "invalid_read", str(exc), "", None, actor=actor.as_dict())
        relative = _relative(target, self.paths.project)
        if relative is None:
            return self._receipt("denied", "path_outside_project", f"read path is outside project: {target}", request, target)
        if _is_plan(relative) and request.mode not in {"PLAN", "DECOMPOSE"} and request.interval is None and not request.exception_reason:
            return self._receipt("denied", "whole_plan_denied", f"whole plan read denied in {request.mode}; request a bounded interval", request, target, content=content_hash(target), metadata={"fail_closed": True})
        disk_version, lines = content_hash(target), line_count(target)
        if disk_version is None:
            return self._receipt("denied", "content_unavailable", f"cannot establish file version: {target}", request, target)
        if request.content_hash and request.content_hash != disk_version:
            return self._receipt("denied", "content_version_mismatch", f"requested version differs from disk: {target}", request, target, content=disk_version)
        if request.interval is None:
            interval = (1, lines or 0)
        else:
            interval = request.interval
        if interval[0] < 1 or interval[1] < interval[0] or (lines is not None and interval[0] > lines):
            return self._receipt("denied", "invalid_read_range", f"invalid line interval {interval} for {target}", request, target, content=disk_version)
        if lines is not None:
            interval = (interval[0], min(interval[1], lines))
        requested = [[interval[0], interval[1]]]
        with _StateLock(self.lock_path):
            data = self._load()
            self._prepare_scope(data, cursor)
            actor_data = data["actors"].setdefault(request.actor.key(), {"identity": request.actor.as_dict(), "step_id": cursor.step_id, "files": []})
            if actor_data.get("step_id") != cursor.step_id:
                actor_data.update({"step_id": cursor.step_id, "files": []})
            files = {str(item.get("path")): item for item in actor_data.get("files", []) if isinstance(item, dict) and item.get("path")}
            state = files.get(relative) or {"path": relative, "version": disk_version, "ranges": []}
            invalidated = bool(state.get("invalidated")) or state.get("version") != disk_version
            if invalidated:
                state.update({"version": disk_version, "ranges": [], "invalidated": False})
                data["metrics"]["invalidations"] += 1
            missing, cached = subtract_interval(interval, state.get("ranges", []))
            data["sequence"] += 1
            sequence = data["sequence"]
            data["metrics"]["reads"] += 1
            if request.exception_reason:
                decision, allowed = "exception", requested
            elif not missing:
                decision, allowed = "duplicate", []
                data["metrics"]["duplicates"] += 1
            elif cached:
                decision, allowed = "partial", missing
                data["metrics"]["partials"] += 1
            else:
                decision, allowed = "allowed", missing
            state["ranges"] = normalize_intervals([*state.get("ranges", []), *allowed])
            state["last_sequence"] = sequence
            files[relative] = state
            actor_data["files"] = list(files.values())
            data["records"] = [*data.get("records", [])[-399:], {"event": "read", "path": relative, "decision": decision, "actor": request.actor.as_dict(), "requested": requested, "allowed": allowed, "cached": cached, "sequence": sequence, "version": disk_version, "at": _now()}]
            data["metrics"]["bytes_read"] = int(data["metrics"].get("bytes_read", 0)) + sum(interval_bytes(target, item) for item in allowed)
            self._save(data)
        return self._receipt(decision, {"allowed": "new_range", "partial": "uncovered_range", "duplicate": "already_read", "exception": "explicit_exception"}[decision], f"{decision} read for {relative} lines {interval[0]}..{interval[1]}", request, target, content=disk_version, requested=requested, allowed=allowed, cached=cached, sequence=sequence, metadata={"invalidated": invalidated})

    def _invalidate_session(self, data: dict[str, Any], session_id: str, relative: str, version: str | None) -> None:
        for actor_data in data.get("actors", {}).values():
            identity = actor_data.get("identity") or {}
            if identity.get("root_session_id") != session_id:
                continue
            for file_data in actor_data.get("files", []):
                if file_data.get("path") == relative:
                    file_data.update({"version": version, "ranges": [], "invalidated": True, "invalidated_at": _now()})
                    data["metrics"]["invalidations"] += 1

    def change(self, payload: Mapping[str, Any], cursor: Cursor, *, stage: str) -> dict[str, Any]:
        raw_paths = paths_from_payload(payload)
        if not raw_paths:
            return {"ok": False, "reason": "write_path_missing", "paths": []}
        actor = actor_from_payload(payload, project_root=self.paths.project, default_session=cursor.session_id)
        changes: list[str] = []
        rejected: list[str] = []
        with _StateLock(self.lock_path):
            data = self._load()
            self._prepare_scope(data, cursor)
            for raw_path in raw_paths:
                target = canonical_path(raw_path, self.paths.project)
                relative = _relative(target, self.paths.project)
                if relative is None:
                    rejected.append(raw_path)
                    continue
                current = content_hash(target)
                item = data["touched"].setdefault(relative, {"path": relative, "before": current, "after": None, "changed": None, "operations": []})
                if stage == "pre" and not item["operations"]:
                    item["before"] = current
                if stage == "post":
                    item.update({"after": current, "changed": item.get("before") != current, "status": "applied"})
                    self._invalidate_session(data, cursor.session_id, relative, current)
                item["operations"] = [*item.get("operations", [])[-31:], {"stage": stage, "tool": _tool_name(payload) or "write", "actor": actor.as_dict(), "at": _now()}]
                item["last_at"] = _now()
                changes.append(relative)
                data["metrics"]["changes"] += 1
            self._save(data)
        return {"ok": not rejected, "reason": "change_recorded" if not rejected else "path_outside_project", "paths": changes, "rejected": rejected}

    def touched_paths(self, cursor: Cursor) -> list[str]:
        data = self._load()
        if data.get("scope_key") != self._scope_key(cursor):
            return []
        return sorted(str(path) for path in data.get("touched", {}) if path)

    def scope(self, cursor: Cursor) -> dict[str, Any]:
        from .index import load_queue, shard_path
        import yaml

        allowlist: set[str] = set()
        try:
            queue = load_queue(self.paths.project, cursor.role, cursor.epic_id)
            step = next((item for item in queue.steps if item.step_id == cursor.step_id), None)
            candidates = [queue.path]
            shard = shard_path(self.paths.project, queue, step) if step else None
            if shard is not None:
                candidates.append(shard)
            for candidate in candidates:
                relative = _relative(candidate, self.paths.project)
                if relative:
                    allowlist.add(relative)
                if not candidate.is_file():
                    continue
                payload = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
                if isinstance(payload, dict):
                    for item in [*(payload.get("files") or []), *(payload.get("deletes") or [])]:
                        path = canonical_path(str(item), self.paths.project)
                        relative = _relative(path, self.paths.project)
                        if relative:
                            allowlist.add(relative)
        except (OSError, ValueError, yaml.YAMLError):
            allowlist = set()
        touched = self.touched_paths(cursor)
        outside = sorted(path for path in touched if allowlist and path not in allowlist)
        return {"schema": "loop-scope/v1", "epic_id": cursor.epic_id, "step_id": cursor.step_id, "touched_paths": touched, "allowlist_paths": sorted(allowlist), "outside_paths": outside, "foreign_dirty_is_blocker": False, "ok": not outside}

    def context(self, cursor: Cursor) -> str:
        data = self._load()
        metrics = data.get("metrics") or {}
        lines = [
            "## Loop boundary context",
            f"attempt: {cursor.attempt}",
            "Read policy: actor-scoped versioned intervals; duplicate ranges are denied and partial reads expose only uncovered ranges.",
            "Mutation policy: every applied change invalidates cached ranges for all actors in the same root session.",
            "Scope policy: touched paths are recorded by tool hooks; unrelated dirty files are not step scope.",
            f"boundary_metrics: {json.dumps(metrics, ensure_ascii=False, sort_keys=True)}",
        ]
        if cursor.failure:
            lines.append(f"retry_context: previous attempt ended with {cursor.failure.code}: {cursor.failure.message}")
        paths = self.touched_paths(cursor)
        lines.append("touched_paths: " + (", ".join(paths) if paths else "(none)"))
        return "\n".join(lines)


def render_read(receipt: BoundaryReceipt, provider: str) -> dict[str, Any]:
    if provider == "claude":
        return {"permission": "allow" if receipt.allowed else "deny", "hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow" if receipt.allowed else "deny", "permissionDecisionReason": receipt.reason, "additionalContext": receipt.diagnostic}, "receipt": receipt.as_dict()}
    return {"decision": receipt.decision, "reason": receipt.reason, "allow": receipt.allowed, "diagnostic": receipt.diagnostic, "receipt": receipt.as_dict(), "exit_code": 0 if receipt.allowed else 1}


__all__ = ["ActorIdentity", "BOUNDARY_SCHEMA", "BoundaryReceipt", "BoundaryService", "ReadRequest", "canonical_path", "content_hash", "is_read_payload", "is_write_payload", "paths_from_payload", "provider_from_payload", "render_read", "normalize_intervals", "subtract_interval"]
