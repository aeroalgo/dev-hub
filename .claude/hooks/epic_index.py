#!/usr/bin/env python3
"""Decompose index.yaml — machine canon for step queue + status.

index.yaml is the sole source of truth for queue + status (runner/prepare).
index.md is human coverage; its status column is a best-effort mirror only
(mark-index-status / repair_index_mirror / rebuild_md_queue_from_yaml).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

SCHEMA_DECOMPOSE_INDEX = "epic-decompose-index/v1"
_STEP_STATUS_WORDS = ("pending", "active", "completed", "done", "blocked")
_STEP_ID_RE = re.compile(r"^[sera]\d{2}$")
_PHASE_RE = re.compile(
    r"\b(BACK|FRONT|INTEG)\s+(IMPLEMENT|PLAN|DECOMPOSE|QA|CREATIVE|REFLECT)\b",
    re.I,
)
_YAML_LINK_RE = re.compile(
    r"\[([^\]]+)\]\(([^)\s]+\.ya?ml)\)",
    re.I,
)
_IMPL_HUB_LINK_RE = re.compile(
    r"\[([^\]]*implement[^\]]*)\]\(([^)\s]*implement[^)\s]*/index\.md)\)",
    re.I,
)
_PLAN_ID_RE = re.compile(r"(?im)^\*\*Plan ID:\*\*\s*(\S+)")
_ROW_RE = re.compile(
    r"(?im)^\|\s*\*\*([sera]\d{2})\*\*\s*\|(?P<body>.*)$",
)


def index_md_path(dir_or_md: Path) -> Path:
    p = Path(dir_or_md)
    if p.is_dir():
        return p / "index.md"
    if p.name == "index.yaml":
        return p.with_name("index.md")
    return p


def index_yaml_path(dir_or_md: Path) -> Path:
    md = index_md_path(dir_or_md)
    return md.with_name("index.yaml")


def _row_status_from_body(body: str) -> str | None:
    words = "|".join(_STEP_STATUS_WORDS)
    status_cell = rf"\**\s*({words})\s*\**"
    found = re.findall(rf"\|\s*{status_cell}\s*\|", body, flags=re.I)
    if found:
        return found[-1].lower()
    m_end = re.search(rf"(?i)\|\s*{status_cell}\s*$", body.rstrip())
    return m_end.group(1).lower() if m_end else None


def parse_steps_from_md(index_text: str) -> list[dict[str, str]]:
    """Extract queue rows from human index.md table."""
    steps: list[dict[str, str]] = []
    for m in _ROW_RE.finditer(index_text):
        sid = m.group(1).lower()
        body = "|" + m.group("body")
        st = _row_status_from_body(body) or "pending"
        file_href = ""
        title = ""
        impl_href = ""
        links = list(_YAML_LINK_RE.finditer(body))
        if links:
            file_href = links[0].group(2).strip()
            label0 = links[0].group(1).strip()
            title = Path(label0).stem if "." in label0 else Path(file_href).stem
            if len(links) > 1:
                impl_href = links[1].group(2).strip()
            elif "/implement/" in file_href.replace("\\", "/"):
                # rare: only implement link in cell
                impl_href = file_href
                file_href = Path(file_href).name
                title = Path(file_href).stem
        phase = ""
        pm = _PHASE_RE.search(body)
        if pm:
            phase = f"{pm.group(1).upper()} {pm.group(2).upper()}"
        steps.append(
            {
                "id": sid,
                "file": file_href or f"{sid}.yaml",
                "implement": impl_href,
                "next_phase": phase,
                "status": st,
                "title": title or sid,
            }
        )
    return steps


def extract_plan_id(index_text: str, fallback: str = "") -> str:
    m = _PLAN_ID_RE.search(index_text or "")
    if m:
        return m.group(1).strip()
    return fallback


def extract_implement_hub_href(index_text: str) -> str:
    hm = _IMPL_HUB_LINK_RE.search(index_text or "")
    return hm.group(2).strip() if hm else ""


def load_index_yaml(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"index.yaml must be a mapping: {path}")
    return data


def dump_index_yaml(doc: dict[str, Any]) -> str:
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)


def steps_from_doc(doc: dict[str, Any]) -> list[dict[str, str]]:
    raw = doc.get("steps") or []
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        sid = str(item.get("id") or item.get("step_id") or "").strip().lower()
        if not _STEP_ID_RE.match(sid):
            continue
        st = str(item.get("status") or "pending").strip().lower()
        if st not in _STEP_STATUS_WORDS:
            st = "pending"
        out.append(
            {
                "id": sid,
                "file": str(item.get("file") or f"{sid}.yaml").strip(),
                "implement": str(item.get("implement") or "").strip(),
                "next_phase": str(item.get("next_phase") or "").strip(),
                "status": st,
                "title": str(item.get("title") or sid).strip(),
            }
        )
    return out


def build_doc_from_steps(
    *,
    plan_id: str,
    steps: list[dict[str, str]],
    implement_index: str = "",
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "schema": SCHEMA_DECOMPOSE_INDEX,
        "plan_id": plan_id,
        "source_md": "index.md",
        "status_canon": "index.yaml",
        "steps": [
            {
                "id": s["id"],
                "file": s["file"],
                "implement": s.get("implement") or None,
                "next_phase": s.get("next_phase") or None,
                "title": s.get("title") or s["id"],
                "status": s["status"],
            }
            for s in steps
        ],
    }
    if implement_index:
        doc["implement_index"] = implement_index
    # drop nulls for cleaner yaml
    for step in doc["steps"]:
        for k in list(step.keys()):
            if step[k] is None or step[k] == "":
                del step[k]
    return doc


def sync_yaml_from_md(
    md_path: Path,
    *,
    preserve_yaml_status: bool = True,
) -> dict[str, Any]:
    """Build/refresh index.yaml from index.md structure.

    Status policy:
    - preserve_yaml_status=True (default): existing yaml status wins for known ids;
      new steps take status from md.
    - False: take all statuses from md (bootstrap / repair).
    """
    md_path = index_md_path(md_path)
    if not md_path.is_file():
        return {"ok": False, "error": f"missing {md_path}"}
    text = md_path.read_text(encoding="utf-8")
    md_steps = parse_steps_from_md(text)
    if not md_steps:
        return {"ok": False, "error": f"no step rows in {md_path}"}

    ypath = index_yaml_path(md_path)
    old_by_id: dict[str, str] = {}
    if preserve_yaml_status and ypath.is_file():
        old = load_index_yaml(ypath) or {}
        for s in steps_from_doc(old):
            old_by_id[s["id"]] = s["status"]

    merged: list[dict[str, str]] = []
    for s in md_steps:
        row = dict(s)
        if preserve_yaml_status and s["id"] in old_by_id:
            row["status"] = old_by_id[s["id"]]
        merged.append(row)

    plan_id = extract_plan_id(text)
    if not plan_id:
        # decompose-v1-portal → v1-portal
        name = md_path.parent.name
        plan_id = re.sub(r"^decompose-", "", name)

    doc = build_doc_from_steps(
        plan_id=plan_id,
        steps=merged,
        implement_index=extract_implement_hub_href(text),
    )
    ypath.write_text(dump_index_yaml(doc), encoding="utf-8")
    rel_md = str(md_path)
    rel_y = str(ypath)
    return {
        "ok": True,
        "path": rel_y,
        "source_md": rel_md,
        "steps": len(merged),
        "preserve_yaml_status": preserve_yaml_status,
        "plan_id": plan_id,
    }


def find_next_step(steps: list[dict[str, str]]) -> dict[str, str] | None:
    for s in steps:
        if s.get("status") in {"active", "pending", "blocked"}:
            return s
    return None


def set_step_status_in_doc(doc: dict[str, Any], step_id: str, status: str) -> str | None:
    """Mutate doc; return previous status or None if missing."""
    sid = step_id.strip().lower()
    status_l = status.strip().lower()
    for item in doc.get("steps") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("id") or item.get("step_id") or "").strip().lower() != sid:
            continue
        prev = str(item.get("status") or "pending").lower()
        item["status"] = status_l
        return prev
    return None


def mirror_status_to_md(
    md_path: Path,
    step_id: str,
    status: str,
    *,
    sync_checklist: bool = True,
) -> dict[str, Any]:
    """Update status cell + optional checklist in human index.md."""
    status_l = status.strip().lower()
    sid = step_id.strip().lower()
    if not md_path.is_file():
        return {"ok": False, "error": f"missing {md_path}", "mirrored": False}
    text = md_path.read_text(encoding="utf-8")
    words = "|".join(_STEP_STATUS_WORDS)
    row_re = re.compile(
        rf"(?im)^(\|\s*\*\*{re.escape(sid)}\*\*\s*\|.*\|\s*)"
        rf"(?:\*\*)?({words})(?:\*\*)?(\s*\|)\s*$"
    )
    m = row_re.search(text)
    if not m:
        return {
            "ok": False,
            "error": f"row **{sid}** not found in {md_path}",
            "mirrored": False,
        }
    old_st = m.group(2).lower()
    new_row = f"{m.group(1)}{status_l}{m.group(3)}"
    new_text = text[: m.start()] + new_row + text[m.end() :]
    n_ck = 0
    if sync_checklist:
        box = "x" if status_l in {"completed", "done"} else " "
        new_text, n_ck = re.subn(
            rf"(?im)^(\s*[-*]\s*)\[[ xX]\](\s*{re.escape(sid)}\b)",
            rf"\1[{box}]\2",
            new_text,
            count=1,
        )
    if new_text == text and old_st == status_l:
        return {
            "ok": True,
            "mirrored": True,
            "unchanged": True,
            "previous": old_st,
            "checklist_updated": False,
        }
    md_path.write_text(new_text, encoding="utf-8")
    return {
        "ok": True,
        "mirrored": True,
        "unchanged": False,
        "previous": old_st,
        "checklist_updated": bool(n_ck),
    }


def render_queue_table_from_steps(steps: list[dict[str, str]]) -> str:
    """Render a parseable human queue table from yaml steps."""
    lines = [
        "| step_id | title & files | next_phase | status |",
        "| :--- | :--- | :--- | :--- |",
    ]
    for s in steps:
        sid = str(s.get("id") or "").strip().lower()
        title = str(s.get("title") or sid).strip()
        file_href = str(s.get("file") or f"{sid}.yaml").strip()
        phase = str(s.get("next_phase") or "").strip()
        status = str(s.get("status") or "pending").strip().lower()
        impl = str(s.get("implement") or "").strip()
        title_cell = f"{title} · [yaml]({file_href})"
        if impl:
            title_cell += f" · [implement]({impl})"
        lines.append(f"| **{sid}** | {title_cell} | {phase} | {status} |")
    return "\n".join(lines)


def _sync_checklist_from_steps(text: str, steps: list[dict[str, str]]) -> str:
    out = text
    for s in steps:
        sid = str(s.get("id") or "").strip().lower()
        if not sid:
            continue
        box = "x" if str(s.get("status") or "").lower() in {"completed", "done"} else " "
        out, _n = re.subn(
            rf"(?im)^(\s*[-*]\s*)\[[ xX]\](\s*{re.escape(sid)}\b)",
            rf"\1[{box}]\2",
            out,
            count=1,
        )
    return out


def rebuild_md_queue_from_yaml(md_path: Path) -> dict[str, Any]:
    """Rewrite index.md queue table from index.yaml (yaml is canon).

    Creates index.md when missing. Preserves non-queue markdown (coverage etc.)
    when a prior queue block exists; otherwise appends a queue section.
    """
    md_path = index_md_path(md_path)
    ypath = index_yaml_path(md_path)
    if not ypath.is_file():
        return {"ok": False, "error": f"missing {ypath}", "rebuilt": False}
    try:
        doc = load_index_yaml(ypath)
    except (OSError, TypeError, ValueError, yaml.YAMLError) as exc:
        return {"ok": False, "error": str(exc), "rebuilt": False}
    if not isinstance(doc, dict):
        return {"ok": False, "error": f"invalid yaml: {ypath}", "rebuilt": False}
    steps = steps_from_doc(doc)
    if not steps:
        return {"ok": False, "error": "index.yaml has no steps", "rebuilt": False}
    table = render_queue_table_from_steps(steps)
    if md_path.is_file():
        text = md_path.read_text(encoding="utf-8")
    else:
        plan_id = str(doc.get("plan_id") or md_path.parent.name).strip()
        text = (
            f"# decompose {plan_id}\n\n"
            f"**Machine index:** [index.yaml](index.yaml) — **канон status**\n\n"
        )
        md_path.parent.mkdir(parents=True, exist_ok=True)

    lines = text.splitlines(keepends=True)
    step_idxs = [
        i for i, line in enumerate(lines) if _ROW_RE.match(line.rstrip("\n"))
    ]
    if step_idxs:
        start = step_idxs[0]
        while start > 0 and lines[start - 1].lstrip().startswith("|"):
            start -= 1
        end = step_idxs[-1]
        while end + 1 < len(lines) and lines[end + 1].lstrip().startswith("|"):
            end += 1
        new_text = "".join(lines[:start]) + table + "\n" + "".join(lines[end + 1 :])
    else:
        new_text = text.rstrip() + "\n\n## Очередь шагов\n\n" + table + "\n"

    new_text = _sync_checklist_from_steps(new_text, steps)
    md_path.write_text(new_text, encoding="utf-8")
    return {
        "ok": True,
        "rebuilt": True,
        "path": str(md_path),
        "yaml_path": str(ypath),
        "steps": len(steps),
        "step_ids": [s["id"] for s in steps],
    }


def md_queue_drift_from_yaml(md_path: Path) -> dict[str, Any]:
    """Detect human-queue drift vs yaml without mutating files."""
    md_path = index_md_path(md_path)
    ypath = index_yaml_path(md_path)
    if not ypath.is_file():
        return {"ok": False, "drift": False, "error": f"missing {ypath}"}
    try:
        doc = load_index_yaml(ypath)
    except (OSError, TypeError, ValueError, yaml.YAMLError) as exc:
        return {"ok": False, "drift": False, "error": str(exc)}
    yaml_steps = steps_from_doc(doc or {})
    yaml_shape = [(s.get("id"), s.get("status")) for s in yaml_steps]
    if not md_path.is_file():
        return {
            "ok": True,
            "drift": True,
            "reason": "md_missing",
            "yaml_steps": len(yaml_steps),
            "md_steps": 0,
        }
    md_steps = parse_steps_from_md(md_path.read_text(encoding="utf-8", errors="replace"))
    md_shape = [(s.get("id"), s.get("status")) for s in md_steps]
    if yaml_shape != md_shape:
        return {
            "ok": True,
            "drift": True,
            "reason": "shape_mismatch",
            "yaml_steps": len(yaml_steps),
            "md_steps": len(md_steps),
        }
    return {
        "ok": True,
        "drift": False,
        "reason": None,
        "yaml_steps": len(yaml_steps),
        "md_steps": len(md_steps),
    }
