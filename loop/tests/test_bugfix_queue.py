from __future__ import annotations

from pathlib import Path

import pytest

from loop.bugfix_queue import (
    append_gate_repair_items,
    bugfix_queue_path,
    load_bugfix_queue,
    seed_or_merge_bugfix_queue,
    set_bugfix_verification,
    update_bugfix_item,
)
from loop.schemas.bugfix_queue import EpicBugfixQueue


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _qa(tmp_path: Path, epic: str = "T-queue") -> Path:
    path = tmp_path / f"memory-bank/back/qa/{epic}/qa-20260911-run.yaml"
    _write(
        path,
        """schema: epic-qa/v1
epic_id: T-queue
verdict: fail
checklist_sha256: freeze-1
blockers:
  - "suite_red: loop/tests/test_queue.py"
fix_plan:
  - "BACK BUGFIX Fix loop/tests/test_queue.py"
""",
    )
    return path


def test_seed_queue_uses_targeted_verify_and_order(tmp_path: Path) -> None:
    qa = _qa(tmp_path)
    path, queue = seed_or_merge_bugfix_queue(tmp_path, "back", "T-queue", qa)

    assert path == bugfix_queue_path(tmp_path, "back", "T-queue")
    assert queue.schema_version == "epic-bugfix-queue/v1"
    assert queue.current_id == "BF-001"
    assert queue.items[0].verify == "bin/pytest loop/tests/test_queue.py -q --tb=line"

    with pytest.raises(ValueError, match="in_progress"):
        update_bugfix_item(path, "BF-001", "done")

    update_bugfix_item(path, "BF-001", "in_progress")
    queue = update_bugfix_item(path, "BF-001", "done", evidence="targeted green")
    assert queue.current_id is None
    assert queue.items[0].status == "done"

    queue = set_bugfix_verification(path, "pass", evidence="full suite green")
    assert queue.verification.status == "pass"
    assert load_bugfix_queue(path).verification.evidence == "full suite green"


def test_seed_merge_preserves_done_and_appends_repair(tmp_path: Path) -> None:
    qa = _qa(tmp_path)
    path, _ = seed_or_merge_bugfix_queue(tmp_path, "back", "T-queue", qa)
    update_bugfix_item(path, "BF-001", "in_progress")
    update_bugfix_item(path, "BF-001", "done", evidence="fixed")
    set_bugfix_verification(path, "pass", evidence="full suite green")

    queue = append_gate_repair_items(path, ["suite_red: loop/tests/test_new.py"])
    assert [item.status for item in queue.items] == ["done", "open"]
    assert queue.current_id == "BF-002"
    assert queue.verification.status == "pending"


def test_queue_rejects_full_suite_as_item_verify() -> None:
    with pytest.raises(ValueError, match="targeted"):
        EpicBugfixQueue.model_validate(
            {
                "schema": "epic-bugfix-queue/v1",
                "epic_id": "T-queue",
                "role": "back",
                "source_qa": "qa.yaml",
                "checklist_sha256": "freeze-1",
                "created_at": "now",
                "updated_at": "now",
                "current_id": "BF-001",
                "items": [
                    {
                        "id": "BF-001",
                        "status": "open",
                        "class": "suite_red",
                        "title": "suite",
                        "blocker_ref": "suite_red: suite",
                        "fix_plan_ref": "fix",
                        "targets": ["loop/tests/test_queue.py"],
                        "verify": "bin/pytest -q --tb=line",
                    }
                ],
            }
        )


def test_finish_qa_requires_queue_before_bugfix_handoff(tmp_path: Path) -> None:
    from epic import default_state, save_epic_state
    from loop.mb_finish.impl import finish_qa
    from loop.mb_finish.schemas import MbFinishRequest

    qa = _qa(tmp_path)
    state = default_state()
    state.update({"armed_epic": "T-queue", "armed_role": "BACK", "phase": "QA"})
    save_epic_state(tmp_path, state)

    result = finish_qa(
        MbFinishRequest(cwd=str(tmp_path), phase="QA", step_id="QA", done_summary="")
    )
    assert result.ok is False
    assert result.diagnostic_codes == ["bugfix_queue_missing"]


def test_finish_bugfix_cannot_skip_open_queue_item(tmp_path: Path) -> None:
    from epic import default_state, save_epic_state
    from loop.mb_finish.impl import finish_bugfix
    from loop.mb_finish.schemas import MbFinishRequest

    qa = _qa(tmp_path)
    queue_path, _ = seed_or_merge_bugfix_queue(tmp_path, "back", "T-queue", qa)
    report = tmp_path / "memory-bank/back/bugfix/T-queue/bugfix-20260911-run.md"
    _write(report, "# Bugfix\n")
    state = default_state()
    state.update({"armed_epic": "T-queue", "armed_role": "BACK", "phase": "BUGFIX"})
    save_epic_state(tmp_path, state)

    result = finish_bugfix(
        MbFinishRequest(cwd=str(tmp_path), phase="BUGFIX", step_id="BUGFIX", done_summary="")
    )
    assert result.ok is False
    assert result.diagnostic_codes == ["bugfix_queue_open"]
    assert queue_path.is_file()
