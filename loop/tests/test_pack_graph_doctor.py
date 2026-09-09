"""Tests for executable workflow pack graph checking and doctor integration (T-HUB-067: s01)."""
from __future__ import annotations

import json
from pathlib import Path
import pytest
import yaml

from loop.workflow.pack_graph import check_pack_graph, CheckPackGraphResult
from loop.doctor.checks.workflow_pack import check_workflow_pack, run_doctor_workflow_pack
from loop.context_loop import main


def test_missing_route_fixture_pack_route_missing(tmp_path: Path) -> None:
    """US-001 / FR-001 / SC-001 / TM-001: Missing command route returns pack_route_missing."""
    # Setup tmp pack with intent routing pointing to non-existent route
    rules_root = tmp_path / ".cursor" / "rules"
    rules_root.mkdir(parents=True, exist_ok=True)
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    phase_reg = tmp_path / "phase_registry.yaml"
    phase_reg.write_text("schema: phase-registry/v1\nphases: {}\n", encoding="utf-8")

    # Intent routing pointing to a missing mdc file
    intent_file = tmp_path / "loop" / "workflow" / "intent_routing.yaml"
    intent_file.parent.mkdir(parents=True, exist_ok=True)
    intent_data = {
        "schema": "workflow-intent-routing/v1",
        "intents": {
            "test_broken_intent": {
                "pack": "broken-pack",
                "pipeline": [{"command": "TEST MISSING_ROUTE", "gate": "auto"}],
            }
        },
    }
    intent_file.write_text(yaml.safe_dump(intent_data), encoding="utf-8")

    from loop.workflow.schemas import WorkflowPack
    broken_pack = WorkflowPack(
        id="broken-pack",
        roles=["test"],
        command_prefixes=["TEST"],
        phase_registry="phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
    )

    res = check_pack_graph(pack_or_id=broken_pack, cwd=tmp_path, hub_root=tmp_path)
    assert not res.ok
    assert "pack_route_missing" in res.diagnostic_codes


def test_missing_lean_gate_pack_gate_missing(tmp_path: Path) -> None:
    """US-003 / QA TM-002 / Failure TM-002: Missing _lean gate -> pack_gate_missing."""
    rules_root = tmp_path / ".cursor" / "rules"
    rules_root.mkdir(parents=True, exist_ok=True)
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    phase_reg = tmp_path / "phase_registry.yaml"
    phase_reg.write_text("schema: phase-registry/v1\nphases: {}\n", encoding="utf-8")

    # Write workflow mdc referencing non-existent _lean gate
    workflow_mdc = rules_root / "workflow-plan.mdc"
    workflow_mdc.write_text(
        "---\ndescription: test\n---\n**Gates**: @.cursor/rules/isolation_rules/_lean/non_existent_gate.mdc\n",
        encoding="utf-8",
    )

    from loop.workflow.schemas import WorkflowPack
    pack = WorkflowPack(
        id="test-pack",
        roles=["test"],
        command_prefixes=["TEST"],
        phase_registry="phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
    )

    res = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert not res.ok
    assert "pack_gate_missing" in res.diagnostic_codes


def test_undeclared_verify_agent_pack_agent_missing(tmp_path: Path) -> None:
    """US-002 / QA TM-003 / Failure TM-003: Undeclared verify_agent -> pack_agent_missing."""
    rules_root = tmp_path / ".cursor" / "rules"
    rules_root.mkdir(parents=True, exist_ok=True)
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)

    phase_reg = tmp_path / "phase_registry.yaml"
    phase_reg_data = {
        "schema": "phase-registry/v1",
        "phases": {
            "IMPLEMENT": {
                "verify_agent": "non-existent-agent-xyz",
                "finish_gates": {"need_verify": True},
            }
        },
    }
    phase_reg.write_text(yaml.safe_dump(phase_reg_data), encoding="utf-8")

    from loop.workflow.schemas import WorkflowPack
    pack = WorkflowPack(
        id="test-pack",
        roles=["test"],
        command_prefixes=["TEST"],
        phase_registry="phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
    )

    res = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert not res.ok
    assert "pack_agent_missing" in res.diagnostic_codes


