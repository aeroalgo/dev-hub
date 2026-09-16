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

from context_ledger import DecisionReceipt
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
        "fd",
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

_SHELL_BINARIES = frozenset({"bash", "sh", "zsh", "dash", "ksh"})
_WRAPPER_BINARIES = frozenset(
    {
        "env",
        "nohup",
        "nice",
        "time",
        "exec",
        "command",
        "builtin",
        "xargs",
        "sudo",
    }
)
_COMPOUND_DELIMS = frozenset({";", "&&", "||", "|", "&", "\n", "|&"})


def _normalize_path(raw: str | Path, project_root: str | Path) -> str:
    """Normalize a path string relative to project_root with forward slashes."""
    p_str = str(raw).replace("\\", "/").strip().strip('"\'')
    if ":" in p_str and not p_str.startswith("http"):
        p_str = p_str.split(":")[0]
    if "#" in p_str:
        p_str = p_str.split("#")[0]

    root = Path(project_root).resolve()
    if not p_str or p_str in (".", "./"):
        return "."
    try:
        abs_target = (root / p_str).resolve()
        rel = abs_target.relative_to(root).as_posix()
        return "." if rel == "" else rel
    except ValueError:
        return (root / p_str).resolve().as_posix()


def _unwrap_wrapper_tokens(tokens: list[str]) -> list[str]:
    """Strip leading environment variable assignments and wrapper commands."""
    idx = 0
    while idx < len(tokens):
        t = tokens[idx]
        if "=" in t and not t.startswith("-"):
            idx += 1
            continue
        if t in _WRAPPER_BINARIES:
            idx += 1
            while idx < len(tokens):
                tok = tokens[idx]
                if tok.startswith("-"):
                    idx += 1
                    if tok in ("-u", "-C", "-n", "-s", "-I", "-P") and idx < len(tokens):
                        idx += 1
                elif "=" in tok:
                    idx += 1
                else:
                    break
            continue
        break
    return tokens[idx:]


def _extract_search_invocations(
    cmd: str | list[str],
    current_rel_dir: str = ".",
) -> tuple[list[dict[str, Any]], bool]:
    """Extract all search invocations and their effective working directory from a command line.

    Returns (invocations, has_parse_error).
    """
    invocations: list[dict[str, Any]] = []
    has_error = False

    if isinstance(cmd, list):
        raw_tokens: list[str] = []
        for item in cmd:
            s_item = str(item).strip()
            if not s_item:
                continue
            try:
                lexer = shlex.shlex(s_item, posix=True, punctuation_chars=";|&()<>\n")
                raw_tokens.extend(list(lexer))
            except Exception:
                raw_tokens.extend(s_item.split())
                has_error = True
    else:
        s_cmd = str(cmd).strip()
        if not s_cmd:
            return [], False
        try:
            lexer = shlex.shlex(s_cmd, posix=True, punctuation_chars=";|&()<>\n")
            raw_tokens = list(lexer)
        except Exception:
            raw_tokens = s_cmd.split()
            has_error = True

    atomic_cmds: list[dict[str, Any]] = []
    curr: list[str] = []
    prev_delim = None
    for tok in raw_tokens:
        if tok in _COMPOUND_DELIMS or tok in ("(", ")"):
            if curr:
                atomic_cmds.append({"tokens": curr, "is_piped_in": prev_delim in ("|", "|&")})
                curr = []
            prev_delim = tok
        else:
            curr.append(tok)
    if curr:
        atomic_cmds.append({"tokens": curr, "is_piped_in": prev_delim in ("|", "|&")})

    active_dir = current_rel_dir

    for item in atomic_cmds:
        raw_atomic = item["tokens"]
        is_piped_in = item["is_piped_in"]
        unwrapped = _unwrap_wrapper_tokens(raw_atomic)
        if not unwrapped:
            continue
        bin_name = Path(unwrapped[0]).name.lower()

        if bin_name in ("cd", "pushd") and len(unwrapped) > 1:
            target_cd = unwrapped[1].strip('"\'')
            if target_cd == "~" or target_cd.startswith("~/"):
                active_dir = target_cd
            elif target_cd.startswith("/"):
                active_dir = target_cd
            else:
                if active_dir == "." or not active_dir:
                    active_dir = target_cd
                else:
                    active_dir = f"{active_dir}/{target_cd}"
            continue

        if bin_name in _SHELL_BINARIES and any(flag in unwrapped for flag in ("-c", "-lc", "-ic")):
            flag_idx = -1
            for i, tok in enumerate(unwrapped):
                if tok in ("-c", "-lc", "-ic"):
                    flag_idx = i
                    break
            if flag_idx >= 0 and flag_idx + 1 < len(unwrapped):
                inner_cmd = unwrapped[flag_idx + 1]
                sub_invs, sub_err = _extract_search_invocations(inner_cmd, current_rel_dir=active_dir)
                invocations.extend(sub_invs)
                if sub_err:
                    has_error = True
            continue

        is_search = False
        if bin_name in _SEARCH_COMMAND_BINARIES:
            is_search = True
        elif bin_name == "git" and len(unwrapped) > 1 and unwrapped[1].lower() in {"grep", "log", "show", "diff"}:
            is_search = True
        elif bin_name.startswith("python") or bin_name in {"python3", "py"}:
            joined = " ".join(unwrapped)
            if any(kw in joined for kw in ("open(", "read_text(", "read()", "rg", "grep", "walk(")):
                is_search = True

        if is_search:
            invocations.append({
                "tokens": unwrapped,
                "binary": bin_name,
                "working_dir": active_dir,
                "is_piped_in": is_piped_in,
            })

    return invocations, has_error


