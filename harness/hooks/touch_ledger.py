"""Epic/step touch ledger — SoT of files this session actually edited.

Scope checks and verify MUST use this ledger, not whole-repo ``git status``.
Pre-existing dirty files from other epics/sessions are not blockers and MUST NOT
be discarded via ``git checkout --`` / ``git restore`` / ``git reset --hard``.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "loop-touch-ledger/v1"
LEDGER_NAME = "touch-ledger.json"

FOREIGN_DIRTY_BLOCKER_IDS = frozenset(
    {
        "diff_outside_allow",
        "scope_outside_allowlist",
        "out_of_scope_changes",
        "foreign_dirty",
        "git_status_outside_scope",
        "scope_outside",
    }
)

FOREIGN_DIRTY_BLOCKER_ID_RE = re.compile(
    r"(?i)^(?:" + "|".join(re.escape(x) for x in sorted(FOREIGN_DIRTY_BLOCKER_IDS)) + r")$"
)

# Empty ledger: scope/AC− isolation FAILs are not attributable to this step.
EMPTY_LEDGER_SCOPE_BLOCKER_ID_RE = re.compile(
    r"(?i)^(?:"
    r"diff_outside_allow|scope_outside_allowlist|out_of_scope_changes|"
    r"foreign_dirty|git_status_outside_scope|scope_outside|"
    r".*scope_violation.*|.*scope_isolation.*|"
    r"ac_minus_.*(?:scope|codex|transport|out_of_scope|deferred).*"
    r")$"
)

FOREIGN_DIRTY_REPORT_RE = re.compile(
    r"(?is)(?:diff_outside_allow|scope_outside_allowlist|out_of_scope_changes|"
    r"foreign_dirty|git\s+status.*(?:вне|outside)|"
    r"изменен\w*\s+вне\s+(?:scope|ALLOW|allowlist)|"
    r"changes?\s+outside\s+(?:scope|ALLOW|allowlist))"
)

EMPTY_LEDGER_SCOPE_REPORT_RE = re.compile(
    r"(?is)(?:diff_outside_allow|scope_outside|out_of_scope|foreign_dirty|"
    r"scope\s+isolation|вне\s+scope|outside\s+S\d+|deferred\s+to\s+s\d+|"
    r"transport[_\s-]?bind|codex[_\s-]?transport|"
    r"изменен\w*.*Codex|modif(?:y|ies|ied).*Codex|"
    r"не\s+трогать.*Codex|Do not modify Codex)"
)

_VERIFY_FAIL_RE = re.compile(r"(?im)^VERIFY:\s*FAIL\b")

_PATH_IN_TEXT_RE = re.compile(
    r"(?m)(?:^|[\s`|'\"(])("
    r"(?:harness|loop|memory-bank|frontend|apps|tests|bin|\.cursor|\.claude|"
    r"dsh|runtime)[/][\w./-]+"
    r"|[\w./-]+\.(?:py|md|ya?ml|toml|json|ts|tsx|js|jsx|sh)"
    r")"
)

_MATRIX_LABEL_RE = re.compile(r"(?i)^(a|n|i)\d+$")
_SECTION_LABELS = frozenset({"AC+", "AC-", "AC−", "VERIFY", "STEP", "BLOCKERS", "§0.11", "0.11"})



def touch_ledger_path(cwd: str | Path) -> Path:
    from epic_paths import epic_dir

    return epic_dir(cwd) / LEDGER_NAME


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm_rel(cwd: str | Path, path: str | Path) -> str | None:
    root = Path(cwd).expanduser().resolve()
    raw = str(path or "").strip()
    if not raw:
        return None
    p = Path(raw).expanduser()
    try:
        if p.is_absolute():
            rel = p.resolve().relative_to(root)
        else:
            rel = Path(str(p).replace("\\", "/").lstrip("./"))
    except (OSError, ValueError):
        return None
    out = str(rel).replace("\\", "/").strip().lstrip("./")
    if not out or ".." in Path(out).parts:
        return None
    return out


def empty_ledger(
    *,
    epic_id: str | None = None,
    step_id: str | None = None,
    phase_run_id: str | None = None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "epic_id": str(epic_id or "").strip() or None,
        "step_id": str(step_id or "").strip() or None,
        "phase_run_id": str(phase_run_id or "").strip() or None,
        "updated_at": _utc_now(),
        "paths": [],
    }


def load_touch_ledger(cwd: str | Path) -> dict[str, Any]:
    path = touch_ledger_path(cwd)
    if not path.is_file():
        return empty_ledger()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_ledger()
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return empty_ledger()
    paths = data.get("paths")
    if not isinstance(paths, list):
        data["paths"] = []
    return data


def save_touch_ledger(cwd: str | Path, data: dict[str, Any]) -> Path:
    path = touch_ledger_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(data)
    payload["schema"] = SCHEMA
    payload["updated_at"] = _utc_now()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)
    return path


def reset_touch_ledger(
    cwd: str | Path,
    *,
    epic_id: str | None = None,
    step_id: str | None = None,
    phase_run_id: str | None = None,
) -> dict[str, Any]:
    data = empty_ledger(
        epic_id=epic_id,
        step_id=step_id,
        phase_run_id=phase_run_id,
    )
    save_touch_ledger(cwd, data)
    return data


def ensure_touch_ledger_identity(
    cwd: str | Path,
    *,
    epic_id: str | None,
    step_id: str | None,
    phase_run_id: str | None = None,
) -> dict[str, Any]:
    """Reset ledger only when armed epic/step changes.

    ``phase_run_id`` updates in place. A new prepare/session must NOT wipe
    paths already recorded for the same epic+step — otherwise Codex/Claude
    edits vanish and verify falls back to whole-repo ``git status``.
    """
    cur = load_touch_ledger(cwd)
    eid = str(epic_id or "").strip() or None
    sid = str(step_id or "").strip() or None
    prid = str(phase_run_id or "").strip() or None
    same_step = (cur.get("epic_id") or None) == eid and (cur.get("step_id") or None) == sid
    if same_step and cur.get("schema") == SCHEMA:
        dirty = False
        if prid and (cur.get("phase_run_id") or None) != prid:
            cur["phase_run_id"] = prid
            dirty = True
        if dirty:
            save_touch_ledger(cwd, cur)
        return cur
    return reset_touch_ledger(
        cwd,
        epic_id=eid,
        step_id=sid,
        phase_run_id=prid or cur.get("phase_run_id"),
    )


def record_touch(
    cwd: str | Path,
    path: str | Path,
    *,
    operation: str = "edit",
    epic_id: str | None = None,
    step_id: str | None = None,
    phase_run_id: str | None = None,
) -> dict[str, Any]:
    """Append a touched path for the current epic/step (idempotent per path)."""
    rel = _norm_rel(cwd, path)
    if not rel:
        return load_touch_ledger(cwd)

    eid = epic_id
    sid = step_id
    prid = phase_run_id
    if eid is None or sid is None or prid is None:
        try:
            from epic.core import load_epic_state

            st = load_epic_state(cwd) or {}
            eid = eid or st.get("armed_epic") or st.get("epic_id") or st.get("epic")
            sid = sid or st.get("armed_step") or st.get("step")
            prid = prid or st.get("phase_run_id")
        except Exception:
            pass

    data = ensure_touch_ledger_identity(
        cwd,
        epic_id=str(eid or "").strip() or None,
        step_id=str(sid or "").strip() or None,
        phase_run_id=str(prid or "").strip() or None,
    )
    entries = list(data.get("paths") or [])
    op = str(operation or "edit").strip() or "edit"
    found = False
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("path") or "") == rel:
            entry["operation"] = op
            entry["at"] = _utc_now()
            found = True
            break
    if not found:
        entries.append({"path": rel, "operation": op, "at": _utc_now()})
    data["paths"] = entries
    save_touch_ledger(cwd, data)
    return data


def touched_paths(
    cwd: str | Path,
    *,
    epic_id: str | None = None,
    step_id: str | None = None,
) -> list[str]:
    data = load_touch_ledger(cwd)
    if epic_id and (data.get("epic_id") or None) != str(epic_id).strip():
        return []
    if step_id and (data.get("step_id") or None) != str(step_id).strip():
        return []
    out: list[str] = []
    seen: set[str] = set()
    for entry in data.get("paths") or []:
        if not isinstance(entry, dict):
            continue
        rel = str(entry.get("path") or "").strip()
        if not rel or rel in seen:
            continue
        seen.add(rel)
        out.append(rel)
    return out


def touch_ledger_prompt_block(cwd: str | Path) -> str:
    data = load_touch_ledger(cwd)
    paths = touched_paths(cwd)
    lines = [
        "## Touch ledger (scope SoT — HARD)",
        f"epic_id: {data.get('epic_id') or '—'}",
        f"step_id: {data.get('step_id') or '—'}",
        "Scope of *this* session edits = paths below (hook-recorded Write/Edit).",
        "Whole-repo `git status` dirty ≠ blocker. Foreign/pre-existing dirty MUST be ignored.",
        "EMPTY ledger = оправдание: нет записанных правок шага → "
        "FORBIDDEN FAIL по scope/git dirty / AC− «вне scope» / Codex deferred в worktree.",
        "FORBIDDEN: `git checkout --` / `git restore` / `git reset --hard` / `git clean` "
        "to discard files not listed here.",
        "REVERT только path из этого ledger, если он вне shard `files:` allowlist.",
    ]
    if paths:
        lines.append("touched:")
        for p in paths:
            lines.append(f"- `{p}`")
    else:
        lines.append(
            "touched: (empty — no Write/Edit recorded; scope/git dirty FAIL → ignore)"
        )
    return "\n".join(lines)


def shard_allowlist_paths(cwd: str | Path) -> list[str]:
    """files:/deletes: from armed implement shard + implement yaml path itself."""
    try:
        from epic.core import load_epic_state
        from epic_yaml import load_implement, resolve_implement_path
    except Exception:
        return []

    st = load_epic_state(cwd) or {}
    step_id = str(st.get("armed_step") or "").strip()
    epic_id = str(st.get("armed_epic") or st.get("epic_id") or "").strip()
    role = str(st.get("armed_role") or st.get("role") or "back").strip().lower() or "back"
    if not step_id or not epic_id:
        return []
    try:
        # Prefer on-disk implement artifact; resolve by convention when present.
        rel = resolve_implement_path(
            cwd,
            role,
            epic_id,
            step_id,
            plan_id=epic_id,
        )
        path = Path(cwd) / rel if not Path(rel).is_absolute() else Path(rel)
        if not path.is_file():
            return []
        doc = load_implement(path)
        out: list[str] = []
        seen: set[str] = set()
        for raw in list(doc.files or []) + list(doc.deletes or []):
            n = _norm_rel(cwd, raw)
            if not n or n in seen:
                continue
            seen.add(n)
            out.append(n)
        impl_rel = _norm_rel(cwd, path)
        if impl_rel and impl_rel not in seen:
            out.append(impl_rel)
        return out
    except Exception:
        return []


def scope_check(cwd: str | Path) -> dict[str, Any]:
    """Machine scope SoT: only touch-ledger paths can be out-of-scope."""
    ledger = load_touch_ledger(cwd)
    ledger_paths = touched_paths(cwd)
    allow = set(shard_allowlist_paths(cwd))
    # Empty allowlist → cannot judge OOS; do not invent violations from git.
    oos = [p for p in ledger_paths if allow and p not in allow]
    return {
        "schema": "loop-scope-check/v1",
        "epic_id": ledger.get("epic_id"),
        "step_id": ledger.get("step_id"),
        "ledger_paths": ledger_paths,
        "allowlist_paths": sorted(allow),
        "oos_ledger_paths": oos,
        "foreign_dirty_is_blocker": False,
        "ok": len(oos) == 0,
    }


def _blocker_ids_from_report(report_text: str) -> list[str]:
    ids: list[str] = []
    in_blockers = False
    for line in str(report_text or "").splitlines():
        s = line.strip()
        if re.match(r"(?i)^BLOCKERS?\s*:", s):
            in_blockers = True
            m = re.match(
                r"(?i)^BLOCKERS?:\s*`?([A-Za-z0-9_][A-Za-z0-9_.:-]*)`?(?:\s|$)",
                s,
            )
            if m:
                bid = m.group(1).strip()
                if bid.upper() not in _SECTION_LABELS and bid.upper() not in {
                    "PASS",
                    "FAIL",
                    "BLOCKED",
                    "DONE",
                    "OK",
                }:
                    ids.append(bid)
            continue
        if in_blockers and re.match(
            r"(?i)^\s*(?:AC\+|AC[−\-]|§\s*0\.11|0\.11\b|VERIFY\s*:|STEP\s*:|Модель\s*:)",
            s,
        ):
            break
        if not in_blockers:
            continue
        if not s.startswith(("-", "*")):
            continue
        m = re.match(
            r"^[-*]\s*`?([A-Za-z0-9_][A-Za-z0-9_.:-]*)`?\s*(?:—|-|\||$)",
            s,
        )
        if not m:
            continue
        bid = m.group(1).strip()
        if bid.upper() in _SECTION_LABELS or bid.upper() in {
            "PASS",
            "FAIL",
            "BLOCKED",
            "DONE",
            "OK",
        }:
            continue
        ids.append(bid)
    return ids


def _ac_plus_failed(text: str) -> bool:
    """True only if the AC+ section itself reports FAIL (not later AC−)."""
    in_ac_plus = False
    for line in str(text or "").splitlines():
        if re.match(r"(?i)^\s*AC\+\s*:?\s*$", line) or re.match(r"(?i)^\s*AC\+\s*:", line):
            in_ac_plus = True
            after = line.split(":", 1)[1] if ":" in line else ""
            if re.search(r"(?i)\bFAIL\b", after):
                return True
            continue
        if in_ac_plus and re.match(
            r"(?i)^\s*(?:AC[−\-]\s*:|§\s*0\.11|0\.11\b|VERIFY\s*:|STEP\s*:|BLOCKERS?\s*:)",
            line,
        ):
            break
        if in_ac_plus and re.search(r"(?i)\bFAIL\b", line):
            return True
    return False


def _is_scope_blocker_id(blocker_id: str) -> bool:
    bid = str(blocker_id or "").strip()
    if not bid:
        return False
    return bool(
        FOREIGN_DIRTY_BLOCKER_ID_RE.match(bid)
        or EMPTY_LEDGER_SCOPE_BLOCKER_ID_RE.match(bid)
    )


def should_promote_foreign_dirty_fail(
    cwd: str | Path,
    report_text: str | None,
) -> tuple[bool, list[str]]:
    """Promote FAIL→PASS when scope complaint is not attributable to this step.

    Rules:
    - Empty touch-ledger = оправдание: нет записанных правок шага → scope/git/
      AC− isolation FAIL не блокирует (VERIFY/AC+ FAIL не promote).
    - Non-empty: promote only classic foreign-dirty; real OOS = path in ledger
      and outside shard allowlist.
    """
    text = str(report_text or "")
    if not text.strip():
        return False, []

    ledger = set(touched_paths(cwd))

    if not ledger:
        if _VERIFY_FAIL_RE.search(text):
            return False, ["empty_ledger_but_verify_fail"]
        if _ac_plus_failed(text):
            return False, ["empty_ledger_but_ac_plus_fail"]

        other: list[str] = []
        scope_bids: list[str] = []
        for bid in _blocker_ids_from_report(text):
            if not bid or bid.upper() in _SECTION_LABELS or _MATRIX_LABEL_RE.match(bid):
                continue
            if _is_scope_blocker_id(bid):
                scope_bids.append(bid)
            else:
                other.append(bid)
        if other:
            return False, ["other_blockers:" + ",".join(other)]

        if (
            scope_bids
            or EMPTY_LEDGER_SCOPE_REPORT_RE.search(text)
            or FOREIGN_DIRTY_REPORT_RE.search(text)
        ):
            return True, [
                "empty_touch_ledger: no recorded step edits — scope/git dirty FAIL ignored",
            ]
        return False, []

    if not FOREIGN_DIRTY_REPORT_RE.search(text):
        return False, []

    other = []
    for bid in _blocker_ids_from_report(text):
        if not bid or bid.upper() in _SECTION_LABELS or _MATRIX_LABEL_RE.match(bid):
            continue
        if FOREIGN_DIRTY_BLOCKER_ID_RE.match(bid):
            continue
        other.append(bid)
    if other:
        return False, ["other_blockers:" + ",".join(other)]

    allow = set(shard_allowlist_paths(cwd))
    mentioned = []
    for m in _PATH_IN_TEXT_RE.finditer(text):
        p = m.group(1).strip().strip("`").lstrip("./")
        if p:
            mentioned.append(p)
    implicated = [
        p
        for p in mentioned
        if p in ledger and (not allow or p not in allow)
    ]
    if implicated:
        return False, ["ledger_oos_in_report:" + ",".join(sorted(set(implicated)))]

    return True, [
        "foreign_dirty_ignored: git dirty outside touch-ledger is not a scope blocker",
    ]

