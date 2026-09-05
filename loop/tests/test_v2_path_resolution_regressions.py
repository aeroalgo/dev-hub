from __future__ import annotations

import json
from pathlib import Path

import yaml

from harness.hooks.epic.core import (
    _declared_artifacts,
    arm_pre_implement_context,
    default_state,
    resolve_pipeline_identity,
    save_epic_state,
)
from harness.hooks.epic.reconcile import resolve_epic_bundle
from harness.hooks.epic_yaml import seed_implement_from_decompose, verify_decompose_creative
from loop.board_launch.metadata import parse_launch_metadata
from loop.board_sync.scan_epics import scan_epics
from loop.board_sync.scan_mb import scan_steps
from loop.board_sync.workspaces import WorkspaceRef
from loop.mb_finish.finish_implement import (
    _resolve_armed_decompose_index,
    _resolve_work_shard_rel,
)
from loop.mb_finish.impl import finish_decompose
from loop.mb_finish.schemas import MbFinishRequest
from loop.parallel.orchestrator import filter_non_overlapping
from loop.paths.epic_layout import EpicLayoutKind, resolve


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _v2_tree(tmp_path: Path, epic_id: str = "T-HUB-062-v2-paths") -> tuple[Path, Path, Path]:
    index = resolve("back", epic_id, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=tmp_path)
    index_md = resolve("back", epic_id, EpicLayoutKind.DECOMPOSE_INDEX_MD, project_root=tmp_path)
    shard = resolve(
        "back",
        epic_id,
        EpicLayoutKind.DECOMPOSE_STEP,
        step_id="s01",
        step_slug="path-check",
        project_root=tmp_path,
    )
    _write(
        index,
        yaml.safe_dump(
            {
                "schema": "epic-decompose-index/v1",
                "plan_id": epic_id,
                "source_md": "decompose-index.md",
                "status_canon": "decompose-index.yaml",
                "steps": [
                    {
                        "id": "s01",
                        "file": "s01-path-check.yaml",
                        "title": "path check",
                        "next_phase": "BACK IMPLEMENT",
                        "status": "pending",
                    }
                ],
            },
            sort_keys=False,
        ),
    )
    _write(
        index_md,
        "## Requirements coverage\n- REQ-01: covered\n\n"
        "## Stages coverage\n- s01: covered\n\n"
        "## Outcome map\n- OUT-01: covered\n\n"
        "## Replacement cleanup\n- CLEAN-01: covered\n",
    )
    _write(
        shard,
        yaml.safe_dump(
            {
                "schema": "epic-decompose/v1",
                "role": "back",
                "step_id": "s01",
                "plan_id": epic_id,
                "title": "path check",
                "next_phase": "BACK IMPLEMENT",
                "as_built": [],
                "plan_contract": {
                    "fr_ids": ["FR-01"],
                    "nouns": ["path"],
                    "layout_paths": ["memory-bank/activeContext.md"],
                    "ac_quotes": ["quote"],
                    "plan_jumps": ["jump"],
                },
            },
            sort_keys=False,
        ),
    )
    return index, index_md, shard


def test_finish_decompose_discovers_v2_index_from_armed_epic(tmp_path: Path) -> None:
    index, _, _ = _v2_tree(tmp_path)
    state = default_state()
    state.update(
        {
            "active": True,
            "status": "armed",
            "armed_epic": "T-HUB-062-v2-paths",
            "armed_role": "BACK",
            "armed_step": "DECOMPOSE",
            "armed_decompose": None,
        }
    )
    save_epic_state(tmp_path, state)
    _write(
        tmp_path / "memory-bank/activeContext.md",
        "---\nschema: loop-handoff/v1\nrole: BACK\nmode: DECOMPOSE\n"
        "epic_id: T-HUB-062-v2-paths\nstep_id: DECOMPOSE\n---\n\n"
        "## load_now\n\n## Handoff BACK DECOMPOSE\n",
    )

    result = finish_decompose(
        MbFinishRequest(
            phase="BACK DECOMPOSE",
            step_id="DECOMPOSE",
            done_summary="decompose ready",
            cwd=str(tmp_path),
        )
    )

    assert result.ok is True, result.shape_errors
    assert load_state(tmp_path)["armed_decompose"] == index.relative_to(tmp_path).as_posix()


def test_identity_resolves_v2_index_from_active_context(tmp_path: Path) -> None:
    index, _, _ = _v2_tree(tmp_path, "T-HUB-063-v2-identity")
    _write(
        tmp_path / "memory-bank/activeContext.md",
        "## load_now\n"
        f"1. [decompose-index.yaml]({index.relative_to(tmp_path).as_posix()})\n",
    )

    result = resolve_pipeline_identity(tmp_path)

    assert result["status"] == "resolved"
    assert result["epic_id"] == "T-HUB-063-v2-identity"
    assert result["decompose"] == index.relative_to(tmp_path).as_posix()


def test_declared_artifacts_discovers_v2_decompose_and_implement(tmp_path: Path) -> None:
    index, _, shard = _v2_tree(tmp_path, "T-HUB-064-v2-events")
    implement = resolve(
        "back",
        "T-HUB-064-v2-events",
        EpicLayoutKind.IMPLEMENT_STEP,
        step_id="s01",
        step_slug="path-check",
        project_root=tmp_path,
    )
    _write(
        implement,
        "schema: epic-implement/v1\nstep_id: s01\nstatus: completed\n",
    )

    records = _declared_artifacts(tmp_path, "back", "T-HUB-064-v2-events")

    assert ("decompose_step_done", shard) in records
    assert ("implement_done", implement) in records
    assert index.is_file()


