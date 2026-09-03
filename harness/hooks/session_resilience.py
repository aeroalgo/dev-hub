#!/usr/bin/env python3
"""Session resilience: abort detection, dirty resume, last-session marker."""
from __future__ import annotations

import argparse
import json
import os
import re
import selectors
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

# Script/import must bind THIS hub's loop/, not a shadowing PYTHONPATH entry
# (e.g. another checkout's loop/ without runtime_adapters).
_HUB_ROOT = Path(__file__).resolve().parents[2]
_hub_s = str(_HUB_ROOT)
if _hub_s in sys.path:
    sys.path.remove(_hub_s)
sys.path.insert(0, _hub_s)

from epic_yaml import all_checkpoints_done, compute_resume_from, load_implement
from loop.runtime_adapters.base import SessionContext
from loop.runtime_adapters.common import get_adapter_for_runtime
from loop.runtime_adapters.dsh import detect_dsh_model_mismatch

# Match order: specific → broad. classify_abort() separates transient vs fatal.
_FATAL_ABORT_PATTERNS = (
    re.compile(r"(?i)KeyboardInterrupt"),
)

_SHELL_COMMAND_NOT_FOUND_RE = re.compile(
    r"(?i)(?:^|\n)(?:[\w/.~-]+:\s*)?(?:line \d+:\s*)?[\w/.~-]+: command not found"
)

_PERMANENT_FAILURE_PATTERNS = (
    re.compile(r"(?i)(?:CLI|command) error:[^\\n]*"),
    re.compile(r"(?i)invalid (?:config|option|argument)"),
    re.compile(r"(?i)auth_failed"),
    re.compile(r"(?i)Authentication\s+(?:failed|error|invalid)"),
    # Claude Code / org allowlist silently swaps --model; never treat as success.
    re.compile(
        r'(?i)Model\s+\\*"[^"\\]+\\*"\s+is restricted by your organization\'s settings\.'
        r"\s*Using\s+\S+\s+instead"
    ),
)

_STRUCTURED_MODEL_SUBSTITUTION_RE = re.compile(
    r"(?i)model_substitution:\s*requested=\S+\s+actual=\S+"
)

_DSH_TRANSIENT_PATTERNS = (
    re.compile(r"(?i)429\s*Too\s*Many\s*Requests"),
    re.compile(r"(?i)503\s*Service\s*Unavailable"),
    re.compile(r"(?i)5[0-9]{2}\s+(?:Server|Service|Gateway)\s+Error"),
    re.compile(r"(?i)Connection\s+(?:refused|reset|timed?\s*out)"),
)

_DSH_PERMANENT_PATTERNS = (
    re.compile(r"(?i)API\s+Error:\s*terminated"),
    re.compile(r"(?i)API\s+Error:\s*overloaded"),
    re.compile(r"(?i)API\s+Error:.*rate.?limit"),
    re.compile(r"(?i)Authentication\s+(?:failed|error|invalid)"),
    re.compile(r"(?i)Invalid\s+API\s+key"),
)

_MODEL_RESTRICTED_RE = re.compile(
    r'(?i)Model\s+\\*"(?P<requested>[^"\\]+)\\*"\s+is restricted by your organization\'s settings\.'
    r"\s*Using\s+(?P<actual>\S+)\s+instead"
)

_MALFORMED_RESULT_PATTERNS = (
    re.compile(r"(?i)malformed [^\n]*(?:result|output)"),
    re.compile(r"(?i)invalid stream[- ]json"),
)

# Process exit when run_session kills Claude after detecting model swap.
MODEL_SUBSTITUTION_EXIT = 125
_MODEL_SUBSTITUTION_MARKER = "MODEL_SUBSTITUTION\n"


def _safe_killpg(pid: int, sig: int) -> None:
    try:
        os.killpg(pid, sig)
    except OSError:
        try:
            os.kill(pid, sig)
        except OSError:
            pass


_TRANSIENT_ABORT_PATTERNS = (
    re.compile(r"(?i)timeout: sending signal (?:TERM|KILL) to command"),
    re.compile(r"(?i)timed out|timeout expired|command timed out"),
    re.compile(r"(?i)API Error:\s*terminated"),
    re.compile(r"(?i)API Error:\s*overloaded"),
    re.compile(r"(?i)API Error:\s*.*rate.?limit"),
    re.compile(r"(?i)Server error mid-response[^\n]*"),
    re.compile(r"(?i)API Error:\s*Server error[^\n]*"),
    re.compile(r"(?i)response above may be incomplete"),
    re.compile(r"(?i)response stalled mid.?stream"),
    re.compile(r"(?i)stream ended unexpectedly"),
    re.compile(r"(?i)connection (?:reset|aborted|closed)"),
    re.compile(r"(?i)API Error:\s*Stream idle timeout[^\n]*"),
    re.compile(r"(?i)API Error:[^\n]*"),
    re.compile(r"(?i)abrupt stream termination"),
    re.compile(r"(?i)log truncated.*session output exceeded cap"),
)

# Back-compat alias used by older tests / imports
ABORT_PATTERNS = _FATAL_ABORT_PATTERNS + _TRANSIENT_ABORT_PATTERNS

