from __future__ import annotations

import json
import hashlib
import os
import re
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from .model import Cursor, utc_now

try:
    import fcntl
except ImportError:  # pragma: no cover - the supported runtime is POSIX
    fcntl = None


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
    def sessions(self) -> Path:
        return self.runtime / "sessions"

    @property
    def active_context(self) -> Path:
        return self.project / "memory-bank" / "activeContext.md"

    @classmethod
    def for_project(cls, value: str | Path | None = None) -> "LoopPaths":
        return cls(project=project_root(value), hub=hub_root())


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


@contextmanager
def cursor_lock(paths: LoopPaths) -> Iterator[None]:
    paths.runtime.mkdir(parents=True, exist_ok=True)
    handle = paths.lock.open("a+", encoding="utf-8")
    try:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


class CursorStore:
    """The only writer for the runtime cursor and generated active context."""

    def __init__(self, paths: LoopPaths):
        self.paths = paths

    def read(self) -> Cursor | None:
        if not self.paths.cursor.is_file():
            return None
        try:
            payload = json.loads(self.paths.cursor.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cursor is unreadable: {self.paths.cursor}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("cursor must be a JSON object")
        return Cursor.from_dict(payload)

    def write(self, cursor: Cursor) -> Cursor:
        cursor.revision += 1
        cursor.updated_at = utc_now()
        _atomic_write(self.paths.cursor, json.dumps(cursor.to_dict(), indent=2, sort_keys=True) + "\n")
        return cursor

    def append_event(self, event: dict[str, Any]) -> None:
        self.paths.events.parent.mkdir(parents=True, exist_ok=True)
        payload = {"at": utc_now(), **event}
        with self.paths.events.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    def write_active_context(self, body: str) -> None:
        _atomic_write(self.paths.active_context, body)

    def session_log(self, session_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", session_id).strip("-") or "session"
        self.paths.sessions.mkdir(parents=True, exist_ok=True)
        return self.paths.sessions / f"{safe}.log"
