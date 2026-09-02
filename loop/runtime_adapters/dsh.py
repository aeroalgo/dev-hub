from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from loop.runtime_adapters.base import RuntimeAdapter, SessionAnalysis, SessionContext


_REQUESTED_MODEL_RE = re.compile(
    r"\brequested[ _-]model\s*[:=]\s*[\"']?([^\s,;|\"']+)",
    re.IGNORECASE,
)
_ACTUAL_MODEL_RE = re.compile(
    r"\bactual[ _-]model\s*[:=]\s*[\"']?([^\s,;|\"']+)",
    re.IGNORECASE,
)
_MODEL_KEYS = ("requested_model", "actual_model")


def _normalize_model_id(value: str | None) -> str:
    model = (value or "").strip().lower()
    if not model:
        return ""
    model = re.sub(r"\[\d+m\]$", "", model)
    if "/" in model:
        model = model.rsplit("/", 1)[-1]
    return model


def _models_equivalent(left: str | None, right: str | None) -> bool:
    normalized_left = _normalize_model_id(left)
    normalized_right = _normalize_model_id(right)
    if not normalized_left or not normalized_right:
        return True
    return (
        normalized_left == normalized_right
        or normalized_left in normalized_right
        or normalized_right in normalized_left
    )


def _model_pair_from_mapping(value: Any) -> tuple[str, str] | None:
    if not isinstance(value, dict):
        return None
    requested = value.get(_MODEL_KEYS[0])
    actual = value.get(_MODEL_KEYS[1])
    if not isinstance(requested, str) or not isinstance(actual, str):
        return None
    requested = requested.strip()
    actual = actual.strip()
    return (requested, actual) if requested and actual else None


def _model_pair_from_text(value: str) -> tuple[str, str] | None:
    requested = _REQUESTED_MODEL_RE.search(value)
    actual = _ACTUAL_MODEL_RE.search(value)
    if not requested or not actual:
        return None
    return requested.group(1).strip(), actual.group(1).strip()


def _dsh_model_pairs(raw_log: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for line in raw_log.splitlines():
        try:
            event: Any = json.loads(line)
        except (TypeError, ValueError):
            event = None
        if isinstance(event, dict):
            candidates = [event]
            nested_event = event.get("event")
            if isinstance(nested_event, dict):
                candidates.append(nested_event)
            for candidate in candidates:
                pair = _model_pair_from_mapping(candidate)
                if pair:
                    pairs.append(pair)
                for key in ("content", "result"):
                    content = candidate.get(key)
                    if isinstance(content, str):
                        pair = _model_pair_from_text(content)
                        if pair:
                            pairs.append(pair)
                        try:
                            content_data = json.loads(content)
                        except (TypeError, ValueError):
                            content_data = None
                        pair = _model_pair_from_mapping(content_data)
                        if pair:
                            pairs.append(pair)
        pair = _model_pair_from_text(line)
        if pair:
            pairs.append(pair)
    return pairs


DSH_MISSING_EXIT = 127


def _build_dsh_command(
    profile: str, prompt: str, dsh_bin: str = "dsh"
) -> list[str]:
    return [dsh_bin, "--profile", profile, "--no-open", prompt]


def _normalize_dsh_log(raw_log: str) -> str:
    extracted: list[str] = []
    for line in raw_log.splitlines():
        try:
            event: Any = json.loads(line)
        except (TypeError, ValueError):
            return raw_log
        if not isinstance(event, dict):
            return raw_log
        event_type = event.get("type")
        nested_event = event.get("event")
        if isinstance(nested_event, dict):
            event_type = nested_event.get("type", event_type)
            content = nested_event.get("content")
        else:
            content = event.get("content", event.get("result"))
        if event_type in {"session_end", "result"} and isinstance(content, str):
            extracted.append(content)
    return "\n".join(extracted) if extracted else raw_log


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

_STRUCTURED_MODEL_SUBSTITUTION_RE = re.compile(
    r"(?i)model_substitution:\s*requested=\S+\s+actual=\S+"
)


def is_structured_model_substitution_reason(reason: str | None) -> bool:
    return bool(reason and _STRUCTURED_MODEL_SUBSTITUTION_RE.search(reason))


def _match_patterns(text: str, patterns: tuple[re.Pattern, ...]) -> str | None:
    for pat in patterns:
        m = pat.search(text)
        if m:
            return m.group(0)
    return None


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


def detect_dsh_model_mismatch(
    raw_log: str, expected_model: str | None
) -> str | None:
    """Return a fail-closed reason for an explicit DSH model substitution."""
    expected = _normalize_model_id(expected_model)
    if not expected:
        return None
    for requested, actual in _dsh_model_pairs(raw_log):
        if not _models_equivalent(requested, actual) and _models_equivalent(
            requested, expected
        ):
            return (
                f"model_substitution: requested={requested} actual={actual} "
                "(dsh model mismatch; refuse silent downgrade)"
            )
    return None

_detect_dsh_model_mismatch = detect_dsh_model_mismatch


class DshAdapter(RuntimeAdapter):
    """RuntimeAdapter implementation wrapping existing DSH functions."""

    def build_command(self, ctx: SessionContext) -> list[str]:
        profile = ctx.extras.get("dsh_profile") or f"epic-{ctx.phase.lower()}"
        return _build_dsh_command(profile=profile, prompt=ctx.prompt)

    def analyze_log(self, raw_log: str, ctx: SessionContext) -> SessionAnalysis:
        reason = (
            _detect_dsh_model_mismatch(raw_log, ctx.model)
            or detect_dsh_abort_in_log(raw_log)
        )
        if "exit_code" in ctx.extras:
            exit_code = ctx.extras["exit_code"]
            if not reason and exit_code in (0, None) and not _detect_dsh_session_complete(raw_log):
                reason = "dsh incomplete FINISH"
            elif not reason and exit_code not in (0, None):
                reason = f"dsh process exit={exit_code}"

        dsh_abort_kind = None
        if reason and reason.startswith("dsh_transient:"):
            dsh_abort_kind = "transient"
        elif reason and (
            reason.startswith("dsh_permanent:")
            or is_structured_model_substitution_reason(reason)
        ):
            dsh_abort_kind = "fatal"
        elif reason:
            dsh_abort_kind = "unknown"

        normalized = _normalize_dsh_log(raw_log)
        struct_out = {"log": normalized} if normalized != raw_log else None

        return SessionAnalysis(
            reason=reason,
            dsh_abort_kind=dsh_abort_kind,
            structured_output=struct_out,
        )

    def prepare_extras(self, ctx: SessionContext) -> dict[str, Any]:
        return {"dsh_profile": f"epic-{ctx.phase.lower()}"}