def is_search_command_line(cmd: str | list[str]) -> bool:
    """Check whether a command is a search or file reading utility."""
    invs, has_error = _extract_search_invocations(cmd)
    if invs:
        return True
    if has_error:
        raw_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        if any(b in raw_str for b in _SEARCH_COMMAND_BINARIES):
            return True
    return False


def _extract_targets_from_tokens(
    binary: str,
    tokens: list[str],
    working_dir: str = ".",
    is_piped_in: bool = False,
) -> list[str]:
    targets: list[str] = []
    args = tokens[1:]

    if binary in ("rg", "grep", "egrep", "fgrep", "ag", "ack"):
        skip_next = False
        non_flag_args: list[str] = []
        has_dash_e = False
        for i, t in enumerate(args):
            if skip_next:
                skip_next = False
                continue
            if t in ("-e", "-g", "-t", "-m", "-C", "-A", "-B", "-f", "--glob", "--type", "--max-count", "--regexp", "--file"):
                if t in ("-e", "--regexp"):
                    has_dash_e = True
                skip_next = True
                continue
            if t.startswith("-"):
                continue
            non_flag_args.append(t)

        if has_dash_e:
            path_candidates = non_flag_args
        else:
            path_candidates = non_flag_args[1:] if len(non_flag_args) > 1 else []

        for cand in path_candidates:
            cand_clean = cand.strip('"\'')
            if cand_clean:
                targets.append(cand_clean)

        if not targets and not is_piped_in:
            targets = [working_dir]

    elif binary in ("cat", "head", "tail", "sed", "awk", "locate"):
        skip_next = False
        for t in args:
            if skip_next:
                skip_next = False
                continue
            if t in ("-n", "-c", "-e", "-f") and binary in ("sed", "awk"):
                skip_next = True
                continue
            if t.startswith("-"):
                continue
            cand_clean = t.strip('"\'')
            if cand_clean:
                targets.append(cand_clean)

        if not targets and not is_piped_in:
            targets = [working_dir]

    elif binary in ("find", "fd"):
        for t in args:
            if t.startswith("-"):
                break
            cand_clean = t.strip('"\'')
            if cand_clean:
                targets.append(cand_clean)
        if not targets:
            targets = [working_dir]

    elif binary == "git":
        subcmd = args[0].lower() if args else ""
        git_args = args[1:]
        if "--" in git_args:
            dash_idx = git_args.index("--")
            for t in git_args[dash_idx + 1:]:
                if t.strip('"\'') :
                    targets.append(t.strip('"\''))
        else:
            skip_next = False
            non_flags = []
            for t in git_args:
                if skip_next:
                    skip_next = False
                    continue
                if t in ("-S", "-G", "-n", "-L", "--grep", "--author", "--since", "--until", "-C", "-m", "--max-count"):
                    skip_next = True
                    continue
                if t.startswith("-"):
                    continue
                non_flags.append(t)

            if subcmd == "grep":
                if len(non_flags) > 1:
                    targets.extend(non_flags[1:])
            elif subcmd in ("log", "diff", "show"):
                for t in non_flags:
                    cand = t.strip('"\'')
                    if "/" in cand or "." in cand or cand == ".":
                        targets.append(cand)
        if not targets:
            targets = [working_dir]

    elif binary.startswith("python"):
        joined = " ".join(args)
        for m in re.finditer(r"""(?:open|Path|read_text)\s*\(\s*['"]([^'"]+)['"]""", joined):
            targets.append(m.group(1))
        if not targets:
            targets = [working_dir]

    resolved_targets: list[str] = []
    for t in targets:
        if working_dir != "." and not t.startswith("/"):
            resolved_targets.append(f"{working_dir}/{t}")
        else:
            resolved_targets.append(t)
    return resolved_targets


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
        if data is None and not self.shard_path:
            act_file = self.project_root / "memory-bank" / "activeContext.md"
            if act_file.is_file():
                try:
                    import yaml
                    text = act_file.read_text(encoding="utf-8", errors="replace")
                    meta = {}
                    if text.startswith("---"):
                        parts = text.split("---", 2)
                        if len(parts) >= 3:
                            meta = yaml.safe_load(parts[1]) or {}
                    epic_id = meta.get("epic_id") or meta.get("epic")
                    step_id = meta.get("step_id") or meta.get("step")

                    found_shard: Path | None = None
                    if epic_id and step_id:
                        for cand in self.project_root.glob(f"memory-bank/**/plan/{epic_id}*/yaml/steps/{step_id}*.yaml"):
                            if cand.is_file():
                                found_shard = cand
                                break
                        if not found_shard:
                            for cand in self.project_root.glob(f"memory-bank/**/plan/{epic_id}*/yaml/steps/{step_id}.yaml"):
                                if cand.is_file():
                                    found_shard = cand
                                    break
                        if not found_shard:
                            for cand in self.project_root.glob(f"memory-bank/**/steps/{step_id}*.yaml"):
                                if cand.is_file():
                                    found_shard = cand
                                    break

                    if not found_shard:
                        try:
                            from epic.core import extract_load_now
                            ln = extract_load_now(text)
                            for path_str in ln:
                                if "/yaml/steps/" in path_str.replace(os.sep, "/") and not path_str.endswith("decompose-index.yaml"):
                                    cand = self.project_root / path_str
                                    if cand.is_file():
                                        found_shard = cand
                                        break
                        except Exception:
                            pass

                    if found_shard and found_shard.is_file():
                        self.shard_path = found_shard
                        data = yaml.safe_load(found_shard.read_text(encoding="utf-8")) or {}

                    try:
                        from epic.core import extract_load_now
                        for lp in extract_load_now(text):
                            if lp not in self.load_now:
                                self.load_now.append(lp)
                    except Exception:
                        pass
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
        clean_norm = norm.rstrip("/")
        if clean_norm in self._allowed_files or norm in self._allowed_files:
            return True
        if clean_norm in self._allowed_dirs or norm in self._allowed_dirs:
            return True
        p = Path(clean_norm).parent
        while str(p) not in (".", "", "/"):
            if p.as_posix() in self._allowed_dirs:
                return True
            p = p.parent
        return False

    def evaluate_search(
        self,
        command: str | list[str],
        cwd: str | Path | None = None,
        graphify_evidence: str | None = None,
        exception_reason: str | None = None,
    ) -> tuple[bool, str, dict[str, Any]]:
        """Evaluate whether a search command is within allowlist or supported by graphify evidence."""
        has_graphify = bool(graphify_evidence and str(graphify_evidence).strip())
        has_reason = bool(exception_reason and str(exception_reason).strip())
        if has_graphify and has_reason:
            return True, "graphify_exception_approved", {
                "graphify_evidence": str(graphify_evidence).strip(),
                "exception_reason": str(exception_reason).strip(),
            }

        invocations, has_error = _extract_search_invocations(command)
        if has_error:
            diag = (
                "Compound command could not be safely parsed for search enforcement; fail-closed. "
                "Broad codebase search requires successful graphify evidence and typed reason."
            )
            return False, "search_outside_scope_denied", {
                "diagnostic": diag,
                "graphify_required": True,
                "fail_closed": True,
            }

        if not invocations:
            return True, "empty_command", {}

        for inv in invocations:
            targets = _extract_targets_from_tokens(
                inv["binary"],
                inv["tokens"],
                working_dir=inv["working_dir"],
                is_piped_in=inv.get("is_piped_in", False),
            )
            for target in targets:
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

        return True, "search_inside_scope", {"invocations": len(invocations)}

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

    if tokens and tokens[0] == "timeout":
        idx = 1
        while idx < len(tokens):
            if tokens[idx].startswith("-"):
                if tokens[idx] in ("-k", "-s") and idx + 1 < len(tokens):
                    idx += 2
                else:
                    idx += 1
            elif re.match(r"^\d+[smhd]?$", tokens[idx]):
                idx += 1
                break
            else:
                break
        tokens = tokens[idx:]

    if not tokens:
        return ""

    if tokens[0].endswith("pytest"):
        tokens = ["pytest"] + tokens[1:]
    elif len(tokens) >= 3 and tokens[0].startswith("python") and tokens[1] == "-m" and tokens[2] == "pytest":
        tokens = ["pytest"] + tokens[3:]
    elif len(tokens) >= 3 and tokens[0] in ("npm", "npx", "yarn", "pnpm") and tokens[1] in ("exec", "run") and tokens[2] in ("vitest", "jest"):
        tokens = [tokens[2]] + tokens[3:]
    elif len(tokens) >= 2 and tokens[0] in ("npm", "npx", "yarn", "pnpm") and tokens[1] in ("test", "vitest", "jest"):
        tokens = [tokens[1]] + tokens[2:]

    return " ".join(tokens)