def test_missing_skill_ref_pack_unusable(tmp_path: Path) -> None:
    """FR-003 / Failure TM-004: Missing canonical skill ref -> skill_ref_missing."""
    rules_root = tmp_path / ".cursor" / "rules"
    rules_root.mkdir(parents=True, exist_ok=True)
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    phase_reg = tmp_path / "phase_registry.yaml"
    phase_reg.write_text("schema: phase-registry/v1\nphases: {}\n", encoding="utf-8")

    # Workflow mdc referencing missing skill
    mdc_file = rules_root / "workflow-plan.mdc"
    mdc_file.write_text(
        "Skill ref: @.agents/skills/non-existent-skill-xyz/SKILL.md\n",
        encoding="utf-8",
    )

    from loop.workflow.schemas import WorkflowPack
    pack = WorkflowPack(
        id="test-pack",
        roles=["test"],
        command_prefixes=["TEST"],
        phase_registry="phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
    )

    res = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert not res.ok
    assert "skill_ref_missing" in res.diagnostic_codes


def test_multiple_codes_not_first_only_hide(tmp_path: Path) -> None:
    """FR-002: Multiple errors return all codes (list), not first-only."""
    rules_root = tmp_path / ".cursor" / "rules"
    rules_root.mkdir(parents=True, exist_ok=True)
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)

    # 1. Missing verify agent
    phase_reg = tmp_path / "phase_registry.yaml"
    phase_reg_data = {
        "schema": "phase-registry/v1",
        "phases": {
            "IMPLEMENT": {
                "verify_agent": "non-existent-agent-xyz",
                "finish_gates": {"need_verify": True},
            }
        },
    }
    phase_reg.write_text(yaml.safe_dump(phase_reg_data), encoding="utf-8")

    # 2. Missing lean gate
    workflow_mdc = rules_root / "workflow-plan.mdc"
    workflow_mdc.write_text(
        "**Gates**: @.cursor/rules/isolation_rules/_lean/missing.mdc\n"
        "Skill: @.agents/skills/missing-skill/SKILL.md\n",
        encoding="utf-8",
    )

    from loop.workflow.schemas import WorkflowPack
    pack = WorkflowPack(
        id="test-pack",
        roles=["test"],
        command_prefixes=["TEST"],
        phase_registry="phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
    )

    res = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert not res.ok
    assert "pack_agent_missing" in res.diagnostic_codes
    assert "pack_gate_missing" in res.diagnostic_codes
    assert "skill_ref_missing" in res.diagnostic_codes


def test_keys_only_yaml_missing_file_not_green(tmp_path: Path) -> None:
    """TM-009 / Independent Test FAIL: Keys-only yaml present but missing file -> not green."""
    rules_root = tmp_path / ".cursor" / "rules"
    rules_root.mkdir(parents=True, exist_ok=True)
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    phase_reg = tmp_path / "phase_registry.yaml"
    phase_reg.write_text("schema: phase-registry/v1\nphases: {}\n", encoding="utf-8")

    intent_file = tmp_path / "loop" / "workflow" / "intent_routing.yaml"
    intent_file.parent.mkdir(parents=True, exist_ok=True)
    intent_data = {
        "schema": "workflow-intent-routing/v1",
        "intents": {
            "fake_intent": {
                "pack": "keys-only-pack",
                "pipeline": [{"command": "KEYS ONLY", "gate": "auto"}],
            }
        },
    }
    intent_file.write_text(yaml.safe_dump(intent_data), encoding="utf-8")

    from loop.workflow.schemas import WorkflowPack
    pack = WorkflowPack(
        id="keys-only-pack",
        roles=["keys"],
        command_prefixes=["KEYS"],
        phase_registry="phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
    )

    res = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert not res.ok
    assert "pack_route_missing" in res.diagnostic_codes


