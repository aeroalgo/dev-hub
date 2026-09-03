"""Tests for finish_qa and finish_bugfix (s05 / TM-006)."""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from harness.hooks.epic.core import read_active_context, save_epic_state
from loop.mb_finish.impl import finish_bugfix, finish_qa
from loop.mb_finish.schemas import MbFinishRequest


def test_finish_qa_no_artifact(tmp_path: Path):
    """cp2: finish_qa without qa artifact returns ok=False and does not write activeContext."""
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    save_epic_state(tmp_path, {"armed_epic": "T-HUB-040", "armed_role": "BACK"})

    req = MbFinishRequest(
        phase="BACK QA",
        step_id="s05",
        done_summary="qa complete",
        cwd=str(tmp_path),
    )
    res = finish_qa(req)
    assert res.ok is False
    assert "qa_artifact_missing" in res.diagnostic_codes
    assert not (mb_dir / "activeContext.md").exists()


def test_finish_qa_happy(tmp_path: Path):
    """cp1: finish_qa happy path with valid QA artifact -> ok=True, activeContext mode=REFLECT."""
    mb_dir = tmp_path / "memory-bank" / "back" / "qa" / "T-HUB-040"
    mb_dir.mkdir(parents=True, exist_ok=True)
    qa_file = mb_dir / "qa-001.yaml"
    qa_file.write_text("verdict: pass\nepic_id: T-HUB-040\n", encoding="utf-8")

    save_epic_state(tmp_path, {"armed_epic": "T-HUB-040", "armed_role": "BACK"})

    req = MbFinishRequest(
        phase="BACK QA",
        step_id="s05",
        done_summary="qa passed successfully",
        cwd=str(tmp_path),
    )
    res = finish_qa(req)
    assert res.ok is True
    assert res.active_context is not None

    written = read_active_context(tmp_path)
    assert "mode: DONE" in written
    assert "## Handoff BACK DONE" in written


def test_finish_qa_handoff(tmp_path: Path):
    """cp3 / TM-006: finish_qa results in REFLECT handoff in activeContext."""
    mb_dir = tmp_path / "memory-bank" / "back" / "qa" / "T-HUB-040"
    mb_dir.mkdir(parents=True, exist_ok=True)
    qa_file = mb_dir / "qa-001.yaml"
    qa_file.write_text("verdict: pass\nepic_id: T-HUB-040\n", encoding="utf-8")

    save_epic_state(tmp_path, {"armed_epic": "T-HUB-040", "armed_role": "BACK"})

    req = MbFinishRequest(
        phase="BACK QA",
        step_id="s05",
        done_summary="qa verified",
        cwd=str(tmp_path),
    )
    res = finish_qa(req)
    assert res.ok is True

    written = read_active_context(tmp_path)
    assert "mode: DONE" in written
    assert "## Handoff BACK DONE" in written


def test_finish_bugfix_happy(tmp_path: Path):
    """cp4: finish_bugfix happy path with valid bugfix artifact -> ok=True."""
    bugfix_dir = tmp_path / "memory-bank" / "back" / "bugfix" / "T-HUB-040"
    bugfix_dir.mkdir(parents=True, exist_ok=True)
    (bugfix_dir / "bugfix-001.md").write_text(
        "# Bugfix\n\nRoot cause fixed.\n",
        encoding="utf-8",
    )

    save_epic_state(
        tmp_path,
        {
            "armed_epic": "T-HUB-040",
            "armed_role": "BACK",
        },
    )

    req = MbFinishRequest(
        phase="BACK BUGFIX",
        step_id="s01",
        done_summary="bugfix applied",
        cwd=str(tmp_path),
    )
    res = finish_bugfix(req)
    assert res.ok is True
    assert res.active_context is not None

    written = read_active_context(tmp_path)
    assert "mode: QA" in written
    assert "## Handoff BACK QA" in written


def test_finish_bugfix_fail_closed(tmp_path: Path):
    """cp4: finish_bugfix without decompose shard fails closed."""
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    save_epic_state(tmp_path, {"armed_epic": "T-HUB-040", "armed_role": "BACK"})

    req = MbFinishRequest(
        phase="BACK BUGFIX",
        step_id="s01",
        done_summary="bugfix applied",
        cwd=str(tmp_path),
    )
    res = finish_bugfix(req)
    assert res.ok is False
    assert "bugfix_artifact_missing" in res.diagnostic_codes
