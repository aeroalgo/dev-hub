"""Unit tests for epic-audit/v2 plan↔runtime validation gate."""

from __future__ import annotations

from pathlib import Path

from harness.hooks.epic.audit_validate import (
    extract_plan_intent_ids,
    validate_audit_artifact,
)


def _plan(tmp_path: Path, epic: str, body: str) -> Path:
    d = tmp_path / "memory-bank" / "back" / "plan" / epic / "md"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "plan.md"
    p.write_text(body, encoding="utf-8")
    return p


def test_extract_plan_intent_ids_from_markdown(tmp_path: Path):
    p = _plan(
        tmp_path,
        "E1",
        "# Plan\n- **FR-001:** a\n- **FR-002:** b\n| US-003 | story |\n",
    )
    assert extract_plan_intent_ids(p) == ["FR-001", "FR-002", "US-003"]


def test_validate_rejects_v1_shallow(tmp_path: Path):
    epic = "E-SHALLOW"
    _plan(tmp_path, epic, "# P\n- **FR-001:** x\n")
    audit = tmp_path / "a.yaml"
    audit.write_text(
        "schema: epic-audit/v1\nstatus: PASS\nnot_implemented: []\n",
        encoding="utf-8",
    )
    errs = validate_audit_artifact(
        tmp_path, role_dir="back", epic_id=epic, audit_path=audit
    )
    assert any("audit_schema_not_v2" in e for e in errs)


def test_validate_requires_full_fr_coverage(tmp_path: Path):
    epic = "E-COV"
    _plan(tmp_path, epic, "# P\n- **FR-001:** a\n- **FR-002:** b\n")
    audit = tmp_path / "a.yaml"
    audit.write_text(
        "schema: epic-audit/v2\n"
        "plan_intent:\n"
        "  epic_goal: Ship registry for domain packs end to end\n"
        "  source: plan.md#WHAT\n"
        "intent_checked:\n"
        "  fr_total: 1\n"
        "  fr_satisfied: 1\n"
        "  sc_checked: 0\n"
        "  layout_paths_total: 0\n"
        "  layout_paths_closed: 0\n"
        "  constitution_checked: false\n"
        "plan_vs_runtime:\n"
        "  - source_ref: FR-001\n"
        "    status: satisfied\n"
        "    evidence: file loop/workflow/registry.py wired\n"
        "    remaining_work: \"\"\n"
        "architecture_parity: []\n"
        "findings: []\n"
        "converged: true\n"
        "sunset_inventory_scan:\n"
        "  scanned_at: '2026-09-04'\n"
        "  plan_ref: n/a\n"
        "  rows: []\n",
        encoding="utf-8",
    )
    errs = validate_audit_artifact(
        tmp_path, role_dir="back", epic_id=epic, audit_path=audit
    )
    assert any("audit_plan_fr_uncovered" in e for e in errs)
    assert any("FR-002" in e for e in errs)


def test_validate_pass_when_all_fr_covered(tmp_path: Path):
    epic = "E-OK"
    _plan(tmp_path, epic, "# P\n- **FR-001:** a\n")
    audit = tmp_path / "a.yaml"
    audit.write_text(
        "schema: epic-audit/v2\n"
        "plan_intent:\n"
        "  epic_goal: Ship registry for domain packs end to end\n"
        "  source: plan.md#WHAT\n"
        "intent_checked:\n"
        "  fr_total: 1\n"
        "  fr_satisfied: 1\n"
        "  sc_checked: 0\n"
        "  layout_paths_total: 0\n"
        "  layout_paths_closed: 0\n"
        "  constitution_checked: false\n"
        "plan_vs_runtime:\n"
        "  - source_ref: FR-001\n"
        "    status: satisfied\n"
        "    evidence: file loop/workflow/registry.py wired\n"
        "    remaining_work: \"\"\n"
        "architecture_parity: []\n"
        "findings: []\n"
        "converged: true\n"
        "sunset_inventory_scan:\n"
        "  scanned_at: '2026-09-04'\n"
        "  plan_ref: n/a\n"
        "  rows: []\n",
        encoding="utf-8",
    )
    errs = validate_audit_artifact(
        tmp_path, role_dir="back", epic_id=epic, audit_path=audit
    )
    assert errs == []
