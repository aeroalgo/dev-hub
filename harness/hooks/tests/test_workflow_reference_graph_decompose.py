"""Tests for DECOMPOSE workflow reference graph hygiene (T-HUB-084: s02)."""
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
    "BACK": ROOT / "harness/cursor/rules/back_developer/workflow-decompose.mdc",
    "FRONT": ROOT / "harness/cursor/rules/front_developer/workflow-decompose.mdc",
    "INTEG": ROOT / "harness/cursor/rules/integration_developer/workflow-decompose.mdc",
}

SCOPED_LEAN_GATES = {
    "BACK": ROOT / "harness/cursor/rules/back_developer/isolation_rules/_lean/decompose.mdc",
    "FRONT": ROOT / "harness/cursor/rules/front_developer/isolation_rules/_lean/decompose.mdc",
    "INTEG": ROOT / "harness/cursor/rules/integration_developer/isolation_rules/_lean/decompose.mdc",
}


def test_decompose_edges_have_one_lazy_owner() -> None:
    """cp1 / FR-001 / FR-002: Every active BACK/FRONT/INTEG DECOMPOSE chain has exactly one behavior-first owner edge and explicit lazy timing."""
    rules_root = ROOT / ".cursor/rules"

    for role, w_path in SCOPED_WORKFLOWS.items():
        assert w_path.is_file(), f"Missing workflow file for {role}: {w_path}"
        content = w_path.read_text(encoding="utf-8")

        # Check explicit lazy timing note
        assert re.search(r"Policy lazy\s*\(по триггеру,\s*не грузить целиком\):", content), (
            f"{role} DECOMPOSE workflow must declare explicit lazy timing note"
        )

        # Extract reference edges via pack_graph
        edges = extract_reference_edges(w_path, rules_root, ROOT, ROOT)

        bf_edges = [e for e in edges if e.target_canonical and "workflow-behavior-first" in e.target_canonical]
        assert len(bf_edges) == 1, f"{role} DECOMPOSE workflow must have exactly 1 behavior-first edge, found {len(bf_edges)}"

        tg_edges = [e for e in edges if e.target_canonical and "workflow-decompose-transition-gate" in e.target_canonical]
        assert len(tg_edges) == 1, f"{role} DECOMPOSE workflow must have exactly 1 transition-gate edge, found {len(tg_edges)}"

    for role, l_path in SCOPED_LEAN_GATES.items():
        assert l_path.is_file(), f"Missing lean gate file for {role}: {l_path}"
        edges = extract_reference_edges(l_path, rules_root, ROOT, ROOT)

        bf_edges = [e for e in edges if e.target_canonical and "workflow-behavior-first" in e.target_canonical]
        assert len(bf_edges) == 0, f"{role} lean decompose gate must not declare @ edge to behavior-first, found {len(bf_edges)}"

        tg_edges = [e for e in edges if e.target_canonical and "workflow-decompose-transition-gate" in e.target_canonical]
        assert len(tg_edges) == 0, f"{role} lean decompose gate must not declare @ edge to transition-gate, found {len(tg_edges)}"


def test_decompose_mode_markers_survive_owner_rewrite() -> None:
    """cp2 / FR-004 / TM-084-03: Mode markers and Hot path sections remain intact in canonical workflow owners."""
    for role, w_path in SCOPED_WORKFLOWS.items():
        content = w_path.read_text(encoding="utf-8")
        expected_marker = f"### Команда: {role} DECOMPOSE"
        assert expected_marker in content, f"{role} workflow must retain mode marker {expected_marker}"

    back_content = SCOPED_WORKFLOWS["BACK"].read_text(encoding="utf-8")
    assert "## Hot path" in back_content, "BACK DECOMPOSE must retain ## Hot path section"


def test_decompose_sole_owner_cannot_be_removed(tmp_path: Path) -> None:
    """cp4 / FR-002 / TM-084-02: Removing a DECOMPOSE sole owner is rejected while removing only a redundant edge is accepted."""
    rules_root = tmp_path / ".cursor/rules"
    rules_root.mkdir(parents=True, exist_ok=True)
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

    pack = WorkflowPack(
        id="decompose-test-pack",
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
