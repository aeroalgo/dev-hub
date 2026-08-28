from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


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


def build_dsh_command(
    profile: str, prompt: str, dsh_bin: str = "dsh"
) -> list[str]:
    return [dsh_bin, "--profile", profile, "--no-open", prompt]


def build_dsh_command_from_file(
    profile: str, prompt_file: Path, dsh_bin: str = "dsh"
) -> list[str]:
    return build_dsh_command(profile, prompt_file.read_text(encoding="utf-8"), dsh_bin)


def normalize_dsh_log(raw_log: str) -> str:
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
