#!/usr/bin/env python3
"""Event-specific dispatch layer for harness lifecycle hooks.

Provides normalized EventContext, ordered DispatchBranch execution,
deterministic DecisionEnvelope responses, input merging, and fail-closed
diagnostics for all hook events.
"""
from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

try:
    from ._lib import normalize_tool_name, product_cwd
except ImportError:
    try:
        from _lib import normalize_tool_name, product_cwd
    except ImportError:
        def normalize_tool_name(raw: str | None) -> str:
            return str(raw).strip() if raw else ""

        def product_cwd(cwd: str | Path | None) -> Path:
            return Path(cwd).resolve() if cwd else Path.cwd().resolve()

# Canonical lifecycle event constants (matching nouns)
PreToolUse = "PreToolUse"
PostToolUse = "PostToolUse"
SubagentStart = "SubagentStart"
SubagentStop = "SubagentStop"
Stop = "Stop"
SessionStart = "SessionStart"
UserPromptSubmit = "UserPromptSubmit"

LIFECYCLE_EVENTS = frozenset({
    PreToolUse,
    PostToolUse,
    SubagentStart,
    SubagentStop,
    Stop,
    SessionStart,
    UserPromptSubmit,
})


class DiagnosticCode(str, enum.Enum):
    ALLOW = "allow"
    DENY = "deny"
    RETRY = "retry"
    RECORDED = "recorded"
    OUTPUT_CAPPED = "output_capped"
    STALE = "stale"
    STALE_IDENTITY = "stale_identity"
    CONFLICT_INPUT = "conflict_input"
    UNKNOWN_EVENT = "unknown_event"
    UNKNOWN_TOOL = "unknown_tool"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"
    EXCEPTION = "exception"
    PROJECT_BOUNDARY_DENY = "project_boundary_deny"
    FINISH_BOUNDARY_DENY = "finish_boundary_deny"
    TOOL_POLICY_DENY = "tool_policy_deny"
    SCHEMA_ERROR = "schema_error"

    def __str__(self) -> str:
        return self.value


@dataclass
class EventContext:
    event_name: str
    tool_name: str = ""
    tool_input: dict[str, Any] = field(default_factory=dict)
    tool_output: Any = None
    cwd: Path = field(default_factory=Path.cwd)
    session_id: str = ""
    runtime_id: str = ""
    raw_payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, Any] | None,
        *,
        default_event: str | None = None,
        cwd: str | Path | None = None,
    ) -> EventContext:
        payload = payload or {}
        raw_event = (
            payload.get("event_name")
            or payload.get("hookEventName")
            or payload.get("hook_event_name")
            or payload.get("event")
            or default_event
            or ""
        )
        raw_tool = payload.get("tool_name") or payload.get("toolName") or payload.get("tool") or ""
        tool_name = normalize_tool_name(str(raw_tool)) if raw_tool else ""

        tool_input = payload.get("tool_input")
        if not isinstance(tool_input, dict):
            tool_input = payload.get("toolInput")
        if not isinstance(tool_input, dict):
            tool_input = {}
        tool_input = dict(tool_input)

        tool_output = payload.get("tool_output")
        if tool_output is None:
            tool_output = payload.get("toolOutput")
        if tool_output is None:
            tool_output = payload.get("result")

        raw_cwd = cwd or payload.get("cwd") or payload.get("project_root")
        resolved_cwd = product_cwd(raw_cwd) if raw_cwd else Path.cwd().resolve()

        session_id = str(payload.get("session_id") or payload.get("sessionId") or "")
        runtime_id = str(payload.get("runtime_id") or payload.get("runtimeId") or "")

        return cls(
            event_name=str(raw_event),
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
            cwd=resolved_cwd,
            session_id=session_id,
            runtime_id=runtime_id,
            raw_payload=payload,
        )


