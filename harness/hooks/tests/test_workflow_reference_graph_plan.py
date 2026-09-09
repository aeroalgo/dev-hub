"""Tests for ANALYZE, PLAN, and CLARIFY workflow reference graph hygiene (T-HUB-084: s03)."""
from __future__ import annotations

from pathlib import Path
import re
import pytest

from loop.workflow.pack_graph import (
    extract_reference_edges,
    validate_reference_graph,
    check_pack_graph,
)
from loop.workflow.schemas import WorkflowPack

ROOT = Path(__file__).resolve().parents[3]

SCOPED_WORKFLOWS = {
    "ANALYZE": ROOT / "harness/cursor/rules/back_developer/workflow-analyze.mdc",
    "PLAN": ROOT / "harness/cursor/rules/back_developer/workflow-plan.mdc",
    "CLARIFY": ROOT / "harness/cursor/rules/back_developer/workflow-clarify.mdc",
}

SCOPED_LEAN_GATES = {
    "ANALYZE": ROOT / "harness/cursor/rules/back_developer/isolation_rules/_lean/analyze.mdc",
    "PLAN": ROOT / "harness/cursor/rules/back_developer/isolation_rules/_lean/plan.mdc",
    "CLARIFY": ROOT / "harness/cursor/rules/back_developer/isolation_rules/_lean/clarify.mdc",
}

SHARED_ORCHESTRATION = ROOT / "harness/cursor/rules/shared/workflow-plan-clarify-orchestration.mdc"


def test_analyze_plan_clarify_each_have_one_owner() -> None:
    """cp1 / FR-001 / FR-002: ANALYZE, PLAN, and CLARIFY each have one canonical owner edge with an explicit lazy timing contract."""
    rules_root = ROOT / ".cursor/rules"

    # 1. Check explicit lazy timing in all three workflows
    for mode, w_path in SCOPED_WORKFLOWS.items():
        assert w_path.is_file(), f"Missing workflow file for {mode}: {w_path}"
        content = w_path.read_text(encoding="utf-8")
        assert re.search(r"Policy lazy\s*\(по триггеру,\s*не грузить целиком\):", content), (
            f"{mode} workflow must declare explicit lazy timing note"
        )

    # 2. ANALYZE ownership
    an_edges = extract_reference_edges(SCOPED_WORKFLOWS["ANALYZE"], rules_root, ROOT, ROOT)
    an_core_edges = [e for e in an_edges if e.target_canonical and "workflow-analyze-core" in e.target_canonical]
    assert len(an_core_edges) == 1, f"ANALYZE workflow must have exactly 1 edge to workflow-analyze-core, found {len(an_core_edges)}"

    lean_an_edges = extract_reference_edges(SCOPED_LEAN_GATES["ANALYZE"], rules_root, ROOT, ROOT)
    lean_an_core_edges = [e for e in lean_an_edges if e.target_canonical and "workflow-analyze-core" in e.target_canonical]
    assert len(lean_an_core_edges) == 0, f"Lean analyze gate must have 0 edges to workflow-analyze-core, found {len(lean_an_core_edges)}"

    # 3. PLAN ownership
    plan_edges = extract_reference_edges(SCOPED_WORKFLOWS["PLAN"], rules_root, ROOT, ROOT)
    for expected_target in [
        "workflow-plan-clarify-orchestration",
        "workflow-plan-multi-epic",
        "workflow-plan-outcome-prompt",
        "workflow-behavior-first",
        "workflow-legacy-fallback-cleanup",
        "workflow-spec-first-replace",
    ]:
        matched = [e for e in plan_edges if e.target_canonical and expected_target in e.target_canonical]
        assert len(matched) == 1, f"PLAN workflow must have exactly 1 edge to {expected_target}, found {len(matched)}"

    lean_plan_edges = extract_reference_edges(SCOPED_LEAN_GATES["PLAN"], rules_root, ROOT, ROOT)
    for forbidden_target in [
        "workflow-plan-clarify-orchestration",
        "workflow-plan-multi-epic",
        "workflow-plan-outcome-prompt",
        "workflow-legacy-fallback-cleanup",
    ]:
        matched = [e for e in lean_plan_edges if e.target_canonical and forbidden_target in e.target_canonical]
        assert len(matched) == 0, f"Lean plan gate must have 0 edges to {forbidden_target}, found {len(matched)}"

    # 4. CLARIFY ownership
    clarify_edges = extract_reference_edges(SCOPED_WORKFLOWS["CLARIFY"], rules_root, ROOT, ROOT)
    for expected_target in [
        "workflow-clarify-core",
        "workflow-plan-clarify-orchestration",
        "templates/clarify.md",
    ]:
        matched = [e for e in clarify_edges if e.target_canonical and expected_target in e.target_canonical]
        assert len(matched) == 1, f"CLARIFY workflow must have exactly 1 edge to {expected_target}, found {len(matched)}"

    lean_clarify_edges = extract_reference_edges(SCOPED_LEAN_GATES["CLARIFY"], rules_root, ROOT, ROOT)
    for forbidden_target in [
        "workflow-clarify-core",
        "workflow-plan-clarify-orchestration",
        "templates/clarify.md",
    ]:
        matched = [e for e in lean_clarify_edges if e.target_canonical and forbidden_target in e.target_canonical]
        assert len(matched) == 0, f"Lean clarify gate must have 0 edges to {forbidden_target}, found {len(matched)}"

    # 5. Shared orchestration has 0 redundant outgoing @ edges
    orch_edges = extract_reference_edges(SHARED_ORCHESTRATION, rules_root, ROOT, ROOT)
    for forbidden_target in [
        "workflow-clarify-core",
        "templates/clarify.md",
        "grill-me",
        "workflow-plan-outcome-prompt",
    ]:
        matched = [e for e in orch_edges if e.target_canonical and forbidden_target in e.target_canonical]
        assert len(matched) == 0, f"Shared orchestration must have 0 edges to {forbidden_target}, found {len(matched)}"


