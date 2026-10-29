from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from loop.kernel.index import plan_path, resolve_epic_kind, resolve_epic_role


@dataclass(frozen=True)
class BoardCardCopy:
    title: str
    summary: str


_BOARD_SECTION_RE = re.compile(
    r"(?ms)^##\s+Board\s*\n(?P<body>.*?)(?=^##\s+|\Z)"
)
_TITLE_RE = re.compile(r"(?im)^title\s*:\s*(?P<title>\S.*)$")
_SUMMARY_RE = re.compile(
    r"(?ims)^summary\s*:\s*(?P<summary>.+?)(?=^(?:title|summary)\s*:|\Z)"
)
_OUTCOME_RE = re.compile(
    r"(?ms)^##\s+Epic\b.*?^###\s+Outcome\s*\n(?P<outcome>.*?)(?=^###\s+|\Z)"
)


def prompt_md_path(
    project_root: Path | str,
    epic_id: str,
    role: str = "back",
    kind: str | None = None,
) -> Path:
    root = Path(project_root)
    resolved_role = resolve_epic_role(root, epic_id, role=role, kind=kind)
    resolved_kind = resolve_epic_kind(root, epic_id, kind=kind, role=resolved_role)
    return plan_path(root, resolved_role, epic_id, kind=resolved_kind).with_name("prompt.md")


def bugfix_prompt_md_path(
    project_root: Path | str,
    epic_id: str,
    role: str = "back",
) -> Path:
    """Ad-hoc / epic BUGFIX Board copy — never invent plan/ for this."""

    root = Path(project_root)
    resolved_role = role if role and role != "auto" else "back"
    return root / "memory-bank" / resolved_role / "bugfix" / epic_id / "prompt.md"


def resolve_board_prompt_path(
    project_root: Path | str,
    epic_id: str,
    role: str = "back",
    kind: str | None = None,
) -> Path | None:
    """Prefer feature plan prompt; fall back to bugfix/<id>/prompt.md."""

    root = Path(project_root)
    resolved_role = role if role and role != "auto" else "back"
    resolved_kind = kind
    try:
        resolved_role = resolve_epic_role(root, epic_id, role=role, kind=kind)
        resolved_kind = resolve_epic_kind(root, epic_id, kind=kind, role=resolved_role)
    except (ValueError, FileNotFoundError, OSError):
        pass

    candidates: list[Path] = []
    try:
        candidates.append(
            prompt_md_path(root, epic_id, role=resolved_role, kind=resolved_kind)
        )
    except (ValueError, FileNotFoundError, OSError):
        pass
    candidates.append(bugfix_prompt_md_path(root, epic_id, role=resolved_role))
    for path in candidates:
        if path.is_file():
            return path
    return None


def parse_board_card_copy(text: str) -> BoardCardCopy | None:
    board_match = _BOARD_SECTION_RE.search(text or "")
    if not board_match:
        return None
    body = board_match.group("body").strip()
    if not body:
        return None

    title_match = _TITLE_RE.search(body)
    summary_match = _SUMMARY_RE.search(body)
    title = (title_match.group("title").strip() if title_match else "")
    summary = (summary_match.group("summary").strip() if summary_match else "")
    if not title and not summary:
        return None
    if not title:
        title = summary.splitlines()[0].strip()
    if not summary:
        summary = title
    return BoardCardCopy(title=title, summary=summary)


def parse_outcome_fallback(text: str) -> BoardCardCopy | None:
    match = _OUTCOME_RE.search(text or "")
    if not match:
        return None
    outcome = " ".join(line.strip() for line in match.group("outcome").splitlines() if line.strip())
    if not outcome:
        return None
    title = outcome.split(".")[0].strip() or outcome[:80].strip()
    return BoardCardCopy(title=title, summary=outcome)


def load_board_card_copy(
    project_root: Path | str,
    epic_id: str,
    role: str = "back",
    kind: str | None = None,
) -> BoardCardCopy | None:
    path = resolve_board_prompt_path(project_root, epic_id, role=role, kind=kind)
    if path is None:
        return None
    text = path.read_text(encoding="utf-8")
    return parse_board_card_copy(text) or parse_outcome_fallback(text)


def format_card_description(
    *,
    epic_id: str,
    summary: str,
    role: str,
    kind: str = "feature",
    artifact_rel: str | None = None,
) -> str:
    if artifact_rel:
        ref_line = f"Artifact: {artifact_rel}"
    else:
        kind_prefix = {
            "feature": "",
            "refactor": "refactor/",
            "security": "security/",
        }.get(kind, "")
        ref_line = f"Plan: memory-bank/{role}/{kind_prefix}plan/{epic_id}/md/plan.md"
    summary_text = summary.strip() or f"Epic: {epic_id}"
    return f"{summary_text}\n\nEpic: {epic_id}\n{ref_line}"


def resolve_card_fields(
    project_root: Path | str,
    epic_id: str,
    role: str = "back",
    kind: str | None = None,
    title: str = "",
    description: str = "",
) -> tuple[str, str]:
    if title.strip() and description.strip():
        return title.strip(), description.strip()

    root = Path(project_root)
    resolved_role = role if role and role != "auto" else "back"
    resolved_kind = kind or "feature"
    try:
        resolved_role = resolve_epic_role(root, epic_id, role=role, kind=kind)
        resolved_kind = resolve_epic_kind(root, epic_id, kind=kind, role=resolved_role)
    except (ValueError, FileNotFoundError, OSError):
        pass

    prompt_path = resolve_board_prompt_path(
        root, epic_id, role=resolved_role, kind=resolved_kind
    )
    copy = None
    if prompt_path is not None:
        try:
            text = prompt_path.read_text(encoding="utf-8")
            copy = parse_board_card_copy(text) or parse_outcome_fallback(text)
        except (OSError, UnicodeError):
            copy = None

    resolved_title = title.strip() or (copy.title if copy else epic_id)
    if description.strip():
        resolved_description = description.strip()
    elif copy:
        artifact_rel = None
        if prompt_path is not None:
            try:
                artifact_rel = prompt_path.relative_to(root).as_posix()
            except ValueError:
                artifact_rel = str(prompt_path)
            if "/bugfix/" in artifact_rel.replace("\\", "/"):
                pass
            else:
                # Feature plan prompt → keep Plan: line pointing at plan.md
                artifact_rel = None
        resolved_description = format_card_description(
            epic_id=epic_id,
            summary=copy.summary,
            role=resolved_role,
            kind=resolved_kind,
            artifact_rel=artifact_rel,
        )
    else:
        resolved_description = f"Epic: {epic_id}"
    return resolved_title, resolved_description