@dataclass
class DecisionEnvelope:
    decision: str = "allow"
    reason: str | None = None
    updated_input: dict[str, Any] | None = None
    diagnostic_code: DiagnosticCode | str | None = None
    diagnostic_details: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def allow(
        cls,
        *,
        updated_input: dict[str, Any] | None = None,
        reason: str | None = None,
        diagnostic_code: DiagnosticCode | str | None = None,
        diagnostic_details: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionEnvelope:
        return cls(
            decision="allow",
            reason=reason,
            updated_input=updated_input,
            diagnostic_code=diagnostic_code or DiagnosticCode.ALLOW,
            diagnostic_details=diagnostic_details or {},
            metadata=metadata or {},
        )

    @classmethod
    def deny(
        cls,
        reason: str,
        *,
        diagnostic_code: DiagnosticCode | str = DiagnosticCode.DENY,
        diagnostic_details: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionEnvelope:
        return cls(
            decision="deny",
            reason=reason,
            updated_input=None,
            diagnostic_code=diagnostic_code,
            diagnostic_details=diagnostic_details or {},
            metadata=metadata or {},
        )

    @classmethod
    def retry(
        cls,
        reason: str,
        *,
        diagnostic_code: DiagnosticCode | str = DiagnosticCode.RETRY,
        diagnostic_details: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionEnvelope:
        return cls(
            decision="retry",
            reason=reason,
            updated_input=None,
            diagnostic_code=diagnostic_code,
            diagnostic_details=diagnostic_details or {},
            metadata=metadata or {},
        )

    @classmethod
    def record(
        cls,
        *,
        reason: str | None = None,
        diagnostic_code: DiagnosticCode | str = DiagnosticCode.RECORDED,
        diagnostic_details: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionEnvelope:
        return cls(
            decision="record",
            reason=reason,
            diagnostic_code=diagnostic_code,
            diagnostic_details=diagnostic_details or {},
            metadata=metadata or {},
        )

    @classmethod
    def fail_closed(
        cls,
        reason: str,
        *,
        diagnostic_code: DiagnosticCode | str = DiagnosticCode.INFRASTRUCTURE_FAILURE,
        exc: BaseException | None = None,
        diagnostic_details: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionEnvelope:
        details = dict(diagnostic_details or {})
        if exc is not None:
            details["exception_type"] = type(exc).__name__
            details["exception_message"] = str(exc)
        return cls(
            decision="deny",
            reason=reason,
            updated_input=None,
            diagnostic_code=diagnostic_code,
            diagnostic_details=details,
            metadata=metadata or {},
        )

    @property
    def is_allow(self) -> bool:
        return self.decision == "allow"

    @property
    def is_deny(self) -> bool:
        return self.decision == "deny"

    def to_hook_output(self, event_name: str | None = None) -> dict[str, Any]:
        event = event_name or PreToolUse
        if event == PreToolUse:
            output: dict[str, Any] = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny" if self.is_deny else "allow",
                }
            }
            if self.reason:
                output["hookSpecificOutput"]["permissionReason"] = self.reason
                output["hookSpecificOutput"]["permissionDecisionReason"] = self.reason
            if self.is_allow and self.updated_input is not None:
                output["hookSpecificOutput"]["updatedInput"] = self.updated_input
            if self.metadata and ("additional_context" in self.metadata or "additionalContext" in self.metadata):
                output["hookSpecificOutput"]["additionalContext"] = (
                    self.metadata.get("additional_context") or self.metadata.get("additionalContext")
                )
            if self.diagnostic_code:
                output["hookSpecificOutput"]["diagnosticCode"] = str(self.diagnostic_code)
            if self.diagnostic_details:
                output["hookSpecificOutput"]["diagnosticDetails"] = self.diagnostic_details
            return output
        elif event == PostToolUse:
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                }
            }
            if self.reason:
                output["hookSpecificOutput"]["reason"] = self.reason
            if self.updated_input is not None:
                output["hookSpecificOutput"]["updatedInput"] = self.updated_input
            if self.diagnostic_code:
                output["hookSpecificOutput"]["diagnosticCode"] = str(self.diagnostic_code)
            if self.diagnostic_details:
                output["hookSpecificOutput"]["diagnosticDetails"] = self.diagnostic_details
            return output
        else:
            output = {
                "event": event,
                "decision": self.decision,
            }
            if self.reason:
                output["reason"] = self.reason
            if self.diagnostic_code:
                output["diagnostic_code"] = str(self.diagnostic_code)
            if self.diagnostic_details:
                output["diagnostic_details"] = self.diagnostic_details
            return output


@dataclass
class DispatchBranch:
    name: str
    handler: Callable[[EventContext], DecisionEnvelope | None]
    description: str = ""
    order: int = 100


def _deep_merge_dict(
    base: dict[str, Any],
    update: dict[str, Any],
    path: str = "",
) -> tuple[dict[str, Any] | None, str | None]:
    result = dict(base)
    for k, v in update.items():
        current_path = f"{path}.{k}" if path else str(k)
        if k in result:
            if isinstance(result[k], dict) and isinstance(v, dict):
                merged_sub, err = _deep_merge_dict(result[k], v, current_path)
                if err:
                    return None, err
                result[k] = merged_sub
            elif result[k] != v:
                return None, f"conflicting values at {current_path}: {result[k]!r} vs {v!r}"
        else:
            result[k] = v
    return result, None


def merge_updated_inputs(
    base: dict[str, Any] | None,
    update: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, str | None]:
    if base is None and update is None:
        return None, None
    if base is None:
        return (dict(update), None) if isinstance(update, dict) else (None, None)
    if update is None:
        return (dict(base), None) if isinstance(base, dict) else (None, None)
    return _deep_merge_dict(base, update)


def run_pipeline(
    context: EventContext,
    branches: list[DispatchBranch],
    *,
    validate_event: bool = True,
    allowed_tools: set[str] | frozenset[str] | None = None,
) -> DecisionEnvelope:
    if validate_event:
        if not context.event_name or context.event_name not in LIFECYCLE_EVENTS:
            return DecisionEnvelope.fail_closed(
                f"Unknown or unsupported lifecycle event: {context.event_name}",
                diagnostic_code=DiagnosticCode.UNKNOWN_EVENT,
                diagnostic_details={"event_name": context.event_name},
            )

    if allowed_tools is not None:
        if not context.tool_name or context.tool_name not in allowed_tools:
            return DecisionEnvelope.fail_closed(
                f"Tool {context.tool_name} not allowed for event {context.event_name}",
                diagnostic_code=DiagnosticCode.UNKNOWN_TOOL,
                diagnostic_details={"tool_name": context.tool_name, "event_name": context.event_name},
            )

    accumulated_updated_input: dict[str, Any] | None = None

    for branch in branches:
        try:
            branch_result = branch.handler(context)
        except Exception as exc:
            return DecisionEnvelope.fail_closed(
                f"Unexpected exception during dispatch in branch {branch.name}: {exc}",
                diagnostic_code=DiagnosticCode.EXCEPTION,
                exc=exc,
                diagnostic_details={"branch": branch.name},
            )

        if branch_result is None:
            continue

        if not isinstance(branch_result, DecisionEnvelope):
            return DecisionEnvelope.fail_closed(
                f"Branch {branch.name} returned invalid response type: {type(branch_result).__name__}",
                diagnostic_code=DiagnosticCode.SCHEMA_ERROR,
                diagnostic_details={"branch": branch.name},
            )

        if branch_result.is_deny or branch_result.decision in {"deny", "retry"}:
            return branch_result

        if branch_result.updated_input:
            merged, err = merge_updated_inputs(accumulated_updated_input, branch_result.updated_input)
            if err:
                return DecisionEnvelope.deny(
                    f"Conflicting updatedInput proposals between policies: {err}",
                    diagnostic_code=DiagnosticCode.CONFLICT_INPUT,
                    diagnostic_details={"branch": branch.name, "conflict": err},
                )
            accumulated_updated_input = merged
            context.tool_input = dict(accumulated_updated_input)

    return DecisionEnvelope.allow(updated_input=accumulated_updated_input)


def dispatch_event(
    context: EventContext | dict[str, Any],
    branches: list[DispatchBranch],
    *,
    default_event: str | None = None,
    allowed_tools: set[str] | frozenset[str] | None = None,
) -> DecisionEnvelope:
    try:
        if not isinstance(context, EventContext):
            context = EventContext.from_payload(context, default_event=default_event)
        return run_pipeline(context, branches, allowed_tools=allowed_tools)
    except Exception as exc:
        return DecisionEnvelope.fail_closed(
            f"Unhandled dispatch error: {exc}",
            diagnostic_code=DiagnosticCode.EXCEPTION,
            exc=exc,
        )


def dispatch_pretool(
    context: EventContext | dict[str, Any],
    branches: list[DispatchBranch],
    *,
    allowed_tools: set[str] | frozenset[str] | None = None,
) -> DecisionEnvelope:
    return dispatch_event(context, branches, default_event=PreToolUse, allowed_tools=allowed_tools)


def dispatch_posttool(
    context: EventContext | dict[str, Any],
    branches: list[DispatchBranch],
    *,
    allowed_tools: set[str] | frozenset[str] | None = None,
) -> DecisionEnvelope:
    return dispatch_event(context, branches, default_event=PostToolUse, allowed_tools=allowed_tools)


def dispatch_subagent_start(
    context: EventContext | dict[str, Any],
    branches: list[DispatchBranch],
) -> DecisionEnvelope:
    return dispatch_event(context, branches, default_event=SubagentStart)


def dispatch_subagent_stop(
    context: EventContext | dict[str, Any],
    branches: list[DispatchBranch],
) -> DecisionEnvelope:
    return dispatch_event(context, branches, default_event=SubagentStop)


def dispatch_stop(
    context: EventContext | dict[str, Any],
    branches: list[DispatchBranch],
) -> DecisionEnvelope:
    return dispatch_event(context, branches, default_event=Stop)