LAST_SESSION_NAME = "last-session.json"
DEFAULT_TRANSIENT_RETRY_MAX = 3
DEFAULT_TRANSIENT_BACKOFF_SEC = 20
DEFAULT_TRANSIENT_BACKOFF_MAX = 80
DEFAULT_IDLE_BACKOFF_SEC = 60

# Idle watchdog counts only real tool progress, not stream noise (deltas/thinking/status).
_TOOL_PROGRESS_RE = re.compile(r'"type"\s*:\s*"(?:tool_use|tool_result)"')
_CODEX_PROGRESS_RE = re.compile(
    r'"type"\s*:\s*"(?:command_execution|agent_message)"'
)
_TOOL_PROGRESS_TAIL = 64
_PROGRESS_MODES = frozenset({"tool_json", "stream_bytes", "codex_json"})


def _write_status(text: str) -> None:
    try:
        sys.stderr.write(text)
        sys.stderr.flush()
    except BrokenPipeError:
        pass


def _tool_progress_seen(tail: str, chunk: str, *, progress_mode: str = "tool_json") -> tuple[bool, str]:
    """Return whether chunk completes a new progress token; update overlap tail."""
    if not chunk:
        return False, tail
    combined = tail + chunk
    pattern = _CODEX_PROGRESS_RE if progress_mode == "codex_json" else _TOOL_PROGRESS_RE
    found = False
    for match in pattern.finditer(combined):
        if match.end() > len(tail):
            found = True
    return found, combined[-_TOOL_PROGRESS_TAIL:]


class SessionOutcome(str, Enum):
    """Stable outcome names shared by the loop and resume marker."""

    CLEAN = "clean"
    TIMEOUT = "timeout"
    TRANSIENT_ABORT = "transient_abort"
    SIGNAL = "signal"
    PERMANENT_FAILURE = "permanent_failure"
    MALFORMED_RESULT = "malformed_result"
    UNKNOWN_FAILURE = "unknown_failure"


class SessionAnalysis(TypedDict):
    outcome: str
    aborted: bool
    retryable: bool
    abort_kind: str | None
    reason: str | None
    backoff_sec: int


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def last_session_path(cwd: str | Path, *, track: str = "epic") -> Path:
    """Resolve last-session.json next to state.json via epic_dir (HUB_ROOT/DEV_HUB aware).

    ``track`` kept for API compatibility; epic runtime is always under EPIC_DIRNAME.
    """
    from epic_paths import epic_dir

    _ = track  # API compat; production callers always pass track="epic"
    return epic_dir(cwd) / LAST_SESSION_NAME


def _match_patterns(text: str, patterns: tuple[re.Pattern[str], ...]) -> str | None:
    for pat in patterns:
        m = pat.search(text or "")
        if m:
            return m.group(0).strip()[:200]
    return None


def normalize_model_id(value: str | None) -> str:
    """Compare requested vs actual model ids across providers / aliases."""
    raw = (value or "").strip().lower()
    if not raw:
        return ""
    raw = re.sub(r"\[\d+m\]$", "", raw)
    if "/" in raw:
        raw = raw.rsplit("/", 1)[-1]
    return raw


def models_equivalent(requested: str | None, actual: str | None) -> bool:
    a = normalize_model_id(requested)
    b = normalize_model_id(actual)
    if not a or not b:
        return True
    if a == b:
        return True
    return a in b or b in a


def format_model_substitution(requested: str, actual: str) -> str:
    return (
        f"model_substitution: requested={requested} actual={actual} "
        "(org/runtime swapped --model; refuse silent downgrade)"
    )


def is_structured_model_substitution_reason(reason: str | None) -> bool:
    return bool(reason and _STRUCTURED_MODEL_SUBSTITUTION_RE.search(reason))


def detect_structured_model_substitution_message(text: str) -> str | None:
    m = _STRUCTURED_MODEL_SUBSTITUTION_RE.search(text or "")
    if not m:
        return None
    return m.group(0).strip()[:200]


def detect_model_substitution_message(text: str) -> str | None:
    """Detect Claude Code org allowlist downgrade in stream/log text."""
    m = _MODEL_RESTRICTED_RE.search(text or "")
    if not m:
        return None
    requested = m.group("requested").strip()
    actual = m.group("actual").strip().rstrip(".")
    return format_model_substitution(requested, actual)


