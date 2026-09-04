"""Tests for mb-finish step path via resolver in v2 layout."""
import pytest
from pathlib import Path
from unittest.mock import patch
import yaml
from loop.mb_finish.finish_implement import finish_implement_step
from loop.mb_finish.impl import finish_decompose
from loop.mb_finish.schemas import MbFinishRequest
from loop.paths.epic_layout import resolve, EpicLayoutKind
from epic.core import save_epic_state, default_state


def test_finish_implement_v2_resolver_path(tmp_path: Path):
    role = "back"
    epic_id = "T-HUB-047-test"
    step_id = "s01"

    # Setup v2 decompose index
    decomp_yaml = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=tmp_path)
    decomp_yaml.parent.mkdir(parents=True, exist_ok=True)
    decomp_yaml.write_text(
        f"schema: epic-decompose-index/v1\n"
        f"plan_id: {epic_id}\n"
        f"steps:\n"
        f"  - id: {step_id}\n"
        f"    file: {step_id}-test.yaml\n"
        f"    title: Step 1\n"
        f"    status: in_progress\n",
        encoding="utf-8",
    )

    # Setup v2 decompose step file
    decomp_step = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_STEP, step_id=step_id, step_slug="test", project_root=tmp_path)
    decomp_step.parent.mkdir(parents=True, exist_ok=True)
    decomp_step.write_text(
        f"schema: epic-decompose/v1\n"
        f"role: {role}\n"
        f"step_id: {step_id}\n"
        f"plan_id: {epic_id}\n"
        f"title: test step\n"
        f"next_phase: BACK IMPLEMENT\n"
        f"checkpoints:\n"
        f"  - id: cp1\n"
        f"    criterion: test cp\n",
        encoding="utf-8",
    )

    # Setup v2 implement step file
    impl_step = resolve(role, epic_id, EpicLayoutKind.IMPLEMENT_STEP, step_id=step_id, step_slug="test", project_root=tmp_path)
    impl_step.parent.mkdir(parents=True, exist_ok=True)
    impl_step.write_text(
        f"schema: epic-implement/v1\n"
        f"role: {role}\n"
        f"step_id: {step_id}\n"
        f"plan_id: {epic_id}\n"
        f"title: test step\n"
        f"status: in_progress\n"
        f"date: '2026-09-04'\n"
        f"decompose_ref: {decomp_step.relative_to(tmp_path)}\n"
        f"skills_used: []\n"
        f"discovery: []\n"
        f"gaps:\n"
        f"  status: none\n"
        f"done:\n"
        f"  - done item\n"
        f"files:\n"
        f"  - file1.py\n"
        f"deletes: []\n"
        f"tests:\n"
        f"  - '`timeout 300s .venv/bin/pytest loop/tests/test_mb_finish_paths.py`'\n"
        f"integration_check:\n"
        f"  - ok\n"
        f"grep_control: []\n"
        f"verification_results: []\n"
        f"checkpoints:\n"
        f"  - id: cp1\n"
        f"    criterion: test cp\n"
        f"    status: done\n",
        encoding="utf-8",
    )

    # Setup state.json
    state = default_state()
    state.update(
        {
            "active": True,
            "status": "running",
            "armed_epic": epic_id,
            "role": role,
            "armed_step": step_id,
            "armed_decompose": str(decomp_yaml.relative_to(tmp_path)),
        }
    )
    save_epic_state(tmp_path, state)

    # Setup activeContext.md
    ac_path = tmp_path / "memory-bank" / "activeContext.md"
    ac_path.parent.mkdir(parents=True, exist_ok=True)
    ac_path.write_text(
        f"---\n"
        f"schema: loop-handoff/v1\n"
        f"role: BACK\n"
        f"mode: IMPLEMENT\n"
        f"epic_id: {epic_id}\n"
        f"step_id: {step_id}\n"
        f"---\n\n"
        f"## load_now\n"
        f"1. [{decomp_step.name}]({decomp_step.relative_to(tmp_path)}) — test.\n\n"
        f"## Handoff BACK IMPLEMENT — {step_id}\n"
        f"- **Дальше:** test\n\n"
        f"## done\n"
        f"- test initial\n",
        encoding="utf-8",
    )

    req = MbFinishRequest(
        phase="BACK IMPLEMENT",
        role=role,
        epic_id=epic_id,
        step_id=step_id,
        done_summary="Completed step 1",
        cwd=str(tmp_path),
    )

    with patch("loop.mb_finish.finish_implement._verify_pass_ready_for_step") as mock_verify_check, \
         patch("harness.hooks.epic.core._verify_pass_ready_for_step") as mock_verify_fin:
        mock_verify_check.return_value = {"ok": True, "diagnostic": "verify_pass"}
        mock_verify_fin.return_value = {"ok": True, "diagnostic": "verify_pass"}

        res = finish_implement_step(req)
        assert res.ok is True

    # Verify decompose index updated
    updated_idx = yaml.safe_load(decomp_yaml.read_text(encoding="utf-8"))
    assert updated_idx["steps"][0]["status"] == "completed"