def test_doctor_cli_exit_nonzero_unusable_pack(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """FR-005: Doctor CLI exit != 0 on unusable pack."""
    rules_root = tmp_path / ".cursor" / "rules"
    rules_root.mkdir(parents=True, exist_ok=True)
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    phase_reg = tmp_path / "phase_registry.yaml"
    phase_reg.write_text("schema: phase-registry/v1\nphases: {}\n", encoding="utf-8")

    intent_file = tmp_path / "loop" / "workflow" / "intent_routing.yaml"
    intent_file.parent.mkdir(parents=True, exist_ok=True)
    intent_data = {
        "schema": "workflow-intent-routing/v1",
        "intents": {
            "unusable": {
                "pack": "unusable-pack",
                "pipeline": [{"command": "UNUSABLE ROUTE", "gate": "auto"}],
            }
        },
    }
    intent_file.write_text(yaml.safe_dump(intent_data), encoding="utf-8")

    from loop.workflow.schemas import WorkflowPack
    pack = WorkflowPack(
        id="unusable-pack",
        roles=["unusable"],
        command_prefixes=["UNUSABLE"],
        phase_registry="phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
    )
    reg_file = tmp_path / "loop" / "workflow_pack_registry.yaml"
    reg_file.parent.mkdir(parents=True, exist_ok=True)
    reg_file.write_text(
        yaml.safe_dump({
            "schema": "workflow-pack-registry/v1",
            "default": "unusable-pack",
            "packs": {
                "unusable-pack": pack.model_dump(),
            },
        }),
        encoding="utf-8",
    )

    exit_code = run_doctor_workflow_pack(cwd=tmp_path, hub_root=tmp_path, pack_id="unusable-pack")
    assert exit_code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert "pack_route_missing" in out["diagnostic_codes"]


def test_doctor_pack_filter(tmp_path: Path) -> None:
    """FR-005: --pack filter in doctor CLI."""
    exit_code = main(["--cwd", str(Path.cwd()), "doctor", "workflow-pack", "--pack", "dev-hub-software"])
    assert exit_code == 0


def test_doctor_io_error_not_skip_pack(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """FR-014: IO errors produce diagnostic code workflow_pack_check_error, not skip pack."""
    def raise_io(*args: object, **kwargs: object) -> object:
        raise OSError("Disk failure")

    monkeypatch.setattr("loop.workflow.pack_graph.check_pack_graph", raise_io)

    codes = check_workflow_pack()
    assert "workflow_pack_check_error" in codes

    exit_code = run_doctor_workflow_pack()
    assert exit_code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert "workflow_pack_check_error" in out["diagnostic_codes"]


def test_ffmpeg_tool_gate_advisory_unless_required(tmp_path: Path) -> None:
    """FR-015: Tool gate missing fails only if required=true; default software does not fail on ffmpeg."""
    rules_root = tmp_path / ".cursor" / "rules"
    rules_root.mkdir(parents=True, exist_ok=True)
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    phase_reg = tmp_path / "phase_registry.yaml"
    phase_reg.write_text("schema: phase-registry/v1\nphases: {}\n", encoding="utf-8")

    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        yaml.safe_dump({
            "id": "advisory-pack",
            "tool_gates": {
                "ffmpeg": {
                    "adapter": "missing/adapter.py",
                    "required": False,
                }
            }
        }),
        encoding="utf-8",
    )

    from loop.workflow.schemas import WorkflowPack
    pack = WorkflowPack(
        id="advisory-pack",
        roles=["adv"],
        command_prefixes=["ADV"],
        phase_registry="phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
    )

    res = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert "pack_tool_gate_missing" not in res.diagnostic_codes

    # Now make it required
    manifest.write_text(
        yaml.safe_dump({
            "id": "advisory-pack",
            "tool_gates": {
                "ffmpeg": {
                    "adapter": "missing/adapter.py",
                    "required": True,
                }
            }
        }),
        encoding="utf-8",
    )
    res_req = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert "pack_tool_gate_missing" in res_req.diagnostic_codes


def test_check_pack_graph_reuses_route_command_and_skill_refs() -> None:
    """FR-003 / FR-004: check_pack_graph composes route_command and check_skill_refs."""
    # Production dev-hub-software pack check
    res = check_pack_graph(pack_or_id="dev-hub-software")
    assert res.ok, f"Expected dev-hub-software pack to pass check_pack_graph, got codes: {res.diagnostic_codes}"


def test_software_pack_doctor_exists_based() -> None:
    """FR-013 / SC-004 / QA TM-007: dev-hub-software pack doctor checks physical file existence."""
    # Real dev-hub-software graph must be green based on real filesystem layout
    res = check_pack_graph(pack_or_id="dev-hub-software")
    assert res.ok is True
    assert res.diagnostic_codes == []


def test_doctor_reports_red_video_pack_not_skip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """FR-013 / AC-4 / Failure TM-008: Video pack red is reported, not skipped in doctor."""
    # Setup a video pack with missing rules_root
    broken_video_manifest = {
        "schema": "workflow-pack-registry/v1",
        "default": "video-production",
        "packs": {
            "video-production": {
                "id": "video-production",
                "rules_root": "non_existent_video_rules",
                "phase_registry": "phase_registry.yaml",
                "memory_bank": "memory-bank",
                "roles": ["script", "visual", "post"],
                "command_prefixes": ["SCRIPT", "VISUAL", "POST"],
            }
        },
    }
    reg_file = tmp_path / "workflow_pack_registry.yaml"
    reg_file.write_text(yaml.safe_dump(broken_video_manifest), encoding="utf-8")
    (tmp_path / "phase_registry.yaml").write_text("schema: phase-registry/v1\nphases: {}\n", encoding="utf-8")
    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)

    exit_code = run_doctor_workflow_pack(cwd=tmp_path, hub_root=tmp_path, pack_id="video-production")
    assert exit_code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert out["pack_id"] == "video-production"
    assert "pack_rules_missing" in out["diagnostic_codes"]


