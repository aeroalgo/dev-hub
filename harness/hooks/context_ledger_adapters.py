"""Provider-neutral normalizer and adapters for context ledger enforcement.

Normalizes Claude PreToolUse/PostToolUse and Codex event bridge payloads
for Read/read, Edit/Write, NotebookEdit, rename/delete, and missing-range events
into a shared ContextLedger request and DecisionReceipt.
Guarantees provider parity, actor lineage, deterministic derived_identity,
session-wide invalidation across root and subagents, and fail-closed handling.

Part of T-HUB-078 (FR-002, FR-007, FR-008, FR-009, FR-010).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sys
from typing import Any, Literal

_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from context_ledger import (
    ActorKey,
    ContextLedger,
    DecisionReceipt,
    ReadRequest,
    canonicalize_path,
    compute_content_hash,
    count_file_lines,
)

logger = logging.getLogger(__name__)

READ_TOOL_ALIASES: frozenset[str] = frozenset(
    {
        "Read",
        "read",
        "ReadFile",
        "read_file",
        "View",
        "view",
        "file_read",
        "open_file",
        "NotebookRead",
        "notebook_read",
        "cat",
    }
)

WRITE_TOOL_ALIASES: frozenset[str] = frozenset(
    {
        "Write",
        "write",
        "Edit",
        "edit",
        "NotebookEdit",
        "notebook_edit",
        "MultiEdit",
        "multi_edit",
        "apply_patch",
        "patch",
        "create_file",
        "delete_file",
        "rename_file",
        "mv",
        "rm",
    }
)

PATH_KEYS: tuple[str, ...] = (
    "file_path",
    "path",
    "notebook_path",
    "file",
    "filename",
    "target_path",
    "target",
    "uri",
    "path_to_file",
    "source_path",
)


@dataclass
class NormalizedReadPayload:
    """Normalized provider-neutral representation of a read tool request."""

    raw_path: str | Path
    project_root: str | Path
    root_session_id: str
    agent_invocation_id: str
    runtime_provider: str = "claude"
    actor_kind: str = "root"  # "root" | "subagent"
    parent_invocation_id: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    line_interval: tuple[int | None, int | None] | list[int | None] | None = None
    content_hash: str | None = None
    mode: str = "IMPLEMENT"
    purpose: str | None = None
    exception_reason: str | None = None
    derived_identity: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_read_request(self) -> ReadRequest:
        return ReadRequest(
            raw_path=self.raw_path,
            project_root=self.project_root,
            root_session_id=self.root_session_id,
            agent_invocation_id=self.agent_invocation_id,
            runtime_provider=self.runtime_provider,
            actor_kind=self.actor_kind,
            parent_invocation_id=self.parent_invocation_id,
            line_interval=self.line_interval,
            start_line=self.start_line,
            end_line=self.end_line,
            content_hash=self.content_hash,
            mode=self.mode,
            purpose=self.purpose,
            exception_reason=self.exception_reason,
        )


@dataclass
class NormalizedWritePayload:
    """Normalized provider-neutral representation of an edit or write event."""

    raw_path: str | Path
    project_root: str | Path
    root_session_id: str
    agent_invocation_id: str
    runtime_provider: str = "claude"
    actor_kind: str = "root"
    parent_invocation_id: str | None = None
    operation: str = "write"  # "write" | "edit" | "notebook_edit" | "rename" | "delete"
    new_content: str | None = None
    new_content_hash: str | None = None
    old_path: str | Path | None = None
    derived_identity: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


def _detect_runtime_provider(data: dict[str, Any], explicit: str | None = None) -> str:
    if explicit:
        return explicit.lower()
    provider = data.get("provider") or data.get("runtime_provider") or data.get("runtime")
    if isinstance(provider, str) and provider.strip():
        return provider.strip().lower()
    if "hookSpecificOutput" in data or "tool_use_id" in data:
        return "claude"
    if "executor_session_id" in data or "arguments" in data or "args" in data:
        return "codex"
    if "tool" in data and "tool_name" not in data:
        return "codex"
    return "claude"


def _extract_path_from_input(tool_input: dict[str, Any]) -> str | None:
    for key in PATH_KEYS:
        val = tool_input.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def generate_derived_identity(
    root_session_id: str,
    runtime_provider: str,
    actor_kind: str,
    path_hint: str = "",
    tool_hint: str = "",
) -> str:
    """Generate deterministic derived_identity when provider invocation id is absent."""
    seed = f"{root_session_id}:{runtime_provider}:{actor_kind}:{path_hint}:{tool_hint}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return f"derived_identity_{digest}"


def normalize_read_payload(
    data: dict[str, Any],
    provider: str | None = None,
    default_cwd: str | Path | None = None,
) -> NormalizedReadPayload:
    """Normalize Claude or Codex read payload into a canonical NormalizedReadPayload.

    Fails closed (raises ValueError) if path is missing or bounds are invalid,
    preventing unconstrained reads without ledger accounting.
    """
    runtime_provider = _detect_runtime_provider(data, provider)
    cwd = str(data.get("cwd") or default_cwd or Path.cwd())

    # Extract tool input mapping
    tool_input: dict[str, Any] = {}
    if isinstance(data.get("tool_input"), dict):
        tool_input = data["tool_input"]
    elif isinstance(data.get("arguments"), dict):
        tool_input = data["arguments"]
    elif isinstance(data.get("args"), dict):
        tool_input = data["args"]
    elif isinstance(data.get("input"), dict):
        tool_input = data["input"]
    else:
        # Check top-level keys
        for key in PATH_KEYS:
            if key in data and isinstance(data[key], str):
                tool_input = data
                break

    raw_path = _extract_path_from_input(tool_input)
    if not raw_path:
        raise ValueError("Missing file path in read payload; fail-closed enforcement active")

    # Session lineage
    session_id = str(data.get("session_id") or data.get("root_session_id") or "default-session")
    raw_inv_id = (
        data.get("agent_invocation_id")
        or data.get("invocation_id")
        or data.get("tool_use_id")
        or tool_input.get("invocation_id")
        or tool_input.get("tool_use_id")
    )

    actor_kind = str(data.get("actor_kind") or "root")
    subagent_type = data.get("subagent_type") or tool_input.get("subagent_type") or data.get("agent_type")
    parent_invocation_id = data.get("parent_invocation_id") or tool_input.get("parent_invocation_id")
    if subagent_type or parent_invocation_id:
        actor_kind = "subagent"

    derived = False
    if not raw_inv_id:
        tool_name = str(data.get("tool_name") or data.get("tool") or data.get("name") or "Read")
        agent_invocation_id = generate_derived_identity(
            root_session_id=session_id,
            runtime_provider=runtime_provider,
            actor_kind=actor_kind,
            path_hint=raw_path,
            tool_hint=tool_name,
        )
        derived = True
    else:
        agent_invocation_id = str(raw_inv_id)

    # Line intervals & range normalization
    start_line: int | None = None
    end_line: int | None = None
    line_interval: tuple[int | None, int | None] | list[int | None] | None = None

    if "offset" in tool_input and "limit" in tool_input:
        # Claude Read format: offset (1-based line), limit (number of lines)
        try:
            offset_val = int(tool_input["offset"])
            limit_val = int(tool_input["limit"])
            if offset_val >= 1 and limit_val >= 1:
                start_line = offset_val
                end_line = offset_val + limit_val - 1
                line_interval = (start_line, end_line)
        except (ValueError, TypeError):
            pass
    elif "start_line" in tool_input or "end_line" in tool_input:
        try:
            s = int(tool_input["start_line"]) if tool_input.get("start_line") is not None else 1
            e = int(tool_input["end_line"]) if tool_input.get("end_line") is not None else None
            start_line = s
            end_line = e
            line_interval = (start_line, end_line)
        except (ValueError, TypeError):
            pass
    elif "startLine" in tool_input or "endLine" in tool_input:
        try:
            s = int(tool_input["startLine"]) if tool_input.get("startLine") is not None else 1
            e = int(tool_input["endLine"]) if tool_input.get("endLine") is not None else None
            start_line = s
            end_line = e
            line_interval = (start_line, end_line)
        except (ValueError, TypeError):
            pass
    elif "line_interval" in tool_input and isinstance(tool_input["line_interval"], (list, tuple)):
        raw_iv = tool_input["line_interval"]
        if len(raw_iv) >= 2:
            try:
                s = int(raw_iv[0]) if raw_iv[0] is not None else 1
                e = int(raw_iv[1]) if raw_iv[1] is not None else None
                start_line = s
                end_line = e
                line_interval = (start_line, end_line)
            except (ValueError, TypeError):
                pass

    mode = str(data.get("mode") or "IMPLEMENT")
    purpose = data.get("purpose")
    if purpose is not None:
        purpose = str(purpose)
    exception_reason = data.get("exception_reason") or tool_input.get("exception_reason")
    if exception_reason is not None:
        exception_reason = str(exception_reason)

    metadata = dict(data.get("metadata") or {})
    if derived:
        metadata["derived_identity"] = True
        metadata["identity_source"] = "derived_identity"

    return NormalizedReadPayload(
        raw_path=raw_path,
        project_root=cwd,
        root_session_id=session_id,
        agent_invocation_id=agent_invocation_id,
        runtime_provider=runtime_provider,
        actor_kind=actor_kind,
        parent_invocation_id=str(parent_invocation_id) if parent_invocation_id else None,
        start_line=start_line,
        end_line=end_line,
        line_interval=line_interval,
        content_hash=data.get("content_hash"),
        mode=mode,
        purpose=purpose,
        exception_reason=exception_reason,
        derived_identity=derived,
        metadata=metadata,
    )


def normalize_write_payload(
    data: dict[str, Any],
    provider: str | None = None,
    default_cwd: str | Path | None = None,
) -> NormalizedWritePayload:
    """Normalize Claude or Codex edit/write payload into NormalizedWritePayload.

    Fails closed if target path is missing.
    """
    runtime_provider = _detect_runtime_provider(data, provider)
    cwd = str(data.get("cwd") or default_cwd or Path.cwd())

    tool_input: dict[str, Any] = {}
    if isinstance(data.get("tool_input"), dict):
        tool_input = data["tool_input"]
    elif isinstance(data.get("arguments"), dict):
        tool_input = data["arguments"]
    elif isinstance(data.get("args"), dict):
        tool_input = data["args"]
    elif isinstance(data.get("input"), dict):
        tool_input = data["input"]
    else:
        for key in PATH_KEYS:
            if key in data and isinstance(data[key], str):
                tool_input = data
                break

    raw_path = _extract_path_from_input(tool_input)
    if not raw_path:
        raise ValueError("Missing file path in write/edit payload; fail-closed enforcement active")

    session_id = str(data.get("session_id") or data.get("root_session_id") or "default-session")
    raw_inv_id = (
        data.get("agent_invocation_id")
        or data.get("invocation_id")
        or data.get("tool_use_id")
        or tool_input.get("invocation_id")
    )

    actor_kind = str(data.get("actor_kind") or "root")
    subagent_type = data.get("subagent_type") or tool_input.get("subagent_type") or data.get("agent_type")
    parent_invocation_id = data.get("parent_invocation_id") or tool_input.get("parent_invocation_id")
    if subagent_type or parent_invocation_id:
        actor_kind = "subagent"

    tool_name = str(data.get("tool_name") or data.get("tool") or data.get("name") or "Write")
    derived = False
    if not raw_inv_id:
        agent_invocation_id = generate_derived_identity(
            root_session_id=session_id,
            runtime_provider=runtime_provider,
            actor_kind=actor_kind,
            path_hint=raw_path,
            tool_hint=tool_name,
        )
        derived = True
    else:
        agent_invocation_id = str(raw_inv_id)

    # Content or patch
    new_content = (
        tool_input.get("contents")
        or tool_input.get("content")
        or tool_input.get("new_string")
        or tool_input.get("patch")
        or tool_input.get("code")
    )
    if new_content is not None:
        new_content = str(new_content)

    new_hash: str | None = None
    if new_content is not None:
        new_hash = hashlib.sha256(new_content.encode("utf-8")).hexdigest()

    old_path = tool_input.get("old_path") or tool_input.get("source_path")
    operation = "write"
    if tool_name.lower() in ("edit", "notebookedit", "apply_patch", "patch"):
        operation = "edit"
    elif tool_name.lower() in ("rename_file", "mv"):
        operation = "rename"
    elif tool_name.lower() in ("delete_file", "rm"):
        operation = "delete"

    metadata = dict(data.get("metadata") or {})
    if derived:
        metadata["derived_identity"] = True
        metadata["identity_source"] = "derived_identity"

    return NormalizedWritePayload(
        raw_path=raw_path,
        project_root=cwd,
        root_session_id=session_id,
        agent_invocation_id=agent_invocation_id,
        runtime_provider=runtime_provider,
        actor_kind=actor_kind,
        parent_invocation_id=str(parent_invocation_id) if parent_invocation_id else None,
        operation=operation,
        new_content=new_content,
        new_content_hash=new_hash,
        old_path=str(old_path) if old_path else None,
        derived_identity=derived,
        metadata=metadata,
    )


def invalidate_session_actors(
    project_root: str | Path,
    root_session_id: str,
    path: str | Path,
    new_content_hash: str | None = None,
    runtime_dir: Path | None = None,
) -> list[str]:
    """Invalidate cached ranges for target file across ALL actors in the session.

    Ensures that when a root-agent or subagent writes a file, every actor's
    ledger in that session is invalidated and transitions to the new content version.
    """
    proj_path = Path(project_root).expanduser().resolve()
    if runtime_dir is None:
        from epic_paths import epic_dir as runtime_epic_dir
        base_dir = runtime_epic_dir(proj_path).parent
    else:
        base_dir = runtime_dir
    safe_proj = re.sub(r"[^a-zA-Z0-9._-]+", "_", proj_path.name or "proj")[:64]
    safe_sess = re.sub(r"[^a-zA-Z0-9._-]+", "_", root_session_id or "sess")[:64]
    sess_dir = base_dir / "context-ledger" / safe_proj / safe_sess

    invalidated_actors: list[str] = []
    canonical = canonicalize_path(path, proj_path)
    active_hash = new_content_hash or compute_content_hash(canonical)

    if sess_dir.is_dir():
        for ledger_file in sess_dir.glob("*.json"):
            if ledger_file.name.endswith(".lock.json") or ledger_file.name.endswith(".tmp.json"):
                continue
            actor_id = ledger_file.stem
            try:
                ledger = ContextLedger(
                    project_root=proj_path,
                    root_session_id=root_session_id,
                    agent_invocation_id=actor_id,
                    runtime_dir=runtime_dir,
                )
                ledger.record_edit(canonical, new_content_hash=active_hash)
                invalidated_actors.append(actor_id)
            except Exception as exc:
                logger.warning("Failed to invalidate actor ledger %s: %s", ledger_file, exc)

    return invalidated_actors


def format_claude_response(receipt: DecisionReceipt) -> dict[str, Any]:
    """Map DecisionReceipt to Claude PreToolUse hook output format."""
    if receipt.decision in ("duplicate", "denied"):
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": receipt.reason_code,
                "additionalContext": (
                    f"context-ledger DENY [{receipt.reason_code}]: {receipt.diagnostic}"
                ),
            }
        }
    elif receipt.decision == "partial":
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "additionalContext": (
                    f"context-ledger PARTIAL [{receipt.reason_code}]: "
                    f"allowed_intervals={receipt.allowed_intervals}, "
                    f"cached_intervals={receipt.cached_intervals}"
                ),
            }
        }
    else:
        # allowed, invalidated, exception
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "additionalContext": f"context-ledger [{receipt.reason_code}]: {receipt.diagnostic}",
            }
        }


def format_codex_response(receipt: DecisionReceipt) -> dict[str, Any]:
    """Map DecisionReceipt to Codex bridge output format."""
    is_allowed = receipt.decision in ("allowed", "partial", "invalidated", "exception")
    return {
        "decision": receipt.decision,
        "reason_code": receipt.reason_code,
        "allow": is_allowed,
        "receipt": receipt.to_dict(),
        "diagnostic": receipt.diagnostic,
        "exit_code": 0 if is_allowed else 1,
    }


def evaluate_read_payload(
    data: dict[str, Any],
    provider: str | None = None,
    cwd: str | Path | None = None,
    runtime_dir: Path | None = None,
) -> tuple[DecisionReceipt, dict[str, Any]]:
    """Evaluate a read tool invocation against ContextLedger, returning (receipt, formatted_response).

    Enforces fail-closed behavior on provider divergence or malformed payloads.
    """
    runtime_provider = _detect_runtime_provider(data, provider)
    try:
        norm = normalize_read_payload(data, provider=runtime_provider, default_cwd=cwd)
    except Exception as exc:
        # Fail-closed without provider-local fallback
        raw_p = str(data.get("file_path") or data.get("path") or "")
        actor_k = {
            "project_root": str(cwd or Path.cwd()),
            "root_session_id": str(data.get("session_id") or "unknown"),
            "agent_invocation_id": "fail-closed",
            "runtime_provider": runtime_provider,
            "actor_kind": "root",
            "parent_invocation_id": None,
        }
        receipt = DecisionReceipt(
            decision="denied",
            reason_code="payload_divergence_denied",
            diagnostic=f"Fail-closed on payload divergence or malformed request: {exc}",
            canonical_path=raw_p,
            content_hash=None,
            requested_intervals=[],
            allowed_intervals=[],
            cached_intervals=[],
            actor_key=actor_k,
            sequence=0,
            cached=False,
            metadata={"fail_closed": True, "error": str(exc)},
        )
        resp = format_claude_response(receipt) if runtime_provider == "claude" else format_codex_response(receipt)
        return receipt, resp

    # Enforce whole-plan monolith guard in lean execution modes
    from loop.mb_load.plan_section import evaluate_plan_read, is_whole_plan_path

    if is_whole_plan_path(norm.raw_path):
        allowed, plan_reason, details = evaluate_plan_read(
            path=norm.raw_path,
            start_line=norm.start_line,
            end_line=norm.end_line,
            mode=norm.mode,
            exception_reason=norm.exception_reason,
            project_root=norm.project_root,
        )
        if not allowed:
            ledger = ContextLedger(
                project_root=norm.project_root,
                root_session_id=norm.root_session_id,
                agent_invocation_id=norm.agent_invocation_id,
                runtime_provider=norm.runtime_provider,
                actor_kind=norm.actor_kind,
                parent_invocation_id=norm.parent_invocation_id,
                runtime_dir=runtime_dir,
            )
            ledger.record_monolith_attempt()
            actor_k = {
                "project_root": str(norm.project_root),
                "root_session_id": norm.root_session_id,
                "agent_invocation_id": norm.agent_invocation_id,
                "runtime_provider": norm.runtime_provider,
                "actor_kind": norm.actor_kind,
                "parent_invocation_id": norm.parent_invocation_id,
            }
            receipt = DecisionReceipt(
                decision="denied",
                reason_code=plan_reason,
                diagnostic=details.get("diagnostic", "Whole plan read denied in lean execution mode"),
                canonical_path=str(norm.raw_path),
                content_hash=None,
                requested_intervals=[[norm.start_line or 1, norm.end_line or 1]],
                allowed_intervals=[],
                cached_intervals=[],
                actor_key=actor_k,
                sequence=0,
                cached=False,
                metadata={"plan_guard": True, "details": details},
            )
            resp = format_claude_response(receipt) if runtime_provider == "claude" else format_codex_response(receipt)
            return receipt, resp

    ledger = ContextLedger(
        project_root=norm.project_root,
        root_session_id=norm.root_session_id,
        agent_invocation_id=norm.agent_invocation_id,
        runtime_provider=norm.runtime_provider,
        actor_kind=norm.actor_kind,
        parent_invocation_id=norm.parent_invocation_id,
        runtime_dir=runtime_dir,
    )
    req = norm.to_read_request()
    receipt = ledger.decide(req)

    # Attach derived identity metadata to receipt if applicable
    if norm.derived_identity:
        receipt.metadata["derived_identity"] = True
        receipt.metadata["identity_source"] = "derived_identity"

    resp = format_claude_response(receipt) if runtime_provider == "claude" else format_codex_response(receipt)
    return receipt, resp


def evaluate_write_payload(
    data: dict[str, Any],
    provider: str | None = None,
    cwd: str | Path | None = None,
    runtime_dir: Path | None = None,
) -> tuple[bool, str, dict[str, Any]]:
    """Evaluate a write/edit event, invalidating file ranges for all session actors."""
    runtime_provider = _detect_runtime_provider(data, provider)
    try:
        norm = normalize_write_payload(data, provider=runtime_provider, default_cwd=cwd)
    except Exception as exc:
        err_msg = f"Fail-closed write evaluation: {exc}"
        resp = (
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "payload_divergence_denied",
                    "additionalContext": err_msg,
                }
            }
            if runtime_provider == "claude"
            else {
                "decision": "denied",
                "reason_code": "payload_divergence_denied",
                "allow": False,
                "diagnostic": err_msg,
                "exit_code": 1,
            }
        )
        return False, "payload_divergence_denied", resp

    # Invalidate target file across all session actors
    invalidated = invalidate_session_actors(
        project_root=norm.project_root,
        root_session_id=norm.root_session_id,
        path=norm.raw_path,
        new_content_hash=norm.new_content_hash,
        runtime_dir=runtime_dir,
    )

    # If old path exists (rename), invalidate it too
    if norm.old_path:
        invalidate_session_actors(
            project_root=norm.project_root,
            root_session_id=norm.root_session_id,
            path=norm.old_path,
            runtime_dir=runtime_dir,
        )

    # Also ensure current actor ledger records the edit
    current_ledger = ContextLedger(
        project_root=norm.project_root,
        root_session_id=norm.root_session_id,
        agent_invocation_id=norm.agent_invocation_id,
        runtime_provider=norm.runtime_provider,
        actor_kind=norm.actor_kind,
        parent_invocation_id=norm.parent_invocation_id,
        runtime_dir=runtime_dir,
    )
    current_ledger.record_edit(norm.raw_path, new_content_hash=norm.new_content_hash)

    resp = (
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "additionalContext": f"context-ledger write invalidated actors: {invalidated}",
            }
        }
        if runtime_provider == "claude"
        else {
            "decision": "allowed",
            "reason_code": "write_invalidated",
            "allow": True,
            "invalidated_actors": invalidated,
            "exit_code": 0,
        }
    )
    return True, "write_invalidated", resp


def main() -> None:
    """CLI hook entrypoint reading JSON from stdin and emitting response."""
    try:
        raw_text = sys.stdin.read().strip()
        data = json.loads(raw_text) if raw_text else {}
    except Exception as exc:
        print(f"Error reading JSON from stdin: {exc}", file=sys.stderr)
        sys.exit(1)

    tool_name = str(data.get("tool_name") or data.get("tool") or data.get("name") or "")
    if tool_name in READ_TOOL_ALIASES:
        _receipt, resp = evaluate_read_payload(data)
        print(json.dumps(resp))
    elif tool_name in WRITE_TOOL_ALIASES:
        _ok, _reason, resp = evaluate_write_payload(data)
        print(json.dumps(resp))
    elif not tool_name:
        # Unknown/missing tool payload -> fail-closed
        print(
            json.dumps(
                {
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "unknown_tool_payload: missing or unrecognized tool name",
                    "additionalContext": "context-ledger-adapter DENY: unknown tool payload fail-closed.",
                }
            )
        )
    else:
        # Explicit non-read/write tool passthrough with typed reason code
        print(
            json.dumps(
                {
                    "permissionDecision": "allow",
                    "permissionDecisionReason": f"non_file_tool_passthrough:{tool_name}",
                }
            )
        )


if __name__ == "__main__":
    main()