def is_test_command_line(cmd: str | list[str]) -> bool:
    """Return True if command represents a recognized test execution."""
    norm = normalize_test_command(cmd)
    if not norm:
        return False
    tokens = norm.split()
    if not tokens:
        return False
    first = tokens[0].lower()
    if first in {"pytest", "vitest", "jest"}:
        return True
    if len(tokens) >= 2 and first in {"cargo", "npm", "yarn", "pnpm"} and tokens[1].lower() == "test":
        return True
    return False


def evaluate_test_command(
    command: str | list[str],
    project_root: str | Path,
    session_id: str = "",
    actor_key: dict[str, Any] | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    """Evaluate whether a test command has a valid cached execution fingerprint.

    Returns (cached, reason_code, receipt_dict).
    If cached=True, receipt_dict conforms to DecisionReceipt schema.
    If cached=False, receipt_dict is None.
    """
    root = Path(project_root).resolve()
    cache = TestFingerprintCache(project_root=root)
    hit = cache.lookup(command)
    if not hit:
        return False, "test_cache_miss", None

    actor = dict(actor_key or {"session_id": session_id, "role": "root"})
    receipt = DecisionReceipt(
        decision="duplicate",
        reason_code="cached_test_execution",
        diagnostic=(
            f"Test execution '{hit['command']}' cached (fingerprint: {hit['fingerprint']}). "
            f"Previous exit code: {hit['exit_code']}. Output summary: {hit.get('output_summary', '')}"
        ),
        canonical_path=hit["command"],
        content_hash=hit["fingerprint"],
        requested_intervals=[],
        allowed_intervals=[],
        cached_intervals=[],
        actor_key=actor,
        sequence=0,
        cached=True,
        metadata=hit,
    )
    return True, "cached_test_execution", receipt.to_dict()


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
        self._load()
        norm_cmd = normalize_test_command(command)
        entry = self._entries.get(norm_cmd)
        if not entry:
            return None

        paths = relevant_paths if relevant_paths is not None else entry.get("relevant_paths")
        current_fp = compute_test_fingerprint(command, self.project_root, paths)

        if entry.get("fingerprint") == current_fp:
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
        self._load()
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
        self._load()
        norm_p = str(path).replace("\\", "/")
        try:
            resolved_p = str((self.project_root / path).resolve()).replace("\\", "/") if not Path(path).is_absolute() else str(Path(path).resolve()).replace("\\", "/")
        except Exception:
            resolved_p = norm_p

        invalidated_cmds: list[str] = []
        for cmd, entry in list(self._entries.items()):
            paths = entry.get("relevant_paths", [])
            if not paths:
                del self._entries[cmd]
                invalidated_cmds.append(cmd)
                continue
            match = False
            for p in paths:
                sp = str(p).replace("\\", "/")
                if norm_p in sp or sp in norm_p or resolved_p in sp or sp in resolved_p:
                    match = True
                    break
                try:
                    resp = str((self.project_root / p).resolve()).replace("\\", "/") if not Path(p).is_absolute() else str(Path(p).resolve()).replace("\\", "/")
                    if resolved_p == resp or norm_p == resp or resolved_p in resp or resp in resolved_p:
                        match = True
                        break
                except Exception:
                    pass
            if match:
                del self._entries[cmd]
                invalidated_cmds.append(cmd)
        if invalidated_cmds:
            self._save()
        return invalidated_cmds


def invalidate_test_cache(
    project_root: str | Path,
    path: str | Path,
    cache_file: str | Path | None = None,
) -> list[str]:
    """Invalidate test fingerprint cache entries associated with a changed path."""
    cache = TestFingerprintCache(project_root=project_root, cache_file=cache_file)
    return cache.invalidate_path(path)
