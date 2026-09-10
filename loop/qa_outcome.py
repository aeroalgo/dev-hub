"""Deterministic QA outcome classifier + suite plan after BUGFIX."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from loop.schemas.qa_outcome import (
    SCHEMA_LOOP_QA_OUTCOME,
    QaNextAction,
    QaOutcome,
    QaOutcomeKind,
    QaSignals,
    QaSuiteScope,
)

RUNTIME_PREFIXES = (
    "loop/",
    "harness/",
    ".claude/hooks/",
    "bin/",
    "dsh/",
)

_PATH_RE = re.compile(
    r"(?m)(?:^|\s|`)((?:loop|harness|bin|dsh|\.claude/hooks)[/][\w./\-]+\.(?:py|sh|md|toml|yaml|yml|json))"
)
_FILES_LINE_RE = re.compile(r"(?im)^(?:[-*]\s*)?(?:files?|changed|paths?)\s*[:=]\s*(.+)$")


def _norm_path(path: str) -> str:
    return str(path or "").replace("\\", "/").lstrip("./")


def is_runtime_path(path: str) -> bool:
    norm = _norm_path(path)
    return any(norm.startswith(prefix) for prefix in RUNTIME_PREFIXES)



def extract_changed_paths(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in _PATH_RE.finditer(text or ""):
        path = match.group(1).replace(chr(92), chr(47))
        if path not in seen:
            seen.add(path)
            found.append(path)
    for match in _FILES_LINE_RE.finditer(text or ""):
        for token in re.split(r"[\s,]+", match.group(1).strip()):
            token = token.strip("`\"' ")
            if not token or chr(47) not in token:
                continue
            if token not in seen:
                seen.add(token)
                found.append(token)
    return found


def suite_plan_after_changes(
    changed_paths: list[str],
    *,
    epic_id: str = "",
) -> QaOutcome:
    """Fail-closed: unknown changes -> full suite."""
    paths = [_norm_path(p) for p in changed_paths if str(p).strip()]
    if not paths:
        return QaOutcome(
            schema=SCHEMA_LOOP_QA_OUTCOME,
            kind="all_green",
            next_action="verify_qa",
            suite_scope="full",
            suite_command='bin/pytest -q --tb=line',
            reasons=["unknown_changes_fail_closed_full_suite"],
            changed_paths=[],
            epic_id=epic_id,
        )
    runtime = [p for p in paths if is_runtime_path(p)]
    if runtime:
        return QaOutcome(
            schema=SCHEMA_LOOP_QA_OUTCOME,
            kind="all_green",
            next_action="verify_qa",
            suite_scope="full",
            suite_command='bin/pytest -q --tb=line',
            reasons=["runtime_paths_changed"],
            changed_paths=paths,
            epic_id=epic_id,
        )
    marker = chr(47) + "tests" + chr(47)
    testish = [p for p in paths if marker in p or p.startswith("tests" + chr(47)) or p.endswith("_test.py") or p.startswith("test_")]
    targets = testish or [p for p in paths if p.endswith(".py")]
    if not targets:
        return QaOutcome(
            schema=SCHEMA_LOOP_QA_OUTCOME,
            kind="all_green",
            next_action="verify_qa",
            suite_scope="full",
            suite_command='bin/pytest -q --tb=line',
            reasons=["no_pytestable_targets_fail_closed_full_suite"],
            changed_paths=paths,
            epic_id=epic_id,
        )
    cmd = "bin" + chr(47) + "pytest " + " ".join(targets) + " -q --tb=line"
    return QaOutcome(
        schema=SCHEMA_LOOP_QA_OUTCOME,
        kind="all_green",
        next_action="verify_qa",
        suite_scope="targeted",
        suite_command=cmd,
        reasons=["non_runtime_changes_targeted_suite"],
        changed_paths=paths,
        epic_id=epic_id,
    )


def classify_qa_outcome(signals: QaSignals | dict[str, Any]) -> QaOutcome:
    """Pure classifier: signals -> sole next_action."""
    sig = signals if isinstance(signals, QaSignals) else QaSignals.model_validate(signals)
    scope: QaSuiteScope = sig.suite_scope
    command = sig.suite_command or 'bin/pytest -q --tb=line'
    common = {
        "schema": SCHEMA_LOOP_QA_OUTCOME,
        "suite_scope": scope,
        "suite_command": command,
        "changed_paths": list(sig.changed_paths),
        "epic_id": sig.epic_id,
        "transport_retries": sig.transport_retries,
    }

    if sig.transport_broken:
        if sig.transport_retries >= 1:
            return QaOutcome(**common, kind="transport_broken", next_action="need_human", reasons=["transport_broken_after_retry"])
        return QaOutcome(**common, kind="transport_broken", next_action="retry_spawn", reasons=["transport_broken_retry_once"])

    if sig.suite_ok is False:
        reasons = ["suite_red"]
        if not sig.suite_is_full and scope == "full":
            reasons.append("suite_not_full_reported_as_red")
        return QaOutcome(**common, kind="suite_red", next_action="bugfix", reasons=reasons)

    if sig.plan_mismatch:
        return QaOutcome(**common, kind="plan_mismatch", next_action="bugfix", reasons=["plan_runtime_mismatch"])

    if sig.ac_gap and sig.verify_verdict is None:
        return QaOutcome(**common, kind="ac_gap", next_action="bugfix", reasons=["parent_ac_gap_before_verify"])

    if sig.verify_verdict in {"FAIL", "BLOCKED"}:
        return QaOutcome(**common, kind="ac_gap", next_action="bugfix", reasons=[f"verify_qa_{sig.verify_verdict.lower()}"])

    if sig.verify_verdict == "PASS":
        return QaOutcome(**common, kind="all_green", next_action="done", reasons=["verify_qa_pass"])

    if sig.suite_ok is True:
        return QaOutcome(**common, kind="all_green", next_action="verify_qa", reasons=["suite_green_await_verify"])

    return QaOutcome(**common, kind="all_green", next_action="verify_qa", reasons=["suite_pending_or_unknown_default_verify_path"])


def resolve_qa_suite_plan(cwd: str | Path, state: dict[str, Any] | None = None) -> QaOutcome:
    """Suite command for current QA arm (full by default; after BUGFIX may be targeted)."""
    st = dict(state or {})
    rerun = st.get("qa_after_bugfix")
    epic_id = str(st.get("armed_epic") or st.get("epic_id") or "")
    if not isinstance(rerun, dict):
        return QaOutcome(schema=SCHEMA_LOOP_QA_OUTCOME, kind="all_green", next_action="verify_qa", suite_scope="full", suite_command='bin/pytest -q --tb=line', reasons=["fresh_qa_full_suite"], epic_id=epic_id)
    scope = str(rerun.get("suite_scope") or "full").strip().lower()
    command = str(rerun.get("suite_command") or "").strip()
    paths = [str(p) for p in (rerun.get("changed_paths") or []) if str(p).strip()]
    if scope == "targeted" and command:
        return QaOutcome(schema=SCHEMA_LOOP_QA_OUTCOME, kind="all_green", next_action="verify_qa", suite_scope="targeted", suite_command=command, reasons=["qa_after_bugfix_targeted"], changed_paths=paths, epic_id=str(rerun.get("epic_id") or epic_id))
    if paths:
        return suite_plan_after_changes(paths, epic_id=str(rerun.get("epic_id") or epic_id))
    return QaOutcome(schema=SCHEMA_LOOP_QA_OUTCOME, kind="all_green", next_action="verify_qa", suite_scope="full", suite_command='bin/pytest -q --tb=line', reasons=["qa_after_bugfix_default_full"], epic_id=str(rerun.get("epic_id") or epic_id))


def render_qa_outcome_policy(outcome: QaOutcome) -> str:
    """Prompt block — agent follows classifier, does not invent a second path."""
    lines = [
        "## QA outcome classifier (HARD — runner SoT)",
        f"- schema: `{SCHEMA_LOOP_QA_OUTCOME}`",
        f"- suite_scope: `{outcome.suite_scope}`",
        f"- suite_command: `{outcome.suite_command}`",
        f"- planned next_action if signals green: `{outcome.next_action}`",
        "- Classify after the single suite (and optional verify) with these kinds only:",
        "  `suite_red` | `plan_mismatch` | `ac_gap` | `transport_broken` | `all_green`",
        "- Mapping:",
        "  - suite_red / plan_mismatch / ac_gap -> next_action=bugfix (qa-*.yaml fail|blocked, mb-finish qa). FORBIDDEN: verify-qa, repair-loop, second suite.",
        "  - all_green after suite -> next_action=verify_qa (AC review only; do not re-run pytest).",
        "  - verify PASS -> done; verify FAIL/BLOCKED -> bugfix.",
        "  - transport_broken -> one retry_spawn; then need_human.",
        "- verify-qa must NOT re-run suite; it reviews AC+/AC-/section 0.11 against Suite results.",
    ]
    if outcome.changed_paths:
        lines.append("- changed_paths: " + ", ".join(f"`{p}`" for p in outcome.changed_paths[:20]))
    if outcome.reasons:
        lines.append("- plan_reasons: " + ", ".join(outcome.reasons))
    return chr(10).join(lines) + chr(10)


def action_for_kind(kind: QaOutcomeKind) -> QaNextAction:
    return {
        "suite_red": "bugfix",
        "plan_mismatch": "bugfix",
        "ac_gap": "bugfix",
        "transport_broken": "retry_spawn",
        "all_green": "verify_qa",
    }[kind]
