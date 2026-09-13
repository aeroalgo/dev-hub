from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "harness" / "hooks"))
sys.path.insert(0, str(ROOT / ".claude" / "hooks"))

import epic_yaml
from epic_yaml import (
    CheckpointProgress,
    CheckpointSpec,
    EpicDecomposeDoc,
    EpicImplementDoc,
    step_context_prompt_lines,
    validate_shard_yaml_full,
)


def test_epic_yaml_canonical_validator_and_legacy_alias_purged(tmp_path: Path) -> None:
    """Verify canonical validate_shard_yaml_full behavior and dead validate_shard_yaml alias purged."""
    shard_file = tmp_path / "s01-demo.yaml"
    shard_file.write_text("schema: epic-implement/v1\nrole: back\n", encoding="utf-8")

    errs, warns = validate_shard_yaml_full(shard_file)
    assert len(errs) > 0

    assert not hasattr(epic_yaml, "validate_shard_yaml"), "validate_shard_yaml alias must be purged"


def test_step_context_prompt_lines_and_legacy_checkpoint_prompt_lines_purged() -> None:
    """Verify step_context_prompt_lines helper output and dead checkpoint_prompt_lines alias purged."""
    dec = EpicDecomposeDoc(
        schema="epic-decompose/v1",
        role="back",
        step_id="s01",
        plan_id="T-DEMO",
        title="demo",
        next_phase="BACK IMPLEMENT",
        checkpoints=[
            CheckpointSpec(id="cp1", criterion="Test cp1", verify="bin/pytest"),
            CheckpointSpec(id="cp2", criterion="Test cp2", verify="bin/pytest"),
        ],
    )
    impl = EpicImplementDoc(
        schema="epic-implement/v1",
        role="back",
        step_id="s01",
        plan_id="T-DEMO",
        title="demo",
        status="in_progress",
        date="2026-09-12",
        decompose_ref="path/to/shard.yaml",
        skills_used=[],
        discovery=[],
        gaps={"status": "none"},
        done=[],
        files=[],
        deletes=[],
        tests=[],
        integration_check=[],
        grep_control=[],
        verification_results=[],
        checkpoints=[
            CheckpointProgress(id="cp1", criterion="Test cp1", status="done"),
            CheckpointProgress(id="cp2", criterion="Test cp2", status="pending"),
        ],
        resume_from="cp2",
    )
    lines = step_context_prompt_lines(dec, impl, shard_rel="memory-bank/steps/s01.yaml")
    assert "## step" in lines
    assert "- step_id: `s01`" in lines
    assert "- shard: `memory-bank/steps/s01.yaml`" in lines
    assert "- implement_status: `in_progress`" in lines
    assert "- resume_from: `cp2`" in lines
    assert "- pending: cp2" in lines
    assert "- done: cp1" in lines

    assert not hasattr(epic_yaml, "checkpoint_prompt_lines"), "checkpoint_prompt_lines alias must be purged"
