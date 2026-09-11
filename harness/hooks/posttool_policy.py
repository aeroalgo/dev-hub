#!/usr/bin/env python3
"""Pure policy adapters for PostToolUse lifecycle event dispatch.

Contains adapters for:
- AgentPostToolAdapter: processes Agent/Task completions, extracts verdicts,
  records gate evidence idempotently, releases repair/in-flight markers, updates telemetry.
- BashOutputCapAdapter: caps large bash command outputs, extracts signals/LLM summary/head-tail,
  writes complete raw dump safely to disk, and updates tool output.
- WritePostToolAdapter: handles post-write context ledger invalidation and epic touch ledger.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

_HOOKS_DIR = Path(__file__).resolve().parent
_HUB_ROOT = _HOOKS_DIR.parents[1]
if str(_HUB_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUB_ROOT))
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

try:
    from hook_dispatch import (
        DecisionEnvelope,
        DiagnosticCode,
        DispatchBranch,
        EventContext,
        PostToolUse,
        dispatch_posttool,
        merge_updated_inputs,
    )
except ImportError:
    from harness.hooks.hook_dispatch import (
        DecisionEnvelope,
        DiagnosticCode,
        DispatchBranch,
        EventContext,
        PostToolUse,
        dispatch_posttool,
        merge_updated_inputs,
    )

from _lib import (
    _discover_registry,
    clear_in_flight,
    current_gate_identity,
    extract_verdict,
    is_epic_loop_env,
    load_output_summary_env,
    load_project_env,
    load_state,
    mark_verdict_recorded,
    product_cwd,
    record_verdict,
    save_state,
    should_skip_verdict_record,
    sync_gate_identity,
    verdict_dedupe_key,
    verdict_evidence,
    workflow_state_active,
)
from context_ledger_adapters import (
    WRITE_TOOL_ALIASES,
    evaluate_write_payload,
    normalize_write_payload,
)
from touch_ledger import record_touch

try:
    from loop.output_summary import LogSummary, build_summary, format_summary
except ImportError:
    LogSummary = None  # type: ignore
    build_summary = None  # type: ignore
    format_summary = None  # type: ignore


# Bash Output Cap constants
MAX_CHARS = 12_000
SOFT_NOISY = 4_000
HEAD = 4_000
TAIL = 2_500
EXTRACT_MAX_LINES = 40
EXTRACT_MAX_CHARS = 4_000
EXTRACT_MAX_UNIQUE = 12
EXTRACT_CONTEXT = 1
LLM_INPUT_MAX = 24_000
LLM_TIMEOUT_SEC = 30
LLM_RETRIES = 3
LLM_BACKOFF_SEC = 0.8

_NOISY = re.compile(
    r"(?i)\b(pytest|cargo test|npm test|vitest|playwright|jest|"
    r"docker compose logs|docker logs|journalctl|tail -f)\b"
)

_SIGNAL = re.compile(
    r"(?i)("
    r"\bFAILED\b|\bFAILURES\b|\bERRORS\b|\bERROR\b|Traceback|AssertionError|"
    r"ModbusException|ExceptionResponse|"
    r"^=+\s*\d+\s+(failed|passed|error)|"
    r"EXIT(_STATUS)?=\d+|exit_code|short test summary|"
    r"poll group .*crash|already exists|last_run_started_at|"
    r"^\s*E\s+\S"
    r")"
)

_FINGERPRINT_SUBS = [
    (re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:\s*UTC)?"), "<TS>"),
    (re.compile(r"^\s*\d+[:-]"), ""),  # rg line prefixes "12:" / "12-"
    (re.compile(r"\bauto_\d+\b"), "auto_*"),
    (re.compile(r"\b_hyper_\d+_\d+_chunk\b"), "_hyper_*_chunk"),
    (re.compile(r"\bcompress_hyper_\d+_\d+_chunk\b"), "compress_hyper_*_chunk"),
    (re.compile(r"\bpid=\d+\b"), "pid=*"),
    (re.compile(r"\[\d+\]"), "[*]"),  # postgres [58291]
    (re.compile(r"\b0x[0-9a-fA-F]+\b"), "0x*"),
]


def _tool_response_text(value: object) -> str:
    """Extract string representation from arbitrary tool_response payload."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        content = value.get("content")
        if isinstance(content, list):
            parts = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and isinstance(item.get("text"), str)
            ]
            return "\n".join(parts)
        if isinstance(content, str):
            return content
        if "stdout" in value or "stderr" in value:
            out = str(value.get("stdout") or "")
            err = str(value.get("stderr") or "")
            return out if not err else f"{out}\n--- stderr ---\n{err}"
    if isinstance(value, list):
        return "\n".join(_tool_response_text(item) for item in value)
    return ""


