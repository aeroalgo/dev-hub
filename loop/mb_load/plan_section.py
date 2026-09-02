"""load_plan_section for loop/mb_load."""

import re
from pathlib import Path

from harness.hooks.epic.core import read_active_context
from loop.schemas.active_context import parse_handoff_meta


def load_plan_section(cwd: str | Path = ".", section: int | str = 1) -> tuple[str | None, str | None]:
    """Reads activeContext -> epic_id -> finds plan-<epic_id>*.md -> extracts section N by ## headers.

    Returns:
        (content, error_code)
        If success: (content_str, None)
        If error: (None, "plan_missing" | "section_not_found" | "missing_active_context")
    """
    try:
        sec_num = int(section)
        if sec_num <= 0:
            return None, "section_not_found"
    except (ValueError, TypeError):
        return None, "section_not_found"

    cwd_path = Path(cwd).resolve()
    act_text = read_active_context(cwd_path)
    if not act_text:
        return None, "missing_active_context"

    meta = parse_handoff_meta(act_text)
    if not meta or not meta.epic_id:
        return None, "plan_missing"

    epic_id = meta.epic_id
    plan_dir = cwd_path / "memory-bank" / "back" / "plan"
    if not plan_dir.is_dir():
        return None, "plan_missing"

    matching_plans = list(plan_dir.glob(f"plan-{epic_id}*.md"))
    if not matching_plans:
        return None, "plan_missing"

    plan_file = matching_plans[0]
    try:
        plan_text = plan_file.read_text(encoding="utf-8")
    except Exception:
        return None, "plan_missing"

    # Split by ## headers
    # Find all ## lines
    lines = plan_text.splitlines()
    sections: list[list[str]] = []
    current_sec: list[str] = []
    in_section = False

    for line in lines:
        if line.startswith("## "):
            if current_sec:
                sections.append(current_sec)
            current_sec = [line]
            in_section = True
        elif in_section:
            current_sec.append(line)

    if current_sec:
        sections.append(current_sec)

    if sec_num > len(sections):
        return None, "section_not_found"

    target_lines = sections[sec_num - 1]
    return "\n".join(target_lines).strip(), None
