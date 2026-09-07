"""Context ledger and deterministic read/edit policy boundary.

Implements actor-isolated, durable, metadata-only tracking of file reads,
interval algebra, hash-based invalidation, and fail-closed decisions.
Provides atomic file persistence and lock coordination.
Part of T-HUB-078 (FR-001, FR-008, FR-009, FR-010).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Iterable, Literal, Sequence

try:
    import fcntl
except ImportError:
    fcntl = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

LEDGER_SCHEMA = "context-ledger/v1"


@dataclass(frozen=True)
class ActorKey:
    project_root: str
    root_session_id: str
    agent_invocation_id: str
    runtime_provider: str = "claude"
    actor_kind: str = "root"  # "root" | "subagent"
    parent_invocation_id: str | None = None

    def identity_tuple(self) -> tuple[str, str, str, str]:
        return (
            self.project_root,
            self.root_session_id,
            self.agent_invocation_id,
            self.runtime_provider,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "root_session_id": self.root_session_id,
            "agent_invocation_id": self.agent_invocation_id,
            "runtime_provider": self.runtime_provider,
            "actor_kind": self.actor_kind,
            "parent_invocation_id": self.parent_invocation_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActorKey:
        return cls(
            project_root=str(data.get("project_root", "")),
            root_session_id=str(data.get("root_session_id", "")),
            agent_invocation_id=str(data.get("agent_invocation_id", "")),
            runtime_provider=str(data.get("runtime_provider", "claude")),
            actor_kind=str(data.get("actor_kind", "root")),
            parent_invocation_id=data.get("parent_invocation_id"),
        )


def canonicalize_path(raw_path: str | Path, project_root: str | Path | None = None) -> str:
    """Resolve symlinks and relative paths into absolute canonical realpath string."""
    p = Path(raw_path).expanduser()
    if not p.is_absolute():
        if project_root:
            p = (Path(project_root).expanduser() / p)
        else:
            p = p.resolve()
    return os.path.realpath(str(p))


def compute_content_hash(path: str | Path) -> str | None:
    """Compute SHA-256 content hash of file on disk. Returns None if unreadable/missing."""
    try:
        p = Path(path)
        if not p.is_file():
            return None
        data = p.read_bytes()
        return f"sha256:{hashlib.sha256(data).hexdigest()}"
    except Exception:
        return None


def compute_interval_bytes(path: str | Path, interval: Sequence[int] | None = None) -> int:
    """Compute byte length of file lines [s, e] or total file size."""
    try:
        p = Path(path)
        if not p.is_file():
            return 0
        if interval is None:
            return p.stat().st_size
        if len(interval) < 2:
            return p.stat().st_size
        s, e = int(interval[0]), int(interval[1])
        if s > e or s < 1:
            return 0
        with p.open('rb') as f:
            lines = f.readlines()
        sliced = lines[s - 1 : e]
        return sum(len(line) for line in sliced)
    except Exception:
        return 0

def count_file_lines(path: str | Path) -> int | None:
    """Count total lines in file if it exists and is readable."""
    try:
        p = Path(path)
        if not p.is_file():
            return None
        with p.open("r", encoding="utf-8", errors="replace") as f:
            count = sum(1 for _ in f)
        return count
    except Exception:
        return None


def normalize_intervals(intervals: Iterable[Sequence[int]]) -> list[list[int]]:
    """Normalize and sort 1-based intervals, merging overlapping or contiguous ranges."""
    cleaned: list[list[int]] = []
    for iv in intervals:
        if len(iv) < 2:
            continue
        s, e = int(iv[0]), int(iv[1])
        if s > e or s < 1:
            continue
        cleaned.append([s, e])

    if not cleaned:
        return []

    cleaned.sort(key=lambda x: (x[0], x[1]))
    merged: list[list[int]] = [cleaned[0]]
    for s, e in cleaned[1:]:
        prev_s, prev_e = merged[-1]
        if s <= prev_e + 1:
            merged[-1] = [prev_s, max(prev_e, e)]
        else:
            merged.append([s, e])
    return merged


def interval_contains(interval_set: Iterable[Sequence[int]], target: Sequence[int]) -> bool:
    """Check if target interval [s, e] is completely covered by interval_set."""
    if len(target) < 2:
        return False
    t_s, t_e = int(target[0]), int(target[1])
    if t_s > t_e:
        return False
    norm = normalize_intervals(interval_set)
    for s, e in norm:
        if s <= t_s and e >= t_e:
            return True
    return False


def interval_subtract(
    target: Sequence[int], interval_set: Iterable[Sequence[int]]
) -> tuple[list[list[int]], list[list[int]]]:
    """Subtract interval_set from target [t_s, t_e].

    Returns (missing_intervals, covered_intervals).
    """
    if len(target) < 2:
        return ([], [])
    t_s, t_e = int(target[0]), int(target[1])
    if t_s > t_e or t_s < 1:
        return ([], [])

    norm = normalize_intervals(interval_set)
    missing: list[list[int]] = []
    covered: list[list[int]] = []
    current_s = t_s

    for iv_s, iv_e in norm:
        if iv_e < current_s:
            continue
        if iv_s > t_e:
            break
        overlap_s = max(iv_s, current_s)
        overlap_e = min(iv_e, t_e)
        if overlap_s <= overlap_e:
            if current_s < overlap_s:
                missing.append([current_s, overlap_s - 1])
            covered.append([overlap_s, overlap_e])
            current_s = overlap_e + 1

    if current_s <= t_e:
        missing.append([current_s, t_e])

    return (missing, covered)


def interval_union(
    interval_set: Iterable[Sequence[int]], new_intervals: Iterable[Sequence[int]]
) -> list[list[int]]:
    """Compute union of two interval sets, normalized."""
    combined = list(interval_set) + list(new_intervals)
    return normalize_intervals(combined)


@dataclass
class ReadRequest:
    raw_path: str | Path
    project_root: str | Path
    root_session_id: str
    agent_invocation_id: str
    runtime_provider: str = "claude"
    actor_kind: str = "root"  # "root" | "subagent"
    parent_invocation_id: str | None = None
    line_interval: tuple[int | None, int | None] | list[int | None] | None = None
    start_line: int | None = None
    end_line: int | None = None
    content_hash: str | None = None
    mode: str = "IMPLEMENT"
    purpose: str | None = None
    exception_reason: str | None = None


@dataclass
class DecisionReceipt:
    decision: str  # "allowed" | "duplicate" | "partial" | "invalidated" | "denied" | "exception"
    reason_code: str
    diagnostic: str
    canonical_path: str
    content_hash: str | None
    requested_intervals: list[list[int]]
    allowed_intervals: list[list[int]]
    cached_intervals: list[list[int]]
    actor_key: dict[str, Any]
    sequence: int
    cached: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason_code": self.reason_code,
            "diagnostic": self.diagnostic,
            "canonical_path": self.canonical_path,
            "content_hash": self.content_hash,
            "requested_intervals": self.requested_intervals,
            "allowed_intervals": self.allowed_intervals,
            "cached_intervals": self.cached_intervals,
            "actor_key": self.actor_key,
            "sequence": self.sequence,
            "cached": self.cached,
            "metadata": self.metadata,
        }


@dataclass
class ReadRecord:
    canonical_path: str
    content_hash: str
    line_interval: list[list[int]]
    mode: str
    purpose: str | None
    actor_kind: str
    runtime_provider: str
    session_id: str
    invocation_id: str
    sequence: int
    decision: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_path": self.canonical_path,
            "content_hash": self.content_hash,
            "line_interval": self.line_interval,
            "mode": self.mode,
            "purpose": self.purpose,
            "actor_kind": self.actor_kind,
            "runtime_provider": self.runtime_provider,
            "session_id": self.session_id,
            "invocation_id": self.invocation_id,
            "sequence": self.sequence,
            "decision": self.decision,
            "timestamp": self.timestamp,
        }


class _LedgerFileLock:
    """Exclusive lock for ledger file operations to prevent concurrency conflicts."""

    def __init__(self, lock_path: Path, timeout: float = 3.0):
        self.lock_path = lock_path
        self.timeout = timeout
        self._fd: Any | None = None

    def __enter__(self) -> _LedgerFileLock:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = open(self.lock_path, "a+", encoding="utf-8")
        if fcntl is not None:
            deadline = time.monotonic() + self.timeout
            while True:
                try:
                    fcntl.flock(self._fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except (BlockingIOError, OSError):
                    if time.monotonic() >= deadline:
                        try:
                            fcntl.flock(self._fd.fileno(), fcntl.LOCK_EX)
                            break
                        except Exception as exc:
                            self._fd.close()
                            self._fd = None
                            raise TimeoutError(f"Ledger lock timeout on {self.lock_path}") from exc
                    time.sleep(0.01)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._fd is not None:
            if fcntl is not None:
                try:
                    fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
            self._fd.close()
            self._fd = None


class ContextLedger:
    """Actor-isolated, durable ledger tracking file read intervals and invalidations with atomic persistence."""

    def __init__(
        self,
        project_root: str | Path,
        root_session_id: str,
        agent_invocation_id: str,
        runtime_provider: str = "claude",
        actor_kind: str = "root",
        parent_invocation_id: str | None = None,
        runtime_dir: Path | None = None,
    ):
        self.actor_key = ActorKey(
            project_root=str(Path(project_root).expanduser().resolve()),
            root_session_id=str(root_session_id),
            agent_invocation_id=str(agent_invocation_id),
            runtime_provider=str(runtime_provider),
            actor_kind=str(actor_kind),
            parent_invocation_id=parent_invocation_id,
        )
        self._runtime_dir = runtime_dir
        self.files: dict[str, dict[str, Any]] = {}
        self.counters: dict[str, int] = {
            "unique_reads": 0,
            "duplicate_reads": 0,
            "partial_reads": 0,
            "bytes_read": 0,
            "ranges_read": 0,
            "read_ranges": 0,
            "monolith_plan_attempts": 0,
            "search_exceptions": 0,
            "invalidations": 0,
            "denials": 0,
            "exceptions": 0,
            "total_requests": 0,
        }
        self.records: list[dict[str, Any]] = []
        self.sequence: int = 0
        self.load()

    @property
    def ledger_path(self) -> Path:
        if self._runtime_dir:
            base_dir = self._runtime_dir
        else:
            base_dir = Path(self.actor_key.project_root) / ".claude" / "runtime"
        safe_proj = re.sub(r"[^a-zA-Z0-9._-]+", "_", Path(self.actor_key.project_root).name or "proj")[:64]
        safe_sess = re.sub(r"[^a-zA-Z0-9._-]+", "_", self.actor_key.root_session_id or "sess")[:64]
        safe_inv = re.sub(r"[^a-zA-Z0-9._-]+", "_", self.actor_key.agent_invocation_id or "root")[:64]
        return base_dir / "context-ledger" / safe_proj / safe_sess / f"{safe_inv}.json"

    @property
    def lock_path(self) -> Path:
        p = self.ledger_path
        return p.with_suffix(p.suffix + ".lock")

    def load(self) -> None:
        p = self.ledger_path
        if not p.is_file():
            return
        try:
            with _LedgerFileLock(self.lock_path, timeout=2.0):
                text = p.read_text(encoding="utf-8")
                data = json.loads(text)
                self.files = data.get("files", {})
                loaded_counters = data.get("counters", {})
                for k, v in loaded_counters.items():
                    self.counters[k] = int(v)
                self.records = data.get("records", [])
                self.sequence = int(data.get("sequence", 0))
        except Exception as exc:
            logger.warning("Failed to load context ledger %s: %s", p, exc)

    def save(self) -> None:
        """Atomic write with temporary file and exclusive lock to ensure no corruption."""
        p = self.ledger_path
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "schema": LEDGER_SCHEMA,
            "actor_key": self.actor_key.to_dict(),
            "files": self.files,
            "counters": self.counters,
            "records": self.records,
            "sequence": self.sequence,
        }
        text = json.dumps(data, ensure_ascii=False, indent=2)
        with _LedgerFileLock(self.lock_path, timeout=3.0):
            tmp_path = p.with_name(f"{p.name}.tmp.{os.getpid()}.{time.time_ns()}")
            try:
                tmp_path.write_text(text, encoding="utf-8")
                with tmp_path.open("r+") as handle:
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp_path, p)
            finally:
                try:
                    if tmp_path.exists():
                        tmp_path.unlink()
                except Exception:
                    pass

    def decide(self, request: ReadRequest) -> DecisionReceipt:
        """Evaluate read request, enforce interval algebra, detect duplicates/edits, and record metadata."""
        canonical = canonicalize_path(request.raw_path, request.project_root or self.actor_key.project_root)
        now_ts = datetime.now(timezone.utc).isoformat()

        # Step 1: Exception reason bypass (e.g. diff exception or approved reason)
        if request.exception_reason:
            disk_hash = compute_content_hash(canonical)
            if disk_hash is None and request.content_hash is None:
                self.counters["denials"] += 1
                return DecisionReceipt(
                    decision="denied",
                    reason_code="content_version_unknown",
                    diagnostic=f"File {canonical} not readable and no content hash provided; fail-closed",
                    canonical_path=canonical,
                    content_hash=None,
                    requested_intervals=[],
                    allowed_intervals=[],
                    cached_intervals=[],
                    actor_key=self.actor_key.to_dict(),
                    sequence=self.sequence,
                    cached=False,
                )
            active_hash = disk_hash or request.content_hash
            total_lines = count_file_lines(canonical)
            target_range = self._resolve_target_range(request, total_lines)
            if target_range is None:
                target_range = [1, total_lines or 1]
            self.sequence += 1
            self.counters["exceptions"] += 1
            self.counters["unique_reads"] += 1
            self.counters["total_requests"] += 1
            b = compute_interval_bytes(canonical, target_range)
            self.counters["bytes_read"] = self.counters.get("bytes_read", 0) + b
            self.counters["ranges_read"] = self.counters.get("ranges_read", 0) + 1
            self.counters["read_ranges"] = self.counters.get("read_ranges", 0) + 1
            self.counters["search_exceptions"] = self.counters.get("search_exceptions", 0) + 1
            self._update_file_intervals(canonical, active_hash, [target_range])
            self._append_record(canonical, active_hash, [target_range], request.mode, request.purpose, "exception", now_ts)
            self.save()
            return DecisionReceipt(
                decision="exception",
                reason_code="exception_approved",
                diagnostic=f"Exception approved for {canonical}: {request.exception_reason}",
                canonical_path=canonical,
                content_hash=active_hash,
                requested_intervals=[target_range],
                allowed_intervals=[target_range],
                cached_intervals=[],
                actor_key=self.actor_key.to_dict(),
                sequence=self.sequence,
                cached=False,
            )

        # Step 2: Content hash check / fail-closed
        disk_hash = compute_content_hash(canonical)
        total_lines = count_file_lines(canonical)

        if disk_hash is None:
            if request.content_hash is None:
                self.counters["denials"] += 1
                return DecisionReceipt(
                    decision="denied",
                    reason_code="content_version_unknown",
                    diagnostic=f"Content hash unknown for {canonical}; fail-closed",
                    canonical_path=canonical,
                    content_hash=None,
                    requested_intervals=[],
                    allowed_intervals=[],
                    cached_intervals=[],
                    actor_key=self.actor_key.to_dict(),
                    sequence=self.sequence,
                    cached=False,
                )
            active_hash = request.content_hash
        else:
            if request.content_hash is not None and request.content_hash != disk_hash:
                self.counters["denials"] += 1
                return DecisionReceipt(
                    decision="denied",
                    reason_code="content_version_unknown",
                    diagnostic=f"Content hash mismatch for {canonical}: disk {disk_hash} != requested {request.content_hash}",
                    canonical_path=canonical,
                    content_hash=disk_hash,
                    requested_intervals=[],
                    allowed_intervals=[],
                    cached_intervals=[],
                    actor_key=self.actor_key.to_dict(),
                    sequence=self.sequence,
                    cached=False,
                )
            active_hash = disk_hash

        # Step 3: Range resolution
        target_range = self._resolve_target_range(request, total_lines)
        if target_range is None:
            self.counters["denials"] += 1
            return DecisionReceipt(
                decision="denied",
                reason_code="content_version_unknown" if disk_hash is None else "omitted_range_unknown_bounds",
                diagnostic=f"Cannot resolve range bounds for {canonical}; fail-closed",
                canonical_path=canonical,
                content_hash=active_hash,
                requested_intervals=[],
                allowed_intervals=[],
                cached_intervals=[],
                actor_key=self.actor_key.to_dict(),
                sequence=self.sequence,
                cached=False,
            )

        # Step 4: Hash invalidation / state lookup
        file_state = self.files.get(canonical)
        if file_state is None:
            file_state = {
                "content_hash": active_hash,
                "intervals": [],
                "last_read_sequence": 0,
                "read_count": 0,
                "invalidated": False,
            }
            self.files[canonical] = file_state
        else:
            if file_state.get("content_hash") != active_hash or file_state.get("invalidated", False):
                # Hash changed or file was invalidated -> reset ranges
                file_state["content_hash"] = active_hash
                file_state["intervals"] = []
                file_state["invalidated"] = False
                self.counters["invalidations"] += 1

        existing_intervals = file_state.get("intervals", [])
        missing, covered = interval_subtract(target_range, existing_intervals)

        self.sequence += 1
        self.counters["total_requests"] += 1

        # Case A: Exact duplicate / completely covered
        if not missing:
            self.counters["duplicate_reads"] += 1
            file_state["last_read_sequence"] = self.sequence
            file_state["read_count"] = file_state.get("read_count", 0) + 1
            self._append_record(canonical, active_hash, [target_range], request.mode, request.purpose, "duplicate", now_ts)
            self.save()
            return DecisionReceipt(
                decision="duplicate",
                reason_code="duplicate_range",
                diagnostic=f"Duplicate read for {canonical} lines {target_range[0]}..{target_range[1]}: already cached",
                canonical_path=canonical,
                content_hash=active_hash,
                requested_intervals=[target_range],
                allowed_intervals=[],
                cached_intervals=[target_range],
                actor_key=self.actor_key.to_dict(),
                sequence=self.sequence,
                cached=True,
            )

        # Case B: Partial overlap
        if covered:
            self.counters["partial_reads"] += 1
            self.counters["unique_reads"] += 1
            self.counters["read_ranges"] += len(missing)
            self.counters["ranges_read"] = self.counters.get("ranges_read", 0) + len(missing)
            partial_b = sum(compute_interval_bytes(canonical, r) for r in missing)
            self.counters["bytes_read"] = self.counters.get("bytes_read", 0) + partial_b
            file_state["intervals"] = interval_union(existing_intervals, missing)
            file_state["last_read_sequence"] = self.sequence
            file_state["read_count"] = file_state.get("read_count", 0) + 1
            self._append_record(canonical, active_hash, missing, request.mode, request.purpose, "partial", now_ts)
            self.save()
            return DecisionReceipt(
                decision="partial",
                reason_code="partial_overlap",
                diagnostic=f"Partial read for {canonical}: returning uncovered intervals {missing}",
                canonical_path=canonical,
                content_hash=active_hash,
                requested_intervals=[target_range],
                allowed_intervals=missing,
                cached_intervals=covered,
                actor_key=self.actor_key.to_dict(),
                sequence=self.sequence,
                cached=False,
            )

        # Case C: Fully new uncached interval
        self.counters["unique_reads"] += 1
        self.counters["read_ranges"] += 1
        self.counters["ranges_read"] = self.counters.get("ranges_read", 0) + 1
        allowed_b = compute_interval_bytes(canonical, target_range)
        self.counters["bytes_read"] = self.counters.get("bytes_read", 0) + allowed_b
        file_state["intervals"] = interval_union(existing_intervals, [target_range])
        file_state["last_read_sequence"] = self.sequence
        file_state["read_count"] = file_state.get("read_count", 0) + 1
        self._append_record(canonical, active_hash, [target_range], request.mode, request.purpose, "allowed", now_ts)
        self.save()
        return DecisionReceipt(
            decision="allowed",
            reason_code="uncached_interval",
            diagnostic=f"Read allowed for {canonical} lines {target_range[0]}..{target_range[1]}",
            canonical_path=canonical,
            content_hash=active_hash,
            requested_intervals=[target_range],
            allowed_intervals=[target_range],
            cached_intervals=[],
            actor_key=self.actor_key.to_dict(),
            sequence=self.sequence,
            cached=False,
        )

    def _resolve_target_range(self, request: ReadRequest, total_lines: int | None) -> list[int] | None:
        """Normalize requested line interval into [start, end]."""
        if request.line_interval is not None:
            if len(request.line_interval) >= 2:
                s_raw = request.line_interval[0]
                e_raw = request.line_interval[1]
                s = int(s_raw) if s_raw is not None else 1
                if e_raw is None:
                    if total_lines is None:
                        return None
                    e = total_lines if total_lines > 0 else 1
                else:
                    e = int(e_raw)
                if s < 1 or e < s:
                    return None
                return [s, e]

        if request.start_line is not None or request.end_line is not None:
            s = int(request.start_line) if request.start_line is not None else 1
            if request.end_line is None:
                if total_lines is None:
                    return None
                e = total_lines if total_lines > 0 else 1
            else:
                e = int(request.end_line)
            if s < 1 or e < s:
                return None
            return [s, e]

        # Whole file requested
        if total_lines is not None:
            return [1, total_lines if total_lines > 0 else 1]

        return None

    def _update_file_intervals(self, canonical: str, content_hash: str, intervals: list[list[int]]) -> None:
        file_state = self.files.setdefault(canonical, {
            "content_hash": content_hash,
            "intervals": [],
            "last_read_sequence": self.sequence,
            "read_count": 0,
            "invalidated": False,
        })
        file_state["content_hash"] = content_hash
        file_state["intervals"] = interval_union(file_state.get("intervals", []), intervals)
        file_state["last_read_sequence"] = self.sequence
        file_state["read_count"] = file_state.get("read_count", 0) + 1

    def _append_record(
        self,
        canonical: str,
        content_hash: str,
        intervals: list[list[int]],
        mode: str,
        purpose: str | None,
        decision: str,
        timestamp: str,
    ) -> None:
        rec = ReadRecord(
            canonical_path=canonical,
            content_hash=content_hash,
            line_interval=intervals,
            mode=mode,
            purpose=purpose,
            actor_kind=self.actor_key.actor_kind,
            runtime_provider=self.actor_key.runtime_provider,
            session_id=self.actor_key.root_session_id,
            invocation_id=self.actor_key.agent_invocation_id,
            sequence=self.sequence,
            decision=decision,
            timestamp=timestamp,
        )
        self.records.append(rec.to_dict())

    def invalidate(self, path: str | Path) -> None:
        """Invalidate stored ranges for path in this ledger."""
        canonical = canonicalize_path(path, self.actor_key.project_root)
        disk_hash = compute_content_hash(canonical)
        if canonical in self.files:
            self.files[canonical]["intervals"] = []
            self.files[canonical]["invalidated"] = True
            if disk_hash:
                self.files[canonical]["content_hash"] = disk_hash
            self.counters["invalidations"] += 1
        else:
            self.files[canonical] = {
                "content_hash": disk_hash,
                "intervals": [],
                "last_read_sequence": self.sequence,
                "read_count": 0,
                "invalidated": True,
            }
            self.counters["invalidations"] += 1
        self.save()

    def record_edit(self, path: str | Path, new_content_hash: str | None = None) -> None:
        """Record that a file was edited or written, resetting old ranges."""
        canonical = canonicalize_path(path, self.actor_key.project_root)
        disk_hash = new_content_hash or compute_content_hash(canonical)
        if canonical in self.files:
            self.files[canonical]["intervals"] = []
            self.files[canonical]["invalidated"] = True
            if disk_hash:
                self.files[canonical]["content_hash"] = disk_hash
            self.counters["invalidations"] += 1
        else:
            self.files[canonical] = {
                "content_hash": disk_hash,
                "intervals": [],
                "last_read_sequence": self.sequence,
                "read_count": 0,
                "invalidated": True,
            }
            self.counters["invalidations"] += 1
        self.save()

    def record_monolith_attempt(self) -> None:
        """Record attempt to read entire plan in restricted execution modes."""
        self.counters["monolith_plan_attempts"] = self.counters.get("monolith_plan_attempts", 0) + 1
        self.save()

    def record_search_exception(self) -> None:
        """Record approved search exception outside shard allowlist."""
        self.counters["search_exceptions"] = self.counters.get("search_exceptions", 0) + 1
        self.save()

    def get_telemetry(self) -> dict[str, Any]:
        """Return summary counters and metadata without source content."""
        highest_repeat_path: str | None = None
        max_reads = 0
        for p, data in self.files.items():
            cnt = data.get("read_count", 0)
            if cnt > max_reads:
                max_reads = cnt
                highest_repeat_path = p

        if highest_repeat_path:
            try:
                root_p = Path(self.actor_key.project_root).resolve()
                p_obj = Path(highest_repeat_path)
                if p_obj.is_relative_to(root_p):
                    highest_repeat_path = p_obj.relative_to(root_p).as_posix()
            except Exception:
                pass

        return {
            "unique_reads": int(self.counters.get("unique_reads", 0)),
            "duplicate_reads": int(self.counters.get("duplicate_reads", 0)),
            "partial_reads": int(self.counters.get("partial_reads", 0)),
            "bytes_read": int(self.counters.get("bytes_read", 0)),
            "ranges_read": int(self.counters.get("ranges_read", self.counters.get("read_ranges", 0))),
            "read_ranges": int(self.counters.get("read_ranges", 0)),
            "monolith_plan_attempts": int(self.counters.get("monolith_plan_attempts", 0)),
            "search_exceptions": int(self.counters.get("search_exceptions", 0)),
            "invalidations": int(self.counters.get("invalidations", 0)),
            "denials": int(self.counters.get("denials", 0)),
            "exceptions": int(self.counters.get("exceptions", 0)),
            "total_requests": int(self.counters.get("total_requests", 0)),
            "highest_repeat_path": highest_repeat_path,
            "files_tracked": len(self.files),
            "records_count": len(self.records),
            "actor_key": self.actor_key.to_dict(),
        }
