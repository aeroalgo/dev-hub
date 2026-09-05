"""Tests for loop/mb_load/resolver.py mode matrix & auto-resolve."""

from pathlib import Path
import pytest

from loop.mb_load.resolver import resolve_bundle_paths


def test_auto_resolve_implement_yaml(tmp_path: Path) -> None:
    # Setup decompose shard and implement shard on disk
    dec_dir = tmp_path / "memory-bank/back/plan/decompose-T-HUB-999-test"
    dec_dir.mkdir(parents=True, exist_ok=True)
    dec_file = dec_dir / "s05-test-step.yaml"
    dec_file.write_text("schema: epic-decompose/v1\nrole: back\nstep_id: s05\nplan_id: T-HUB-999-test\n", encoding="utf-8")

    impl_dir = tmp_path / "memory-bank/back/implement/implement-T-HUB-999-test"
    impl_dir.mkdir(parents=True, exist_ok=True)
    impl_file = impl_dir / "s05-test-step.yaml"
    impl_file.write_text("schema: epic-implement/v1\nrole: back\nstep_id: s05\nplan_id: T-HUB-999-test\n", encoding="utf-8")

    load_now = [
        "memory-bank/back/plan/decompose-T-HUB-999-test/s05-test-step.yaml",
        "memory-bank/back/plan/decompose-T-HUB-999-test/index.yaml",
    ]

    res = resolve_bundle_paths(tmp_path, mode="IMPLEMENT", step_id="s05", load_now_paths=load_now)
    rel_impl = "memory-bank/back/implement/implement-T-HUB-999-test/s05-test-step.yaml"
    assert rel_impl in res.resolved_paths
    assert rel_impl in res.auto_added


def test_mode_matrix(tmp_path: Path) -> None:
    # QA mode auto-resolves qa shard if exists
    qa_dir = tmp_path / "memory-bank/back/qa/T-HUB-999-test"
    qa_dir.mkdir(parents=True, exist_ok=True)
    qa_file = qa_dir / "qa-20260902-s05-pass.yaml"
    qa_file.write_text("schema: epic-qa/v1\n", encoding="utf-8")

    res_qa = resolve_bundle_paths(tmp_path, mode="QA", step_id="s05", load_now_paths=[], epic_id="T-HUB-999-test", role="back")
    assert any("qa-20260902-s05-pass.yaml" in p for p in res_qa.resolved_paths)
    assert any("qa-20260902-s05-pass.yaml" in p for p in res_qa.auto_added)

    # IMPLEMENT mode forbids plan-*.md
    load_now_impl = [
        "memory-bank/back/plan/plan-T-HUB-999-test.md",
        "loop/mb_load/resolver.py",
    ]
    res_impl = resolve_bundle_paths(tmp_path, mode="IMPLEMENT", step_id="s05", load_now_paths=load_now_impl)
    assert "memory-bank/back/plan/plan-T-HUB-999-test.md" in res_impl.forbidden_skipped
    assert "memory-bank/back/plan/plan-T-HUB-999-test.md" not in res_impl.resolved_paths
    assert "loop/mb_load/resolver.py" in res_impl.resolved_paths


def test_decompose_plan_allowed(tmp_path: Path) -> None:
    load_now = [
        "memory-bank/back/plan/plan-T-HUB-999-test.md",
        "memory-bank/back/plan/decompose-T-HUB-999-test/index.yaml",
    ]
    res = resolve_bundle_paths(tmp_path, mode="DECOMPOSE", step_id=None, load_now_paths=load_now)
    assert "memory-bank/back/plan/plan-T-HUB-999-test.md" in res.resolved_paths
    assert "memory-bank/back/plan/plan-T-HUB-999-test.md" not in res.forbidden_skipped


def test_resolver_idempotent(tmp_path: Path) -> None:
    load_now = [
        "memory-bank/back/plan/decompose-T-HUB-999-test/index.yaml",
    ]
    res1 = resolve_bundle_paths(tmp_path, mode="IMPLEMENT", step_id="s05", load_now_paths=load_now)
    res2 = resolve_bundle_paths(tmp_path, mode="IMPLEMENT", step_id="s05", load_now_paths=res1.resolved_paths)
    assert res1.resolved_paths == res2.resolved_paths
    assert res2.auto_added == []


@pytest.mark.parametrize("mode", ["IMPLEMENT", "QA", "BUGFIX"])
def test_no_cross_epic_auto_added_artifacts(tmp_path, mode):
    kind = mode.lower()
    filename = "s01-old.yaml" if mode == "IMPLEMENT" else f"{kind}-20260905-s01.yaml"
    old = tmp_path / f"memory-bank/back/{kind}/T-OLD/{filename}"
    old.parent.mkdir(parents=True)
    old.write_text("epic_id: T-OLD\n")
    paths = ["memory-bank/back/plan/T-NEW/yaml/decompose-index.yaml"]
    result = resolve_bundle_paths(tmp_path, mode, "s01", paths)
    assert result.auto_added == []
    assert not any("T-OLD" in p for p in result.resolved_paths)


def test_layout_v2_resolves_exact_step_and_epic(tmp_path):
    for epic, step in [("T-OLD", "s01"), ("T-NEW", "s010"), ("T-NEW", "s01")]:
        p = tmp_path / f"memory-bank/back/implement/implement-{epic}/{step}-impl.yaml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"epic_id: {epic}\nstep_id: {step}\n")
    result = resolve_bundle_paths(tmp_path, "IMPLEMENT", "s01", ["memory-bank/back/plan/T-NEW/yaml/decompose-index.yaml"])
    assert result.auto_added == ["memory-bank/back/implement/implement-T-NEW/s01-impl.yaml"]
