from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from loop.kernel.implement_schema import (
    coerce_checkpoint_status,
    coerce_step_status,
    validate_implement_artifact,
)


def _write(path: Path, body: str) -> Path:
    path.write_text(dedent(body).lstrip(), encoding="utf-8")
    return path


def test_coerce_checkpoint_aliases() -> None:
    assert coerce_checkpoint_status("passed") == "done"
    assert coerce_checkpoint_status("PASS") == "done"
    assert coerce_checkpoint_status("pending") == "pending"
    with pytest.raises(ValueError, match="banana"):
        coerce_checkpoint_status("banana")


def test_coerce_step_aliases() -> None:
    assert coerce_step_status("in-progress") == "in_progress"
    assert coerce_step_status("done") == "completed"
    assert coerce_step_status("completed") == "completed"
    with pytest.raises(ValueError, match="nope"):
        coerce_step_status("nope")


def test_validate_rewrites_passed_to_done(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "s02.yaml",
        """
        schema: epic-implement/v1
        role: front
        step_id: s02
        plan_id: T-F02-unified-design-controls
        status: in_progress
        # keep me
        done: []
        files: []
        deletes: []
        tests: []
        integration_check: []
        checkpoints:
          - id: cp1
            criterion: wire
            status: passed
          - id: cp2
            criterion: asset
            status: passed
        resume_from: cp1
        """,
    )
    model = validate_implement_artifact(
        path,
        expected_step_id="s02",
        expected_plan_id="T-F02-unified-design-controls",
        rewrite=True,
    )
    assert [cp.status for cp in model.checkpoints] == ["done", "done"]
    text = path.read_text(encoding="utf-8")
    assert "# keep me" in text
    assert "status: passed" not in text
    assert text.count("status: done") == 2
    payload = yaml.safe_load(text)
    assert payload["checkpoints"][0]["status"] == "done"


def test_validate_rejects_unknown_checkpoint_status(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "s01.yaml",
        """
        schema: epic-implement/v1
        role: front
        step_id: s01
        plan_id: T-X
        status: in_progress
        checkpoints:
          - id: cp1
            criterion: x
            status: banana
        """,
    )
    with pytest.raises(ValueError, match="banana"):
        validate_implement_artifact(path, rewrite=False)


def test_flush_overwrites_agent_passed_to_machine_done(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "s03.yaml",
        """
        schema: epic-implement/v1
        role: front
        step_id: s03
        plan_id: T-F02
        status: completed
        done:
          - evidence
        files: []
        deletes: []
        tests: []
        integration_check: []
        checkpoints:
          - id: cp1
            criterion: x
            status: passed
          - id: cp2
            criterion: y
            status: pending
        """,
    )
    from loop.kernel.implement_schema import flush_implement_for_verify, complete_implement_artifact

    flushed = flush_implement_for_verify(path, expected_step_id="s03", expected_plan_id="T-F02")
    assert flushed.status == "in_progress"
    assert [cp.status for cp in flushed.checkpoints] == ["done", "done"]
    text = path.read_text(encoding="utf-8")
    assert "status: passed" not in text
    assert "status: completed" not in text

    completed = complete_implement_artifact(path, expected_step_id="s03", expected_plan_id="T-F02")
    assert completed.status == "completed"
    assert [cp.status for cp in completed.checkpoints] == ["done", "done"]


def test_flush_requires_evidence(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "s01.yaml",
        """
        schema: epic-implement/v1
        role: front
        step_id: s01
        plan_id: T-X
        status: in_progress
        done: []
        files: []
        checkpoints:
          - id: cp1
            criterion: x
            status: pending
        """,
    )
    from loop.kernel.implement_schema import flush_implement_for_verify

    with pytest.raises(ValueError, match="evidence empty"):
        flush_implement_for_verify(path)


def test_app_flush_requires_wire_complete_evidence(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "s01-app.yaml",
        """
        schema: epic-implement/v1
        role: app
        step_id: s01
        plan_id: APP-1
        status: in_progress
        done:
          - contract and UI wired
        files:
          - backend/contract.py
          - frontend/feature.ts
        tests:
          - bin/pytest loop/tests/test_app_lifecycle.py -q
        integration_check:
          - real wire journey
        checkpoints:
          - id: cp1
            criterion: mixed slice
            status: pending
        """,
    )

    from loop.kernel.implement_schema import flush_implement_for_verify

    with pytest.raises(ValueError, match="requires wire_complete"):
        flush_implement_for_verify(path, expected_step_id="s01", expected_plan_id="APP-1")


def test_validate_step_id_mismatch(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "s01.yaml",
        """
        schema: epic-implement/v1
        role: front
        step_id: s01
        plan_id: T-X
        status: in_progress
        checkpoints: []
        """,
    )
    with pytest.raises(ValueError, match="step_id mismatch"):
        validate_implement_artifact(path, expected_step_id="s02", rewrite=False)
