from __future__ import annotations

import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from epic import validate_qa_finish_handoff

def test_qa_mode_with_verdict_pass(tmp_path: Path):
    active_context = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: DONE\n"
        "epic_id: T-HUB-999-test-epic\n"
        "step_id: s10\n"
        "---\n\n"
        "## Handoff BACK DONE\n"
        "EPIC_DONE\n"
    )
    qa_dir = tmp_path / "memory-bank" / "back" / "qa" / "T-HUB-999-test-epic"
    qa_dir.mkdir(parents=True, exist_ok=True)
    (qa_dir / "qa-20260831-test.yaml").write_text("verdict: pass\n", encoding="utf-8")

    ok, diagnostic = validate_qa_finish_handoff(tmp_path, active_context)
    assert ok is True
    assert diagnostic is None

def test_qa_mode_no_verdict(tmp_path: Path):
    active_context = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: DONE\n"
        "epic_id: T-HUB-999-test-epic\n"
        "step_id: s10\n"
        "---\n\n"
        "## Handoff BACK DONE\n"
    )
    ok, diagnostic = validate_qa_finish_handoff(tmp_path, active_context)
    assert ok is False
    assert diagnostic == "QA FINISH без qa-*.yaml — запиши epic-qa/v1 artifact"

def test_non_qa_mode_skip(tmp_path: Path):
    active_context = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        "epic_id: T-HUB-999-test-epic\n"
        "step_id: s10\n"
        "---\n\n"
        "## Handoff BACK IMPLEMENT — s10\n"
    )
    # create a dummy qa artifact so validate_qa_finish_handoff passes even if called
    qa_dir = tmp_path / "memory-bank" / "back" / "qa" / "T-HUB-999-test-epic"
    qa_dir.mkdir(parents=True, exist_ok=True)
    (qa_dir / "qa-20260831-test.yaml").write_text("verdict: pass\n", encoding="utf-8")

    ok, diagnostic = validate_qa_finish_handoff(tmp_path, active_context)
    assert ok is True
    assert diagnostic is None


@pytest.mark.parametrize("target_mode", ["DONE", "IMPLEMENT", "ANALYZE", "DECOMPOSE", "PLAN", "QA"])
def test_finish_handoff_with_latest_qa_fail_blocks_non_bugfix(tmp_path: Path, target_mode: str):
    """cp3 / US-003 / SC-003: finish_handoff to DONE/IMPLEMENT/etc. while latest qa is fail -> rejected."""
    qa_dir = tmp_path / "memory-bank" / "back" / "qa" / "T-HUB-999-test-epic"
    qa_dir.mkdir(parents=True, exist_ok=True)
    (qa_dir / "qa-20260831-test.yaml").write_text("verdict: fail\n", encoding="utf-8")

    active_context = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        f"mode: {target_mode}\n"
        "epic_id: T-HUB-999-test-epic\n"
        "step_id: s10\n"
        "---\n\n"
        f"## Handoff BACK {target_mode}\n"
    )

    ok, diagnostic = validate_qa_finish_handoff(tmp_path, active_context)
    assert ok is False
    assert "BUGFIX" in (diagnostic or "") or "qa_fail_blocks_handoff" in (diagnostic or "")

