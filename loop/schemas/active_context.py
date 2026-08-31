"""activeContext frontmatter parse/render — typed handoff projection."""

from __future__ import annotations

import re
from typing import Any

import yaml
from pydantic import ValidationError

from loop.schemas.handoff import LoopHandoffFrontmatter, SCHEMA_LOOP_HANDOFF

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)

_HANDOFF_PHASE_HEADING_RE = re.compile(
    r"(?im)^##\s*Handoff\s+(?:BACK|FRONT|INTEG(?:RATION)?)\s+"
    r"(AUDIT|QA|REFLECT|BUGFIX|DECOMPOSE)\b"
)
_HANDOFF_MODE_LINE_RE = re.compile(
    r"(?im)(?:Режим/шаг|Mode/step):\s*`(?:BACK|FRONT|INTEG(?:RATION)?)\s+"
    r"(AUDIT|QA|REFLECT|BUGFIX|DECOMPOSE)`"
)
_HANDOFF_NEXT_PHASE_RE = re.compile(
    r"(?im)(?:Дальше|Next):\s*.*`(?:BACK|FRONT|INTEG(?:RATION)?)\s+"
    r"(AUDIT|QA|REFLECT|BUGFIX)`"
)
_IMPLEMENT_HANDOFF_RE = re.compile(
    r"(?im)^##\s*Handoff\s+(?:BACK|FRONT|INTEG(?:RATION)?)\s+IMPLEMENT\b"
)


def split_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    value = text or ""
    match = _FRONTMATTER_RE.match(value)
    if not match:
        return None, value
    raw = match.group(1)
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError:
        return None, value
    if not isinstance(parsed, dict):
        return None, value
    body = value[match.end() :]
    return parsed, body


def parse_frontmatter(text: str) -> LoopHandoffFrontmatter | None:
    return parse_handoff_meta(text)


def parse_handoff_meta(text: str) -> LoopHandoffFrontmatter | None:
    raw, _body = split_frontmatter(text)
    if not raw:
        return None
    if str(raw.get("schema") or "") != SCHEMA_LOOP_HANDOFF:
        return None
    try:
        return LoopHandoffFrontmatter.model_validate(raw)
    except ValidationError:
        return None


def validate_handoff_frontmatter(text: str) -> tuple[LoopHandoffFrontmatter | None, list[str]]:
    raw, _body = split_frontmatter(text)
    if not raw:
        return None, ["missing_handoff_frontmatter"]
    if str(raw.get("schema") or "") != SCHEMA_LOOP_HANDOFF:
        return None, ["handoff_frontmatter_schema_invalid"]
    try:
        return LoopHandoffFrontmatter.model_validate(raw), []
    except ValidationError as exc:
        codes = [
            f"handoff_frontmatter_invalid:{'.'.join(str(part) for part in err['loc'])}"
            for err in exc.errors()
        ]
        return None, codes or ["handoff_frontmatter_invalid"]


def render_with_frontmatter(body: str, meta: LoopHandoffFrontmatter) -> str:
    payload = meta.model_dump_frontmatter()
    front = yaml.safe_dump(
        payload,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).strip()
    content = (body or "").lstrip("\n")
    return f"---\n{front}\n---\n\n{content}"


def handoff_mode_from_text(text: str) -> str | None:
    meta = parse_handoff_meta(text)
    if meta is not None:
        return meta.mode
    return _handoff_mode_from_legacy_markdown(text)


def _handoff_mode_from_legacy_markdown(text: str) -> str | None:
    handoff = _extract_handoff_block(text) or ""
    if not handoff:
        return None
    if _IMPLEMENT_HANDOFF_RE.search(handoff):
        return "IMPLEMENT"
    for pattern in (
        _HANDOFF_PHASE_HEADING_RE,
        _HANDOFF_MODE_LINE_RE,
        _HANDOFF_NEXT_PHASE_RE,
    ):
        match = pattern.search(handoff)
        if match:
            return str(match.group(1)).upper()
    return None


def _extract_handoff_block(text: str) -> str:
    match = re.search(r"(?im)^##\s*Handoff\b.*$", text)
    if not match:
        return ""
    start = match.start()
    rest = text[match.end() :]
    nxt = re.search(r"(?im)^##\s+", rest)
    end = match.end() + (nxt.start() if nxt else len(rest))
    return text[start:end].strip()