def test_kind_i_no_fully_wired_while_red() -> None:
    """FR-012 / Kind I: Documentation / pack README / CLAUDE table cannot say 'fully wired' while doctor is red."""
    claude_md = Path("CLAUDE.md").read_text(encoding="utf-8")
    assert "fully wired" not in claude_md.lower()
    assert "pack wired" not in claude_md.lower()
    assert "partial load ok" not in claude_md.lower()



def test_dangling_reference_rejected_by_doctor(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """cp3 / FR-003: Dangling dead reference is rejected by the production pack-graph doctor entrypoint."""
    rules_root = tmp_path / ".cursor" / "rules"
    rules_root.mkdir(parents=True, exist_ok=True)
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    phase_reg = tmp_path / "phase_registry.yaml"
    phase_reg.write_text("schema: phase-registry/v1\nphases: {}\n", encoding="utf-8")

    workflow_mdc = rules_root / "workflow-test.mdc"
    workflow_mdc.write_text(
        "---\ndescription: test\n---\n"
        "Reference to missing: @.cursor/rules/shared/cheatsheets/back-audit.mdc\n",
        encoding="utf-8",
    )

    from loop.workflow.schemas import WorkflowPack
    pack = WorkflowPack(
        id="dangling-doc-pack",
        roles=["test"],
        command_prefixes=["TEST"],
        phase_registry="phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
    )

    res = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert not res.ok
    assert "pack_reference_dangling" in res.diagnostic_codes


def test_multiple_codes_with_reference_diagnostics(tmp_path: Path) -> None:
    """cp4 / FR-003: Existing route, gate, and skill diagnostics remain fail-closed alongside reference diagnostics."""
    rules_root = tmp_path / ".cursor" / "rules"
    rules_root.mkdir(parents=True, exist_ok=True)
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    phase_reg = tmp_path / "phase_registry.yaml"
    phase_reg.write_text("schema: phase-registry/v1\nphases: {}\n", encoding="utf-8")

    # 1. Missing lean gate
    workflow_mdc = rules_root / "workflow-plan.mdc"
    workflow_mdc.write_text(
        "---\ndescription: test\n---\n"
        "**Gates**: @.cursor/rules/isolation_rules/_lean/missing_gate.mdc\n"
        "Duplicate target: @.cursor/rules/shared/leaf.mdc\n"
        "Duplicate target: @.cursor/rules/shared/leaf.mdc\n"
        "Dangling target: @.cursor/rules/shared/missing_file.mdc\n",
        encoding="utf-8",
    )
    shared_dir = rules_root / "shared"
    shared_dir.mkdir(parents=True, exist_ok=True)
    (shared_dir / "leaf.mdc").write_text("content\n", encoding="utf-8")

    from loop.workflow.schemas import WorkflowPack
    pack = WorkflowPack(
        id="multi-diag-pack",
        roles=["test"],
        command_prefixes=["TEST"],
        phase_registry="phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
    )

    res = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert not res.ok
    assert "pack_gate_missing" in res.diagnostic_codes
    assert "pack_reference_duplicate" in res.diagnostic_codes
    assert "pack_reference_dangling" in res.diagnostic_codes


def test_active_corpus_duplicate_and_dangling_edges_fail(tmp_path: Path) -> None:
    """cp1 / FR-001 / FR-003 / TM-084-01 / TM-084-04: Production check_pack_graph fails on direct duplicate, transitive ambiguity and dangling active-corpus fixtures with source lines."""
    rules_root = tmp_path / ".cursor" / "rules"
    rules_root.mkdir(parents=True, exist_ok=True)
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    phase_reg = tmp_path / "phase_registry.yaml"
    phase_reg.write_text("schema: phase-registry/v1\nphases: {}\n", encoding="utf-8")

    shared_dir = rules_root / "shared"
    shared_dir.mkdir(parents=True, exist_ok=True)
    (shared_dir / "leaf.mdc").write_text("leaf content\n", encoding="utf-8")
    (shared_dir / "owner.mdc").write_text(
        "---\ndescription: owner\n---\n"
        "@.cursor/rules/shared/leaf.mdc\n",
        encoding="utf-8",
    )

    workflow_mdc = rules_root / "workflow-test.mdc"
    workflow_mdc.write_text(
        "---\ndescription: test\n---\n"
        "Duplicate line 4: @.cursor/rules/shared/leaf.mdc\n"
        "Duplicate line 5: @.cursor/rules/shared/leaf.mdc\n"
        "Transitive ambiguity line 6: @.cursor/rules/shared/owner.mdc\n"
        "Dangling dead ref line 7: @.cursor/rules/shared/missing_file.mdc\n",
        encoding="utf-8",
    )

    from loop.workflow.schemas import WorkflowPack
    pack = WorkflowPack(
        id="active-corpus-fixture-pack",
        roles=["test"],
        command_prefixes=["TEST"],
        phase_registry="phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
    )

    res = check_pack_graph(pack_or_id=pack, cwd=tmp_path, hub_root=tmp_path)
    assert not res.ok
    assert "pack_reference_duplicate" in res.diagnostic_codes
    assert "pack_reference_transitive_ambiguity" in res.diagnostic_codes
    assert "pack_reference_dangling" in res.diagnostic_codes

    diags = res.details.get("reference_diagnostics", [])
    dup_diag = next(d for d in diags if d.get("code") == "pack_reference_duplicate")
    assert [loc["line"] for loc in dup_diag.get("locations", [])] == [4, 5]

    trans_diag = next(d for d in diags if d.get("code") == "pack_reference_transitive_ambiguity")
    assert any(loc["line"] in (4, 5) and "workflow-test.mdc" in loc["path"] for loc in trans_diag.get("locations", []))
    assert any(loc["line"] == 4 and "owner.mdc" in loc["path"] for loc in trans_diag.get("locations", []))

    dangling_diag = next(d for d in diags if d.get("code") == "pack_reference_dangling")
    assert any(loc["line"] == 7 for loc in dangling_diag.get("locations", []))

def test_pack_graph_module_cli_entrypoint(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify python -m loop.workflow.pack_graph doctor runs as executable CLI entrypoint."""
    import subprocess
    import sys
    proc = subprocess.run(
        [sys.executable, "-m", "loop.workflow.pack_graph", "doctor"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["pack_id"] == "dev-hub-software"
    assert data["diagnostic_codes"] == []
