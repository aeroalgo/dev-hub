"""Freeze / inject QA AC checklist so re-QA cannot raise the bar."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loop.schemas.qa_checklist_freeze import (
    ELIGIBLE_BLOCKER_CLASSES,
    REQA_CYCLE_MAX,
    SCHEMA_LOOP_QA_CHECKLIST_FREEZE,
    QaChecklistFreeze,
)

_DEFAULT_SECTION_011 = [
    "orphan external refs only (API/env/storage/event/DB counterparts); not style/naming/comments",
]

_AC_PLUS_RE = re.compile(
    r"(?ms)^#{2,3}\s*AC(?!\s*[−\-])\b[^\n]*\n(.*?)(?=^#{2,3}\s*AC\s*[−\-]|^#{2,3}\s|\Z)"
)
_AC_MINUS_RE = re.compile(
    r"(?ms)^#{2,3}\s*AC\s*[−\-][^\n]*\n(.*?)(?=^#{2,3}\s|\Z)"
)
_SC_TABLE_ROW_RE = re.compile(
    r"(?m)^\|\s*(SC-\d+)\s*\|\s*([^|]+?)\s*\|"
)
_NUMBERED_RE = re.compile(r"(?m)^\s*(?:\d+\.|[-*])\s+(.+?)\s*$")
_QA_CONSUMES_RE = re.compile(
    r"(?ms)<!--\s*#qa-consumes\s*-->\s*##\s*QA consumes\n(.*?)(?=\n<!--|\Z)"
)
_FREEZE_SHA_RE = re.compile(
    r"(?im)checklist_sha256:\s*`([0-9a-f]{64})`|checklist_sha256:\s*([0-9a-f]{64})"
)
_SECTION_LIST_RE = re.compile(
    r"(?ms)^###\s*(AC\+|AC−|AC-|§\s*0\.11|0\.11|Prior blockers)\s*\n(.*?)(?=^###\s|^##\s|\Z)"
)
_BLOCKER_CLASS_RE = re.compile(
    r"(?i)^\s*(suite_red|ac_gap|leftover|orphan_ref|prior_open|behavior_smoke)\s*:\s*(.+)$"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def checklist_sha256(ac_plus: list[str], ac_minus: list[str], section_011: list[str]) -> str:
    blob = "\n".join(
        [
            "AC+",
            *[f"- {x.strip()}" for x in ac_plus if str(x).strip()],
            "AC-",
            *[f"- {x.strip()}" for x in ac_minus if str(x).strip()],
            "0.11",
            *[f"- {x.strip()}" for x in section_011 if str(x).strip()],
        ]
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _items_from_block(block: str) -> list[str]:
    items: list[str] = []
    for match in _NUMBERED_RE.finditer(block or ""):
        text = match.group(1).strip()
        if text and text.lower() != "none":
            items.append(text)
    return items


def extract_qa_consumes(plan_text: str) -> list[str]:
    match = _QA_CONSUMES_RE.search(plan_text or "")
    if not match:
        return []
    return _items_from_block(match.group(1))


def extract_plan_checklist(plan_text: str) -> tuple[list[str], list[str], list[str], str]:
    """Return (ac_plus, ac_minus, section_011, source_kind). Prefer #qa-consumes when present."""
    consumes = extract_qa_consumes(plan_text)
    ac_plus: list[str] = []
    ac_minus: list[str] = []
    section_011: list[str] = list(_DEFAULT_SECTION_011)
    source = "plan_ac"

    if consumes:
        ac_plus.extend(consumes)
        source = "qa_consumes"

    plus_match = _AC_PLUS_RE.search(plan_text or "")
    if plus_match:
        for item in _items_from_block(plus_match.group(1)):
            if item not in ac_plus:
                ac_plus.append(item)

    minus_match = _AC_MINUS_RE.search(plan_text or "")
    if minus_match:
        ac_minus.extend(_items_from_block(minus_match.group(1)))

    for row in _SC_TABLE_ROW_RE.finditer(plan_text or ""):
        sc_id = row.group(1).strip()
        sc_text = row.group(2).strip()
        line = f"{sc_id}: {sc_text}"
        if line not in ac_plus:
            ac_plus.append(line)

    return ac_plus, ac_minus, section_011, source


