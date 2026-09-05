"""activeContext frontmatter parse/render — typed handoff projection."""

from __future__ import annotations

import re
from typing import Any

import yaml
from pydantic import ValidationError

from loop.schemas.handoff import LoopHandoffFrontmatter, SCHEMA_LOOP_HANDOFF

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)

_ROLE_TOKEN = r"(?:BACK|FRONT|INTEG(?:RATION)?)"
_HANDOFF_PHASE_HEADING_RE = re.compile(
    rf"(?im)^##\s*Handoff\s+{_ROLE_TOKEN}\s+"
    rf"(?:{_ROLE_TOKEN}\s+)?"
    r"(AUDIT|QA|BUGFIX|DECOMPOSE)\b"
)
_POST_IMPLEMENT_GATE_PHASES = frozenset(
    {"AUDIT", "QA", "BUGFIX", "DECOMPOSE"}
)
_POST_IMPLEMENT_PHASE_RANK = {
    "AUDIT": 0,
    "QA": 1,
    "BUGFIX": 1,
    "DONE": 2,
}
_HANDOFF_MODE_LINE_RE = re.compile(
    r"(?im)(?:[-*]\s*)?(?:\*\*)?(?:Режим/шаг|Mode/step):(?:\*\*)?\s*"
    r"`?(?:BACK|FRONT|INTEG(?:RATION)?)\s+"
    r"(AUDIT|QA|BUGFIX|DECOMPOSE)`?"
)
_HANDOFF_NEXT_PHASE_RE = re.compile(
    r"(?im)(?:\*\*)?(?:Дальше|Next)(?:\*\*)?:\s*.*`(?:BACK|FRONT|INTEG(?:RATION)?)\s+"
    r"(AUDIT|QA|BUGFIX)`"
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


def normalize_gate_mode(mode: str, role: str | None = None) -> str:
    value = (mode or "").strip().upper()
    if not value:
        return value
    if role:
        role_u = role.upper()
        if role_u == "INTEGRATION":
            role_u = "INTEG"
        prefix = f"{role_u} "
        if value.startswith(prefix):
            value = value[len(prefix) :].strip()
    else:
        value = re.sub(rf"^{_ROLE_TOKEN}\s+", "", value, count=1, flags=re.I).strip()
    return value


def handoff_gate_phase_from_text(text: str) -> str | None:
    """Post-implement gate phase from Handoff markdown, then frontmatter."""
    handoff = _extract_handoff_block(text) or ""
    if handoff:
        for pattern in (
            _HANDOFF_MODE_LINE_RE,
            _HANDOFF_PHASE_HEADING_RE,
            _HANDOFF_NEXT_PHASE_RE,
        ):
            match = pattern.search(handoff)
            if match:
                return str(match.group(1)).upper()
    meta = parse_handoff_meta(text)
    if meta is not None:
        token = normalize_gate_mode(meta.mode, meta.role)
        if token in _POST_IMPLEMENT_GATE_PHASES:
            return token
    return None


def post_implement_phase_rank(phase: str | None) -> int:
    return _POST_IMPLEMENT_PHASE_RANK.get(str(phase or "").upper(), -1)


def handoff_mode_from_text(text: str) -> str | None:
    meta = parse_handoff_meta(text)
    if meta is not None:
        return normalize_gate_mode(meta.mode, meta.role)
    handoff = _extract_handoff_block(text) or ""
    if not handoff:
        return None
    if _IMPLEMENT_HANDOFF_RE.search(handoff):
        return "IMPLEMENT"
    match = _HANDOFF_MODE_LINE_RE.search(handoff)
    if match:
        return str(match.group(1)).upper()
    match = _HANDOFF_PHASE_HEADING_RE.search(handoff)
    if match:
        return str(match.group(1)).upper()
    return None


def _handoff_mode_from_legacy_markdown(text: str) -> str | None:
    return handoff_mode_from_text(text)


def _extract_handoff_block(text: str) -> str:
    match = re.search(r"(?im)^##\s*Handoff\b.*$", text)
    if not match:
        return ""
    start = match.start()
    rest = text[match.end() :]
    nxt = re.search(r"(?im)^##\s+", rest)
    end = match.end() + (nxt.start() if nxt else len(rest))
    return text[start:end].strip()