def _as_text(resp: object) -> tuple[str, str, dict[str, Any]]:
    """Parse tool_response into stdout, stderr and shaped structure."""
    if isinstance(resp, dict):
        out = dict(resp)
        stdout = str(out.get("stdout") or out.get("output") or "")
        stderr = str(out.get("stderr") or "")
        if not stdout and not stderr and "content" in out:
            stdout = str(out.get("content") or "")
        return stdout, stderr, out
    if isinstance(resp, str):
        return resp, "", {
            "stdout": resp,
            "stderr": "",
            "interrupted": False,
            "isImage": False,
        }
    s = str(resp or "")
    return s, "", {
        "stdout": s,
        "stderr": "",
        "interrupted": False,
        "isImage": False,
    }


def _dump_dir(cwd: str) -> Path:
    root = Path(cwd or os.getcwd())
    d = root / ".claude" / "runtime" / "bash-dumps"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_dump(cwd: str, session_id: str, cmd: str, text: str) -> Path:
    h = hashlib.sha1(f"{time.time_ns()}:{cmd[:80]}".encode()).hexdigest()[:10]
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", session_id or "nosession")[:40]
    path = _dump_dir(cwd) / f"{safe}-{h}.log"
    header = f"# cmd: {cmd[:500]}\n# chars: {len(text)}\n\n"
    path.write_text(header + text, encoding="utf-8", errors="replace")
    return path


def _fingerprint(line: str) -> str:
    s = line.strip()
    for pat, repl in _FINGERPRINT_SUBS:
        s = pat.sub(repl, s)
    s = re.sub(r"\s+", " ", s)
    return s[:240]


def extract_signals(text: str, max_lines: int = EXTRACT_MAX_LINES) -> tuple[str, bool]:
    lines = text.splitlines()
    groups: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for i, line in enumerate(lines):
        if not _SIGNAL.search(line):
            continue
        fp = _fingerprint(line)
        if not fp:
            continue
        if fp not in groups:
            groups[fp] = {"count": 1, "first_idx": i, "sample": line.rstrip()}
            order.append(fp)
        else:
            groups[fp]["count"] += 1

    out: list[str] = []
    unique_kept = 0
    for fp in order:
        if unique_kept >= EXTRACT_MAX_UNIQUE:
            skipped = len(order) - unique_kept
            if skipped > 0:
                more = sum(groups[f]["count"] for f in order[unique_kept:])
                out.append(
                    f"… [{skipped} more unique signal patterns, {more} lines total — see full dump]"
                )
            break
        g = groups[fp]
        idx = g["first_idx"]
        for j in range(max(0, idx - EXTRACT_CONTEXT), min(len(lines), idx + EXTRACT_CONTEXT + 1)):
            if j == idx:
                continue
            ctx = lines[j].rstrip()
            if ctx and not _SIGNAL.search(ctx):
                out.append(ctx)
        sample = g["sample"]
        if g["count"] > 1:
            out.append(f"{sample}  [×{g['count']} same]")
        else:
            out.append(sample)
        unique_kept += 1
        if len(out) >= max_lines:
            break

    footer = lines[-25:] if len(lines) > 25 else lines
    footer_added = 0
    for line in footer:
        if not (
            _SIGNAL.search(line)
            or line.startswith("=")
            or "passed" in line.lower()
            or "failed" in line.lower()
        ):
            continue
        fp = _fingerprint(line)
        if fp in groups and groups[fp]["count"] > 1:
            continue
        if line.rstrip() in out:
            continue
        out.append(line.rstrip())
        footer_added += 1
        if footer_added >= 8 or len(out) >= max_lines:
            break

    body_lines: list[str] = []
    size = 0
    for line in out:
        add = len(line) + 1
        if size + add > EXTRACT_MAX_CHARS and body_lines:
            body_lines.append(
                f"… [extract truncated at {EXTRACT_MAX_CHARS} chars; see full dump]"
            )
            break
        body_lines.append(line)
        size += add

    body = "\n".join(body_lines).strip()
    good = bool(body) and (
        unique_kept >= 1
        or bool(
            re.search(
                r"(?i)(failed|error|traceback|modbusexception|exit(_status)?=)",
                body,
            )
        )
    )
    return body, good


