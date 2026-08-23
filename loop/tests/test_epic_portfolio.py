from __future__ import annotations

import sys
from datetime import date
from pathlib import Path


HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"


def _load_portfolio():
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    import epic_portfolio as ep

    return ep


def test_desired_step_skips_in_progress_sNN() -> None:
    ep = _load_portfolio()
    assert (
        ep.desired_tasks_step_cell(
            "IMPLEMENT in progress (s09)", all_completed=False
        )
        is None
    )


def test_desired_step_promotes_decompose_to_implement() -> None:
    ep = _load_portfolio()
    assert (
        ep.desired_tasks_step_cell("DECOMPOSE done (s01–s09)", all_completed=False)
        == "IMPLEMENT in progress"
    )


def test_desired_step_last_to_audit() -> None:
    ep = _load_portfolio()
    assert (
        ep.desired_tasks_step_cell("IMPLEMENT in progress (s09)", all_completed=True)
        == "IMPLEMENT done · next AUDIT"
    )
    assert (
        ep.desired_tasks_step_cell("IMPLEMENT done · next AUDIT", all_completed=True)
        is None
    )


def test_append_log_and_phase_change(tmp_path: Path) -> None:
    ep = _load_portfolio()
    (tmp_path / "memory-bank").mkdir()
    tasks = tmp_path / "memory-bank/tasks.md"
    tasks.write_text(
        "# Tasks — index\n\n"
        "## Active\n\n"
        "| ID | Title | Level | Step | Status | Progress |\n"
        "|----|-------|-------|------|--------|----------|\n"
        "| T-006 | Contacts | L3 | PLAN done | pending | x |\n\n"
        "## Последние события\n\n"
        "| Date | ID | Event |\n"
        "|------|-----|-------|\n"
        "| 2026-08-01 | T-001 | VAN |\n",
        encoding="utf-8",
    )
    day = date(2026, 8, 14)
    first = ep.sync_portfolio_after_step(
        tmp_path,
        epic_id="T-006",
        role="BACK",
        step_id="s01",
        artifact="memory-bank/back/implement/implement-T-006/s01-a.yaml",
        all_completed=False,
        day=day,
    )
    assert first["log"]["skipped"] is False
    body = tasks.read_text(encoding="utf-8")
    assert "IMPLEMENT in progress" in body
    assert "PLAN done" not in body
    log = (tmp_path / "memory-bank/tasks/log/2026-08.md").read_text(encoding="utf-8")
    assert "BACK IMPLEMENT s01" in log

    second = ep.sync_portfolio_after_step(
        tmp_path,
        epic_id="T-006",
        role="BACK",
        step_id="s02",
        artifact="memory-bank/back/implement/implement-T-006/s02-b.yaml",
        all_completed=False,
        day=day,
    )
    assert second["tasks_md"]["updated"] is False
    body2 = tasks.read_text(encoding="utf-8")
    assert body2.count("| IMPLEMENT in progress |") == 1
    assert body2.count("| T-006 | BACK IMPLEMENT in progress |") == 1
    log2 = (tmp_path / "memory-bank/tasks/log/2026-08.md").read_text(encoding="utf-8")
    assert "BACK IMPLEMENT s02" in log2

    last = ep.sync_portfolio_after_step(
        tmp_path,
        epic_id="T-006",
        role="BACK",
        step_id="s09",
        artifact="memory-bank/back/implement/implement-T-006/s09-z.yaml",
        all_completed=True,
        day=day,
    )
    assert last["tasks_md"]["updated"] is True
    assert "IMPLEMENT done · next AUDIT" in tasks.read_text(encoding="utf-8")
