"""Tests for VAN and REFACTOR workflow reference graph hygiene (T-HUB-084: s04)."""
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
    "VAN": ROOT / "harness/cursor/rules/back_developer/workflow-van.mdc",
    "REFACTOR": ROOT / "harness/cursor/rules/back_developer/workflow-refactor.mdc",
    "PLAN_REFACTOR": ROOT / "harness/cursor/rules/back_developer/workflow-plan-refactor.mdc",
}

SCOPED_LEAN_GATES = {
    "VAN": ROOT / "harness/cursor/rules/back_developer/isolation_rules/_lean/van.mdc",
    "REFACTOR": ROOT / "harness/cursor/rules/back_developer/isolation_rules/_lean/refactor.mdc",
    "PLAN_REFACTOR": ROOT / "harness/cursor/rules/back_developer/isolation_rules/_lean/plan-refactor.mdc",
}

SHARED_OWNERS = {
    "VAN_BROWNFIELD": ROOT / "harness/cursor/rules/shared/workflow-van-brownfield.mdc",
    "REFACTOR_EPIC": ROOT / "harness/cursor/rules/shared/workflow-refactor-epic.mdc",
}


def test_van_refactor_topology_has_one_owner() -> None:
    """cp1 / FR-001 / FR-002: VAN and REFACTOR topology each has one canonical owner edge and explicit lazy timing."""
    rules_root = ROOT / ".cursor/rules"

    # 1. VAN workflow has explicit lazy timing note for brownfield map
    van_w = SCOPED_WORKFLOWS["VAN"]
    assert van_w.is_file()
    van_content = van_w.read_text(encoding="utf-8")
    assert re.search(r"Policy lazy\s*\(по триггеру,\s*не грузить целиком\):", van_content), (
        "VAN workflow must declare explicit lazy timing note"
    )

    van_edges = extract_reference_edges(van_w, rules_root, ROOT, ROOT)
    van_bf_edges = [e for e in van_edges if e.target_canonical and "workflow-van-brownfield" in e.target_canonical]
    assert len(van_bf_edges) == 1, f"VAN workflow must have exactly 1 edge to workflow-van-brownfield, found {len(van_bf_edges)}"

    # VAN lean gate has 0 redundant @ edges
    van_lean = SCOPED_LEAN_GATES["VAN"]
    assert van_lean.is_file()
    van_lean_edges = extract_reference_edges(van_lean, rules_root, ROOT, ROOT)
    for forbidden in ["workflow-van-brownfield", "shared/_lean/van"]:
        matched = [e for e in van_lean_edges if e.target_canonical and forbidden in e.target_canonical]
        assert len(matched) == 0, f"VAN lean gate must have 0 edges to {forbidden}, found {len(matched)}"

    # VAN brownfield shared policy has 0 redundant outgoing @ edges
    van_bf = SHARED_OWNERS["VAN_BROWNFIELD"]
    assert van_bf.is_file()
    van_bf_edges_out = extract_reference_edges(van_bf, rules_root, ROOT, ROOT)
    for forbidden in ["memory-bank-paths"]:
        matched = [e for e in van_bf_edges_out if e.target_canonical and forbidden in e.target_canonical]
        assert len(matched) == 0, f"workflow-van-brownfield must have 0 edges to {forbidden}, found {len(matched)}"

    # 2. REFACTOR workflow has explicit lazy timing note
    ref_w = SCOPED_WORKFLOWS["REFACTOR"]
    assert ref_w.is_file()
    ref_content = ref_w.read_text(encoding="utf-8")
    assert re.search(r"Policy lazy\s*\(по триггеру,\s*не грузить целиком\):", ref_content), (
        "REFACTOR workflow must declare explicit lazy timing note"
    )

    ref_edges = extract_reference_edges(ref_w, rules_root, ROOT, ROOT)
    ref_epic_edges = [e for e in ref_edges if e.target_canonical and "workflow-refactor-epic" in e.target_canonical]
    assert len(ref_epic_edges) == 1, f"REFACTOR workflow must have exactly 1 edge to workflow-refactor-epic, found {len(ref_epic_edges)}"

    # REFACTOR lean gate has 0 redundant @ edges
    ref_lean = SCOPED_LEAN_GATES["REFACTOR"]
    assert ref_lean.is_file()
    ref_lean_edges = extract_reference_edges(ref_lean, rules_root, ROOT, ROOT)
    ref_lean_epic_edges = [e for e in ref_lean_edges if e.target_canonical and "workflow-refactor-epic" in e.target_canonical]
    assert len(ref_lean_epic_edges) == 0, f"REFACTOR lean gate must have 0 edges to workflow-refactor-epic, found {len(ref_lean_epic_edges)}"

    # 3. PLAN REFACTOR workflow has single owner edges to workflow-plan and workflow-refactor-epic
    plan_ref_w = SCOPED_WORKFLOWS["PLAN_REFACTOR"]
    assert plan_ref_w.is_file()
    plan_ref_content = plan_ref_w.read_text(encoding="utf-8")
    assert re.search(r"Policy lazy\s*\(по триггеру,\s*не грузить целиком\):", plan_ref_content), (
        "PLAN REFACTOR workflow must declare explicit lazy timing note"
    )

    plan_ref_edges = extract_reference_edges(plan_ref_w, rules_root, ROOT, ROOT)
    plan_edges = [e for e in plan_ref_edges if e.target_canonical and "workflow-plan.mdc" in e.target_canonical]
    assert len(plan_edges) == 1, f"PLAN REFACTOR workflow must have exactly 1 edge to workflow-plan, found {len(plan_edges)}"

    plan_ref_epic_edges = [e for e in plan_ref_edges if e.target_canonical and "workflow-refactor-epic" in e.target_canonical]
    assert len(plan_ref_epic_edges) == 1, f"PLAN REFACTOR workflow must have exactly 1 edge to workflow-refactor-epic, found {len(plan_ref_epic_edges)}"

    for forbidden in [
        "workflow-plan-multi-epic",
        "workflow-plan-outcome-prompt",
        "workflow-behavior-first",
    ]:
        matched = [e for e in plan_ref_edges if e.target_canonical and forbidden in e.target_canonical]
        assert len(matched) == 0, f"PLAN REFACTOR workflow must have 0 redundant edges to {forbidden}, found {len(matched)}"

    # PLAN REFACTOR lean gate has 0 redundant @ edges
    plan_ref_lean = SCOPED_LEAN_GATES["PLAN_REFACTOR"]
    assert plan_ref_lean.is_file()
    plan_ref_lean_edges = extract_reference_edges(plan_ref_lean, rules_root, ROOT, ROOT)
    assert len(plan_ref_lean_edges) == 0, f"PLAN REFACTOR lean gate must have 0 edges, found {len(plan_ref_lean_edges)}"

    # REFACTOR EPIC shared owner has 0 redundant outgoing @ edges
    ref_epic = SHARED_OWNERS["REFACTOR_EPIC"]
    assert ref_epic.is_file()
    ref_epic_edges_out = extract_reference_edges(ref_epic, rules_root, ROOT, ROOT)
    for forbidden in ["memory-bank-paths", "epic-scoped-paths", "finish-block"]:
        matched = [e for e in ref_epic_edges_out if e.target_canonical and forbidden in e.target_canonical]
        assert len(matched) == 0, f"workflow-refactor-epic must have 0 edges to {forbidden}, found {len(matched)}"