def _head_tail(text: str, head: int = HEAD, tail: int = TAIL) -> str:
    if len(text) <= MAX_CHARS:
        return text
    omitted = len(text) - head - tail
    return (
        text[:head]
        + f"\n\n… [truncated {omitted} chars] …\n\n"
        + text[-tail:]
    )


def _llm_enabled() -> bool:
    load_output_summary_env()
    return os.environ.get("PROJECT_OUTPUT_SUMMARY", "1").strip() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _llm_config() -> tuple[str, str, str, str | None]:
    load_output_summary_env()
    url = (
        os.environ.get("PROJECT_OUTPUT_SUMMARY_URL")
        or "http://localhost:20128/v1"
    ).rstrip("/")
    model = (
        os.environ.get("PROJECT_OUTPUT_SUMMARY_MODEL")
        or "free-stack"
    )
    fallback_raw = os.environ.get("PROJECT_OUTPUT_SUMMARY_FALLBACK_MODEL")
    if fallback_raw is None:
        fallback: str | None = "aug/claude-haiku-4.5"
    elif fallback_raw.strip() in {"", "0", "-", "off", "none"}:
        fallback = None
    else:
        fallback = fallback_raw.strip()
    key = os.environ.get("PROJECT_OUTPUT_SUMMARY_KEY") or ""
    if not key:
        key_file = Path(
            os.environ.get("PROJECT_OUTPUT_SUMMARY_KEY_FILE")
            or Path.home() / ".codex" / ".omniroute_key"
        ).expanduser()
        if key_file.is_file():
            key = key_file.read_text(encoding="utf-8").strip()
    return url, model, key, fallback


def _retry_settings() -> tuple[int, float, float, bool]:
    load_output_summary_env()
    try:
        retries = int(os.environ.get("PROJECT_OUTPUT_SUMMARY_RETRIES", str(LLM_RETRIES)))
    except ValueError:
        retries = LLM_RETRIES
    try:
        timeout = float(os.environ.get("PROJECT_OUTPUT_SUMMARY_TIMEOUT", str(LLM_TIMEOUT_SEC)))
    except ValueError:
        timeout = float(LLM_TIMEOUT_SEC)
    try:
        backoff = float(os.environ.get("PROJECT_OUTPUT_SUMMARY_BACKOFF", str(LLM_BACKOFF_SEC)))
    except ValueError:
        backoff = float(LLM_BACKOFF_SEC)
    debug = os.environ.get("PROJECT_OUTPUT_SUMMARY_DEBUG", "").strip() in {"1", "true", "yes"}
    return retries, timeout, backoff, debug


def _structured_enabled() -> bool:
    load_output_summary_env()
    return os.environ.get("PROJECT_OUTPUT_SUMMARY_STRUCTURED", "1").strip() not in {
        "0",
        "false",
        "no",
        "off",
    }