def find_plan_md(cwd: Path | str, epic_id: str, role: str = "back") -> Path | None:
    root = Path(cwd).resolve()
    role_l = (role or "back").strip().lower()
    if role_l == "integ":
        role_l = "integration"
    candidates = [
        root / "memory-bank" / role_l / "plan" / epic_id / "md" / "plan.md",
        root / "memory-bank" / role_l / "plan" / f"plan-{epic_id}.md",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def freeze_from_lists(
    *,
    epic_id: str,
    ac_plus: list[str],
    ac_minus: list[str],
    section_011: list[str] | None = None,
    source: str = "plan_ac",
    source_path: str = "",
    prior_blockers: list[str] | None = None,
    verify_scope: str = "full",
    reqa_cycles: int = 0,
) -> QaChecklistFreeze:
    sec = list(section_011 or _DEFAULT_SECTION_011)
    plus = [str(x).strip() for x in ac_plus if str(x).strip()]
    minus = [str(x).strip() for x in ac_minus if str(x).strip()]
    if not plus:
        raise ValueError("qa checklist freeze requires non-empty ac_plus")
    if not minus:
        minus = [
            "no action sentence interpretable as unqualified managed runner without hub-only marker",
        ]
    digest = checklist_sha256(plus, minus, sec)
    return QaChecklistFreeze(
        schema=SCHEMA_LOOP_QA_CHECKLIST_FREEZE,
        epic_id=epic_id,
        ac_plus=plus,
        ac_minus=minus,
        section_011=sec,
        prior_blockers=[str(x).strip() for x in (prior_blockers or []) if str(x).strip()],
        source=source,  # type: ignore[arg-type]
        source_path=source_path,
        checklist_sha256=digest,
        frozen_at=utc_now(),
        verify_scope="prior_only" if verify_scope == "prior_only" else "full",  # type: ignore[arg-type]
        reqa_cycles=max(0, int(reqa_cycles or 0)),
    )


def load_freeze(state: dict[str, Any] | None) -> QaChecklistFreeze | None:
    raw = (state or {}).get("qa_checklist_freeze")
    if not isinstance(raw, dict):
        return None
    try:
        return QaChecklistFreeze.model_validate(raw)
    except Exception:
        return None


def ensure_freeze(
    cwd: Path | str,
    *,
    epic_id: str,
    role: str = "back",
    state: dict[str, Any] | None = None,
    prior_only: bool = False,
) -> QaChecklistFreeze | None:
    """Return existing freeze or create from plan AC/SC / qa-consumes when possible."""
    existing = load_freeze(state)
    if existing and existing.epic_id == epic_id and existing.ac_plus:
        if prior_only and existing.verify_scope != "prior_only":
            data = existing.model_dump(by_alias=True)
            data["verify_scope"] = "prior_only"
            return QaChecklistFreeze.model_validate(data)
        return existing
    if not epic_id:
        return None
    plan_path = find_plan_md(cwd, epic_id, role=role)
    if plan_path is None:
        return existing
    text = plan_path.read_text(encoding="utf-8")
    plus, minus, sec, source = extract_plan_checklist(text)
    if not plus:
        return existing
    try:
        rel = plan_path.relative_to(Path(cwd).resolve()).as_posix()
    except ValueError:
        rel = str(plan_path)
    prior = list(existing.prior_blockers) if existing else []
    cycles = int(existing.reqa_cycles) if existing else 0
    return freeze_from_lists(
        epic_id=epic_id,
        ac_plus=plus,
        ac_minus=minus,
        section_011=sec,
        source=source,
        source_path=rel,
        prior_blockers=prior,
        verify_scope="prior_only" if prior_only else "full",
        reqa_cycles=cycles,
    )


def freeze_from_qa_checks(
    *,
    epic_id: str,
    checks: list[str],
    ac_plus: list[str] | None = None,
    ac_minus: list[str] | None = None,
    section_011: list[str] | None = None,
    blockers: list[str] | None = None,
    source_path: str = "",
    verify_scope: str = "full",
    reqa_cycles: int = 0,
) -> QaChecklistFreeze:
    plus = [str(x).strip() for x in (ac_plus or checks or []) if str(x).strip()]
    minus = [str(x).strip() for x in (ac_minus or []) if str(x).strip()]
    return freeze_from_lists(
        epic_id=epic_id,
        ac_plus=plus,
        ac_minus=minus,
        section_011=section_011,
        source="qa_artifact",
        source_path=source_path,
        prior_blockers=blockers if blockers else None,
        verify_scope=verify_scope,
        reqa_cycles=reqa_cycles,
    )


def with_prior_blockers(freeze: QaChecklistFreeze, blockers: list[str]) -> QaChecklistFreeze:
    cleaned = [str(x).strip() for x in blockers if str(x).strip()]
    data = freeze.model_dump(by_alias=True)
    data["prior_blockers"] = cleaned
    return QaChecklistFreeze.model_validate(data)


def with_verify_scope(freeze: QaChecklistFreeze, scope: str) -> QaChecklistFreeze:
    data = freeze.model_dump(by_alias=True)
    data["verify_scope"] = "prior_only" if scope == "prior_only" else "full"
    return QaChecklistFreeze.model_validate(data)


def bump_reqa_cycle(freeze: QaChecklistFreeze) -> QaChecklistFreeze:
    data = freeze.model_dump(by_alias=True)
    data["reqa_cycles"] = int(data.get("reqa_cycles") or 0) + 1
    return QaChecklistFreeze.model_validate(data)


def persist_freeze(state: dict[str, Any], freeze: QaChecklistFreeze | None) -> dict[str, Any]:
    st = dict(state or {})
    if freeze is None:
        st["qa_checklist_freeze"] = None
        st["qa_reqa_halt"] = None
        st["qa_reqa_cycles"] = None
        st["qa_reqa_sha"] = None
    else:
        st["qa_checklist_freeze"] = freeze.model_dump(by_alias=True)
        st["qa_reqa_cycles"] = freeze.reqa_cycles
        st["qa_reqa_sha"] = freeze.checklist_sha256
        if freeze.reqa_cycles >= REQA_CYCLE_MAX:
            st["qa_reqa_halt"] = True
    return st


def render_freeze_prompt_block(
    freeze: QaChecklistFreeze | None,
    *,
    prior_only: bool = False,
) -> str:
    if freeze is None or not freeze.ac_plus:
        return (
            "## Frozen QA checklist (HARD)\n"
            "- status: missing\n"
            "- Parent MUST derive AC+/AC−/§0.11 from plan AC/SC or #qa-consumes once, then FINISH will freeze.\n"
            "- FORBIDDEN: reformulate or raise bar across QA runs.\n"
            "- Blockers MUST use eligible class prefix: "
            + "|".join(sorted(ELIGIBLE_BLOCKER_CLASSES))
            + ":\n"
        )
    scope = "prior_only" if prior_only or freeze.verify_scope == "prior_only" else "full"
    lines = [
        "## Frozen QA checklist (HARD — runner SoT)",
        f"- schema: `{SCHEMA_LOOP_QA_CHECKLIST_FREEZE}`",
        f"- epic_id: `{freeze.epic_id}`",
        f"- checklist_sha256: `{freeze.checklist_sha256}`",
        f"- source: `{freeze.source}` `{freeze.source_path}`",
        f"- verify_scope: `{scope}`",
        f"- reqa_cycles: `{freeze.reqa_cycles}` / max `{REQA_CYCLE_MAX}`",
        "- Pack verify-qa `AC+` / `AC−` / `§0.11` **exactly** as lists below (1:1 wording).",
        "- FORBIDDEN: rewrite, strengthen, add AC items, or invent style/naming gaps as blockers.",
        "- Eligible blocker prefixes only: "
        + ", ".join(f"`{c}:`" for c in sorted(ELIGIBLE_BLOCKER_CLASSES)),
    ]
    if scope == "prior_only":
        lines.append(
            "- PRIOR_ONLY (HARD): after BUGFIX re-QA — suite + Prior blockers + §0.11 orphans; "
            "do not reopen full AC matrix for new interpretations."
        )
    else:
        lines.append(
            "- Re-QA: same lists + `Prior blockers`; new eligible B* only if a frozen item still fails."
        )
    lines.extend(["", "### AC+"])
    for item in freeze.ac_plus:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### AC−")
    for item in freeze.ac_minus:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### §0.11")
    for item in freeze.section_011:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### Prior blockers")
    if freeze.prior_blockers:
        for item in freeze.prior_blockers:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def read_qa_artifact_lists(
    path: Path,
) -> tuple[list[str], list[str], list[str], list[str], str | None, list[str]]:
    """Return (checks, blockers, ac_plus, ac_minus, checklist_sha256, section_011)."""
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return [], [], [], [], None, []
    if not isinstance(data, dict):
        return [], [], [], [], None, []

    def _as_str_list(key: str) -> list[str]:
        raw = data.get(key) or []
        if not isinstance(raw, list):
            return []
        out: list[str] = []
        for item in raw:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict):
                note = str(item.get("note") or item.get("text") or item.get("id") or "").strip()
                if note:
                    out.append(note)
        return out

    sha = data.get("checklist_sha256")
    sha_s = str(sha).strip() if sha else None
    return (
        _as_str_list("checks"),
        _as_str_list("blockers"),
        _as_str_list("ac_plus"),
        _as_str_list("ac_minus"),
        sha_s or None,
        _as_str_list("section_011"),
    )


