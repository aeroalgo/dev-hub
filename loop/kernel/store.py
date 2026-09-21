from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .model import Cursor, utc_now

try:
    import fcntl
except ImportError:  # pragma: no cover - the supported runtime is POSIX
    fcntl = None


JOURNAL_SCHEMA = "loop-journal/v1"


class ConcurrentWriteError(RuntimeError):
    pass


def project_root(value: str | Path | None = None) -> Path:
    candidate = Path(value or os.environ.get("PROJECT_ROOT") or Path.cwd()).resolve()
    if not (candidate / "memory-bank").is_dir():
        raise ValueError(f"not a loop project: {candidate} (memory-bank/ missing)")
    return candidate


def hub_root() -> Path:
    return Path(os.environ.get("HUB_ROOT") or os.environ.get("DEV_HUB") or Path.cwd()).resolve()


@dataclass(frozen=True)
class LoopPaths:
    project: Path
    hub: Path

    @property
    def runtime(self) -> Path:
        identity = hashlib.sha256(str(self.project).encode("utf-8")).hexdigest()[:10]
        return self.hub / "runtime" / f"{self.project.name}-{identity}" / "epic"

    @property
    def cursor(self) -> Path:
        return self.runtime / "cursor.json"

    @property
    def lock(self) -> Path:
        return self.runtime / "cursor.lock"

    @property
    def events(self) -> Path:
        return self.runtime / "events.jsonl"

    @property
    def boundary_state(self) -> Path:
        return self.runtime / "boundary-state.json"

    @property
    def sessions(self) -> Path:
        return self.runtime / "sessions"

    @property
    def active_context(self) -> Path:
        return self.project / "memory-bank" / "activeContext.md"

    @classmethod
    def for_project(cls, value: str | Path | None = None) -> "LoopPaths":
        return cls(project=project_root(value), hub=hub_root())


def file_digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def text_digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fsync_directory(path: Path) -> None:
    if os.name != "posix":
        return
    try:
        descriptor = os.open(path, os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    _fsync_directory(path.parent)


class _CursorLock:
    def __init__(self, paths: LoopPaths):
        self.paths = paths
        self.handle = None

    def __enter__(self) -> None:
        self.paths.runtime.mkdir(parents=True, exist_ok=True)
        self.handle = self.paths.lock.open("a+", encoding="utf-8")
        if fcntl is not None:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)

    def __exit__(self, *_: Any) -> None:
        if self.handle is not None:
            if fcntl is not None:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()
            self.handle = None


@dataclass(frozen=True)
class FileMutation:
    path: Path
    content: str
    expected_hash: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "content": self.content,
            "expected_hash": self.expected_hash,
            "content_hash": text_digest(self.content),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FileMutation":
        path = Path(str(payload.get("path") or ""))
        content = str(payload.get("content") or "")
        expected_hash = payload.get("expected_hash")
        return cls(path, content, str(expected_hash) if expected_hash else None)


@dataclass(frozen=True)
class TransactionPlan:
    cursor: Cursor | None
    event: dict[str, Any] = field(default_factory=dict)
    mutations: tuple[FileMutation, ...] = ()
    additional_events: tuple[dict[str, Any], ...] = ()
    changed: bool = True


@dataclass(frozen=True)
class CommitResult:
    cursor: Cursor | None
    tx_id: str | None
    changed: bool
    event: dict[str, Any] = field(default_factory=dict)


class StoreTransaction:
    def __init__(self, store: "CursorStore", current: Cursor | None):
        self.store = store
        self.current = current

    def event_seen(self, event: str, key: str) -> bool:
        return self.store._event_seen_unlocked(event, key)

    def event_count(self, event: str, key_prefix: str = "") -> int:
        return self.store._event_count_unlocked(event, key_prefix)

    def mutation(self, path: Path, content: str) -> FileMutation:
        return FileMutation(path.resolve(), content, file_digest(path))