def test_finish_decompose_v2_resolver_path(tmp_path: Path):
    role = "back"
    epic_id = "T-HUB-047-test"

    decomp_yaml = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=tmp_path)
    decomp_yaml.parent.mkdir(parents=True, exist_ok=True)
    decomp_yaml.write_text(
        f"schema: epic-decompose-index/v1\n"
        f"plan_id: {epic_id}\n"
        f"source_md: index.md\n"
        f"status_canon: index.yaml\n"
        f"steps:\n"
        f"  - id: s01\n"
        f"    file: s01-test.yaml\n"
        f"    title: Step 1\n"
        f"    status: pending\n"
        f"    next_phase: BACK IMPLEMENT\n",
        encoding="utf-8",
    )

    decomp_md = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_MD, project_root=tmp_path)
    decomp_md.parent.mkdir(parents=True, exist_ok=True)
    decomp_md.write_text(
        "## Requirements coverage\n- REQ-01: covered\n\n"
        "## Stages coverage\n- s01: covered\n\n"
        "## Outcome map\n- OUT-01: covered\n\n"
        "## Replacement cleanup\n- CLEAN-01: covered\n",
        encoding="utf-8",
    )

    # Setup v2 decompose step file
    decomp_step = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_STEP, step_id="s01", step_slug="test", project_root=tmp_path)
    decomp_step.parent.mkdir(parents=True, exist_ok=True)
    decomp_step.write_text(
        f"schema: epic-decompose/v1\n"
        f"step_id: s01\n"
        f"plan_id: {epic_id}\n"
        f"role: {role}\n"
        f"title: Step 1\n"
        f"next_phase: BACK IMPLEMENT\n"
        f"as_built: []\n"
        f"plan_contract:\n"
        f"  fr_ids: [FR-01]\n"
        f"  nouns: [noun-1]\n"
        f"  layout_paths: [memory-bank/back/activeContext.md]\n"
        f"  ac_quotes: [quote-1]\n"
        f"  plan_jumps: [jump-1]\n",
        encoding="utf-8",
    )

    # Setup state.json
    state = default_state()
    state.update(
        {
            "active": True,
            "status": "running",
            "armed_epic": epic_id,
            "role": role,
            "armed_step": "DECOMPOSE",
            "armed_decompose": str(decomp_yaml.relative_to(tmp_path)),
        }
    )
    save_epic_state(tmp_path, state)

    # Setup activeContext.md
    ac_path = tmp_path / "memory-bank" / "activeContext.md"
    ac_path.parent.mkdir(parents=True, exist_ok=True)
    ac_path.write_text(
        f"---\n"
        f"schema: loop-handoff/v1\n"
        f"role: BACK\n"
        f"mode: DECOMPOSE\n"
        f"epic_id: {epic_id}\n"
        f"---\n\n"
        f"## load_now\n"
        f"1. [{decomp_yaml.name}]({decomp_yaml.relative_to(tmp_path)}) — index.\n\n"
        f"## Handoff BACK DECOMPOSE\n"
        f"- **Дальше:** proceed to implement\n\n"
        f"## done\n"
        f"- decompose done\n",
        encoding="utf-8",
    )

    req = MbFinishRequest(
        phase="BACK DECOMPOSE",
        role=role,
        epic_id=epic_id,
        step_id="DECOMPOSE",
        done_summary="Decompose completed",
        cwd=str(tmp_path),
    )
    res = finish_decompose(req)
    assert res.ok is True