def parse_blocker_class(blocker: str) -> tuple[str | None, str]:
    match = _BLOCKER_CLASS_RE.match(blocker or "")
    if not match:
        return None, (blocker or "").strip()
    return match.group(1).lower(), match.group(2).strip()


def validate_blockers_against_freeze(
    blockers: list[str],
    freeze: QaChecklistFreeze | None,
    *,
    require_class: bool = True,
) -> list[str]:
    """Return error strings; empty = ok."""
    errors: list[str] = []
    prior = {p.strip() for p in (freeze.prior_blockers if freeze else []) if p.strip()}
    freeze_items = []
    if freeze:
        freeze_items = [
            *freeze.ac_plus,
            *freeze.ac_minus,
            *freeze.section_011,
            *freeze.prior_blockers,
        ]
    for idx, raw in enumerate(blockers or [], start=1):
        klass, body = parse_blocker_class(raw)
        if require_class and klass is None:
            errors.append(
                f"blocker[{idx}]: missing eligible class prefix "
                f"({'|'.join(sorted(ELIGIBLE_BLOCKER_CLASSES))}): {raw!r}"
            )
            continue
        if klass is not None and klass not in ELIGIBLE_BLOCKER_CLASSES:
            errors.append(f"blocker[{idx}]: unknown class {klass!r}")
            continue
        if freeze is None:
            continue
        if klass == "suite_red" or klass == "leftover" or klass == "behavior_smoke":
            continue
        if klass == "prior_open":
            if prior and body not in prior and not any(body in p or p in body for p in prior):
                errors.append(
                    f"blocker[{idx}]: prior_open body not in frozen prior_blockers: {body!r}"
                )
            continue
        if klass in {"ac_gap", "orphan_ref"} and freeze_items:
            lowered = body.lower()
            ok = any(
                item.lower() in lowered or lowered in item.lower() or item.strip() == body
                for item in freeze_items
            )
            if not ok and freeze.verify_scope == "prior_only" and klass == "ac_gap":
                errors.append(
                    f"blocker[{idx}]: prior_only forbids new ac_gap outside Prior blockers: {body!r}"
                )
            elif not ok and freeze.verify_scope != "prior_only":
                # soft: still allow if class present; optional strict later
                pass
    return errors


