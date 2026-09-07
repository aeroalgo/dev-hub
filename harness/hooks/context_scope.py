"""ContextScope and ScopeResolver enforcement for T-HUB-078.

Derives allowlists from work shard files, declared delta, layout paths, and parent directories.
Enforces whole-plan monolith denial, plan-jump bounds, search scope boundaries,
graphify evidence requirements, and test execution fingerprint caching.

Part of T-HUB-078 (FR-003, FR-004, FR-006, Stage 2, Stage 3).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shlex
import sys
from typing import Any, Sequence

_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from loop.mb_load.plan_section import (
    evaluate_plan_read,
    is_whole_plan_path,
    load_plan_jumps,
    materialize_plan_jump,
    parse_plan_jump,
)

logger = logging.getLogger(__name__)

_PATH_EXTRACTION_RE = re.compile(
    r"(?:^|[\s`'\"(])([a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)+(?:\.[a-zA-Z0-9_]+)?)(?:$|[\s`'\")])"
)

_SEARCH_COMMAND_BINARIES = frozenset(
    {
        "rg",
        "grep",
        "egrep",
        "fgrep",
        "find",
        "ag",
        "ack",
        "locate",
        "cat",
        "head",
        "tail",
        "sed",
        "awk",
    }
)


def _normalize_path(raw: str | Path, project_root: str | Path) -> str:
    """Normalize a path string relative to project_root with forward slashes."""
    p_str = str(raw).replace("\\", "/").strip().strip("'\"")
    if ":" in p_str and not p_str.startswith("http"):
        p_str = p_str.split(":")[0]
    if "#" in p_str:
        p_str = p_str.split("#")[0]

    root = Path(project_root).resolve()
    target = Path(p_str)
    if target.is_absolute():
        try:
            return target.resolve().relative_to(root).as_posix()
        except ValueError:
            return target.as_posix()
    return p_str


def _extract_paths_from_text(text: str) -> list[str]:
    """Extract potential repo relative paths from delta or documentation text."""
    paths: list[str] = []
    for line in (text or "").splitlines():
        for m in re.finditer(r"`([^`]+)`", line):
            cand = m.group(1).strip()
            if "/" in cand or cand.endswith((".py", ".yaml", ".yml", ".md", ".json", ".ts", ".js", ".sh")):
                paths.append(cand)
        for m in _PATH_EXTRACTION_RE.finditer(line):
            cand = m.group(1).strip()
            if "/" in cand:
                paths.append(cand)
    return paths


def is_search_command_line(cmd: str | list[str]) -> bool:
    """Check whether a command is a search or file reading utility."""
    if isinstance(cmd, list):
        tokens = [str(t).strip() for t in cmd if str(t).strip()]
    else:
        try:
            tokens = shlex.split(str(cmd).strip())
        except Exception:
            tokens = str(cmd).strip().split()

    if not tokens:
        return False

    binary = Path(tokens[0]).name.lower()
    if binary in _SEARCH_COMMAND_BINARIES:
        return True

    if binary.startswith("python") or binary in {"python3", "py"}:
        joined = " ".join(tokens)
        if any(kw in joined for kw in ("open(", "read_text(", "read()", "rg", "grep")):
            return True

    return False


class ScopeResolver:
    """Derives allowlist from shard files, delta, and parent directories.
    Enforces search and read scope constraints with graphify evidence validation.
    """

    def __init__(
        self,
        project_root: str | Path = ".",
        shard_path: str | Path | None = None,
        shard_data: dict[str, Any] | None = None,
        load_now: list[str] | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.shard_path = Path(shard_path) if shard_path else None
        self.shard_data = shard_data
        self.load_now = list(load_now or [])
        self._allowed_files: set[str] = set()
        self._allowed_dirs: set[str] = set()
        self._declared_jumps: list[str] = []
        self._initialize_allowlist()

    def _initialize_allowlist(self) -> None:
        data = self.shard_data
        if data is None and self.shard_path:
            p = self.shard_path if self.shard_path.is_absolute() else (self.project_root / self.shard_path)
            if p.is_file():
                try:
                    import yaml
                    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                except Exception:
                    data = {}
        if data is None:
            data = {}

        # 1. Essential workflow and root files
        essential_files = {
            "CLAUDE.md",
            "AGENTS.md",
            "mainrule.mdc",
            "memory-bank/activeContext.md",
            "memory-bank/techContext.md",
            "memory-bank/systemPatterns.md",
            "memory-bank/progress.md",
            "memory-bank/productContext.md",
        }
        for ef in essential_files:
            self._allowed_files.add(ef)

        # 2. Shard files from shard YAML
        shard_files = data.get("files") or []
        if isinstance(shard_files, list):
            for sf in shard_files:
                if isinstance(sf, str) and sf.strip():
                    norm = _normalize_path(sf, self.project_root)
                    if norm:
                        self._allowed_files.add(norm)

        # 3. Delta paths
        deltas = data.get("delta") or []
        if isinstance(deltas, list):
            for d in deltas:
                if isinstance(d, str):
                    for path_match in _extract_paths_from_text(d):
                        norm = _normalize_path(path_match, self.project_root)
                        if norm:
                            self._allowed_files.add(norm)

        # 4. Produces / Consumes / Layout paths
        for key in ("produces", "consumes", "layout_paths"):
            items = data.get(key) or []
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, str):
                        for pm in _extract_paths_from_text(item):
                            norm = _normalize_path(pm, self.project_root)
                            if norm:
                                self._allowed_files.add(norm)

        plan_contract = data.get("plan_contract") or {}
        if isinstance(plan_contract, dict):
            layout_paths = plan_contract.get("layout_paths") or []
            if isinstance(layout_paths, list):
                for lp in layout_paths:
                    if isinstance(lp, str):
                        norm = _normalize_path(lp, self.project_root)
                        if norm:
                            self._allowed_files.add(norm)
            jumps = plan_contract.get("plan_jumps") or []
            if isinstance(jumps, list):
                for j in jumps:
                    if isinstance(j, str) and j.strip():
                        self._declared_jumps.append(j.strip())
                        jp, _, _ = parse_plan_jump(j)
                        norm = _normalize_path(jp, self.project_root)
                        if norm:
                            self._allowed_files.add(norm)

        # 5. Load_now paths
        for ln in self.load_now:
            norm = _normalize_path(ln, self.project_root)
            if norm:
                self._allowed_files.add(norm)

        # 6. Shard path itself
        if self.shard_path:
            norm = _normalize_path(str(self.shard_path), self.project_root)
            if norm:
                self._allowed_files.add(norm)

        # 7. Parent directories of all allowed files
        for f in list(self._allowed_files):
            p = Path(f).parent
            while str(p) not in (".", "", "/"):
                self._allowed_dirs.add(p.as_posix())
                p = p.parent

    def get_allowlist(self) -> set[str]:
        return set(self._allowed_files)

    def get_allowlist_dirs(self) -> set[str]:
        return set(self._allowed_dirs)

    def is_path_allowed(self, path: str | Path) -> bool:
        norm = _normalize_path(str(path), self.project_root)
        if not norm:
            return False
        if norm in self._allowed_files:
            return True
        p = Path(norm).parent
        while str(p) not in (".", "", "/"):
            if p.as_posix() in self._allowed_dirs:
                return True
            p = p.parent
        if norm.startswith(".cursor/") or norm.startswith(".claude/") or norm.startswith(".agents/"):
            return True
        return False

    def evaluate_search(
        self,
        command: str | list[str],
        cwd: str | Path | None = None,
        graphify_evidence: str | None = None,
        exception_reason: str | None = None,
    ) -> tuple[bool, str, dict[str, Any]]:
        """Evaluate whether a search command is within allowlist or supported by graphify evidence."""
        if isinstance(command, list):
            tokens = [str(t).strip() for t in command if str(t).strip()]
        else:
            try:
                tokens = shlex.split(str(command).strip())
            except Exception:
                tokens = str(command).strip().split()

        if not tokens:
            return True, "empty_command", {}

        has_graphify = bool(graphify_evidence and str(graphify_evidence).strip())
        has_reason = bool(exception_reason and str(exception_reason).strip())
        if has_graphify and has_reason:
            return True, "graphify_exception_approved", {
                "graphify_evidence": str(graphify_evidence).strip(),
                "exception_reason": str(exception_reason).strip(),
            }

        search_targets: list[str] = []
        skip_next = False
        for i, t in enumerate(tokens[1:], start=1):
            if skip_next:
                skip_next = False
                continue
            if t in ("-e", "-g", "-t", "-m", "-C", "-A", "-B", "--glob", "--type", "--max-count"):
                skip_next = True
                continue
            if t.startswith("-"):
                continue
            if len(search_targets) == 0 and not any(ch in t for ch in ("/", ".")):
                continue
            search_targets.append(t)

        if not search_targets:
            search_targets = ["."]

        for target in search_targets:
            norm_target = _normalize_path(target, self.project_root)
            if norm_target in (".", "", "./"):
                if not (has_graphify and has_reason):
                    diag = (
                        "Search path '.' (entire repository) is outside declared shard scope. "
                        "Broad codebase search requires successful graphify evidence and typed reason."
                    )
                    return False, "search_outside_scope_denied", {
                        "target": target,
                        "diagnostic": diag,
                        "graphify_required": True,
                        "fail_closed": True,
                    }
            elif not self.is_path_allowed(norm_target):
                diag = (
                    f"Search path '{target}' is outside declared shard scope. "
                    "Use graphify query first or provide graphify evidence with typed exception reason."
                )
                return False, "search_outside_scope_denied", {
                    "target": target,
                    "diagnostic": diag,
                    "graphify_required": True,
                    "fail_closed": True,
                }

        return True, "search_inside_scope", {"targets": search_targets}

    def evaluate_read_scope(
        self,
        path: str | Path,
        mode: str = "IMPLEMENT",
        start_line: int | None = None,
        end_line: int | None = None,
        graphify_evidence: str | None = None,
        exception_reason: str | None = None,
    ) -> tuple[bool, str, dict[str, Any]]:
        """Evaluate read scope: monolith plan guard and allowlist boundary."""
        p_str = str(path).replace("\\", "/").strip()

        if is_whole_plan_path(p_str):
            return evaluate_plan_read(
                path=p_str,
                start_line=start_line,
                end_line=end_line,
                mode=mode,
                declared_jumps=self._declared_jumps,
                exception_reason=exception_reason,
                project_root=self.project_root,
            )

        norm = _normalize_path(p_str, self.project_root)
        if self.is_path_allowed(norm):
            return True, "read_inside_scope", {"path": norm}

        if (graphify_evidence and str(graphify_evidence).strip()) or (exception_reason and str(exception_reason).strip()):
            return True, "exception_approved", {
                "path": norm,
                "graphify_evidence": graphify_evidence,
                "exception_reason": exception_reason,
            }

        diag = (
            f"Read path '{norm}' is outside declared shard scope. "
            "Read outside declared files/delta requires graphify evidence or explicit exception reason."
        )
        return False, "read_outside_scope_denied", {
            "path": norm,
            "diagnostic": diag,
            "fail_closed": True,
        }


def normalize_test_command(cmd: str | list[str]) -> str:
    """Normalize test execution command to canonical string."""
    if isinstance(cmd, list):
        tokens = [str(t).strip() for t in cmd if str(t).strip()]
    else:
        try:
            tokens = shlex.split(str(cmd).strip())
        except Exception:
            tokens = str(cmd).strip().split()

    if not tokens:
        return ""

    if tokens[0].endswith("pytest"):
        tokens = ["pytest"] + tokens[1:]
    elif len(tokens) >= 3 and tokens[0].startswith("python") and tokens[1] == "-m" and tokens[2] == "pytest":
        tokens = ["pytest"] + tokens[3:]

    return " ".join(tokens)


def compute_diff_fingerprint(project_root: str | Path, relevant_paths: Sequence[str | Path]) -> str:
    """Compute deterministic SHA-256 fingerprint of relevant files' content."""
    root = Path(project_root).resolve()
    h = hashlib.sha256()
    for p in sorted(str(path) for path in relevant_paths):
        full_p = root / p if not Path(p).is_absolute() else Path(p)
        if full_p.is_file():
            try:
                content = full_p.read_bytes()
                h.update(f"{p}:{len(content)}:".encode("utf-8"))
                h.update(hashlib.sha256(content).digest())
            except Exception:
                h.update(f"{p}:error:".encode("utf-8"))
        else:
            h.update(f"{p}:missing:".encode("utf-8"))
    return h.hexdigest()