def test_board_scan_reports_v2_shard_path(tmp_path: Path) -> None:
    index, _, _ = _v2_tree(tmp_path, "T-HUB-065-v2-board")
    result = scan_steps([WorkspaceRef(tmp_path, "v2")])

    assert len(result) == 1
    assert result[0].decompose_rel == index.relative_to(tmp_path).as_posix()
    assert result[0].shard_rel == (
        "memory-bank/back/plan/T-HUB-065-v2-board/yaml/steps/s01-path-check.yaml"
    )


def test_epic_board_scan_discovers_v2_plan_only_epic(tmp_path: Path) -> None:
    plan = resolve("back", "T-HUB-066-v2-board-epic", EpicLayoutKind.PLAN_MD, project_root=tmp_path)
    _write(plan, "# Plan\n")

    result = scan_epics([WorkspaceRef(tmp_path, "v2")])

    assert [item.epic_id for item in result] == ["T-HUB-066-v2-board-epic"]


def test_parallel_wave_uses_v2_steps_directory(tmp_path: Path) -> None:
    steps_dir = tmp_path / "memory-bank/back/plan/T-HUB-067-v2-parallel/yaml/steps"
    _write(steps_dir / "s01-first.yaml", "context:\n  files: [shared.py]\n")
    _write(steps_dir / "s02-second.yaml", "context:\n  files: [shared.py]\n")

    selected = filter_non_overlapping(
        ["s01", "s02"],
        steps_dir.parent,
    )

    assert selected == ["s01"]


def test_spec_reconcile_resolves_v2_bundle_from_short_queue_id(tmp_path: Path) -> None:
    epic_id = "T-HUB-068-v2-reconcile"
    plan = resolve("back", epic_id, EpicLayoutKind.PLAN_MD, project_root=tmp_path)
    index, _, _ = _v2_tree(tmp_path, epic_id)
    _write(plan, "# Plan\n")

    bundle = resolve_epic_bundle(tmp_path, "T-HUB-068")

    assert bundle is not None
    assert bundle.plan_path == plan
    assert bundle.decompose_index == index


def test_creative_verifier_reads_v2_plan_index_and_shard_paths(tmp_path: Path) -> None:
    epic_id = "T-HUB-069-v2-creative"
    index, _, _ = _v2_tree(tmp_path, epic_id)
    plan = resolve("back", epic_id, EpicLayoutKind.PLAN_MD, project_root=tmp_path)
    _write(plan, "### CREATIVE need\n**нет**\n")

    result = verify_decompose_creative(tmp_path, str(index.relative_to(tmp_path)))

    assert result["ready"] is True
    assert result["plan_creative_need"] == "no"


def test_epic_launch_default_and_seed_implement_use_v2_layout(tmp_path: Path) -> None:
    epic_id = "T-070-v2-launch"
    index, _, shard = _v2_tree(tmp_path, epic_id)

    card = parse_launch_metadata(
        {
            "metadata": {
                "card_kind": "epic",
                "project_root": str(tmp_path),
                "role": "back",
                "epic_id": epic_id,
            }
        }
    )
    seeded = seed_implement_from_decompose(tmp_path, str(shard.relative_to(tmp_path)))

    assert card.decompose_rel == index.relative_to(tmp_path).as_posix()
    assert seeded["ok"] is True
    assert seeded["path"] == f"memory-bank/back/implement/{epic_id}/s01-path-check.yaml"


def test_legacy_finish_implement_resolves_v2_state_and_shard_paths(tmp_path: Path) -> None:
    epic_id = "T-071-v2-finish-implement"
    index, _, shard = _v2_tree(tmp_path, epic_id)
    state = default_state()
    state.update({"armed_epic": epic_id, "armed_role": "BACK", "armed_decompose": None})
    save_epic_state(tmp_path, state)

    index_ref, _ = _resolve_armed_decompose_index(tmp_path)

    assert index_ref == index.relative_to(tmp_path).as_posix()
    assert _resolve_work_shard_rel(tmp_path, index_ref, "s01") == shard.relative_to(tmp_path).as_posix()


def test_analyze_arm_normalizes_v2_md_mirror_to_yaml_sot(tmp_path: Path) -> None:
    index, index_md, _ = _v2_tree(tmp_path, "T-072-v2-analyze-arm")
    plan = resolve("back", "T-072-v2-analyze-arm", EpicLayoutKind.PLAN_MD, project_root=tmp_path)
    _write(plan, "# Plan\n")

    result = arm_pre_implement_context(
        tmp_path,
        epic_id="T-072-v2-analyze-arm",
        role="back",
        phase="ANALYZE",
        target_rel=plan.relative_to(tmp_path).as_posix(),
        decompose_rel=index_md.relative_to(tmp_path).as_posix(),
    )

    assert result["ok"] is True
    assert load_state(tmp_path)["armed_decompose"] == index.relative_to(tmp_path).as_posix()


def load_state(tmp_path: Path) -> dict[str, object]:
    return json.loads((tmp_path / ".claude/runtime/epic/state.json").read_text(encoding="utf-8"))
