"""Portfolio bookkeeping for finalize-step.

tasks/log — every completed IMPLEMENT step.
tasks.md Active row — only when the epic phase actually changes.
"""
from __future__ import annotations

import re
from datetime import date as date_cls
from pathlib import Path
from typing import Any

_PRE_IMPLEMENT_RE = re.compile(
    r"\b(PLAN|DECOMPOSE|CREATIVE|VAN)\b",
    re.I,
)
_PAST_IMPLEMENT_RE = re.compile(
    r"\b(AUDIT|QA|REFLECT|ARCHIVE|IMPLEMENT done)\b",
    re.I,
)
_IN_PROGRESS_RE = re.compile(r"IMPLEMENT in progress", re.I)
_ACTIVE_HEADER_RE = re.compile(r"(?im)^##\s*Active\s*$")
_EVENTS_HEADER_RE = re.compile(r"(?im)^##\s*Последние события\s*$")


def _posix(path: Path, cwd: Path) -> str:
    try:
        return path.relative_to(cwd).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def _log_path(cwd: Path, day: date_cls) -> Path:
    return cwd / "memory-bank" / "tasks" / "log" / f"{day:%Y-%m}.md"


def _ensure_month_log(path: Path, day: date_cls) -> None:
    if path.is_file():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# Delivery log — {day:%Y-%m}\n\n"
        "Сквозная хронология эпиков. Пишет `finalize-step`. Не в `load_now`.\n\n"
        "## Timeline\n\n"
        "| Date | ID | Event | Artifact |\n"
        "|------|-----|-------|----------|\n",
        encoding="utf-8",
    )


def append_delivery_log(
    cwd: Path,
    *,
    epic_id: str,
    role: str,
    step_id: str,
    artifact: str,
    day: date_cls | None = None,
) -> dict[str, Any]:
    today = day or date_cls.today()
    path = _log_path(cwd, today)
    _ensure_month_log(path, today)
    event = f"{role} IMPLEMENT {step_id}"
    link = artifact.replace("\\", "/")
    if link.startswith("memory-bank/"):
        href = link[len("memory-bank/") :]
    else:
        href = link
    name = Path(href).name
    row = f"| {today.isoformat()} | {epic_id} | {event} | [{name}]({href}) |"
    text = path.read_text(encoding="utf-8")
    if row in text:
        return {
            "ok": True,
            "path": _posix(path, cwd),
            "skipped": True,
            "reason": "duplicate",
        }
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text + row + "\n", encoding="utf-8")
    return {"ok": True, "path": _posix(path, cwd), "skipped": False, "row": row}


def desired_tasks_step_cell(current: str, *, all_completed: bool) -> str | None:
    cell = (current or "").strip()
    if all_completed:
        if _PAST_IMPLEMENT_RE.search(cell):
            return None
        return "IMPLEMENT done · next AUDIT"
    if _IN_PROGRESS_RE.search(cell):
        return None
    if _PRE_IMPLEMENT_RE.search(cell):
        return "IMPLEMENT in progress"
    return None


def _table_block(text: str, header_re: re.Pattern[str]) -> tuple[int, int, list[str]] | None:
    m = header_re.search(text)
    if not m:
        return None
    start = m.end()
    rest = text[start:]
    lines = rest.splitlines(keepends=True)
    block: list[str] = []
    offset = 0
    for line in lines:
        if line.startswith("## ") and block:
            break
        block.append(line)
        offset += len(line)
    return start, start + offset, block


def _split_cells(line: str) -> list[str]:
    raw = line.rstrip("\n")
    if not raw.strip().startswith("|"):
        return []
    return [c.strip() for c in raw.strip().strip("|").split("|")]


def _format_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def maybe_update_tasks_md(
    cwd: Path,
    *,
    epic_id: str,
    all_completed: bool,
    day: date_cls | None = None,
    event_note: str | None = None,
) -> dict[str, Any]:
    path = cwd / "memory-bank" / "tasks.md"
    if not path.is_file():
        return {"ok": True, "updated": False, "reason": "missing_tasks_md"}
    text = path.read_text(encoding="utf-8")
    block = _table_block(text, _ACTIVE_HEADER_RE)
    if block is None:
        return {"ok": True, "updated": False, "reason": "no_active_table"}
    bstart, bend, lines = block
    eid = (epic_id or "").strip()
    if not eid:
        return {"ok": True, "updated": False, "reason": "no_epic_id"}
    changed = False
    new_step: str | None = None
    out_lines: list[str] = []
    for line in lines:
        cells = _split_cells(line)
        if len(cells) >= 5 and cells[0] == eid:
            desired = desired_tasks_step_cell(cells[3], all_completed=all_completed)
            if desired and desired != cells[3]:
                cells[3] = desired
                if all_completed:
                    cells[4] = "active"
                else:
                    cells[4] = "active"
                line = _format_row(cells) + "\n"
                changed = True
                new_step = desired
        out_lines.append(line if line.endswith("\n") or not line.strip() else line + "\n")
    if not changed:
        return {"ok": True, "updated": False, "reason": "no_phase_change"}
    new_text = text[:bstart] + "".join(out_lines) + text[bend:]
    today = day or date_cls.today()
    note = event_note or (new_step or "")
    new_text = _prepend_last_event(new_text, today, eid, note)
    path.write_text(new_text, encoding="utf-8")
    return {
        "ok": True,
        "updated": True,
        "path": _posix(path, cwd),
        "step": new_step,
    }


def _nl(line: str) -> str:
    return line if line.endswith("\n") else line + "\n"


def _prepend_last_event(text: str, day: date_cls, epic_id: str, event: str) -> str:
    m = _EVENTS_HEADER_RE.search(text)
    if not m:
        return text
    after = text[m.end() :]
    lines = after.splitlines(keepends=True)
    i = 0
    head: list[str] = []
    while i < len(lines) and not lines[i].lstrip().startswith("|"):
        head.append(_nl(lines[i]))
        i += 1
    if i >= len(lines):
        return text
    head.append(_nl(lines[i]))
    i += 1
    if i < len(lines) and re.match(r"^\|\s*-+", lines[i]):
        head.append(_nl(lines[i]))
        i += 1
    data: list[str] = []
    while i < len(lines) and lines[i].lstrip().startswith("|"):
        data.append(_nl(lines[i]))
        i += 1
    rest = [ _nl(x) for x in lines[i:] ]
    new_row = f"| {day.isoformat()} | {epic_id} | {event} |\n"
    data = [new_row, *[r for r in data if r.strip() != new_row.strip()]][:5]
    return text[: m.end()] + "".join(head + data + rest)


def sync_portfolio_after_step(
    cwd: Path,
    *,
    epic_id: str,
    role: str,
    step_id: str,
    artifact: str,
    all_completed: bool,
    day: date_cls | None = None,
) -> dict[str, Any]:
    log = append_delivery_log(
        cwd,
        epic_id=epic_id,
        role=role,
        step_id=step_id,
        artifact=artifact,
        day=day,
    )
    tasks = maybe_update_tasks_md(
        cwd,
        epic_id=epic_id,
        all_completed=all_completed,
        day=day,
        event_note=(
            f"{role} IMPLEMENT done · next AUDIT"
            if all_completed
            else f"{role} IMPLEMENT in progress"
        ),
    )
    return {"ok": True, "log": log, "tasks_md": tasks}
