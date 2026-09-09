"""Tests for workflow reference graph hygiene validation (T-HUB-084: s01)."""
from __future__ import annotations

from pathlib import Path
import pytest
import yaml

from loop.workflow.pack_graph import (
    check_pack_graph,
    validate_reference_graph,
    extract_reference_edges,
    CheckPackGraphResult,
    ReferenceDiagnostic,
)
from loop.workflow.schemas import WorkflowPack


def _setup_base_pack(tmp_path: Path, pack_id: str = "test-pack") -> tuple[WorkflowPack, Path]:
    """Helper to create a minimal valid workflow pack structure."""
    rules_root = tmp_path / ".cursor" / "rules"
    rules_root.mkdir(parents=True, exist_ok=True)
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    phase_reg = tmp_path / "phase_registry.yaml"
    phase_reg.write_text("schema: phase-registry/v1\nphases: {}\n", encoding="utf-8")

    pack = WorkflowPack(
        id=pack_id,
        roles=["test"],
        command_prefixes=["TEST"],
        phase_registry="phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
    )
    return pack, rules_root


def test_direct_duplicate_reports_both_source_lines(tmp_path: Path) -> None:
    """cp1 / FR-001 / TM-084-01: Direct duplicate reference fails closed and reports both line numbers."""
    pack, rules_root = _setup_base_pack(tmp_path, "dup-pack")

    shared_dir = rules_root / "shared"
    shared_dir.mkdir(parents=True, exist_ok=True)
    target_file = shared_dir / "target.mdc"
    target_file.write_text("---\ndescription: target\n---\nTarget content\n", encoding="utf-8")

    workflow_file = rules_root / "workflow-plan.mdc"
    workflow_file.write_text(
        "---\n"
        "description: plan\n"
        "---\n"
        "Line 4: @.cursor/rules/shared/target.mdc\n"
        "Line 5: intermediate text\n"
        "Line 6: @.cursor/rules/shared/target.mdc\n",
        encoding="utf-8",
    )

    res = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert not res.ok
    assert "pack_reference_duplicate" in res.diagnostic_codes

    diags = res.details.get("reference_diagnostics", [])
    dup_diags = [d for d in diags if d.get("code") == "pack_reference_duplicate"]
    assert len(dup_diags) >= 1

    diag = dup_diags[0]
    locations = diag.get("locations", [])
    assert len(locations) == 2
    assert locations[0]["line"] == 4
    assert locations[1]["line"] == 6
    assert ".cursor/rules/workflow-plan.mdc" in locations[0]["path"]
    assert diag["details"]["lines"] == [4, 6]


def test_direct_duplicate_both_lines_evidence(tmp_path: Path) -> None:
    """cp1: Direct duplicate fixture reports both declaring paths and line numbers."""
    pack, rules_root = _setup_base_pack(tmp_path, "dup-evidence-pack")

    target = rules_root / "shared_rule.mdc"
    target.write_text("content\n", encoding="utf-8")

    caller = rules_root / "caller.mdc"
    caller.write_text(
        "First call: @.cursor/rules/shared_rule.mdc\n"
        "Second call: @.cursor/rules/shared_rule.mdc\n",
        encoding="utf-8",
    )

    diags = validate_reference_graph(rules_root, tmp_path, tmp_path)
    dup = [d for d in diags if d.code == "pack_reference_duplicate"]
    assert len(dup) == 1
    assert [loc["line"] for loc in dup[0].locations] == [1, 2]


def test_active_only_excludes_orphan_shared_entrypoints(tmp_path: Path) -> None:
    _, rules_root = _setup_base_pack(tmp_path, "active-corpus-pack")

    shared_dir = rules_root / "shared"
    shared_dir.mkdir(parents=True, exist_ok=True)
    reachable = shared_dir / "reachable.mdc"
    reachable.write_text("reachable\n", encoding="utf-8")
    orphan = shared_dir / "workflow-orphan.mdc"
    orphan.write_text(
        "@.cursor/rules/shared/orphan-missing.mdc\n",
        encoding="utf-8",
    )
    workflow = rules_root / "workflow-plan.mdc"
    workflow.write_text(
        "@.cursor/rules/shared/reachable.mdc\n",
        encoding="utf-8",
    )
    mainrule = rules_root / "mainrule.mdc"
    mainrule.write_text(
        "@.cursor/rules/shared/mainrule-missing.mdc\n",
        encoding="utf-8",
    )

    diagnostics = validate_reference_graph(rules_root, tmp_path, tmp_path, active_only=True)

    assert len(diagnostics) == 1
    assert diagnostics[0].target == ".cursor/rules/shared/mainrule-missing.mdc"
    assert diagnostics[0].locations[0]["path"] == ".cursor/rules/mainrule.mdc"