class CursorStore:
    """The sole writer and transaction owner for loop state and projections."""

    def __init__(self, paths: LoopPaths):
        self.paths = paths

    def _read_unlocked(self) -> Cursor | None:
        if not self.paths.cursor.is_file():
            return None
        try:
            payload = json.loads(self.paths.cursor.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cursor is unreadable: {self.paths.cursor}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("cursor must be a JSON object")
        return Cursor.from_dict(payload)

    def _journal(self) -> list[dict[str, Any]]:
        if not self.paths.events.is_file():
            return []
        records: list[dict[str, Any]] = []
        lines = self.paths.events.read_bytes().splitlines(keepends=True)
        offset = 0
        for index, raw in enumerate(lines):
            if not raw.strip():
                offset += len(raw)
                continue
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as exc:
                if index == len(lines) - 1 and not raw.endswith(b"\n"):
                    with self.paths.events.open("r+b") as handle:
                        handle.truncate(offset)
                        handle.flush()
                        os.fsync(handle.fileno())
                    break
                raise ValueError(f"journal is unreadable at line {index + 1}: {exc}") from exc
            if not isinstance(value, dict) or value.get("schema") != JOURNAL_SCHEMA:
                raise ValueError(f"unsupported journal record at line {index + 1}")
            records.append(value)
            offset += len(raw)
        return records

    def _write_cursor_unlocked(self, cursor: Cursor) -> None:
        _atomic_write(self.paths.cursor, json.dumps(cursor.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    def _event_parts(self, event: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        event_name = str(event.get("event") or "transition")
        return event_name, {key: value for key, value in event.items() if key != "event"}

    def _commit_record(self, tx_id: str, cursor: Cursor, event: dict[str, Any], additional_events: tuple[dict[str, Any], ...]) -> dict[str, Any]:
        event_name, fields = self._event_parts(event)
        record: dict[str, Any] = {
            "schema": JOURNAL_SCHEMA,
            "record_type": "commit",
            "tx_id": tx_id,
            "event": event_name,
            "cursor": cursor.to_dict(),
            "at": utc_now(),
            **fields,
        }
        if additional_events:
            record["events"] = [dict(item) for item in additional_events]
        return record

    def _observation_record(self, event: dict[str, Any]) -> dict[str, Any]:
        event_name, fields = self._event_parts(event)
        return {
            "schema": JOURNAL_SCHEMA,
            "record_type": "observation",
            "event": event_name,
            "at": utc_now(),
            **fields,
        }

    def _mutation_allowed(self, path: Path) -> bool:
        candidate = path.resolve()
        return candidate == self.paths.active_context.resolve() or candidate.is_relative_to(self.paths.project.resolve())

    def _apply_mutation_unlocked(self, mutation: FileMutation) -> None:
        path = mutation.path.resolve()
        if not self._mutation_allowed(path):
            raise ValueError(f"transaction mutation outside project: {path}")
        current = file_digest(path)
        target = text_digest(mutation.content)
        if current == target:
            return
        if current != mutation.expected_hash:
            raise ConcurrentWriteError(f"file changed during transaction: {path}")
        _atomic_write(path, mutation.content)

    def _prepared_record(self, tx_id: str, current: Cursor | None, cursor: Cursor, event: dict[str, Any], mutations: tuple[FileMutation, ...], additional_events: tuple[dict[str, Any], ...]) -> dict[str, Any]:
        event_name, fields = self._event_parts(event)
        return {
            "schema": JOURNAL_SCHEMA,
            "record_type": "prepare",
            "tx_id": tx_id,
            "base_revision": current.revision if current else 0,
            "target_revision": cursor.revision,
            "cursor": cursor.to_dict(),
            "event_name": event_name,
            "event_fields": fields,
            "mutations": [item.to_dict() for item in mutations],
            "additional_events": [self._event_parts(item) for item in additional_events],
            "at": utc_now(),
        }

    def _recover_unlocked(self) -> Cursor | None:
        records = self._journal()
        prepared = {str(record.get("tx_id")): record for record in records if record.get("record_type") == "prepare"}
        committed = {str(record.get("tx_id")) for record in records if record.get("record_type") == "commit"}
        current = self._read_unlocked()
        for tx_id, record in prepared.items():
            if tx_id in committed:
                continue
            target_payload = record.get("cursor")
            if not isinstance(target_payload, dict):
                raise ValueError(f"journal transaction has no cursor: {tx_id}")
            target = Cursor.from_dict(target_payload)
            if current is not None and current.revision > target.revision:
                raise ValueError(f"journal transaction is stale: {tx_id}")
            mutations = tuple(FileMutation.from_dict(item) for item in record.get("mutations", []) if isinstance(item, dict))
            for mutation in mutations:
                self._apply_mutation_unlocked(mutation)
            if current is None or current.revision < target.revision:
                self._write_cursor_unlocked(target)
                current = target
            elif current.to_dict() != target.to_dict():
                raise ValueError(f"cursor conflicts with journal transaction: {tx_id}")
            event = {"event": str(record.get("event_name") or "transition"), **dict(record.get("event_fields") or {})}
            additional = tuple(
                {"event": str(item[0]), **dict(item[1])}
                for item in record.get("additional_events", [])
                if isinstance(item, (list, tuple)) and len(item) == 2 and isinstance(item[1], dict)
            )
            _append_jsonl(self.paths.events, self._commit_record(tx_id, target, event, additional))
            committed.add(tx_id)
        return current

    def read(self) -> Cursor | None:
        with _CursorLock(self.paths):
            return self._recover_unlocked()

    def transact(self, planner: Callable[[Cursor | None, StoreTransaction], TransactionPlan]) -> CommitResult:
        with _CursorLock(self.paths):
            current = self._recover_unlocked()
            context = StoreTransaction(self, current)
            plan = planner(current, context)
            if not plan.changed:
                return CommitResult(current, None, False, plan.event)
            if plan.cursor is None:
                _append_jsonl(self.paths.events, self._observation_record(plan.event))
                for additional in plan.additional_events:
                    _append_jsonl(self.paths.events, self._observation_record(additional))
                return CommitResult(current, None, True, plan.event)
            candidate = Cursor.from_dict(plan.cursor.to_dict())
            candidate.revision = current.revision + 1 if current else 1
            candidate.updated_at = utc_now()
            tx_id = f"tx-{uuid.uuid4().hex}"
            prepared = self._prepared_record(tx_id, current, candidate, plan.event, plan.mutations, plan.additional_events)
            _append_jsonl(self.paths.events, prepared)
            for mutation in plan.mutations:
                self._apply_mutation_unlocked(mutation)
            self._write_cursor_unlocked(candidate)
            _append_jsonl(self.paths.events, self._commit_record(tx_id, candidate, plan.event, plan.additional_events))
            return CommitResult(candidate, tx_id, True, plan.event)

    def _event_records_unlocked(self) -> list[dict[str, Any]]:
        self._recover_unlocked()
        return [record for record in self._journal() if record.get("record_type") in {"commit", "observation"}]

    @staticmethod
    def _event_matches(record: dict[str, Any], event: str, key: str) -> bool:
        if record.get("event") == event and record.get("key") == key:
            return True
        return any(
            isinstance(item, dict) and item.get("event") == event and item.get("key") == key
            for item in record.get("events", [])
        )

    def _event_seen_unlocked(self, event: str, key: str) -> bool:
        return any(self._event_matches(record, event, key) for record in self._event_records_unlocked())

    def _event_count_unlocked(self, event: str, key_prefix: str = "") -> int:
        count = 0
        for record in self._event_records_unlocked():
            candidates = [record, *(item for item in record.get("events", []) if isinstance(item, dict))]
            for item in candidates:
                if item.get("event") != event:
                    continue
                key = str(item.get("key") or "")
                if key.startswith(key_prefix) and key[len(key_prefix) :].isdigit():
                    count += 1
        return count

    def event_seen(self, event: str, key: str) -> bool:
        with _CursorLock(self.paths):
            return self._event_seen_unlocked(event, key)

    def event_count(self, event: str, key_prefix: str = "") -> int:
        with _CursorLock(self.paths):
            return self._event_count_unlocked(event, key_prefix)

    def record_event(self, event: dict[str, Any]) -> None:
        def planner(_current: Cursor | None, _context: StoreTransaction) -> TransactionPlan:
            return TransactionPlan(None, event)

        self.transact(planner)

    def session_log(self, session_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", session_id).strip("-") or "session"
        self.paths.sessions.mkdir(parents=True, exist_ok=True)
        return self.paths.sessions / f"{safe}.log"


__all__ = [
    "CommitResult",
    "ConcurrentWriteError",
    "CursorStore",
    "FileMutation",
    "LoopPaths",
    "StoreTransaction",
    "TransactionPlan",
    "file_digest",
    "hub_root",
    "project_root",
    "text_digest",
]
