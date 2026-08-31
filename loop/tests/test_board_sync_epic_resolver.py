import pytest
from pathlib import Path
from loop.board_sync.epic_resolver import resolve_epic_next_action, EpicNextAction, _epic_done
from loop.board_sync.plan_next import write_plan_next, validate_plan_next, EpicNextOverride
from epic import _append_event

def _add_event(tmp_path: Path, epic_id: str, kind: str):
    art_dir = tmp_path / "memory-bank" / "back" / "events" / epic_id
    art_dir.mkdir(parents=True, exist_ok=True)
    art = art_dir / f"art-{kind}.txt"
    art.write_text(f"artifact for {kind}")
    _append_event(tmp_path, "back", epic_id, kind, art)

def test_resolve_no_plan_returns_plan_command(tmp_path: Path):
    res = resolve_epic_next_action(tmp_path, "back", "T-HUB-999")
    assert res.phase == "PLAN"
    assert res.next_command == "BACK PLAN T-HUB-999"
    assert res.reason_code == "plan_missing"

def test_resolve_plan_no_decompose_returns_decompose_command(tmp_path: Path):
    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "plan-T-HUB-999.md").write_text("# Plan T-HUB-999\n")

    res = resolve_epic_next_action(tmp_path, "back", "T-HUB-999")
    assert res.phase == "DECOMPOSE"
    assert res.next_command == "BACK DECOMPOSE T-HUB-999"
    assert res.reason_code == "decompose_missing"

def test_resolver_stale_analyze_returns_arm_analyze(tmp_path: Path):
    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "plan-T-HUB-999.md").write_text("# Plan T-HUB-999\n")

    decomp_dir = plan_dir / "decompose-T-HUB-999"
    decomp_dir.mkdir(parents=True, exist_ok=True)
    (decomp_dir / "index.yaml").write_text("""
steps:
  - step_id: s01
    status: pending
""")

    res = resolve_epic_next_action(tmp_path, "back", "T-HUB-999")
    assert res.phase == "ANALYZE"
    assert res.next_command == "BACK ANALYZE T-HUB-999"
    assert res.reason_code == "stale_analyze_pending"


def test_implement_next_step_returns_first_pending(tmp_path: Path):
    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "plan-T-HUB-999.md").write_text("# Plan T-HUB-999\n")

    decomp_dir = plan_dir / "decompose-T-HUB-999"
    decomp_dir.mkdir(parents=True, exist_ok=True)
    (decomp_dir / "index.yaml").write_text("""
steps:
  - step_id: s01
    status: completed
  - step_id: s02
    status: pending
""")

    res = resolve_epic_next_action(tmp_path, "back", "T-HUB-999")
    assert res.phase == "IMPLEMENT"
    assert res.next_command == "BACK IMPLEMENT s02"
    assert res.next_step_id == "s02"
    assert res.reason_code == "implement_pending"

def test_resolve_clarify_required(tmp_path: Path):
    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "plan-T-HUB-999.md").write_text("# Plan T-HUB-999\n- [ ] CRITICAL: Need details\n")

    decomp_dir = plan_dir / "decompose-T-HUB-999"
    decomp_dir.mkdir(parents=True, exist_ok=True)
    (decomp_dir / "index.yaml").write_text("""
steps:
  - step_id: s01
    status: pending
""")

    analyze_dir = tmp_path / "memory-bank" / "back" / "analyze" / "T-HUB-999"
    analyze_dir.mkdir(parents=True, exist_ok=True)
    (analyze_dir / "analyze-01.yaml").write_text("""
metrics:
  critical_count: 0
""")

    res = resolve_epic_next_action(tmp_path, "back", "T-HUB-999")
    assert res.phase == "CLARIFY"
    assert res.next_command == "BACK CLARIFY T-HUB-999"
    assert res.reason_code == "clarify_required"

def test_resolve_override_valid_takes_precedence(tmp_path: Path):
    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / "plan-T-HUB-999.md"
    plan_file.write_text("# Plan T-HUB-999\n")

    write_plan_next(plan_file, EpicNextOverride(epic_id="T-HUB-999", role="back", next_command="BACK DECOMPOSE T-HUB-999"))

    res = resolve_epic_next_action(tmp_path, "back", "T-HUB-999")
    assert res.phase == "DECOMPOSE"
    assert res.next_command == "BACK DECOMPOSE T-HUB-999"
    assert res.reason_code == "override_valid"