def build_view_structured(summary: Any, dump_path: Path) -> str:
    lines: list[str] = [
        f"[output-cap:structured] full dump → {dump_path}",
        f"cmd: {summary.cmd[:300]}",
        f"outcome: {summary.outcome} | {summary.summary_line}",
        "",
    ]
    if getattr(summary, "failed_tests", None):
        lines.append("## Failed tests")
        for test in summary.failed_tests:
            lines.append(f"  - {test}")
        lines.append("")
    if getattr(summary, "errors", None):
        lines.append("## Errors")
        for err in summary.errors:
            lines.append(f"  - {err}")
        lines.append("")
    if getattr(summary, "highlights", None):
        lines.append("## Highlights")
        for h in summary.highlights:
            lines.append(f"  {h}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_view(cmd: str, combined: str, dump_path: Path) -> tuple[str, str]:
    extract, good = extract_signals(combined)
    if good and len(extract) < len(combined) * 0.7:
        if "[×" not in extract and re.search(r"(?i)pytest|FAILED|passed in", combined[-2000:] or ""):
            good = False
        else:
            return (
                f"[output-cap:signal-extract] full dump → {dump_path}\n"
                f"cmd: {cmd[:300]}\n\n"
                f"{extract}\n",
                "signal-extract",
            )
    if _structured_enabled() and build_summary is not None:
        try:
            res = build_summary(cmd, combined)
        except Exception:
            res = None
        if res:
            return build_view_structured(res, dump_path), "structured"
    capped = _head_tail(combined)
    return (
        f"[output-cap:head-tail] full dump → {dump_path}\n"
        f"cmd: {cmd[:300]}\n\n"
        f"{capped}\n",
        "head-tail",
    )


class AgentPostToolAdapter:
    """Pure adapter for Agent and Task posttool verdict persistence and in-flight release."""

    def evaluate(self, context: EventContext) -> DecisionEnvelope | None:
        raw = context.raw_payload or {}
        tool_name = context.tool_name or ""
        # Disjoint check: AgentPostTool only processes Agent and Task tools
        if tool_name not in {"Agent", "Task"}:
            return None

        cwd = str(context.cwd)
        session_id = context.session_id
        text = _tool_response_text(context.tool_output or raw.get("tool_response"))
        tool_input = context.tool_input if isinstance(context.tool_input, dict) else {}
        
        agent_type = str(
            raw.get("agent_type") or tool_input.get("subagent_type") or tool_input.get("agent_type") or ""
        ).strip() or None
        sidecar_agent = str(raw.get("sidecar_agent") or "").strip() or None

        st = load_state(session_id, cwd) if session_id else {}

        # Release in_flight marker if present for this agent
        if agent_type:
            clear_in_flight(st, agent=str(agent_type))

        # Repair completion never authorizes a verifier PASS; parent must retry @verify.
        if st.get("repair_in_flight"):
            st["repair_in_flight"] = False
            st["gate_diagnostic"] = "repair_complete_verify_required"
            if session_id:
                save_state(session_id, cwd, st)
            return DecisionEnvelope.record(
                reason="repair_in_flight_cleared",
                diagnostic_code=DiagnosticCode.RECORDED,
                diagnostic_details={"status": "repair_complete_verify_required"},
            )

        verdict = extract_verdict(
            text,
            cwd=cwd,
            agent_id=sidecar_agent or "verify",
        )
        if not verdict:
            try:
                from gate_runtime import VerdictExtractor
                v_res, _, _ = VerdictExtractor.extract_verdict(text, agent_type=agent_type)
                if v_res:
                    verdict = v_res
            except Exception:
                pass

        if not agent_type or not verdict:
            if session_id:
                save_state(session_id, cwd, st)
            return DecisionEnvelope.record(
                reason="no_agent_or_verdict",
                diagnostic_code=DiagnosticCode.RECORDED,
            )

        definition = _discover_registry(cwd or None).get(agent_type)
        if (
            definition is not None
            and definition.managed
            and definition.mode == "optional"
            and definition.verdict == "none"
        ):
            if session_id:
                save_state(session_id, cwd, st)
            return DecisionEnvelope.record(
                reason="optional_managed_agent_ignored",
                diagnostic_code=DiagnosticCode.RECORDED,
            )

        tool_use_id = str(raw.get("tool_use_id") or "").strip() or None
        dedupe_key = verdict_dedupe_key(
            session_id,
            agent_type,
            tool_use_id=tool_use_id,
            verdict=verdict,
        )

        if should_skip_verdict_record(st, dedupe_key):
            if session_id:
                save_state(session_id, cwd, st)
            return DecisionEnvelope.record(
                reason="duplicate_verdict_skipped",
                diagnostic_code=DiagnosticCode.RECORDED,
                diagnostic_details={"dedupe_key": dedupe_key, "verdict": verdict},
            )

        identity = current_gate_identity(cwd, session_id)
        sync_gate_identity(st, identity)
        evidence = verdict_evidence(identity, verdict)
        record_key = sidecar_agent if sidecar_agent else agent_type
        matched, _diagnostic = record_verdict(st, record_key, verdict, evidence)
        mark_verdict_recorded(st, dedupe_key)

        if record_key == "verify" and matched:
            try:
                from epic_lib import mirror_verify_verdict
                mirror_verify_verdict(
                    cwd,
                    verdict,
                    evidence=evidence,
                    session_id=session_id,
                    agent_id=sidecar_agent or agent_type,
                )
                print(
                    f"posttool: recorded verify verdict={verdict}",
                    file=sys.stderr,
                )
            except (ImportError, OSError, TypeError, ValueError) as exc:
                print(
                    f"posttool: mirror_verify_verdict failed: {exc}",
                    file=sys.stderr,
                )

        if session_id and cwd:
            try:
                from context_telemetry import collect_session_telemetry
                agg, diag = collect_session_telemetry(cwd, session_id)
                if diag and diag != "missing_ledger":
                    print(f"agent-posttool: telemetry diagnostic warning: {diag}", file=sys.stderr)
                elif agg:
                    st["context_telemetry_counters"] = {
                        "unique_reads": agg.unique_reads,
                        "duplicate_reads": agg.duplicate_reads,
                        "monolith_plan_attempts": agg.monolith_plan_attempts,
                        "search_exceptions": agg.search_exceptions,
                        "highest_repeat_path": agg.highest_repeat_path,
                    }
            except Exception as exc:
                print(f"agent-posttool: collect_session_telemetry failed: {exc}", file=sys.stderr)

        if session_id:
            save_state(session_id, cwd, st)

        return DecisionEnvelope.record(
            reason=f"verdict_recorded:{verdict}",
            diagnostic_code=DiagnosticCode.RECORDED,
            diagnostic_details={
                "agent_type": agent_type,
                "verdict": verdict,
                "dedupe_key": dedupe_key,
            },
        )


class BashOutputCapAdapter:
    """Pure adapter for Bash PostToolUse output shaping and full dump retention."""

    def evaluate(self, context: EventContext) -> DecisionEnvelope | None:
        tool_name = context.tool_name or ""
        # Disjoint check: BashOutputCap only processes Bash tool
        if tool_name != "Bash":
            return None

        raw = context.raw_payload or {}
        tool_input = context.tool_input if isinstance(context.tool_input, dict) else {}
        cmd = str(tool_input.get("command") or "")
        resp = context.tool_output or raw.get("tool_response")
        stdout, stderr, shaped = _as_text(resp)
        combined = stdout if not stderr else f"{stdout}\n--- stderr ---\n{stderr}"
        total = len(combined)

        noisy = bool(_NOISY.search(cmd))
        soft = SOFT_NOISY if noisy else MAX_CHARS

        if total <= soft:
            return DecisionEnvelope.allow(
                reason="output_within_limit",
                diagnostic_code=DiagnosticCode.ALLOW,
                metadata={"total_chars": total},
            )

        cwd = str(product_cwd(context.cwd or raw.get("cwd") or os.getcwd()))
        session_id = context.session_id or str(raw.get("session_id") or "")

        dump_path: Path | None = None
        try:
            dump_path = _save_dump(cwd, session_id, cmd, combined)
        except Exception as exc:
            print(f"posttool: failed to save bash dump: {exc}", file=sys.stderr)

        try:
            if dump_path is not None:
                view, mode = build_view(cmd, combined, dump_path)
            else:
                view = _head_tail(combined)
                mode = "head-tail-nodump"
        except Exception as exc:
            print(f"posttool: output shaping build_view failed ({exc}); falling back to head-tail", file=sys.stderr)
            view = _head_tail(combined)
            mode = "head-tail-fallback"

        shaped["stdout"] = view
        shaped["stderr"] = ""
        shaped.setdefault("interrupted", False)
        shaped.setdefault("isImage", False)

        dump_str = str(dump_path) if dump_path else "unavailable"
        additional_ctx = (
            f"output-cap:{mode} ({total}→{len(view)} chars). "
            f"Full: {dump_str}. "
            "Prefer bin/pytest -q --tb=line; docker logs --tail=80; rg dump."
        )

        return DecisionEnvelope.allow(
            updated_input=shaped,
            reason=f"output_capped:{mode}",
            diagnostic_code=DiagnosticCode.OUTPUT_CAPPED,
            diagnostic_details={
                "mode": mode,
                "dump_path": dump_str,
                "original_chars": total,
                "shaped_chars": len(view),
            },
            metadata={
                "additional_context": additional_ctx,
                "additionalContext": additional_ctx,
                "updatedToolOutput": shaped,
            },
        )


class WritePostToolAdapter:
    """Pure adapter for Write/Edit tools posttool touch recording and ledger evaluation."""

    def evaluate(self, context: EventContext) -> DecisionEnvelope | None:
        tool_name = context.tool_name or ""
        if tool_name not in WRITE_TOOL_ALIASES:
            return None

        raw = context.raw_payload or {}
        cwd = product_cwd(context.cwd)
        session_id = context.session_id

        try:
            evaluate_write_payload(raw, provider="claude", cwd=cwd)
        except Exception:
            pass

        try:
            payload = normalize_write_payload(raw, provider="claude", default_cwd=cwd)
            st = load_state(session_id, cwd) if session_id else {}
            if is_epic_loop_env() or workflow_state_active(st, cwd):
                record_touch(
                    cwd,
                    payload.raw_path,
                    operation=str(payload.operation or "edit"),
                )
        except Exception:
            pass

        return DecisionEnvelope.allow(
            reason="write_posttool_processed",
            diagnostic_code=DiagnosticCode.RECORDED,
        )


def create_posttool_branches() -> list[DispatchBranch]:
    """Assemble canonical ordered branches for PostToolUse dispatch."""
    return [
        DispatchBranch("write_posttool", WritePostToolAdapter().evaluate, order=10),
        DispatchBranch("agent_posttool", AgentPostToolAdapter().evaluate, order=20),
        DispatchBranch("bash_output_cap", BashOutputCapAdapter().evaluate, order=30),
    ]


def dispatch_posttool_event(context: EventContext | dict[str, Any]) -> DecisionEnvelope:
    """Convenience helper to dispatch a PostToolUse event through all canonical branches."""
    if not isinstance(context, EventContext):
        context = EventContext.from_payload(context, default_event=PostToolUse)

    branches = create_posttool_branches()
    accumulated_updated_input: dict[str, Any] | None = None
    accumulated_metadata: dict[str, Any] = {}
    last_env: DecisionEnvelope | None = None

    for branch in branches:
        res = branch.handler(context)
        if res is None:
            continue
        if not isinstance(res, DecisionEnvelope):
            return DecisionEnvelope.fail_closed(
                f"Branch {branch.name} returned invalid type: {type(res).__name__}",
                diagnostic_code=DiagnosticCode.SCHEMA_ERROR,
            )
        if res.is_deny or res.decision in {"deny", "retry"}:
            return res

        last_env = res
        if res.metadata:
            accumulated_metadata.update(res.metadata)
        if res.updated_input:
            merged, err = merge_updated_inputs(accumulated_updated_input, res.updated_input)
            if err:
                return DecisionEnvelope.deny(
                    f"Conflicting updated input: {err}",
                    diagnostic_code=DiagnosticCode.CONFLICT_INPUT,
                )
            accumulated_updated_input = merged

    if last_env is not None:
        return DecisionEnvelope(
            decision=last_env.decision,
            reason=last_env.reason,
            updated_input=accumulated_updated_input,
            diagnostic_code=last_env.diagnostic_code,
            diagnostic_details=last_env.diagnostic_details,
            metadata=accumulated_metadata or last_env.metadata,
        )

    return DecisionEnvelope.allow(updated_input=accumulated_updated_input)
