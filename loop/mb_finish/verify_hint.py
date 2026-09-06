"""Map verify subagent types to mb-finish CLI hints after VERDICT."""

from __future__ import annotations

import re
from pathlib import Path

VERIFY_MB_FINISH_SUBCMD: dict[str, str] = {
    "verify": "implement",
    "verify-implement": "implement",
    "verify-bugfix": "bugfix",
    "verify-decompose": "decompose",
    "verify-qa": "qa",
    "reviewer": "qa",
    "analyze-verify": "analyze",
    "verify-script": "script",
    "verify-edit": "edit",
    "verify-publish": "publish",
}

VERIFY_FINISH_AGENTS = frozenset(VERIFY_MB_FINISH_SUBCMD)

BLOCKED_TO_BUGFIX_AGENTS = frozenset({"verify-qa", "reviewer"})
COERCE_VERIFY_AGENTS = frozenset({"verify", "verify-implement"})
REVIEWER_MIRROR_AGENTS = frozenset({"verify-qa", "reviewer"})
BLOCKED_VERDICT_AGENTS = REVIEWER_MIRROR_AGENTS

_EPIC_RESOLVE = "python harness/hooks/epic_resolve.py mb-finish"


def record_agent_key(agent_type: str) -> str:
    norm = str(agent_type or "").strip().lower()
    if norm in {"verify", "verify-implement"}:
        return "verify"
    if norm in {"reviewer", "verify-qa"}:
        return "reviewer"
    return norm


def mb_finish_subcmd_for_verdict(agent_type: str, verdict: str) -> str | None:
    norm = str(agent_type or "").strip().lower()
    base = VERIFY_MB_FINISH_SUBCMD.get(norm)
    if not base:
        return None
    verdict_u = str(verdict or "").strip().upper()
    if norm in BLOCKED_TO_BUGFIX_AGENTS and verdict_u == "BLOCKED":
        return "bugfix"
    if verdict_u == "PASS":
        return base
    return None


def _resolve_implement_step(cwd: str | Path) -> str:
    try:
        import sys

        hooks = Path(__file__).resolve().parents[2] / "harness" / "hooks"
        if str(hooks) not in sys.path:
            sys.path.insert(0, str(hooks))
        from epic_lib import load_epic_state

        st = load_epic_state(cwd) or {}
        armed = str(st.get("armed_step") or "").strip()
        if armed and re.match(r"^[sera]\d+", armed, re.I):
            return armed
    except Exception:
        pass
    return "<sNN>"


def mb_finish_cli(agent_type: str, verdict: str, cwd: str | Path) -> str | None:
    subcmd = mb_finish_subcmd_for_verdict(agent_type, verdict)
    if not subcmd:
        return None
    if subcmd == "implement":
        step = _resolve_implement_step(cwd)
        return f"{_EPIC_RESOLVE} implement --cwd $PROJECT_ROOT --step {step}"
    return f"{_EPIC_RESOLVE} {subcmd} --cwd $PROJECT_ROOT"


def mb_finish_hint_after_verdict(
    agent_type: str, verdict: str, cwd: str | Path
) -> str | None:
    cli = mb_finish_cli(agent_type, verdict, cwd)
    if not cli:
        return None
    label = str(agent_type or "verify")
    return (
        f"{label} VERDICT: {str(verdict).upper()} — parent: сразу вызови `{cli}` "
        "(FORBIDDEN: ручной Write activeContext на FINISH)."
    )
