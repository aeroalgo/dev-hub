"""load_plan_section and bounded plan jump materialization for loop/mb_load."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from harness.hooks.epic.core import read_active_context
from loop.paths.pack_layout import resolve_mb_root
from loop.schemas.active_context import parse_handoff_meta

_PLAN_PATTERN = re.compile(
    r"(?:^|[/\\])(?:plan-[^/\\]+\.md|plan\.md|md[/\\]plan\.md)$",
    re.IGNORECASE,
)
_UNRESTRICTED_MODES = frozenset({"PLAN", "DECOMPOSE", "ANALYZE", "AUDIT", "CREATIVE", "CLARIFY"})


def is_whole_plan_path(path: str | Path) -> bool:
    """Return True if path represents a markdown plan file."""
    p_str = str(path).replace("\\", "/").strip()
    return bool(_PLAN_PATTERN.search(p_str))


def parse_plan_jump(jump_ref: str) -> tuple[str, int | None, int | None]:
    """Parse a plan jump reference into (path, start_line, end_line).

    Examples:
      'path/to/plan.md:84-115' -> ('path/to/plan.md', 84, 115)
      'path/to/plan.md#L84-L115' -> ('path/to/plan.md', 84, 115)
      'path/to/plan.md:84:115' -> ('path/to/plan.md', 84, 115)
      'path/to/plan.md:84' -> ('path/to/plan.md', 84, 84)
      'path/to/plan.md#L84' -> ('path/to/plan.md', 84, 84)
      'path/to/plan.md' -> ('path/to/plan.md', None, None)
    """
    raw = str(jump_ref or "").strip()
    if not raw:
        return "", None, None

    # Check #Lstart-Lend or #Lstart
    hash_match = re.search(r"#L(\d+)(?:-L?(\d+))?$", raw, re.IGNORECASE)
    if hash_match:
        base_path = raw[: hash_match.start()]
        start = int(hash_match.group(1))
        end = int(hash_match.group(2)) if hash_match.group(2) else start
        return base_path, start, end

    # Check :start-end or :start:end or :start
    colon_match = re.search(r":(\d+)(?:[-:](\d+))?$", raw)
    if colon_match:
        base_path = raw[: colon_match.start()]
        start = int(colon_match.group(1))
        end = int(colon_match.group(2)) if colon_match.group(2) else start
        return base_path, start, end

    return raw, None, None


def materialize_plan_jump(jump_ref: str, cwd: str | Path = ".") -> dict[str, Any]:
    """Materialize a single plan jump into a bounded excerpt with identity and line numbers."""
    base_path, start_line, end_line = parse_plan_jump(jump_ref)
    cwd_path = Path(cwd).resolve()
    target = cwd_path / base_path if not Path(base_path).is_absolute() else Path(base_path)

    if not target.is_file():
        return {
            "jump_ref": jump_ref,
            "path": base_path,
            "canonical_path": base_path,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": 0,
            "content": "",
            "excerpt_identity": jump_ref,
            "ok": False,
            "error": "file_not_found",
        }

    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        return {
            "jump_ref": jump_ref,
            "path": base_path,
            "canonical_path": base_path,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": 0,
            "content": "",
            "excerpt_identity": jump_ref,
            "ok": False,
            "error": f"read_error:{exc}",
        }

    total_lines = len(lines)
    s = max(1, start_line) if start_line is not None else 1
    e = min(total_lines, max(s, end_line)) if end_line is not None else total_lines
    excerpt_lines = lines[s - 1 : e]
    excerpt = "\n".join(excerpt_lines)
    try:
        rel_path = target.relative_to(cwd_path).as_posix()
    except ValueError:
        rel_path = base_path
    excerpt_id = f"{rel_path}:{s}-{e}"

    return {
        "jump_ref": jump_ref,
        "path": base_path,
        "canonical_path": rel_path,
        "start_line": s,
        "end_line": e,
        "line_count": e - s + 1,
        "content": excerpt,
        "excerpt_identity": excerpt_id,
        "ok": True,
    }


def load_plan_jumps(shard_data_or_path: dict[str, Any] | str | Path, cwd: str | Path = ".") -> list[dict[str, Any]]:
    """Load and materialize plan jumps from shard YAML data or file path."""
    data: dict[str, Any] = {}
    if isinstance(shard_data_or_path, dict):
        data = shard_data_or_path
    else:
        p = Path(cwd) / shard_data_or_path if not Path(shard_data_or_path).is_absolute() else Path(shard_data_or_path)
        if p.is_file():
            try:
                import yaml
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            except Exception:
                data = {}

    plan_contract = data.get("plan_contract") if isinstance(data, dict) else {}
    if not isinstance(plan_contract, dict):
        return []

    raw_jumps = plan_contract.get("plan_jumps") or []
    if not isinstance(raw_jumps, list):
        return []

    results = []
    for j in raw_jumps:
        if isinstance(j, str) and j.strip():
            results.append(materialize_plan_jump(j.strip(), cwd=cwd))
    return results


def evaluate_plan_read(
    path: str | Path,
    start_line: int | None = None,
    end_line: int | None = None,
    mode: str = "IMPLEMENT",
    declared_jumps: list[str] | None = None,
    exception_reason: str | None = None,
    project_root: str | Path = ".",
) -> tuple[bool, str, dict[str, Any]]:
    """Evaluate whether reading a plan file is allowed under current mode and scope.

    Returns (allowed, reason_code, details).
    Fail-closed: monolith full plan reading is rejected in lean execution modes (IMPLEMENT/TASK/BUGFIX/QA).
    """
    mode_upper = (mode or "").strip().upper()

    p_str = str(path).replace("\\", "/").strip()
    if not is_whole_plan_path(p_str):
        return True, "not_plan_path", {"path": p_str}

    if mode_upper in _UNRESTRICTED_MODES:
        return True, "plan_mode_allowed", {"path": p_str, "mode": mode_upper}

    if exception_reason and str(exception_reason).strip():
        return True, "exception_approved", {
            "path": p_str,
            "exception_reason": str(exception_reason).strip(),
        }

    # Bounded range check
    is_bounded_range = (
        start_line is not None
        and end_line is not None
        and not (start_line == 1 and end_line >= 999999)
    )

    if is_bounded_range:
        jumps = declared_jumps or []
        matched_jump = None
        for j in jumps:
            jp, js, je = parse_plan_jump(j)
            if js is not None and je is not None:
                if start_line >= js and end_line <= je:
                    matched_jump = j
                    break
                elif start_line == js and end_line == je:
                    matched_jump = j
                    break

        excerpt_id = f"{p_str}:{start_line}-{end_line}"
        if matched_jump or not jumps:
            return True, "plan_jump_allowed", {
                "path": p_str,
                "start_line": start_line,
                "end_line": end_line,
                "excerpt_identity": excerpt_id,
                "matched_jump": matched_jump,
            }
        elif (end_line - start_line) <= 300:
            return True, "plan_jump_allowed", {
                "path": p_str,
                "start_line": start_line,
                "end_line": end_line,
                "excerpt_identity": excerpt_id,
                "matched_jump": None,
            }

    diag = (
        f"Whole plan read denied in {mode_upper}: reading full plan.md as monolithic AC is forbidden. "
        f"Use declared plan_jumps bounded excerpts or provide exception_reason. "
        f"Declared valid jumps: {declared_jumps or []}"
    )
    return False, "whole_plan_denied", {
        "path": p_str,
        "mode": mode_upper,
        "declared_jumps": declared_jumps or [],
        "diagnostic": diag,
        "fail_closed": True,
    }


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

    from loop.paths.pack_layout import PackLayoutError

    try:
        mb_root = resolve_mb_root(cwd=cwd_path)
    except PackLayoutError:
        return None, "workflow_pack_unresolved"

    role = "integration" if meta.role.lower() == "integ" else meta.role.lower()
    plan_dir = mb_root / role / "plan"

    # Exact current identity, including the scoped legacy filename layout.
    candidates = [plan_dir / epic_id / "md" / "plan.md"]
    candidates.extend(sorted(plan_dir.glob(f"{epic_id}-*/md/plan.md")))
    candidates.append(plan_dir / f"plan-{epic_id}.md")
    # Older packs append a human slug to the legacy filename.  Scope the glob
    # to the exact epic prefix so another epic's plan cannot be pulled in.
    candidates.extend(sorted(plan_dir.glob(f"plan-{epic_id}-*.md")))
    plan_file = next((p for p in candidates if p.is_file()), None)
    if not plan_file or not plan_file.is_file():
        return None, "plan_missing"

    try:
        plan_text = plan_file.read_text(encoding="utf-8")
    except Exception:
        return None, "plan_missing"

    # Split by ## headers
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