def test_brownfield_and_refactor_guards_remain_reachable() -> None:
    """cp2 / FR-004 / TM-084-03: Brownfield inventory and refactor-path/behavior-freeze guards remain reachable through the owner files."""
    van_w_content = SCOPED_WORKFLOWS["VAN"].read_text(encoding="utf-8")
    assert "### Команда: BACK VAN" in van_w_content
    assert "workflow-van-brownfield" in van_w_content

    van_bf_content = SHARED_OWNERS["VAN_BROWNFIELD"].read_text(encoding="utf-8")
    assert "SUSPENSION GUARD" in van_bf_content
    assert "graphify" in van_bf_content
    assert "Required shards" in van_bf_content
    assert "Mermaid minimum" in van_bf_content
    assert "inventory" in van_bf_content

    ref_w_content = SCOPED_WORKFLOWS["REFACTOR"].read_text(encoding="utf-8")
    assert "### Команда: BACK REFACTOR" in ref_w_content
    assert "workflow-refactor-epic" in ref_w_content
    assert "Behavior freeze" in ref_w_content

    ref_epic_content = SHARED_OWNERS["REFACTOR_EPIC"].read_text(encoding="utf-8")
    assert "REFACTOR epic" in ref_epic_content
    assert "rNN" in ref_epic_content
    assert "session-" in ref_epic_content

    plan_ref_w_content = SCOPED_WORKFLOWS["PLAN_REFACTOR"].read_text(encoding="utf-8")
    assert "BACK PLAN REFACTOR" in plan_ref_w_content
    assert "workflow-refactor-epic" in plan_ref_w_content
    assert "deletion" in plan_ref_w_content.lower()