def test_plan_clarify_phase_zero_semantics_survive() -> None:
    """cp2 / FR-004 / TM-084-03: Mandatory ANALYZE gate and Phase 0 PLAN/CLARIFY semantics remain present."""
    an_content = SCOPED_WORKFLOWS["ANALYZE"].read_text(encoding="utf-8")
    assert "### Команда: BACK ANALYZE" in an_content
    assert "metrics.critical_count = 0" in an_content
    assert "hard gate" in an_content

    plan_content = SCOPED_WORKFLOWS["PLAN"].read_text(encoding="utf-8")
    assert "### Команда: BACK PLAN" in plan_content
    assert "Phase 0 orchestration" in plan_content
    assert "Phase 0 Clarify" in plan_content

    clarify_content = SCOPED_WORKFLOWS["CLARIFY"].read_text(encoding="utf-8")
    assert "### Команда: BACK CLARIFY" in clarify_content
    assert "PLAN orchestration" in clarify_content
    assert "Phase 0" in clarify_content

    orch_content = SHARED_ORCHESTRATION.read_text(encoding="utf-8")
    assert "PLAN Phase 0" in orch_content
    assert "auto-clarify orchestration" in orch_content


def test_analyze_sole_owner_is_fail_closed(tmp_path: Path) -> None:
    """cp4 / FR-002 / TM-084-02: A sole ANALYZE/PLAN/CLARIFY owner cannot be removed without a validation failure."""
    rules_root = tmp_path / ".cursor/rules"
    rules_root.mkdir(parents=True, exist_ok=True)
    shared_dir = rules_root / "shared"
    shared_dir.mkdir(parents=True, exist_ok=True)

    # Core policy leaf
    analyze_core_file = shared_dir / "workflow-analyze-core.mdc"
    analyze_core_file.write_text("---\ndescription: analyze core\n---\nAnalyze core content\n", encoding="utf-8")

    # Workflow declaring single owner edge
    wf_file = rules_root / "workflow-analyze.mdc"
    wf_file.write_text(
        "---\n"
        "description: analyze\n"
        "---\n"
        "### Команда: BACK ANALYZE\n"
        "**Policy lazy (по триггеру, не грузить целиком):** @.cursor/rules/shared/workflow-analyze-core.mdc\n"
        "1. Detection passes using shared/workflow-analyze-core.mdc\n",
        encoding="utf-8",
    )

    pack = WorkflowPack(
        id="analyze-test-pack",
        roles=["back"],
        command_prefixes=["BACK"],
        phase_registry="phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
    )
    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    (tmp_path / "phase_registry.yaml").write_text("schema: phase-registry/v1\nphases: {}\n", encoding="utf-8")

    # 1. Single owner passes validation
    res = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert res.ok is True
    assert len(res.diagnostic_codes) == 0

    # 2. Adding redundant direct edge causes duplicate diagnostic
    wf_file.write_text(
        "---\n"
        "description: analyze\n"
        "---\n"
        "### Команда: BACK ANALYZE\n"
        "**Policy lazy (по триггеру, не грузить целиком):** @.cursor/rules/shared/workflow-analyze-core.mdc\n"
        "1. Detection passes @.cursor/rules/shared/workflow-analyze-core.mdc\n",
        encoding="utf-8",
    )
    res_dup = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert not res_dup.ok
    assert "pack_reference_duplicate" in res_dup.diagnostic_codes

    # 3. Removing redundant edge restores green state
    wf_file.write_text(
        "---\n"
        "description: analyze\n"
        "---\n"
        "### Команда: BACK ANALYZE\n"
        "**Policy lazy (по триггеру, не грузить целиком):** @.cursor/rules/shared/workflow-analyze-core.mdc\n"
        "1. Detection passes using shared/workflow-analyze-core.mdc\n",
        encoding="utf-8",
    )
    res_restored = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert res_restored.ok is True

    # 4. Removing sole owner file causes dangling reference diagnostic
    analyze_core_file.unlink()
    res_dangling = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert not res_dangling.ok
    assert "pack_reference_dangling" in res_dangling.diagnostic_codes