def test_transitive_ambiguity_requires_single_owner(tmp_path: Path) -> None:
    """cp2 / FR-002 / TM-084-02: Transitive ambiguity reports both lines; redundant edge removal passes; sole owner deletion fails."""
    pack, rules_root = _setup_base_pack(tmp_path, "transitive-pack")

    shared_dir = rules_root / "shared"
    shared_dir.mkdir(parents=True, exist_ok=True)

    # Leaf dependency B
    shared_b = shared_dir / "leaf_b.mdc"
    shared_b.write_text("---\ndescription: leaf b\n---\nLeaf content\n", encoding="utf-8")

    # Intermediate owner A referencing B at line 4
    owner_a = shared_dir / "owner_a.mdc"
    owner_a.write_text(
        "---\ndescription: owner a\n---\n"
        "@.cursor/rules/shared/leaf_b.mdc\n",
        encoding="utf-8",
    )

    # Workflow W referencing both A (line 4) and B directly (line 5) -> Transitive Ambiguity!
    workflow_w = rules_root / "workflow.mdc"
    workflow_w.write_text(
        "---\ndescription: workflow\n---\n"
        "@.cursor/rules/shared/owner_a.mdc\n"
        "@.cursor/rules/shared/leaf_b.mdc\n",
        encoding="utf-8",
    )

    # 1. Ambiguous graph fails closed with source lines
    res = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert not res.ok
    assert "pack_reference_transitive_ambiguity" in res.diagnostic_codes

    trans_diags = [d for d in res.details.get("reference_diagnostics", []) if d.get("code") == "pack_reference_transitive_ambiguity"]
    assert len(trans_diags) == 1
    diag = trans_diags[0]
    locations = diag.get("locations", [])
    assert len(locations) == 2
    # Direct edge location (workflow line 5)
    assert locations[0]["line"] == 5
    assert ".cursor/rules/workflow.mdc" in locations[0]["path"]
    # Transitive owner edge location (owner_a line 4)
    assert locations[1]["line"] == 4
    assert ".cursor/rules/shared/owner_a.mdc" in locations[1]["path"]

    # 2. Removing redundant direct edge passes
    workflow_w.write_text(
        "---\ndescription: workflow\n---\n"
        "@.cursor/rules/shared/owner_a.mdc\n",
        encoding="utf-8",
    )
    res_clean = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert res_clean.ok is True
    assert "pack_reference_transitive_ambiguity" not in res_clean.diagnostic_codes

    # 3. Removing sole owner A fails (workflow now points to non-existent A)
    owner_a.unlink()
    res_no_owner = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert res_no_owner.ok is False
    assert "pack_reference_dangling" in res_no_owner.diagnostic_codes


def test_dangling_reference_is_fail_closed(tmp_path: Path) -> None:
    """cp3 / FR-003 / TM-084-04: Dangling dead reference is rejected fail-closed with source line."""
    pack, rules_root = _setup_base_pack(tmp_path, "dangling-pack")

    workflow_file = rules_root / "workflow-dead.mdc"
    workflow_file.write_text(
        "---\ndescription: dead\n---\n"
        "Some text\n"
        "Dead ref: @.cursor/rules/shared/cheatsheets/back-audit.mdc\n",
        encoding="utf-8",
    )

    res = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert not res.ok
    assert "pack_reference_dangling" in res.diagnostic_codes

    dangling_diags = [d for d in res.details.get("reference_diagnostics", []) if d.get("code") == "pack_reference_dangling"]
    assert len(dangling_diags) == 1
    diag = dangling_diags[0]
    assert diag["locations"][0]["line"] == 5
    assert ".cursor/rules/workflow-dead.mdc" in diag["locations"][0]["path"]
    assert diag["target"] == ".cursor/rules/shared/cheatsheets/back-audit.mdc"


def test_decompose_sole_owner_or_redundant_edge(tmp_path: Path) -> None:
    """cp4 / FR-002 / TM-084-02: Removing a DECOMPOSE sole owner is rejected while removing only a redundant edge is accepted."""
    pack, rules_root = _setup_base_pack(tmp_path, "decompose-owner-pack")
    shared_dir = rules_root / "shared"
    shared_dir.mkdir(parents=True, exist_ok=True)

    # Behavior-first policy leaf
    bf_file = shared_dir / "workflow-behavior-first.mdc"
    bf_file.write_text("---\ndescription: behavior first\n---\nBehavior-first content\n", encoding="utf-8")

    # Workflow declaring single owner edge
    wf_file = rules_root / "workflow-decompose.mdc"
    wf_file.write_text(
        "---\n"
        "description: decompose\n"
        "---\n"
        "### Команда: BACK DECOMPOSE\n"
        "**Policy lazy (по триггеру, не грузить целиком):** @.cursor/rules/shared/workflow-behavior-first.mdc\n"
        "## Hot path\n"
        "1. Step one using shared/workflow-behavior-first.mdc §3a\n",
        encoding="utf-8",
    )

    # 1. Single owner passes validation
    res = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert res.ok is True
    assert len(res.diagnostic_codes) == 0

    # 2. Adding redundant direct edge causes duplicate diagnostic
    wf_file.write_text(
        "---\n"
        "description: decompose\n"
        "---\n"
        "### Команда: BACK DECOMPOSE\n"
        "**Policy lazy (по триггеру, не грузить целиком):** @.cursor/rules/shared/workflow-behavior-first.mdc\n"
        "## Hot path\n"
        "1. Step one @.cursor/rules/shared/workflow-behavior-first.mdc §3a\n",
        encoding="utf-8",
    )
    res_dup = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert not res_dup.ok
    assert "pack_reference_duplicate" in res_dup.diagnostic_codes

    # 3. Removing redundant edge restores green state
    wf_file.write_text(
        "---\n"
        "description: decompose\n"
        "---\n"
        "### Команда: BACK DECOMPOSE\n"
        "**Policy lazy (по триггеру, не грузить целиком):** @.cursor/rules/shared/workflow-behavior-first.mdc\n"
        "## Hot path\n"
        "1. Step one using shared/workflow-behavior-first.mdc §3a\n",
        encoding="utf-8",
    )
    res_restored = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert res_restored.ok is True

    # 4. Removing sole owner file causes dangling reference diagnostic
    bf_file.unlink()
    res_dangling = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert not res_dangling.ok
    assert "pack_reference_dangling" in res_dangling.diagnostic_codes
