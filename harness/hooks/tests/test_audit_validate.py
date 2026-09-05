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
        "legacy_surfaces_remaining: []\nfallback_remaining: []\ninstruction_remaining: []\npurge_step_present: true\n"
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
        "legacy_surfaces_remaining: []\nfallback_remaining: []\ninstruction_remaining: []\npurge_step_present: true\n"
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


def _v2_body(epic: str, extra: str = "") -> str:
    return (
        "schema: epic-audit/v2\n"
        f"epic_id: {epic}\n"
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
        "    evidence: runtime wired extract_repair_result JSON fence only\n"
        "    remaining_work: \"\"\n"
        "legacy_surfaces_remaining: []\nfallback_remaining: []\ninstruction_remaining: []\npurge_step_present: true\n"
        "architecture_parity: []\n"
        "findings: []\n"
        "converged: true\n"
        "sunset_inventory_scan:\n"
        "  scanned_at: '2026-09-04'\n"
        "  plan_ref: n/a\n"
        "  rows: []\n"
        f"{extra}"
    )


def test_validate_rejects_phantom_implement_file(tmp_path: Path):
    epic = "E-PHANTOM"
    _plan(tmp_path, epic, "# P\n- **FR-001:** a\n")
    audit = tmp_path / "a.yaml"
    audit.write_text(
        _v2_body(
            epic,
            "implemented:\n"
            "  - step_id: s01\n"
            "    implement_file: memory-bank/back/plan/E-PHANTOM/md/s01.md\n",
        ),
        encoding="utf-8",
    )
    errs = validate_audit_artifact(
        tmp_path, role_dir="back", epic_id=epic, audit_path=audit
    )
    assert any("audit_implemented[0]_implement_file_missing_on_disk" in e for e in errs)


def test_validate_rejects_plan_md_as_implement(tmp_path: Path):
    epic = "E-PLANMD"
    _plan(tmp_path, epic, "# P\n- **FR-001:** a\n")
    fake = (
        tmp_path
        / "memory-bank"
        / "back"
        / "plan"
        / epic
        / "md"
        / "s01-doctor.md"
    )
    fake.parent.mkdir(parents=True, exist_ok=True)
    fake.write_text("# not implement\n", encoding="utf-8")
    audit = tmp_path / "a.yaml"
    audit.write_text(
        _v2_body(
            epic,
            "implemented:\n"
            f"  - step_id: s01\n"
            f"    implement_file: memory-bank/back/plan/{epic}/md/s01-doctor.md\n",
        ),
        encoding="utf-8",
    )
    errs = validate_audit_artifact(
        tmp_path, role_dir="back", epic_id=epic, audit_path=audit
    )
    assert any("audit_implemented[0]_plan_md_not_implement" in e for e in errs)


def test_validate_rejects_presence_only_evidence(tmp_path: Path):
    epic = "E-PRESENCE"
    _plan(tmp_path, epic, "# P\n- **FR-001:** a\n")
    audit = tmp_path / "a.yaml"
    audit.write_text(
        "schema: epic-audit/v2\n"
        f"epic_id: {epic}\n"
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
        "    evidence: Файл на диске, snippet переведен на --json\n"
        "    remaining_work: \"\"\n"
        "architecture_parity:\n"
        "  - layout_path: harness/agents/gate-repair.md\n"
        "    status: present\n"
        "    evidence: Файл на диске\n"
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
    assert any("audit_plan_vs_runtime[0]_presence_only" in e for e in errs)
    assert any("audit_architecture_parity[0]_presence_only" in e for e in errs)


def test_validate_rejects_completed_steps_without_implement_rows(tmp_path: Path):
    epic = "E-STEPS"
    _plan(tmp_path, epic, "# P\n- **FR-001:** a\n")
    idx = tmp_path / "memory-bank" / "back" / "plan" / epic / "yaml"
    idx.mkdir(parents=True, exist_ok=True)
    (idx / "decompose-index.yaml").write_text(
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic}\n"
        "role: back\n"
        "steps:\n"
        "  - id: s01\n"
        "    file: s01-a.yaml\n"
        "    status: completed\n"
        "  - id: s02\n"
        "    file: s02-b.yaml\n"
        "    status: pending\n",
        encoding="utf-8",
    )
    audit = tmp_path / "a.yaml"
    audit.write_text(_v2_body(epic), encoding="utf-8")
    errs = validate_audit_artifact(
        tmp_path, role_dir="back", epic_id=epic, audit_path=audit
    )
    assert any("audit_completed_steps_uncovered" in e for e in errs)
    assert any("s01" in e for e in errs)


def _contract_case(tmp_path, *, plan_extra="", updates=None):
    import yaml
    epic = "T-contract"
    _plan(tmp_path, epic, "# Plan\n- **FR-001:** route requests\n" + plan_extra)
    doc = yaml.safe_load(_v2_body(epic))
    doc.update(legacy_surfaces_remaining=[], fallback_remaining=[], instruction_remaining=[], purge_step_present=True)
    doc.update(updates or {})
    path = tmp_path / "audit.yaml"
    path.write_text(yaml.safe_dump(doc))
    return validate_audit_artifact(tmp_path, role_dir="back", epic_id=epic, audit_path=path)


def test_converged_rejects_unscanned_leftovers_and_missing_purge(tmp_path):
    errors = _contract_case(tmp_path, updates={"sunset_inventory_scan": {}, "legacy_surfaces_remaining": ["old.py"], "purge_step_present": False})
    assert any("scan_incomplete" in e for e in errors)
    assert any("leftovers" in e for e in errors)
    assert any("purge" in e for e in errors)


def test_converged_requires_all_plan_layout_paths(tmp_path):
    errors = _contract_case(tmp_path, plan_extra="\n## Files\n| Path | Action |\n| `app/router.py` | new |\n")
    assert any("layout_uncovered" in e for e in errors)


def test_converged_rejects_missing_architecture_path(tmp_path):
    errors = _contract_case(tmp_path, updates={"architecture_parity": [{"layout_path": "missing.py", "status": "missing", "evidence": "not implemented"}]})
    assert any("architecture_open" in e for e in errors)


def test_audit_requires_ac_and_constitution_inventory(tmp_path):
    (tmp_path / "memory-bank").mkdir()
    (tmp_path / "memory-bank/constitution.md").write_text("# Constitution\n- MUST reject invalid input\n")
    errors = _contract_case(tmp_path, plan_extra="\n## AC+\n1. Requests reach router.\n\n## AC−\n1. Silent fallback.\n")
    assert any("AC+:1" in e for e in errors)
    assert any("AC-:1" in e for e in errors)
    assert any("constitution:L2" in e for e in errors)


def test_brownfield_cannot_claim_na_scan(tmp_path):
    errors = _contract_case(tmp_path, plan_extra="\n## Replacement / sunset\n### A. Code\n| Old | New | Policy |\n| old.py | new.py | delete |\n")
    assert any("scan_incomplete" in e for e in errors)


def test_presence_only_english_evidence_rejected(tmp_path):
    errors = _contract_case(tmp_path, updates={"plan_vs_runtime": [{"source_ref": "FR-001", "status": "satisfied", "evidence": "agent contract file exists"}]})
    assert any("presence_only" in e for e in errors)
