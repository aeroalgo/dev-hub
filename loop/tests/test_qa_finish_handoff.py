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
        "mode: REFLECT\n"
        "epic_id: T-HUB-999-test-epic\n"
        "step_id: s10\n"
        "---\n\n"
        "## Handoff BACK REFLECT\n"
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
        "mode: REFLECT\n"
        "epic_id: T-HUB-999-test-epic\n"
        "step_id: s10\n"
        "---\n\n"
        "## Handoff BACK REFLECT\n"
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
