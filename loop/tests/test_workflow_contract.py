from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_obsolete_review_phases_are_not_public_commands() -> None:
    old_commands = {
        "back-analyze.md",
        "back-audit.md",
        "back-context-sync.md",
        "front-analyze.md",
        "front-audit.md",
        "front-context-sync.md",
        "integ-analyze.md",
        "integ-audit.md",
        "integ-context-sync.md",
    }
    for commands_root in (ROOT / "harness/claude/commands", ROOT / ".claude/commands"):
        assert not old_commands.intersection(path.name for path in commands_root.glob("*.md"))

    for role in ("back_developer", "front_developer", "integration_developer"):
        rules = ROOT / "harness/cursor/rules" / role
        assert not (rules / "workflow-analyze.mdc").exists()
        assert not (rules / "workflow-audit.mdc").exists()
        assert not (rules / "workflow-context-sync.mdc").exists()


def test_plan_and_qa_contracts_keep_the_interactive_and_evidence_gates() -> None:
    review_passes = (ROOT / "harness/cursor/rules/shared/workflow-plan-review-passes.mdc").read_text(
        encoding="utf-8"
    )
    assert review_passes.index("Product → Design? → DX? → Eng") < review_passes.index("## Ownership matrix")
    assert "Вопрос владельцу" in review_passes
    plan_template = (ROOT / "harness/cursor/templates/plan.md").read_text(encoding="utf-8")
    assert "BACK TASK" in plan_template and "BACK IMPLEMENT" in plan_template
    assert "Infra" in review_passes and "Independent check" in review_passes

    board_template = (ROOT / "harness/templates/board/board-projection.yaml.example").read_text(
        encoding="utf-8"
    )
    assert "ANALYZE:" not in board_template
    assert "AUDIT:" not in board_template
    assert "CONTEXT_SYNC:" not in board_template

    for lifecycle_path in (
        ROOT / "harness/cursor/rules/back_developer/mainrule-core.mdc",
        ROOT / "harness/cursor/rules/front_developer/mainrule-core.mdc",
        ROOT / "loop/README.md",
    ):
        lifecycle = lifecycle_path.read_text(encoding="utf-8")
        assert "DECOMPOSE(+analyze-verify)" not in lifecycle
        assert "QA(+contract + context-sync)" not in lifecycle

    qa_readme = (ROOT / "harness/cursor/templates/qa/README.md").read_text(encoding="utf-8")
    assert "/review" in qa_readme and "/test-audit" in qa_readme
    assert "not separate loop phases" in qa_readme

    qa = yaml.safe_load((ROOT / "harness/cursor/templates/qa/epic-step.yaml").read_text(encoding="utf-8"))
    for field in ("coverage_map", "review", "test_audit", "browser", "retro"):
        assert field in qa
    assert {row["kind"] for row in qa["coverage_map"]} == {"AC", "BN"}
    assert {"defect_missed", "redundant_gate", "flaky_test", "next_cycle_change"} <= set(qa["retro"])