def extract_packed_lists_from_prompt(prompt: str) -> tuple[list[str], list[str], list[str]]:
    """Best-effort AC+/AC−/§0.11 lists from spawn prompt (Frozen ### or packed sections)."""
    plus: list[str] = []
    minus: list[str] = []
    sec: list[str] = []
    for match in _SECTION_LIST_RE.finditer(prompt or ""):
        title = match.group(1).lower().replace("−", "-")
        items = _items_from_block(match.group(2))
        if title.startswith("ac+") or title == "ac+":
            plus = items
        elif title.startswith("ac-"):
            minus = items
        elif "0.11" in title:
            sec = items
    if plus or minus or sec:
        return plus, minus, sec

    # Fallback: ## AC+ packed contract sections
    for label, bucket in (
        (r"AC\+", "plus"),
        (r"AC[−\-]", "minus"),
        (r"§?\s*0\.11", "sec"),
    ):
        m = re.search(
            rf"(?ms)^(?:#+\s*)?{label}\s*[:：]?\s*\n(.*?)(?=^(?:#+\s*)?(?:AC\+|AC[−\-]|§?\s*0\.11|ALLOW|VERIFY|Suite|BLOCKERS)\b|\Z)",
            prompt or "",
        )
        if not m:
            continue
        items = _items_from_block(m.group(1))
        if bucket == "plus":
            plus = items
        elif bucket == "minus":
            minus = items
        else:
            sec = items
    return plus, minus, sec


