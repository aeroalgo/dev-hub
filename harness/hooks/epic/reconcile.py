"""Spec reconcile — bounded path checks: decompose as_built/delta/plan layout vs repo."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness.hooks.epic_index import load_index_yaml
from harness.hooks.epic_portfolio import _ACTIVE_HEADER_RE, _split_cells, _table_block
from harness.hooks.epic_yaml import load_decompose, load_implement

REPORT_SCHEMA = "reconcile-report/v1"

_PATH_EXT = frozenset(
    {
        ".py",
        ".md",
        ".yaml",
        ".yml",
        ".mdc",
        ".json",
        ".env",
        ".sh",
        ".ts",
        ".tsx",
        ".js",
        ".toml",
        ".txt",
    }
)
_PATH_PREFIXES = (
    "memory-bank/",
    ".claude/",
    ".cursor/",
    "loop/",
    "frontend/",
    "src/",
    "tests/",
    "test/",
)
_PLAN_LAYOUT_ROW = re.compile(
    r"^\|\s*`?([\w./-]+)`?\s*\|\s*(?:Create|Modify|Delete|Remove|Add)\b",
    re.I | re.M,
)
_DELTA_ADD = re.compile(r"^([\w./-]+)\s+ADD\b", re.I)
_BACKTICK_PATH = re.compile(r"`([\w./-]+\.[a-z0-9]+)`", re.I)


@dataclass(frozen=True)
class EpicBundle:
    epic_id: str
    plan_id: str
    plan_path: Path
    decompose_index: Path
    implement_dir: Path | None


def list_active_epic_ids(cwd: Path) -> list[str]:
    tasks = cwd / "memory-bank" / "tasks.md"
    if not tasks.is_file():
        return []
    text = tasks.read_text(encoding="utf-8")
    block = _table_block(text, _ACTIVE_HEADER_RE)
    if block is None:
        return []
    _, _, lines = block
    out: list[str] = []
    for line in lines:
        cells = _split_cells(line)
        if len(cells) < 5:
            continue
        if cells[0].startswith("----") or cells[0].lower() == "id":
            continue
        if cells[4].strip().lower() == "active":
            eid = cells[0].strip()
            if eid:
                out.append(eid)
    return out


def _epic_id_from_key(key: str, plan_id: str) -> str:
    for candidate in (key, plan_id):
        m = re.match(r"^(T-HUB-\d+)", candidate)
        if m:
            return m.group(1)
    return plan_id


def resolve_epic_bundle(cwd: Path, epic_or_plan_id: str) -> EpicBundle | None:
    key = (epic_or_plan_id or "").strip()
    if not key:
        return None
    plan_root = cwd / "memory-bank" / "back" / "plan"
    candidates = sorted(plan_root.glob(f"decompose-{key}*/index.yaml"))
    if not candidates:
        exact_plan = plan_root / f"plan-{key}.md"
        if exact_plan.is_file():
            candidates = sorted(plan_root.glob(f"decompose-{key}/index.yaml"))
            if not candidates:
                candidates = sorted(plan_root.glob(f"decompose-{key}-*/index.yaml"))
    if not candidates:
        return None
    index_path = candidates[0]
    index_doc = load_index_yaml(index_path)
    plan_id = str(index_doc.get("plan_id") or "").strip()
    if not plan_id:
        return None
    plan_path = plan_root / f"plan-{plan_id}.md"
    if not plan_path.is_file():
        return None
    epic_id = _epic_id_from_key(key, plan_id)
    implement_dir = cwd / "memory-bank" / "back" / "implement" / f"implement-{plan_id}"
    return EpicBundle(
        epic_id=epic_id,
        plan_id=plan_id,
        plan_path=plan_path,
        decompose_index=index_path,
        implement_dir=implement_dir if implement_dir.is_dir() else None,
    )


def looks_like_repo_path(token: str) -> bool:
    s = (token or "").strip().strip('"').strip("'")
    if not s or " " in s:
        return False
    if not re.match(r"^[\w./-]+$", s):
        return False
    if s.startswith(_PATH_PREFIXES):
        return True
    if "/" not in s:
        return False
    suffix = Path(s).suffix.lower()
    return suffix in _PATH_EXT or s.startswith(".")


def extract_path_tokens(text: str) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    for m in _BACKTICK_PATH.finditer(text):
        tok = m.group(1)
        if looks_like_repo_path(tok):
            found.append(tok)
    stripped = text.strip()
    if looks_like_repo_path(stripped):
        found.append(stripped)
    m_add = _DELTA_ADD.match(stripped)
    if m_add and looks_like_repo_path(m_add.group(1)):
        found.append(m_add.group(1))
    first = stripped.split()[0] if stripped.split() else ""
    if first and looks_like_repo_path(first):
        found.append(first)
    out: list[str] = []
    seen: set[str] = set()
    for p in found:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def paths_from_plan_layout(plan_path: Path) -> list[str]:
    if not plan_path.is_file():
        return []
    text = plan_path.read_text(encoding="utf-8")
    out: list[str] = []
    seen: set[str] = set()
    for m in _PLAN_LAYOUT_ROW.finditer(text):
        p = m.group(1).strip()
        if looks_like_repo_path(p) and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _context_paths(context: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ("files", "produces"):
        raw = context.get(key)
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, str):
                    out.extend(extract_path_tokens(item))
    return out


def _load_steps(index_path: Path) -> list[dict[str, Any]]:
    doc = load_index_yaml(index_path)
    steps = doc.get("steps")
    return steps if isinstance(steps, list) else []


def _implement_path(implement_dir: Path | None, step_id: str, step_file: str) -> Path | None:
    if implement_dir is None or not implement_dir.is_dir():
        return None
    sid = step_id.lower()
    stem = Path(step_file).stem
    direct = implement_dir / f"{sid}-{stem.split('-', 1)[-1]}.yaml"
    if direct.is_file():
        return direct
    for p in implement_dir.glob(f"{sid}-*.yaml"):
        return p
    return None


def _collect_allowed_deletes(cwd: Path, bundle: EpicBundle) -> set[str]:
    allowed: set[str] = set()
    for step in _load_steps(bundle.decompose_index):
        step_id = str(step.get("id") or "").lower()
        shard_name = str(step.get("file") or "")
        dec_path = bundle.decompose_index.parent / shard_name
        if dec_path.is_file():
            try:
                dec = load_decompose(dec_path)
                for item in dec.deletes:
                    allowed.update(extract_path_tokens(item))
            except Exception:
                pass
        impl_path = _implement_path(bundle.implement_dir, step_id, shard_name)
        if impl_path and impl_path.is_file():
            try:
                impl = load_implement(impl_path)
                if impl.status == "completed":
                    for item in impl.deletes:
                        allowed.update(extract_path_tokens(item))
            except Exception:
                pass
    return allowed


def reconcile_epic(cwd: Path, bundle: EpicBundle) -> dict[str, Any]:
    root = cwd.resolve()
    findings: list[dict[str, Any]] = []
    finding_seq = 0
    allowed_deletes = _collect_allowed_deletes(root, bundle)

    def add(category: str, severity: str, message: str, *, path: str, step_id: str = "") -> None:
        nonlocal finding_seq
        finding_seq += 1
        findings.append(
            {
                "id": f"RC-{finding_seq:03d}",
                "category": category,
                "severity": severity,
                "message": message,
                "plan_id": bundle.plan_id,
                "step_id": step_id,
                "path": path,
            }
        )

    for layout_path in paths_from_plan_layout(bundle.plan_path):
        if not (root / layout_path).exists() and layout_path not in allowed_deletes:
            add(
                "missing_plan_path",
                "HIGH",
                f"plan layout path missing in repo: {layout_path}",
                path=layout_path,
            )

    constitution = root / "memory-bank" / "constitution.md"
    if not constitution.is_file():
        add(
            "constitution_missing",
            "LOW",
            "memory-bank/constitution.md not present (soft)",
            path="memory-bank/constitution.md",
        )

    for step in _load_steps(bundle.decompose_index):
        step_id = str(step.get("id") or "").lower()
        shard_name = str(step.get("file") or "")
        dec_path = bundle.decompose_index.parent / shard_name
        if not dec_path.is_file():
            continue
        try:
            dec = load_decompose(dec_path)
        except Exception:
            continue
        for ctx_path in _context_paths(dec.context if isinstance(dec.context, dict) else {}):
            if not (root / ctx_path).exists() and ctx_path not in allowed_deletes:
                add(
                    "stale_as_built",
                    "MEDIUM",
                    f"context path missing in repo: {ctx_path}",
                    path=ctx_path,
                    step_id=step_id,
                )
        for item in dec.as_built:
            for path in extract_path_tokens(item):
                if not (root / path).exists() and path not in allowed_deletes:
                    add(
                        "stale_as_built",
                        "HIGH",
                        f"as_built claims path missing in repo: {path}",
                        path=path,
                        step_id=step_id,
                    )
        impl_path = _implement_path(bundle.implement_dir, step_id, shard_name)
        impl_completed = False
        if impl_path and impl_path.is_file():
            try:
                impl = load_implement(impl_path)
                impl_completed = impl.status == "completed"
            except Exception:
                impl_completed = False
        if impl_completed:
            for item in dec.delta:
                for path in extract_path_tokens(item):
                    if not (root / path).exists() and path not in allowed_deletes:
                        add(
                            "missing_delta",
                            "HIGH",
                            f"completed step delta path missing in repo: {path}",
                            path=path,
                            step_id=step_id,
                        )

    high_count = sum(1 for f in findings if f["severity"] == "HIGH")
    return {
        "schema": REPORT_SCHEMA,
        "plan_id": bundle.plan_id,
        "epic_id": bundle.epic_id,
        "findings": findings,
        "findings_total": len(findings),
        "high_count": high_count,
    }


def reconcile_active_epics(cwd: Path) -> dict[str, Any]:
    root = Path(cwd)
    epic_ids = list_active_epic_ids(root)
    reports: list[dict[str, Any]] = []
    errors: list[str] = []
    for epic_id in epic_ids:
        bundle = resolve_epic_bundle(root, epic_id)
        if bundle is None:
            errors.append(f"unknown epic bundle for {epic_id}")
            continue
        reports.append(reconcile_epic(root, bundle))
    high_total = sum(r.get("high_count", 0) for r in reports)
    return {
        "schema": REPORT_SCHEMA,
        "mode": "active_sweep",
        "epic_ids": epic_ids,
        "reports": reports,
        "errors": errors,
        "findings_total": sum(r.get("findings_total", 0) for r in reports),
        "high_count": high_total,
    }


def reconcile_plan_id(cwd: Path, plan_id: str) -> dict[str, Any]:
    bundle = resolve_epic_bundle(Path(cwd), plan_id)
    if bundle is None:
        return {
            "schema": REPORT_SCHEMA,
            "ok": False,
            "error": f"unknown plan-id: {plan_id}",
            "exit_code": 2,
        }
    report = reconcile_epic(Path(cwd), bundle)
    report["mode"] = "single"
    report["ok"] = True
    report["exit_code"] = 0
    return report


def format_report_text(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    mode = payload.get("mode", "")
    lines.append(f"reconcile-spec ({mode or 'report'})")
    if payload.get("epic_ids"):
        lines.append(f"active epics: {', '.join(payload['epic_ids'])}")
    reports = payload.get("reports")
    if isinstance(reports, list):
        for rep in reports:
            lines.append(f"\n[{rep.get('plan_id')}] findings={rep.get('findings_total')} high={rep.get('high_count')}")
            for f in rep.get("findings") or []:
                lines.append(
                    f"  {f.get('id')} {f.get('severity')} {f.get('category')}: {f.get('message')}"
                )
        lines.append(
            f"\ntotal findings={payload.get('findings_total')} high={payload.get('high_count')}"
        )
        for err in payload.get("errors") or []:
            lines.append(f"WARN: {err}")
        return "\n".join(lines)
    if payload.get("error"):
        return str(payload["error"])
    lines.append(f"plan_id={payload.get('plan_id')} findings={payload.get('findings_total')} high={payload.get('high_count')}")
    for f in payload.get("findings") or []:
        lines.append(f"  {f.get('id')} {f.get('severity')} {f.get('category')}: {f.get('message')}")
    return "\n".join(lines)


def run_reconcile_spec(
    cwd: str | Path,
    *,
    plan_id: str | None = None,
    fmt: str = "json",
    strict: bool = False,
) -> dict[str, Any]:
    root = Path(cwd)
    if plan_id:
        payload = reconcile_plan_id(root, plan_id)
    else:
        payload = reconcile_active_epics(root)
        payload["ok"] = True
        payload["exit_code"] = 0
    high = int(payload.get("high_count") or 0)
    if strict and high > 0:
        payload["exit_code"] = 1
    elif payload.get("exit_code") is None:
        payload["exit_code"] = 0
    payload["text"] = format_report_text(payload)
    payload["format"] = fmt
    return payload