def compute_test_fingerprint(
    command: str | list[str],
    project_root: str | Path,
    relevant_paths: Sequence[str | Path] | None = None,
) -> str:
    """Compute overall test fingerprint = hash(normalized_command + diff_fingerprint)."""
    norm_cmd = normalize_test_command(command)
    root = Path(project_root).resolve()

    paths = list(relevant_paths or [])
    if not paths:
        try:
            toks = shlex.split(norm_cmd)
        except Exception:
            toks = norm_cmd.split()
        for t in toks:
            if "/" in t or t.endswith((".py", ".ts", ".js")):
                clean = t.split("::")[0].split(":")[0]
                if (root / clean).exists() or clean.startswith("test"):
                    paths.append(clean)

    diff_fp = compute_diff_fingerprint(root, paths)
    overall = hashlib.sha256(f"{norm_cmd}|{diff_fp}".encode("utf-8")).hexdigest()
    return overall


class TestFingerprintCache:
    """Durable session-scoped test execution fingerprint cache."""

    __test__ = False

    def __init__(self, project_root: str | Path, cache_file: str | Path | None = None) -> None:
        self.project_root = Path(project_root).resolve()
        if cache_file:
            self.cache_file = Path(cache_file) if Path(cache_file).is_absolute() else (self.project_root / cache_file)
        else:
            self.cache_file = self.project_root / ".runtime" / "test_fingerprints.json"
        self._entries: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self.cache_file.is_file():
            try:
                data = json.loads(self.cache_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._entries = data.get("entries", {})
            except Exception:
                self._entries = {}

    def _save(self) -> None:
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_file.with_suffix(".tmp")
        data = {
            "schema": "test-fingerprint-cache/v1",
            "entries": self._entries,
        }
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(self.cache_file)

    def lookup(
        self,
        command: str | list[str],
        relevant_paths: Sequence[str | Path] | None = None,
    ) -> dict[str, Any] | None:
        """Lookup cached test result for command. Returns result dict if hit, None if miss/invalidated."""
        norm_cmd = normalize_test_command(command)
        current_fp = compute_test_fingerprint(command, self.project_root, relevant_paths)

        entry = self._entries.get(norm_cmd)
        if entry and entry.get("fingerprint") == current_fp:
            return {
                "cached": True,
                "no_op": True,
                "command": norm_cmd,
                "fingerprint": current_fp,
                "exit_code": entry.get("exit_code", 0),
                "output_summary": entry.get("output_summary", ""),
                "timestamp": entry.get("timestamp"),
            }
        return None

    def record(
        self,
        command: str | list[str],
        exit_code: int,
        output_summary: str = "",
        relevant_paths: Sequence[str | Path] | None = None,
    ) -> str:
        """Record test execution outcome and fingerprint."""
        norm_cmd = normalize_test_command(command)
        current_fp = compute_test_fingerprint(command, self.project_root, relevant_paths)
        now_ts = datetime.now(timezone.utc).isoformat()

        self._entries[norm_cmd] = {
            "fingerprint": current_fp,
            "exit_code": exit_code,
            "output_summary": output_summary,
            "relevant_paths": [str(p) for p in (relevant_paths or [])],
            "timestamp": now_ts,
        }
        self._save()
        return current_fp

    def invalidate_path(self, path: str | Path) -> list[str]:
        """Invalidate all test cache entries associated with a changed path."""
        norm_p = str(path).replace("\\", "/")
        invalidated_cmds: list[str] = []
        for cmd, entry in list(self._entries.items()):
            paths = entry.get("relevant_paths", [])
            if not paths or any(norm_p in str(p) or str(p) in norm_p for p in paths):
                del self._entries[cmd]
                invalidated_cmds.append(cmd)
        if invalidated_cmds:
            self._save()
        return invalidated_cmds
