"""Tests for plan jumps, whole-plan monolith denial, and excerpt identity in prompt scope.
Addresses FR-003, AC 2, TM-078-03.
"""
from __future__ import annotations

from pathlib import Path
import pytest
import yaml

from loop.mb_load.plan_section import (
    evaluate_plan_read,
    is_whole_plan_path,
    load_plan_jumps,
    materialize_plan_jump,
    parse_plan_jump,
)
from loop.mb_load.resolver import resolve_bundle_paths
from loop.prompt_builder import (
    PromptScope,
    build_prompt_scope,
    render_prompt_scope,
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir(parents=True, exist_ok=True)
    return proj


def test_parse_and_materialize_plan_jump(workspace: Path):
    plan_dir = workspace / "memory-bank" / "back" / "plan" / "T-HUB-078" / "md"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / "plan.md"
    plan_file.write_text(
        "\n".join(f"## Header {i}\nBody line {i}" for i in range(1, 50)),
        encoding="utf-8",
    )

    # 1. Test jump parsing with various syntax forms
    p, s, e = parse_plan_jump("memory-bank/back/plan/T-HUB-078/md/plan.md:10-20")
    assert p == "memory-bank/back/plan/T-HUB-078/md/plan.md"
    assert s == 10
    assert e == 20

    p2, s2, e2 = parse_plan_jump("memory-bank/back/plan/T-HUB-078/md/plan.md#L15-L25")
    assert p2 == "memory-bank/back/plan/T-HUB-078/md/plan.md"
    assert s2 == 15
    assert e2 == 25

    p3, s3, e3 = parse_plan_jump("memory-bank/back/plan/T-HUB-078/md/plan.md:30")
    assert p3 == "memory-bank/back/plan/T-HUB-078/md/plan.md"
    assert s3 == 30
    assert e3 == 30

    # 2. Materialize plan jump excerpt
    res = materialize_plan_jump("memory-bank/back/plan/T-HUB-078/md/plan.md:10-20", cwd=workspace)
    assert res["ok"] is True
    assert res["start_line"] == 10
    assert res["end_line"] == 20
    assert res["line_count"] == 11
    assert "memory-bank/back/plan/T-HUB-078/md/plan.md:10-20" in res["excerpt_identity"]
    assert len(res["content"]) > 0


def test_load_plan_jumps_from_shard_data(workspace: Path):
    plan_dir = workspace / "memory-bank" / "back" / "plan" / "T-HUB-078" / "md"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / "plan.md"
    plan_file.write_text("\n".join(f"line {i}" for i in range(1, 100)), encoding="utf-8")

    shard = {
        "step_id": "s03",
        "plan_contract": {
            "plan_jumps": [
                "memory-bank/back/plan/T-HUB-078/md/plan.md:10-20",
                "memory-bank/back/plan/T-HUB-078/md/plan.md:40-50",
            ],
        },
    }

    excerpts = load_plan_jumps(shard, cwd=workspace)
    assert len(excerpts) == 2
    assert excerpts[0]["excerpt_identity"] == "memory-bank/back/plan/T-HUB-078/md/plan.md:10-20"
    assert excerpts[1]["excerpt_identity"] == "memory-bank/back/plan/T-HUB-078/md/plan.md:40-50"


def test_resolver_denies_whole_plan_in_implement_and_allows_in_decompose(workspace: Path):
    mb = workspace / "memory-bank"
    plan_md = mb / "back" / "plan" / "T-HUB-078" / "md" / "plan.md"
    plan_md.parent.mkdir(parents=True, exist_ok=True)
    plan_md.write_text("# Monolithic Plan\n", encoding="utf-8")

    load_now = ["memory-bank/back/plan/T-HUB-078/md/plan.md"]

    # 1. In IMPLEMENT mode: whole plan is forbidden
    bundle_impl = resolve_bundle_paths(
        cwd=workspace,
        mode="IMPLEMENT",
        step_id="s01",
        load_now_paths=load_now,
        epic_id="T-HUB-078",
        role="back",
    )
    assert "memory-bank/back/plan/T-HUB-078/md/plan.md" in bundle_impl.forbidden_skipped
    assert any("whole_plan_forbidden_in_implement" in d for d in bundle_impl.diagnostics)

    # 2. In DECOMPOSE mode: whole plan is allowed
    bundle_dec = resolve_bundle_paths(
        cwd=workspace,
        mode="DECOMPOSE",
        step_id="s01",
        load_now_paths=load_now,
        epic_id="T-HUB-078",
        role="back",
    )
    assert "memory-bank/back/plan/T-HUB-078/md/plan.md" in bundle_dec.resolved_paths
    assert not bundle_dec.forbidden_skipped


def test_prompt_builder_renders_bounded_plan_jumps(workspace: Path):
    jumps = [
        "memory-bank/back/plan/T-HUB-078/md/plan.md:84-115",
        "memory-bank/back/plan/T-HUB-078/md/plan.md:231-253",
    ]

    scope = build_prompt_scope(
        workspace,
        projection={
            "role": "BACK",
            "phase": "IMPLEMENT",
            "step": "s03",
            "epic": "T-HUB-078",
        },
        plan_jumps=jumps,
    )

    assert scope.plan_jumps == tuple(jumps)
    rendered = render_prompt_scope(scope)

    assert "## PLAN EXCERPTS (bounded)" in rendered
    assert "- jump: `memory-bank/back/plan/T-HUB-078/md/plan.md:84-115`" in rendered
    assert "- jump: `memory-bank/back/plan/T-HUB-078/md/plan.md:231-253`" in rendered