def test_resolve_override_conflict_returns_diagnostic(tmp_path: Path):
    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / "plan-T-HUB-999.md"
    plan_file.write_text("# Plan T-HUB-999\n")

    # IMPLEMENT override without decompose file existing -> conflict
    write_plan_next(plan_file, EpicNextOverride(epic_id="T-HUB-999", role="back", next_command="BACK IMPLEMENT s01"))

    res = resolve_epic_next_action(tmp_path, "back", "T-HUB-999")
    assert res.reason_code == "override_conflict"
    assert res.diagnostic is not None
    assert "decompose shard index does not exist" in res.diagnostic

def test_post_implement_qa(tmp_path: Path):
    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "plan-T-HUB-999.md").write_text("# Plan T-HUB-999\n")

    decomp_dir = plan_dir / "decompose-T-HUB-999"
    decomp_dir.mkdir(parents=True, exist_ok=True)
    (decomp_dir / "index.yaml").write_text("""
steps:
  - step_id: s01
    status: completed
""")
    _add_event(tmp_path, "T-HUB-999", "audit_done")

    res = resolve_epic_next_action(tmp_path, "back", "T-HUB-999")
    assert res.phase == "QA"
    assert res.next_command == "BACK QA T-HUB-999"
    assert res.reason_code == "qa_required"

def test_post_implement_epic_done(tmp_path: Path):
    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "plan-T-HUB-999.md").write_text("# Plan T-HUB-999\n")

    decomp_dir = plan_dir / "decompose-T-HUB-999"
    decomp_dir.mkdir(parents=True, exist_ok=True)
    (decomp_dir / "index.yaml").write_text("""
steps:
  - step_id: s01
    status: completed
""")
    _add_event(tmp_path, "T-HUB-999", "audit_done")
    _add_event(tmp_path, "T-HUB-999", "qa_pass")
    _add_event(tmp_path, "T-HUB-999", "reflection_done")

    res = resolve_epic_next_action(tmp_path, "back", "T-HUB-999")
    assert res.phase == "DONE"
    assert res.reason_code == "epic_done"
    assert _epic_done(tmp_path, "back", "T-HUB-999") is True

def test_validate_conflict_decompose_missing_plan():
    override = EpicNextOverride(
        epic_id="T-HUB-999",
        role="back",
        next_command="BACK DECOMPOSE T-HUB-999",
    )
    diag = validate_plan_next(override, {"plan_exists": False})
    assert diag is not None
    assert "plan file does not exist" in diag

def test_resolve_post_implement_qa_done_reflect_needed(tmp_path: Path):
    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "plan-T-HUB-999.md").write_text("# Plan T-HUB-999\n")

    decomp_dir = plan_dir / "decompose-T-HUB-999"
    decomp_dir.mkdir(parents=True, exist_ok=True)
    (decomp_dir / "index.yaml").write_text("""
steps:
  - step_id: s01
    status: completed
""")
    _add_event(tmp_path, "T-HUB-999", "audit_done")
    _add_event(tmp_path, "T-HUB-999", "qa_pass")

    res = resolve_epic_next_action(tmp_path, "back", "T-HUB-999")
    assert res.phase == "REFLECT"
    assert res.next_command == "BACK REFLECT T-HUB-999"
    assert res.reason_code == "qa_passed"

def test_resolve_post_implement_bugfix_active(tmp_path: Path):
    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "plan-T-HUB-999.md").write_text("# Plan T-HUB-999\n")

    decomp_dir = plan_dir / "decompose-T-HUB-999"
    decomp_dir.mkdir(parents=True, exist_ok=True)
    (decomp_dir / "index.yaml").write_text("""
steps:
  - step_id: s01
    status: completed
""")
    _add_event(tmp_path, "T-HUB-999", "audit_done")
    _add_event(tmp_path, "T-HUB-999", "qa_fail")

    res = resolve_epic_next_action(tmp_path, "back", "T-HUB-999")
    assert res.phase == "BUGFIX"
    assert res.next_command == "BACK BUGFIX T-HUB-999"
    assert res.reason_code == "qa_failed"

def test_validate_plan_next_conflict_post_implement_pending_steps():
    override = EpicNextOverride(
        epic_id="T-HUB-999",
        role="back",
        next_command="BACK QA T-HUB-999",
    )
    diag = validate_plan_next(override, {"pending_steps": True})
    assert diag is not None
    assert "implement steps pending" in diag