def extract_session_init_model(text: str) -> str | None:
    """Best-effort model from stream-json system/init or first message_start."""
    for line in (text or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        if '"init"' not in line and '"message_start"' not in line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get("type") == "system" and obj.get("subtype") == "init":
            model = obj.get("model")
            if isinstance(model, str) and model.strip():
                return model.strip()
        if obj.get("type") == "stream_event":
            ev = obj.get("event") if isinstance(obj.get("event"), dict) else {}
            if ev.get("type") == "message_start":
                msg = ev.get("message") if isinstance(ev.get("message"), dict) else {}
                model = msg.get("model")
                if isinstance(model, str) and model.strip():
                    return model.strip()
        msg = obj.get("message") if isinstance(obj.get("message"), dict) else {}
        model = msg.get("model")
        if isinstance(model, str) and model.strip():
            return model.strip()
    return None


def detect_model_substitution(
    text: str, *, expected_model: str | None = None
) -> str | None:
    """Fail-closed only on explicit org/runtime --model allowlist swap.

    OmniRoute often reports init model as an alias (``gemini-default``) while
    CLI/phase requested ``agy/gemini-3.5-flash-medium`` — that is NOT a
    downgrade. Comparing init ids causes false HALT; ignore ``expected_model``
    for equivalence and trust the restriction warning text only.
    """
    del expected_model  # kept for API compat with callers / --expected-model
    return detect_model_substitution_message(text)


def expected_model_from_command(command: list[str] | None) -> str | None:
    """Extract --model value from Claude argv."""
    if not command:
        return None
    for i, arg in enumerate(command):
        if arg == "--model" and i + 1 < len(command):
            val = (command[i + 1] or "").strip()
            return val or None
        if arg.startswith("--model="):
            val = arg.split("=", 1)[1].strip()
            return val or None
    return None


def detect_stream_json_api_error(text: str) -> str | None:
    """Parse claude stream-json result lines for terminal_reason=api_error."""
    lines = (text or "").splitlines()
    for line in reversed(lines[-80:]):
        line = line.strip()
        if not line.startswith("{"):
            continue
        if (
            "api_error" not in line
            and "API Error" not in line
            and "terminal_reason" not in line
        ):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get("type") != "result" and "terminal_reason" not in obj:
            continue
        term = str(obj.get("terminal_reason") or "")
        result = str(obj.get("result") or "")
        if term == "api_error" or "API Error" in result:
            msg = result.strip() or f"terminal_reason={term or 'api_error'}"
            return msg[:200]
    return None


def detect_shell_command_not_found(text: str) -> str | None:
    """Shell stderr only — not agent prose quoting fixture paths."""
    m = _SHELL_COMMAND_NOT_FOUND_RE.search(text or "")
    if m:
        return m.group(0).strip()[:200]
    return None


def detect_abort_in_text(text: str, *, exit_code: int | None = None) -> str | None:
    fatal = _match_patterns(text or "", _FATAL_ABORT_PATTERNS)
    if fatal:
        return fatal
    stream = detect_stream_json_api_error(text or "")
    if stream:
        return stream
    shell_missing = detect_shell_command_not_found(text or "")
    if shell_missing:
        return "command not found"
    # exit 0/None: process finished cleanly — permanent phrases in tool/doc prose
    # (e.g. runbook "Authentication error") must not HALT the loop.
    patterns: tuple[re.Pattern[str], ...] = _MALFORMED_RESULT_PATTERNS + _TRANSIENT_ABORT_PATTERNS
    if exit_code not in (0, None):
        patterns = (
            _MALFORMED_RESULT_PATTERNS
            + _PERMANENT_FAILURE_PATTERNS
            + _TRANSIENT_ABORT_PATTERNS
        )
    return _match_patterns(text or "", patterns)


def detect_dsh_abort_in_log(text: str) -> str | None:
    transient = _match_patterns(text or "", _DSH_TRANSIENT_PATTERNS)
    if transient:
        return f"dsh_transient: {transient}"
    permanent = _match_patterns(text or "", _DSH_PERMANENT_PATTERNS)
    if permanent:
        return f"dsh_permanent: {permanent}"
    return None


def _detect_dsh_session_complete(text: str) -> bool:
    last_nonempty = ""
    for line in (text or "").splitlines():
        normalized = line.strip()
        if not normalized:
            continue
        last_nonempty = normalized
        try:
            event = json.loads(normalized)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        candidates = [event]
        nested = event.get("event")
        if isinstance(nested, dict):
            candidates.append(nested)
        for item in candidates:
            if item.get("type") == "session_end" and item.get("status") == "completed":
                return True
    return bool(re.search(r"(?i)(?:FINISH|END)\s*$", last_nonempty))


def detect_abort_in_log(
    log_path: Path,
    *,
    exit_code: int | None = None,
    expected_model: str | None = None,
) -> str | None:
    if not log_path.is_file():
        return None
    try:
        data = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if len(data) > 200_000:
        data = data[-200_000:]
    # Extract only system/error lines from JSONL to avoid matching agent response text.
    system_lines: list[str] = []
    has_stream_events = False
    has_result_event = False
    for line in data.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            obj_type = obj.get("type")
            if obj_type == "result":
                has_result_event = True
                for key in ("result", "error", "message"):
                    val = obj.get(key)
                    if isinstance(val, str) and val.strip():
                        system_lines.append(val.strip())
                continue
            # Skip assistant/user content — only look at system/error events.
            if obj_type in ("assistant", "user"):
                continue
            # Surface human-readable system/informational content for pattern match.
            if obj_type == "system":
                content = obj.get("content")
                if isinstance(content, str) and content.strip():
                    system_lines.append(content.strip())
            # For stream events, skip content_block_delta with text/thinking.
            if obj_type == "stream_event":
                ev = obj.get("event") or {}
                delta = ev.get("delta") or {}
                if delta.get("type") in ("text_delta", "thinking_delta"):
                    continue
                has_stream_events = True
            system_lines.append(line)
        except (json.JSONDecodeError, AttributeError):
            # Non-JSON line (SESSION_START/END markers, plain stderr) — keep as-is.
            # Guard: truncated JSONL may fail to parse but still start with user/assistant
            # content — skip those to avoid false abort detection from tool_result text.
            if '"type":"user"' in line or '"type":"assistant"' in line:
                continue
            if '"type":"result"' in line:
                has_result_event = True
            if '"type":"stream_event"' in line:
                has_stream_events = True
            system_lines.append(line)
    system_text = "\n".join(system_lines)
    # Explicit kill marker from run_session (may arrive before JSONL parses cleanly).
    if _MODEL_SUBSTITUTION_MARKER.strip() in system_lines or exit_code == MODEL_SUBSTITUTION_EXIT:
        sub = detect_model_substitution(data, expected_model=expected_model)
        if sub:
            return sub
        structured = detect_structured_model_substitution_message(system_text)
        if structured:
            return structured
        return format_model_substitution(
            (expected_model or "?").strip() or "?", "substituted"
        )
    sub = detect_model_substitution(system_text, expected_model=expected_model)
    if sub:
        return sub
    # Log-cap truncation: tail is missing, so any non-zero exit is a transient abort.
    if _LOG_TRUNCATED_MARKER.strip() in system_lines and exit_code not in (0, None):
        return "log truncated — session output exceeded cap; exit_code indicates abort"
    if exit_code == 127:
        return "command not found"
    text_result = detect_abort_in_text(system_text, exit_code=exit_code)
    if text_result:
        return text_result
    # stream-json success always ends with type=result. Missing result = abrupt cut
    # (incl. exit 0 + balanced message_start/stop — Claude often exits 0 after
    # "API Error: Server error mid-response" without leaving that text in the log).
    if has_stream_events and not has_result_event:
        return "abrupt stream termination (no result event in JSONL)"
    return None


def classify_abort(
    reason: str | None,
    *,
    exit_code: int | None = None,
) -> str:
    """Return 'transient' | 'fatal' for an abort reason / process exit."""
    if exit_code in (130, 143, MODEL_SUBSTITUTION_EXIT, 127):
        return "fatal"
    r = reason or ""
    if r == "command not found":
        return "fatal"
    if _match_patterns(r, _FATAL_ABORT_PATTERNS):
        return "fatal"
    if _match_patterns(r, _PERMANENT_FAILURE_PATTERNS) or is_structured_model_substitution_reason(r):
        return "fatal"
    return "transient"


def transient_retry_max() -> int:
    try:
        return max(
            0, int(os.environ.get("EPIC_TRANSIENT_RETRY_MAX", DEFAULT_TRANSIENT_RETRY_MAX))
        )
    except ValueError:
        return DEFAULT_TRANSIENT_RETRY_MAX


def is_idle_timeout(reason: str | None) -> bool:
    """True when the reason is specifically an API stream idle timeout."""
    return bool(reason and re.search(r"(?i)stream idle timeout", reason))


def transient_backoff_sec(attempt: int, *, idle: bool = False) -> int:
    """Exponential backoff for 1-based retry attempt number."""
    try:
        base = int(os.environ.get("EPIC_TRANSIENT_BACKOFF_SEC", DEFAULT_TRANSIENT_BACKOFF_SEC))
    except ValueError:
        base = DEFAULT_TRANSIENT_BACKOFF_SEC
    if idle:
        try:
            base = max(base, int(os.environ.get("EPIC_IDLE_BACKOFF_SEC", DEFAULT_IDLE_BACKOFF_SEC)))
        except ValueError:
            base = max(base, DEFAULT_IDLE_BACKOFF_SEC)
    try:
        cap = int(os.environ.get("EPIC_TRANSIENT_BACKOFF_MAX", DEFAULT_TRANSIENT_BACKOFF_MAX))
    except ValueError:
        cap = DEFAULT_TRANSIENT_BACKOFF_MAX
    n = max(1, int(attempt))
    return min(base * (2 ** (n - 1)), cap)


def analyze_session_log(
    log_path: Path,
    *,
    exit_code: int | None = None,
    attempt: int = 1,
    expected_model: str | None = None,
    runtime: str = "claude",
) -> SessionAnalysis:
    """Classify one process result and expose a bounded retry decision."""
    try:
        raw_log = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        raw_log = ""
    adapter = get_adapter_for_runtime(runtime)
    ctx = SessionContext(
        prompt="",
        phase="",
        model=expected_model,
        runtime_id=runtime,
        extras={"exit_code": exit_code, "attempt": attempt, "log_path": log_path},
    )
    analysis = adapter.analyze_log(raw_log, ctx)
    reason = analysis.reason
    dsh_abort_kind = analysis.dsh_abort_kind

    if reason and is_structured_model_substitution_reason(reason):
        return {
            "outcome": SessionOutcome.PERMANENT_FAILURE.value,
            "aborted": True,
            "retryable": False,
            "abort_kind": "fatal",
            "reason": reason,
            "backoff_sec": 0,
        }
    if dsh_abort_kind:
        outcome = (
            SessionOutcome.PERMANENT_FAILURE
            if dsh_abort_kind in ("fatal", "unknown")
            else SessionOutcome.TRANSIENT_ABORT
        )
        abort_kind = "fatal" if dsh_abort_kind in ("fatal", "unknown") else dsh_abort_kind
        return {
            "outcome": outcome.value,
            "aborted": True,
            "retryable": dsh_abort_kind == "transient",
            "abort_kind": abort_kind,
            "reason": reason,
            "backoff_sec": transient_backoff_sec(attempt) if dsh_abort_kind == "transient" else 0,
        }

    interrupted = exit_code in (130, 143)
    timeout = exit_code == 124
    model_sub = bool(
        exit_code == MODEL_SUBSTITUTION_EXIT
        or is_structured_model_substitution_reason(reason)
        or _match_patterns(reason or "", (_MODEL_RESTRICTED_RE,))
    )
    malformed = bool(_match_patterns(reason or "", _MALFORMED_RESULT_PATTERNS))
    permanent = model_sub or bool(
        _match_patterns(reason or "", _PERMANENT_FAILURE_PATTERNS)
    ) or reason == "command not found" or exit_code == 127
    if not reason and not interrupted and not timeout and exit_code in (0, None):
        return {
            "outcome": SessionOutcome.CLEAN.value,
            "aborted": False,
            "retryable": False,
            "abort_kind": None,
            "reason": None,
            "backoff_sec": 0,
        }
    if timeout:
        reason = reason or "claude session timeout"
        outcome = SessionOutcome.TIMEOUT
    elif interrupted:
        reason = reason or f"process signal exit={exit_code}"
        outcome = SessionOutcome.SIGNAL
    elif malformed:
        outcome = SessionOutcome.MALFORMED_RESULT
    elif permanent:
        outcome = SessionOutcome.PERMANENT_FAILURE
    elif reason:
        outcome = SessionOutcome.TRANSIENT_ABORT
    else:
        reason = f"process exit={exit_code}"
        outcome = SessionOutcome.UNKNOWN_FAILURE
    kind = classify_abort(reason, exit_code=exit_code)
    if outcome in {
        SessionOutcome.SIGNAL,
        SessionOutcome.PERMANENT_FAILURE,
        SessionOutcome.MALFORMED_RESULT,
        SessionOutcome.UNKNOWN_FAILURE,
    }:
        kind = "fatal"
    retryable = kind == "transient"
    return {
        "outcome": outcome.value,
        "aborted": True,
        "retryable": retryable,
        "abort_kind": kind,
        "reason": reason,
        "backoff_sec": transient_backoff_sec(attempt, idle=is_idle_timeout(reason)) if kind == "transient" else 0,
    }


def git_dirty_paths(cwd: str | Path) -> list[str]:
    root = Path(cwd)
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain", "-uall"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        raise RuntimeError(f"git status failed: {exc}") from exc
    paths: list[str] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        # XY PATH or XY ORIG -> PATH
        rest = line[3:] if len(line) > 3 else line.strip()
        if " -> " in rest:
            rest = rest.split(" -> ", 1)[1]
        paths.append(rest.strip())
    return paths


def filter_step_dirty(
    dirty: list[str],
    *,
    step_id: str | None,
    epic_id: str | None = None,
    delta_paths: list[str] | None = None,
) -> list[str]:
    """Keep dirty files related to current step / delta (not whole repo noise)."""
    sid = (step_id or "").lower()
    eid = (epic_id or "").lower()
    delta_norm = [p.replace("\\", "/") for p in (delta_paths or [])]
    kept: list[str] = []
    for p in dirty:
        norm = p.replace("\\", "/")
        if sid and sid in norm.lower():
            # memory-bank files must also match epic_id to avoid cross-epic noise
            if norm.startswith("memory-bank/") and eid and eid not in norm.lower():
                pass
            else:
                kept.append(norm)
                continue
        if any(
            x in norm
            for x in (
                "frontend/src/",
                "apps/api/",
                "apps/edge/",
                "tests/",
                "memory-bank/",
            )
        ):
            if delta_norm:
                if any(d in norm or norm in d for d in delta_norm if d):
                    kept.append(norm)
                    continue
                # code dirty while step in progress — still relevant
                if norm.startswith(("frontend/", "apps/", "tests/")):
                    kept.append(norm)
                    continue
            else:
                if norm.startswith(("frontend/", "apps/", "tests/")):
                    kept.append(norm)
    # unique preserve order
    seen: set[str] = set()
    out: list[str] = []
    for p in kept:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out[:40]


def write_last_session(
    cwd: str | Path,
    *,
    track: str,
    status: str,
    reason: str | None = None,
    step_id: str | None = None,
    implement: str | None = None,
    resume_from: str | None = None,
    dirty: list[str] | None = None,
    log_file: str | None = None,
    exit_code: int | None = None,
    abort_kind: str | None = None,
    retryable: bool | None = None,
    outcome: str | None = None,
    retry_count: int | None = None,
    resume_dirty: bool | None = None,
    plan_id: str | None = None,
) -> Path:
    """Persist the latest session marker, including its owning plan ID."""
    path = last_session_path(cwd, track=track)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": utc_now(),
        "status": status,
        "reason": reason,
        "step_id": step_id,
        "implement": implement,
        "resume_from": resume_from,
        "dirty": dirty or [],
        "log_file": log_file,
        "exit_code": exit_code,
        "abort_kind": abort_kind,
        "retryable": retryable,
        "outcome": outcome,
        "retry_count": retry_count,
        "resume_dirty": resume_dirty,
        "plan_id": plan_id,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_last_session(cwd: str | Path, *, track: str = "epic") -> dict[str, Any] | None:
    path = last_session_path(cwd, track=track)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def load_implement_checkpoint_trace(
    cwd: str | Path,
    step_id: str | None,
    plan_id: str | None,
) -> list[str]:
    """Load pending checkpoint state for a dirty resume without writing it."""
    try:
        if not step_id:
            return []
        root = Path(cwd)
        matches: list[Path] = []
        if plan_id:
            matches = list(
                root.glob(
                    f"memory-bank/*/implement/implement-{plan_id}/{step_id}-*.yaml"
                )
            )
        if not matches:
            matches = list(
                root.glob(f"memory-bank/*/implement/implement-*/{step_id}-*.yaml")
            )
        if len(matches) != 1:
            print(
                f"checkpoint trace: expected one shard for {step_id}, found {len(matches)}",
                file=sys.stderr,
            )
            return []
        doc = load_implement(matches[0])
        if not doc.checkpoints or all_checkpoints_done(doc.checkpoints):
            return []
        resume = compute_resume_from(doc.checkpoints)
        lines = [
            "",
            "## checkpoint_trace (read-only)",
            f"step: {doc.step_id}",
            "checkpoints:",
        ]
        for checkpoint in doc.checkpoints:
            lines.append(f"- id: {checkpoint.id}")
            lines.append(f"  criterion: {checkpoint.criterion}")
            lines.append(f"  status: {checkpoint.status}")
            if checkpoint.status == "done" and checkpoint.done_at:
                lines.append(f"  done_at: {checkpoint.done_at}")
        if resume:
            lines.append(f"resume_from_checkpoint: {resume}")
        lines.append(
            "HARD rule: checkpoint statuses are read-only; do not modify this trace."
        )
        return lines
    except Exception as exc:
        print(f"checkpoint trace unavailable: {exc}", file=sys.stderr)
        return []


def extract_paths_from_delta(delta: list[str]) -> list[str]:
    """Best-effort path extraction from delta bullet strings."""
    paths: list[str] = []
    pat = re.compile(
        r"(?:frontend/|apps/|tests/|dsh/|loop/|\.claude/|memory-bank/)[^\s`'\"]+"
    )
    for item in delta:
        for m in pat.finditer(str(item)):
            paths.append(m.group(0).rstrip(".,);:"))
    return paths


def dirty_resume_prompt_lines(
    cwd: str | Path,
    *,
    step_id: str | None,
    epic_id: str | None = None,
    delta: list[str] | None = None,
    resume_from: str | None = None,
    last: dict[str, Any] | None = None,
    plan_id: str | None = None,
) -> list[str]:
    dirty = git_dirty_paths(cwd)
    related = filter_step_dirty(
        dirty,
        step_id=step_id,
        epic_id=epic_id,
        delta_paths=extract_paths_from_delta(delta or []),
    )
    aborted = bool(last and str(last.get("status") or "") == "aborted")
    if not related and not aborted:
        return []
    lines = ["", "## resume_dirty (HARD)"]
    if aborted:
        lines.append(
            f"prev_session: aborted"
            + (f" — {last.get('reason')}" if last and last.get("reason") else "")
        )
        if last and last.get("abort_kind"):
            lines.append(f"abort_kind: {last['abort_kind']}")
        if last and last.get("resume_from"):
            lines.append(f"prev_resume_from: {last['resume_from']}")
    if resume_from:
        lines.append(f"continue_from_checkpoint: {resume_from}")
    if related:
        lines.append("dirty_files (do NOT restart discovery; continue edits):")
        for p in related:
            lines.append(f"- {p}")
    lines.append(
        "FORBIDDEN: discard/revert dirty step files; re-do cp со status=done; "
        "full-repo rediscovery when dirty_files non-empty."
    )
    lines.append(
        "REQUIRED: Read dirty_files first → finish pending checkpoints → flush cp status."
    )
    cp_trace = load_implement_checkpoint_trace(cwd, step_id, plan_id)
    if cp_trace:
        lines.extend(["", *cp_trace])
    return lines


def delta_paths_exist(cwd: str | Path, delta: list[str]) -> tuple[bool, list[str]]:
    """True if every extracted path from delta exists on disk (and ≥1 path found)."""
    root = Path(cwd)
    paths = extract_paths_from_delta(delta)
    if not paths:
        return False, []
    missing: list[str] = []
    for p in paths:
        if not (root / p).exists():
            missing.append(p)
    return (len(missing) == 0), missing


_SESSION_LOG_LIMIT_DEFAULT = 10_000_000
_LOG_TRUNCATED_MARKER = "SESSION_LOG_TRUNCATED\n"


def _session_log_limit() -> int:
    raw = os.environ.get("EPIC_SESSION_LOG_LIMIT_BYTES", "").strip()
    if not raw:
        return _SESSION_LOG_LIMIT_DEFAULT
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(
            "EPIC_SESSION_LOG_LIMIT_BYTES must be a positive integer"
        ) from exc
    if value < 64_000:
        raise ValueError("EPIC_SESSION_LOG_LIMIT_BYTES must be >= 64000")
    return value


def _write_session_log(handle: Any, data: bytes, total: int) -> int:
    """Append process output while keeping the raw session log bounded."""
    limit = _session_log_limit()
    if total >= limit:
        return total
    chunk = data[: limit - total]
    handle.write(chunk.decode("utf-8", errors="replace"))
    handle.flush()
    new_total = total + len(chunk)
    if new_total >= limit and len(data) > len(chunk):
        # Log cap hit mid-chunk — write truncation marker so detect_abort_in_log
        # knows the tail is missing and won't misclassify exit_code != 0 as fatal.
        handle.write(_LOG_TRUNCATED_MARKER)
        handle.flush()
    return new_total


def run_session(
    command: list[str],
    *,
    mode: str,
    session_id: str,
    timeout: float,
    kill_grace: float,
    log_path: str | Path,
    expected_model: str | None = None,
    heartbeat_sec: float | None = None,
    idle_timeout: float | None = None,
    stdin_text: str | None = None,
    progress_mode: str = "tool_json",
) -> int:
    """Run one Claude session with bounded output and process-group cleanup."""
    if mode not in {"headless", "interactive"}:
        raise ValueError("mode must be headless or interactive")
    if not command:
        raise ValueError("session command must not be empty")
    if timeout <= 0 or kill_grace < 0:
        raise ValueError("timeout must be positive and kill_grace must not be negative")
    if heartbeat_sec is not None and heartbeat_sec <= 0:
        raise ValueError("heartbeat_sec must be positive when provided")
    if idle_timeout is not None and idle_timeout <= 0:
        raise ValueError("idle_timeout must be positive when provided")
    if progress_mode not in _PROGRESS_MODES:
        raise ValueError(f"progress_mode must be one of {sorted(_PROGRESS_MODES)}")

    expected = (expected_model or "").strip() or expected_model_from_command(command)
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    timed_out = False
    idle_timed_out = False
    model_substituted = False
    total = 0
    scan_buf = ""
    tool_tail = ""
    # Idle: tool_json = last tool_use/tool_result; stream_bytes = last stdout chunk (Codex).
    last_activity = started
    last_heartbeat = started
    with path.open("w", encoding="utf-8") as log:
        log.write(f"SESSION_START session={session_id} mode={mode} command={command[0]}\n")
        if expected:
            log.write(f"EXPECTED_MODEL {expected}\n")
        log.flush()
        stdin_handle = None
        if mode == "interactive":
            stdin_handle = None
        elif stdin_text is not None:
            stdin_handle = subprocess.PIPE
        else:
            stdin_handle = subprocess.DEVNULL
        process = subprocess.Popen(
            command,
            stdin=stdin_handle,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        if stdin_text is not None and process.stdin is not None:
            process.stdin.write(stdin_text.encode("utf-8"))
            process.stdin.close()
        assert process.stdout is not None
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        try:
            while True:
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    timed_out = process.poll() is None
                    if timed_out:
                        try:
                            _safe_killpg(process.pid, signal.SIGTERM)
                        except OSError:
                            try:
                                process.terminate()
                            except OSError:
                                pass
                        try:
                            process.wait(timeout=kill_grace)
                        except subprocess.TimeoutExpired:
                            try:
                                _safe_killpg(process.pid, signal.SIGKILL)
                            except OSError:
                                try:
                                    process.kill()
                                except OSError:
                                    pass
                            process.wait()
                    break
                events = selector.select(min(remaining, 0.1))
                now = time.monotonic()
                if heartbeat_sec is not None and now - last_heartbeat >= heartbeat_sec:
                    elapsed = now - started
                    idle_for = now - last_activity
                    state = "running" if process.poll() is None else "exited"
                    hb = (
                        f"SESSION_HEARTBEAT session={session_id} elapsed={elapsed:.1f}s "
                        f"idle_for={idle_for:.1f}s state={state} cwd={os.getcwd()}\n"
                    )
                    log.write(hb)
                    log.flush()
                    _write_status(
                        f"==> heartbeat: session={session_id} elapsed={elapsed:.1f}s "
                        f"idle_for={idle_for:.1f}s state={state}\n"
                    )
                    last_heartbeat = now
                if (
                    idle_timeout is not None
                    and process.poll() is None
                    and now - last_activity >= idle_timeout
                ):
                    idle_timed_out = True
                    log.write(
                        f"SESSION_IDLE_TIMEOUT session={session_id} idle_timeout={idle_timeout:g}s idle_for={now - last_activity:.1f}s cwd={os.getcwd()}\n"
                    )
                    log.flush()
                    _write_status(
                        f"==> idle timeout: session={session_id} "
                        f"idle_for={now - last_activity:.1f}s limit={idle_timeout:g}s\n"
                    )
                    _safe_killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=kill_grace)
                    except subprocess.TimeoutExpired:
                        _safe_killpg(process.pid, signal.SIGKILL)
                        process.wait()
                    break
                for key, _ in events:
                    data = key.fileobj.read1(65536)
                    if data:
                        total = _write_session_log(log, data, total)
                        try:
                            sys.stdout.buffer.write(data)
                            sys.stdout.buffer.flush()
                        except BrokenPipeError:
                            # Downstream stream-filter/tty closed — keep draining
                            # Claude into the session log so SESSION_END is written.
                            pass
                        try:
                            chunk_txt = data.decode("utf-8", errors="replace")
                        except Exception:
                            chunk_txt = ""
                        if progress_mode == "stream_bytes":
                            last_activity = time.monotonic()
                        elif progress_mode in {"tool_json", "codex_json"}:
                            progressed, tool_tail = _tool_progress_seen(
                                tool_tail, chunk_txt, progress_mode=progress_mode
                            )
                            if progressed:
                                last_activity = time.monotonic()
                        if not model_substituted:
                            scan_buf = (scan_buf + chunk_txt)[-50_000:]
                            sub = detect_model_substitution(
                                scan_buf, expected_model=expected
                            )
                            if sub:
                                model_substituted = True
                                log.write(_MODEL_SUBSTITUTION_MARKER)
                                log.write(sub + "\n")
                                log.flush()
                                _write_status(f"\n==> HALT: {sub}\n")
                                if process.poll() is None:
                                    _safe_killpg(process.pid, signal.SIGTERM)
                                    try:
                                        process.wait(timeout=kill_grace)
                                    except subprocess.TimeoutExpired:
                                        _safe_killpg(process.pid, signal.SIGKILL)
                                        process.wait()
                    else:
                        selector.unregister(key.fileobj)
                if process.poll() is not None and not selector.get_map():
                    break
                if model_substituted and process.poll() is not None:
                    break
            if process.poll() is None:
                process.wait()
        finally:
            selector.close()
            if process.poll() is None:
                _safe_killpg(process.pid, signal.SIGKILL)
                process.wait()

        if model_substituted:
            rc = MODEL_SUBSTITUTION_EXIT
        elif idle_timed_out:
            log.write(
                f'{{"type":"result","terminal_reason":"api_error","result":"API Error: Stream idle timeout - no tool_use/tool_result","subtype":"success"}}\n'
            )
            rc = 124
        elif timed_out:
            log.write(f"SESSION_TIMEOUT session={session_id} timeout={timeout:g}s\n")
            rc = 124
        else:
            rc = process.returncode
            if rc < 0:
                rc = 128 + -rc
            # Late detection: org allowlist swap after Claude already exited 0.
            if rc == 0:
                try:
                    full = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    full = scan_buf
                sub = detect_model_substitution(full, expected_model=expected)
                if sub:
                    log.write(_MODEL_SUBSTITUTION_MARKER)
                    log.write(sub + "\n")
                    log.flush()
                    rc = MODEL_SUBSTITUTION_EXIT
        log.write(f"SESSION_END session={session_id} exit_code={rc} elapsed={time.monotonic() - started:.3f}s\n")
        log.flush()
    return rc


def _session_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="session_resilience.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run-session")
    run_parser.add_argument("--mode", choices=("headless", "interactive"), required=True)
    run_parser.add_argument("--session-id", required=True)
    run_parser.add_argument("--timeout", type=float, required=True)
    run_parser.add_argument("--kill-grace", type=float, required=True)
    run_parser.add_argument("--heartbeat-sec", type=float, default=0.0)
    run_parser.add_argument("--idle-timeout", type=float, default=0.0)
    run_parser.add_argument(
        "--progress-mode",
        choices=sorted(_PROGRESS_MODES),
        default="tool_json",
        help="tool_json=Claude/DSH tool_use idle; stream_bytes=any stdout; codex_json=codex --json events",
    )
    run_parser.add_argument("--log", type=Path, required=True)
    run_parser.add_argument(
        "--expected-model",
        default="",
        help="Requested --model; mismatch/org swap → exit 125 fail-closed",
    )
    run_parser.add_argument(
        "--stdin-file",
        type=Path,
        default=None,
        help="Prompt payload written to subprocess stdin (headless runtimes e.g. codex exec)",
    )
    run_parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    stdin_text = None
    if args.stdin_file is not None:
        try:
            stdin_text = args.stdin_file.read_text(encoding="utf-8")
        except OSError as exc:
            parser.error(f"cannot read stdin-file {args.stdin_file}: {exc}")
    try:
        return run_session(
            command,
            mode=args.mode,
            session_id=args.session_id,
            timeout=args.timeout,
            kill_grace=args.kill_grace,
            log_path=args.log,
            expected_model=(args.expected_model or "").strip() or None,
            heartbeat_sec=args.heartbeat_sec or None,
            idle_timeout=args.idle_timeout or None,
            stdin_text=stdin_text,
            progress_mode=args.progress_mode,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(_session_cli(sys.argv[1:]))
