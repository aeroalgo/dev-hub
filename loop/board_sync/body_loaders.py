"""Load card body text from decomposition step shards and plan files."""

from __future__ import annotations

import re
from pathlib import Path
import yaml

_MAX_BODY_LEN = 4000


def load_gate_body(plan_path: Path | None, reason_code: str | None) -> str | None:
    """Read a plan markdown file and extract structured goal/context/stories body.

    Fail-soft if plan_path is None or missing/broken, returning reason_code (if non-empty) or None.
    """
    if plan_path is None or not plan_path.is_file():
        return reason_code if (reason_code and reason_code.strip()) else None

    try:
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return reason_code if (reason_code and reason_code.strip()) else None

    parts: list[str] = []
    lines = content.splitlines()

    # 1. H1 line
    for line in lines:
        if line.lstrip().startswith("# "):
            parts.append(line.strip())
            break

    # Extract sections
    # Find H2 headings
    sections: dict[str, list[str]] = {}
    current_sec: str | None = None
    for line in lines:
        if line.lstrip().startswith("## "):
            sec_title = line.lstrip()[3:].strip().lower()
            current_sec = sec_title
            sections[current_sec] = []
        elif current_sec is not None:
            if line.lstrip().startswith("#"):
                current_sec = None
            else:
                sections[current_sec].append(line)

    # 2. Section Цель
    goal_lines = None
    for key, val in sections.items():
        if "цель" in key or "goal" in key:
            goal_lines = val
            break
    if goal_lines:
        goal_text = "\n".join(goal_lines).strip()
        if goal_text:
            parts.append(f"## Цель\n{goal_text}")

    # 3. Section Контекст (first paragraph)
    context_lines = None
    for key, val in sections.items():
        if "контекст" in key or "context" in key:
            context_lines = val
            break
    if context_lines:
        paragraphs = "\n".join(context_lines).strip().split("\n\n")
        first_p = next((p.strip() for p in paragraphs if p.strip()), None)
        if first_p:
            parts.append(f"## Контекст\n{first_p}")

    # 4. Section User Stories / Требования / FR (table ≤5 rows)
    stories_lines = None
    for key, val in sections.items():
        if "user stories" in key or "stories" in key or "требования" in key or "user story" in key:
            stories_lines = val
            break
    if stories_lines:
        table_rows = [l for l in stories_lines if "|" in l]
        if table_rows:
            header_rows = [r for r in table_rows if "---" in r]
            if header_rows:
                header_idx = table_rows.index(header_rows[0])
                headers = table_rows[:header_idx+1]
                data_rows = table_rows[header_idx+1:]
                truncated_data = data_rows[:5]
                filtered_table = headers + truncated_data
                parts.append("## User Stories\n" + "\n".join(filtered_table))
            else:
                parts.append("## User Stories\n" + "\n".join(table_rows[:5]))

    if not parts:
        return reason_code if (reason_code and reason_code.strip()) else None

    body = "\n\n".join(parts)
    if len(body) > _MAX_BODY_LEN:
        body = body[: _MAX_BODY_LEN - 1] + "…"
    return body



def load_step_body(path: Path) -> tuple[str | None, str | None]:
    """Read a step shard YAML and compose a markdown body.

    Returns (body, diagnostic_message). On missing/broken file, returns (None, diagnostic).
    """
    if not path.is_file():
        return None, f"Shard file not found: {path}"

    try:
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            return None, f"Shard file is not a valid YAML mapping: {path}"
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return None, f"Failed to read shard {path}: {exc}"

    parts: list[str] = []

    goal = data.get("goal")
    title = data.get("title")
    if isinstance(goal, str) and goal.strip():
        parts.append(goal.strip())
    elif isinstance(title, str) and title.strip():
        parts.append(title.strip())

    delta = data.get("delta")
    if isinstance(delta, list) and delta:
        delta_lines = ["Delta:"]
        for item in delta:
            delta_lines.append(f"- {item}")
        parts.append("\n".join(delta_lines))
    elif isinstance(delta, str) and delta.strip():
        parts.append(f"Delta:\n{delta.strip()}")

    files = data.get("files")
    context = data.get("context")
    if not isinstance(files, list) and isinstance(context, dict):
        files = context.get("files")
        if not isinstance(files, list):
            consumes = context.get("consumes")
            if isinstance(consumes, list):
                files = consumes[:3]

    if isinstance(files, list) and files:
        files_lines = ["Files / Context:"]
        for f in files:
            files_lines.append(f"- `{f}`")
        parts.append("\n".join(files_lines))

    if not parts:
        return None, f"Shard {path} contains no body fields"

    body = "\n\n".join(parts)
    if len(body) > _MAX_BODY_LEN:
        body = body[: _MAX_BODY_LEN - 1] + "…"

    return body, None
