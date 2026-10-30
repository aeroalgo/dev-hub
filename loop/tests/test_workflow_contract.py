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

    for role in ("back_developer", "front_developer", "integration_developer", "app_developer"):
        rules = ROOT / "harness/cursor/rules" / role
        assert not (rules / "workflow-analyze.mdc").exists()
        assert not (rules / "workflow-audit.mdc").exists()
        assert not (rules / "workflow-context-sync.mdc").exists()


def test_app_is_a_full_vertical_slice_role() -> None:
    app_rules = ROOT / "harness/cursor/rules/app_developer"
    app_index = (app_rules / "mainrule.mdc").read_text(encoding="utf-8")
    app_core = (app_rules / "mainrule-core.mdc").read_text(encoding="utf-8")
    router = (ROOT / "harness/cursor/stubs/dev-hub-harness-router.mdc").read_text(encoding="utf-8")
    verify_implement = (ROOT / "harness/agents/verify-implement.md").read_text(encoding="utf-8")
    context_sync = (ROOT / "harness/agents/context-sync.md").read_text(encoding="utf-8")
    assert "APP IMPLEMENT" in app_index
    assert "APP QA" in app_index and "APP BUGFIX" in app_index
    assert "APP не создаёт отдельную INTEG-очередь" in app_index
    assert "Contract first" in app_core
    assert "backend" in app_core and "frontend_build" in app_core and "wire_journey" in app_core
    assert "`APP `" in router
    assert "role: back|front|app" in verify_implement
    assert "`deny_old_proven: true`" in verify_implement
    assert "`back` / `front` / `app` / `integration`" in context_sync
    assert "exactly one fenced JSON object" in context_sync
    assert "do not emit a bare JSON object" in context_sync
    for mode in ("van", "plan", "decompose", "creative", "implement", "task", "refactor", "archive", "replan", "reconcile"):
        assert (app_rules / f"workflow-{mode}.mdc").is_file()
        assert (app_rules / "isolation_rules/_lean" / f"{mode}.mdc").is_file()


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

    manifest = (ROOT / "harness/manifest.yaml").read_text(encoding="utf-8")
    assert "analyze-verify" not in manifest
    verify_decompose = (ROOT / "harness/agents/verify-decompose.md").read_text(encoding="utf-8")
    assert "structural and semantic" in verify_decompose
    assert "атомарно открывает `IMPLEMENT/CREATIVE`" in verify_decompose
    assert "analyze-verify" in verify_decompose and "не являются частью нового контракта" in verify_decompose

    qa_readme = (ROOT / "harness/cursor/templates/qa/README.md").read_text(encoding="utf-8")
    assert "/review" in qa_readme and "/test-audit" in qa_readme
    assert "not separate loop phases" in qa_readme
    assert "test-catalog.yaml" in qa_readme

    catalog = yaml.safe_load((ROOT / "harness/cursor/templates/qa/test-catalog.yaml").read_text(encoding="utf-8"))
    assert catalog["schema"] == "qa-test-catalog/v1"
    catalog_ids = {row["id"] for row in catalog["tests"]}
    assert {
        "contract_acceptance",
        "regression",
        "backend_unit_component",
        "backend_integration_state",
        "api_contract",
        "frontend_build_assets",
        "browser_functional",
        "wire_journey",
        "live_http_smoke",
        "negative_error_paths",
        "auth_session_rbac",
        "security_owasp",
        "accessibility",
        "responsive_compatibility",
        "performance_resilience",
        "cleanup_sot",
    } <= catalog_ids

    qa = yaml.safe_load((ROOT / "harness/cursor/templates/qa/epic-step.yaml").read_text(encoding="utf-8"))
    for field in ("coverage_map", "review", "test_audit", "browser", "retro"):
        assert field in qa
    for template in (qa, yaml.safe_load((ROOT / "harness/cursor/templates/qa/app-epic-step.yaml").read_text(encoding="utf-8"))):
        assert template["test_plan"]["catalog"] == ".cursor/templates/qa/test-catalog.yaml"
        assert set(template["test_plan"]) >= {
            "catalog",
            "source",
            "mode",
            "scope_signals",
            "selected",
            "not_applicable",
            "not_run",
        }
    assert {row["kind"] for row in qa["coverage_map"]} == {"AC", "BN"}
    assert {"defect_missed", "redundant_gate", "flaky_test", "next_cycle_change"} <= set(qa["retro"])
    assert "evidence_file" in qa["browser"]
    assert "evidence_file" in qa["live_smoke"]

    app_qa = yaml.safe_load((ROOT / "harness/cursor/templates/qa/app-epic-step.yaml").read_text(encoding="utf-8"))
    assert app_qa["suite_scope"] == "app_lanes"
    assert "evidence_file" in app_qa["browser"]
    assert "evidence_file" in app_qa["live_smoke"]

    verify_qa = (ROOT / "harness/agents/verify-qa.md").read_text(encoding="utf-8")
    assert "typed runtime artifact" in verify_qa
    assert "scope-driven" in verify_qa and "test_plan" in verify_qa and "test-catalog.yaml" in verify_qa
    assert "mock_*" in verify_qa
    assert "sync-bugfix-queue" in verify_qa
    verify_bugfix = (ROOT / "harness/agents/verify-bugfix.md").read_text(encoding="utf-8")
    assert "evidence_file" in verify_bugfix
    assert "live_evidence: true" in verify_bugfix
    assert "sync-bugfix-queue" in verify_bugfix