def spawn_freeze_violations(prompt: str, state: dict[str, Any] | None) -> list[str]:
    """Deny reasons when verify-qa spawn AC matrix drifts from frozen sha."""
    freeze = load_freeze(state)
    if freeze is None or not freeze.checklist_sha256:
        return []
    errors: list[str] = []
    sha_match = _FREEZE_SHA_RE.search(prompt or "")
    prompt_sha = (sha_match.group(1) or sha_match.group(2)) if sha_match else ""
    if not prompt_sha:
        errors.append(
            "prompt_incomplete: verify-qa spawn missing Frozen checklist_sha256 "
            f"(expected `{freeze.checklist_sha256}`)"
        )
    elif prompt_sha != freeze.checklist_sha256:
        errors.append(
            "qa_checklist_drift: spawn checklist_sha256 "
            f"`{prompt_sha}` ≠ frozen `{freeze.checklist_sha256}`"
        )

    plus, minus, sec = extract_packed_lists_from_prompt(prompt or "")
    if plus or minus or sec:
        packed_sha = checklist_sha256(
            plus or freeze.ac_plus,
            minus or freeze.ac_minus,
            sec or freeze.section_011,
        )
        # Only enforce when parent packed explicit AC+ list
        if plus and packed_sha != freeze.checklist_sha256:
            # Allow if packed lists equal freeze lists even if section order differs
            if [x.strip() for x in plus] != [x.strip() for x in freeze.ac_plus]:
                errors.append(
                    "qa_checklist_drift: packed AC+ wording ≠ frozen AC+ "
                    f"(spawn sha {packed_sha[:12]}… vs freeze {freeze.checklist_sha256[:12]}…)"
                )
    return errors


def finish_qa_freeze_errors(
    *,
    path: Path,
    freeze: QaChecklistFreeze | None,
    verdict: str,
) -> list[str]:
    checks, blockers, ac_plus, ac_minus, art_sha, section_011 = read_qa_artifact_lists(path)
    errors: list[str] = []
    if freeze and art_sha and art_sha != freeze.checklist_sha256:
        errors.append(
            f"checklist_sha256 drift: artifact `{art_sha}` ≠ freeze `{freeze.checklist_sha256}`"
        )
    if freeze and ac_plus and [x.strip() for x in ac_plus] != [x.strip() for x in freeze.ac_plus]:
        errors.append("ac_plus drift vs frozen checklist")
    if freeze and ac_minus and [x.strip() for x in ac_minus] != [x.strip() for x in freeze.ac_minus]:
        errors.append("ac_minus drift vs frozen checklist")
    if verdict in {"fail", "blocked"}:
        errors.extend(validate_blockers_against_freeze(blockers, freeze, require_class=True))
    _ = (checks, section_011)
    return errors