def test_topology_sole_owner_is_fail_closed(tmp_path: Path) -> None:
    """cp4 / FR-002 / TM-084-02: Sole-owner deletion fails validation while redundant-edge deletion passes for both topology families."""
    rules_root = tmp_path / ".cursor/rules"
    rules_root.mkdir(parents=True, exist_ok=True)
    shared_dir = rules_root / "shared"
    shared_dir.mkdir(parents=True, exist_ok=True)

    # 1. VAN brownfield owner fixture
    bf_file = shared_dir / "workflow-van-brownfield.mdc"
    bf_file.write_text("---\ndescription: brownfield map\n---\nBrownfield content\n", encoding="utf-8")

    van_wf = rules_root / "workflow-van.mdc"
    van_wf.write_text(
        "---\n"
        "description: van\n"
        "---\n"
        "### Команда: BACK VAN\n"
        "**Policy lazy (по триггеру, не грузить целиком):** @.cursor/rules/shared/workflow-van-brownfield.mdc\n"
        "1. Refresh architecture map using shared/workflow-van-brownfield.mdc\n",
        encoding="utf-8",
    )

    pack = WorkflowPack(
        id="van-refactor-pack",
        roles=["back"],
        command_prefixes=["BACK"],
        phase_registry="phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
    )
    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    (tmp_path / "phase_registry.yaml").write_text("schema: phase-registry/v1\nphases: {}\n", encoding="utf-8")

    # Single VAN owner passes
    res = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert res.ok is True
    assert len(res.diagnostic_codes) == 0

    # Adding redundant VAN edge causes duplicate diagnostic
    van_wf.write_text(
        "---\n"
        "description: van\n"
        "---\n"
        "### Команда: BACK VAN\n"
        "**Policy lazy (по триггеру, не грузить целиком):** @.cursor/rules/shared/workflow-van-brownfield.mdc\n"
        "1. Refresh map @.cursor/rules/shared/workflow-van-brownfield.mdc\n",
        encoding="utf-8",
    )
    res_dup = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert not res_dup.ok
    assert "pack_reference_duplicate" in res_dup.diagnostic_codes

    # Removing redundant edge restores green state
    van_wf.write_text(
        "---\n"
        "description: van\n"
        "---\n"
        "### Команда: BACK VAN\n"
        "**Policy lazy (по триггеру, не грузить целиком):** @.cursor/rules/shared/workflow-van-brownfield.mdc\n"
        "1. Refresh architecture map using shared/workflow-van-brownfield.mdc\n",
        encoding="utf-8",
    )
    res_restored = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert res_restored.ok is True

    # Removing sole VAN owner causes dangling reference diagnostic
    bf_file.unlink()
    res_dangling = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert not res_dangling.ok
    assert "pack_reference_dangling" in res_dangling.diagnostic_codes

    # 2. REFACTOR owner fixture
    ref_epic_file = shared_dir / "workflow-refactor-epic.mdc"
    ref_epic_file.write_text("---\ndescription: refactor epic\n---\nRefactor epic content\n", encoding="utf-8")

    ref_wf = rules_root / "workflow-refactor.mdc"
    ref_wf.write_text(
        "---\n"
        "description: refactor\n"
        "---\n"
        "### Команда: BACK REFACTOR\n"
        "**Policy lazy (по триггеру, не грузить целиком):** @.cursor/rules/shared/workflow-refactor-epic.mdc\n"
        "1. Detect epic using shared/workflow-refactor-epic.mdc\n",
        encoding="utf-8",
    )

    # Re-create bf_file so pack is valid overall
    bf_file.write_text("---\ndescription: brownfield map\n---\nBrownfield content\n", encoding="utf-8")

    res_ref = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert res_ref.ok is True

    # Adding redundant REFACTOR edge causes duplicate diagnostic
    ref_wf.write_text(
        "---\n"
        "description: refactor\n"
        "---\n"
        "### Команда: BACK REFACTOR\n"
        "**Policy lazy (по триггеру, не грузить целиком):** @.cursor/rules/shared/workflow-refactor-epic.mdc\n"
        "1. Detect epic @.cursor/rules/shared/workflow-refactor-epic.mdc\n",
        encoding="utf-8",
    )
    res_ref_dup = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert not res_ref_dup.ok
    assert "pack_reference_duplicate" in res_ref_dup.diagnostic_codes

    # Removing redundant edge restores green state
    ref_wf.write_text(
        "---\n"
        "description: refactor\n"
        "---\n"
        "### Команда: BACK REFACTOR\n"
        "**Policy lazy (по триггеру, не грузить целиком):** @.cursor/rules/shared/workflow-refactor-epic.mdc\n"
        "1. Detect epic using shared/workflow-refactor-epic.mdc\n",
        encoding="utf-8",
    )
    res_ref_restored = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert res_ref_restored.ok is True

    # Removing sole REFACTOR owner causes dangling reference diagnostic
    ref_epic_file.unlink()
    res_ref_dangling = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert not res_ref_dangling.ok
    assert "pack_reference_dangling" in res_ref_dangling.diagnostic_codes
