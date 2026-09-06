"""Tests for pack-aware phase router and load_phase_registry (T-HUB-049).

Covers failure matrix TM-001..005 and pack-router regression suite (s01-s06).
"""
from __future__ import annotations

import os
from pathlib import Path
import pytest
import yaml

from loop.epic_transition import (
    _PHASE_REGISTRY_CACHE,
    arm_phase,
    get_dsh_preset,
    get_phase_config,
    get_verify_agent,
    load_phase_registry,
    normalize_registry_phase,
)
from harness.hooks.epic.core import (
    gates_from_phase,
    save_epic_state,
    session_start_payload,
)
from loop.workflow.command_router import CommandRoute, route_command
from loop.workflow.schemas import WorkflowPack


# ==============================================================================
# TM-001: Missing phase_registry YAML -> ValueError (fail-closed)
# ==============================================================================

def test_load_phase_registry_uses_pack_id(tmp_path: Path) -> None:
    """AC+1 / cp1: load_phase_registry(pack_id='dev-hub-software', cwd=tmp) loads phases from pack yaml."""
    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    schema_dir = tmp_path / "loop" / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    custom_yaml = {
        "schema": "phase-registry/v1",
        "phases": {
            "IMPLEMENT": {"verify_agent": "verify-implement", "dsh_preset": "implement"},
            "QA": {"verify_agent": "verify-qa", "dsh_preset": "qa"},
        },
    }
    (schema_dir / "phase_registry.yaml").write_text(yaml.dump(custom_yaml), encoding="utf-8")

    res = load_phase_registry(pack_id="dev-hub-software", cwd=tmp_path)
    assert isinstance(res, dict)
    assert "phases" in res
    assert "IMPLEMENT" in res["phases"]
    assert res["phases"]["IMPLEMENT"]["verify_agent"] == "verify-implement"


def test_load_phase_registry_no_args_fails() -> None:
    """AC−1 / cp2: load_phase_registry() without args -> TypeError fail-closed."""
    with pytest.raises(TypeError):
        load_phase_registry()


def test_no_bare_load_phase_registry() -> None:
    """AC−1 / s06: load_phase_registry() without args -> TypeError."""
    with pytest.raises(TypeError):
        load_phase_registry()


def test_role_prefixes_gone() -> None:
    """AC+1 / s06: _ROLE_PREFIXES is removed from epic_transition."""
    import loop.epic_transition as et
    assert not hasattr(et, "_ROLE_PREFIXES")


def test_default_registry_path_gone() -> None:
    """AC+2 / s06: _DEFAULT_REGISTRY_PATH is removed from epic_transition."""
    import loop.epic_transition as et
    assert not hasattr(et, "_DEFAULT_REGISTRY_PATH")


def test_tm_001_load_phase_registry_missing_yaml_raises_value_error(tmp_path: Path) -> None:
    """TM-001 / AC+1 / AC+2 / cp3: pack_id with missing phase_registry path -> ValueError."""
    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    # dev-hub-software expects loop/schemas/phase_registry.yaml which does not exist in tmp_path
    with pytest.raises(ValueError, match="Phase registry yaml file not found|pack_path_missing|Invalid"):
        load_phase_registry(pack_id="dev-hub-software", cwd=tmp_path)


# ==============================================================================
# TM-002: Unknown phase in pack registry -> ValueError (fail-closed)
# ==============================================================================

def test_tm_002_get_phase_config_unknown_phase_raises_value_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TM-002 / AC+2: get_phase_config raises ValueError on unknown phase fail-closed."""
    rel_registry_path = Path("loop/schemas/custom_phases.yaml")
    full_registry_path = tmp_path / rel_registry_path
    full_registry_path.parent.mkdir(parents=True, exist_ok=True)
    full_registry_path.write_text(
        yaml.safe_dump({
            "phases": {
                "IMPLEMENT": {"verify_agent": "verify-implement", "dsh_preset": "default-dev"},
                "PLAN": {"verify_agent": "verify-plan", "dsh_preset": "default-plan"},
            }
        }),
        encoding="utf-8",
    )

    dummy_pack = WorkflowPack(
        id="test-custom-pack",
        artifact_layout="software-epic-v1",
        command_prefixes=["TEST"],
        roles=["test"],
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
        phase_registry=str(rel_registry_path),
    )

    from loop.workflow import registry as reg_module

    class DummyRegistry:
        default = "test-custom-pack"
        packs = [dummy_pack]

    monkeypatch.setattr(reg_module, "load_registry", lambda cwd=None: DummyRegistry())
    monkeypatch.setattr(reg_module, "get_pack", lambda reg, pack_id: dummy_pack if pack_id == "test-custom-pack" else None)

    # Valid phase works
    cfg = get_phase_config("IMPLEMENT", pack_id="test-custom-pack", cwd=tmp_path)
    assert cfg["verify_agent"] == "verify-implement"

    # Unknown phase raises ValueError
    with pytest.raises(ValueError, match=r"unknown phase 'BADPHASE': fail-closed"):
        get_phase_config("BADPHASE", pack_id="test-custom-pack", cwd=tmp_path)


# ==============================================================================
# TM-003: Normalize role-prefixed command against pack command_prefixes
# ==============================================================================

def test_tm_003_normalize_software_pack() -> None:
    """AC+1 / cp1: normalize_registry_phase('BACK IMPLEMENT', software_pack) -> 'IMPLEMENT'."""
    software_pack = WorkflowPack(
        id="software",
        roles=["back", "front"],
        command_prefixes=["BACK", "FRONT", "INTEG", "INTEGRATION"],
        phase_registry="loop/schemas/phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
    )
    assert normalize_registry_phase("BACK IMPLEMENT", software_pack) == "IMPLEMENT"
    assert normalize_registry_phase("front qa", software_pack) == "QA"


def test_tm_003_normalize_custom_prefix() -> None:
    """TM-003 / AC+3: normalize_registry_phase('SCRIPT IMPLEMENT', video_pack) -> 'IMPLEMENT'."""
    video_pack = WorkflowPack(
        id="video",
        roles=["script", "edit"],
        command_prefixes=["SCRIPT", "VIDEO"],
        phase_registry="loop/schemas/phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
    )
    assert normalize_registry_phase("SCRIPT IMPLEMENT", video_pack) == "IMPLEMENT"
    assert normalize_registry_phase("video review", video_pack) == "REVIEW"


def test_tm_003_normalize_no_prefix() -> None:
    """AC-1 / cp3: normalize without matching prefix -> phase unchanged."""
    pack = WorkflowPack(
        id="software",
        roles=["back"],
        command_prefixes=["BACK"],
        phase_registry="loop/schemas/phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
    )
    assert normalize_registry_phase("IMPLEMENT", pack) == "IMPLEMENT"
    assert normalize_registry_phase("implement", pack) == "IMPLEMENT"


# ==============================================================================
# TM-004: arm_phase routes to custom dsh_preset from pack registry
# ==============================================================================

def test_tm_004_arm_phase_dsh_video_pack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TM-004 / AC+4: arm_phase dsh + video pack -> dsh_preset from video phase_registry."""
    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    video_reg_dir = tmp_path / "video" / "schemas"
    video_reg_dir.mkdir(parents=True, exist_ok=True)
    video_reg_file = video_reg_dir / "phase_registry.yaml"
    video_reg_content = {
        "schema": "phase-registry/v1",
        "phases": {
            "IMPLEMENT": {
                "arm_template": "implement",
                "dsh_preset": "video-impl-preset",
            }
        },
    }
    video_reg_file.write_text(yaml.dump(video_reg_content), encoding="utf-8")

    video_pack = WorkflowPack(
        id="video-prod",
        roles=["script", "edit"],
        command_prefixes=["SCRIPT", "VIDEO"],
        phase_registry="video/schemas/phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
    )

    import loop.workflow.registry as wf_reg

    class MockPackRegistry:
        default = "video-prod"
        packs = {"video-prod": video_pack}

    monkeypatch.setattr(wf_reg, "load_registry", lambda hub_root=None: MockPackRegistry())

    def mock_arm_epic(cwd, epic_id, **kwargs):
        return {"ok": True, "armed_epic": epic_id, "kwargs": kwargs}

    monkeypatch.setattr("epic.core.arm_epic", mock_arm_epic)

    res = arm_phase(
        tmp_path,
        "T-VID-001",
        "SCRIPT IMPLEMENT",
        "script",
        epic_runtime="dsh",
        pack_id="video-prod",
    )
    assert res.get("kwargs", {}).get("dsh_preset") == "video-impl-preset"


# ==============================================================================
# TM-005: session_start_payload includes the current command scope
# ==============================================================================

def test_tm_005_session_start_pack_inject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TM-005 / AC+5: EPIC_LOOP=1 + valid pack -> only current scope is injected."""
    monkeypatch.setenv("EPIC_LOOP", "1")
    save_epic_state(tmp_path, {"active": True, "status": "running", "armed_epic": "T-HUB-049"})

    # Create dummy phase registry and memory bank dir so path validation passes
    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    phase_reg = tmp_path / "loop" / "schemas" / "phase_registry.yaml"
    phase_reg.parent.mkdir(parents=True, exist_ok=True)
    phase_reg.write_text("schema: phase-registry/v1\nphases: {}\n", encoding="utf-8")

    payload = session_start_payload(tmp_path)
    assert payload is not None
    assert "additionalContext" in payload
    assert payload["additionalContext"].startswith("COMMAND: BACK IMPLEMENT\n")
    assert "entrypoint: `CLAUDE.md`" in payload["additionalContext"]
    assert "workflow-implement.mdc" not in payload["additionalContext"]
    assert "Prefixes:" not in payload["additionalContext"]


def test_session_start_pack_inject_fail_safe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC+2 / cp2: EPIC_LOOP=1 + full_resolve fails -> ctx contains warning or safe payload without crash."""
    monkeypatch.setenv("EPIC_LOOP", "1")
    save_epic_state(tmp_path, {"active": True, "status": "running", "armed_epic": "T-HUB-049"})

    # Broken project.yaml specifying non-existent pack
    (tmp_path / "project.yaml").write_text("workflow_pack: non-existent-pack\n", encoding="utf-8")

    payload = session_start_payload(tmp_path)
    assert payload is not None
    assert "additionalContext" in payload
    assert "workflow-qa.mdc" not in payload["additionalContext"]
    assert "Prefixes:" not in payload["additionalContext"]


def test_session_start_no_loop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC−1 / cp3: EPIC_LOOP=0 -> session_start_payload returns None."""
    monkeypatch.delenv("EPIC_LOOP", raising=False)
    assert session_start_payload(tmp_path) is None

    monkeypatch.setenv("EPIC_LOOP", "0")
    assert session_start_payload(tmp_path) is None


# ==============================================================================
# Regression Suite: Cache, Gates, Route Command, Verify Agent
# ==============================================================================

def test_registry_cache_per_pack_id(tmp_path: Path) -> None:
    """cp4: Cache is per-pack-id and cwd; two different roots have independent cache entries."""
    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    schema_dir1 = tmp_path / "pack1" / "loop" / "schemas"
    schema_dir2 = tmp_path / "pack2" / "loop" / "schemas"
    schema_dir1.mkdir(parents=True, exist_ok=True)
    schema_dir2.mkdir(parents=True, exist_ok=True)
    (schema_dir1 / "phase_registry.yaml").write_text(
        yaml.dump({"schema": "phase-registry/v1", "phases": {"P1": {"val": 1}}}), encoding="utf-8"
    )
    (schema_dir2 / "phase_registry.yaml").write_text(
        yaml.dump({"schema": "phase-registry/v1", "phases": {"P2": {"val": 2}}}), encoding="utf-8"
    )

    res1 = load_phase_registry(pack_id="dev-hub-software", cwd=tmp_path / "pack1")
    res2 = load_phase_registry(pack_id="dev-hub-software", cwd=tmp_path / "pack2")
    assert "P1" in res1["phases"]
    assert "P2" in res2["phases"]
    assert "P2" not in res1["phases"]


def test_gates_from_phase_video_pack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC+1 / cp1: gates_from_phase with explicit video pack -> gates from video registry."""
    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    video_reg_dir = tmp_path / "video" / "schemas"
    video_reg_dir.mkdir(parents=True, exist_ok=True)
    video_reg_file = video_reg_dir / "phase_registry.yaml"
    video_reg_content = {
        "schema": "phase-registry/v1",
        "roles": ["script", "edit"],
        "terminal_phases": ["DONE"],
        "phases": {
            "IMPLEMENT": {
                "arm_template": "implement",
                "finish_gates_dict": {
                    "mode": "video-implement",
                    "need_verify": True,
                    "need_reviewer": True,
                },
                "verify_agent": "verify-video",
                "dsh_preset": "video-impl",
            }
        },
    }
    video_reg_file.write_text(yaml.dump(video_reg_content), encoding="utf-8")

    video_pack = WorkflowPack(
        id="video-prod",
        roles=["script", "edit"],
        command_prefixes=["SCRIPT", "VIDEO"],
        phase_registry="video/schemas/phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
    )

    import loop.workflow.registry as wf_reg

    class MockPackRegistry:
        default = "video-prod"
        packs = {"video-prod": video_pack}

    monkeypatch.setattr(wf_reg, "load_registry", lambda hub_root=None: MockPackRegistry())

    gates = gates_from_phase("SCRIPT IMPLEMENT", pack=video_pack, cwd=tmp_path)
    assert gates["mode"] == "video-implement"
    assert gates["need_verify"] is True
    assert gates["need_reviewer"] is True


def test_gates_from_phase_auto_resolve(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-1 / cp2: gates_from_phase without pack -> full_resolve auto -> gates from resolved pack."""
    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    custom_yaml = {
        "schema": "phase-registry/v1",
        "phases": {
            "IMPLEMENT": {
                "finish_gates_dict": {
                    "mode": "custom-mode",
                    "need_verify": True,
                    "need_reviewer": False,
                }
            }
        },
    }
    (schema_dir / "custom_phases.yaml").write_text(yaml.dump(custom_yaml), encoding="utf-8")

    custom_pack = WorkflowPack(
        id="custom-pack",
        roles=["back"],
        command_prefixes=["BACK"],
        phase_registry="schemas/custom_phases.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
    )

    import loop.workflow.registry as wf_reg

    class MockPackRegistry:
        default = "custom-pack"
        packs = {"custom-pack": custom_pack}

    monkeypatch.setattr(wf_reg, "load_registry", lambda hub_root=None: MockPackRegistry())

    # project.yaml specifies pack
    (tmp_path / "project.yaml").write_text("workflow_pack: custom-pack\n", encoding="utf-8")

    gates = gates_from_phase("IMPLEMENT", cwd=tmp_path)
    assert gates["mode"] == "custom-mode"
    assert gates["need_verify"] is True


def test_get_verify_agent_pack_id(tmp_path: Path) -> None:
    """cp4 / tdd: get_verify_agent with pack_id and cwd."""
    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    schema_dir = tmp_path / "loop" / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    custom_yaml = {
        "schema": "phase-registry/v1",
        "phases": {
            "IMPLEMENT": {"verify_agent": "verify-implement", "dsh_preset": "implement"},
        },
    }
    (schema_dir / "phase_registry.yaml").write_text(yaml.dump(custom_yaml), encoding="utf-8")

    agent = get_verify_agent("IMPLEMENT", pack_id="dev-hub-software", cwd=tmp_path)
    assert agent == "verify-implement"


def test_route_command_software() -> None:
    """AC+1 / cp1: route_command(software_pack, 'BACK IMPLEMENT') -> CommandRoute."""
    software_pack = WorkflowPack(
        id="dev-hub-software",
        roles=["back", "front", "integration"],
        command_prefixes=["BACK", "FRONT", "INTEG"],
        phase_registry="loop/schemas/phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
        artifact_layout="software-epic-v1",
        description="Default software delivery",
    )

    route = route_command(software_pack, "BACK IMPLEMENT")
    assert isinstance(route, CommandRoute)
    assert route.normalized_phase == "IMPLEMENT"
    assert route.rules_mdc_rel == ".cursor/rules/back_developer/workflow-implement.mdc"
    # TM-006 / FR-009: verify target path exists on disk in repo root
    repo_root = Path(__file__).resolve().parents[2]
    assert (repo_root / route.rules_mdc_rel).is_file()

    route_front = route_command(software_pack, "front qa")
    assert route_front.normalized_phase == "QA"
    assert route_front.rules_mdc_rel == ".cursor/rules/front_developer/workflow-qa.mdc"

    route_integ = route_command(software_pack, "INTEG PLAN")
    assert route_integ.normalized_phase == "PLAN"
    assert route_integ.rules_mdc_rel == ".cursor/rules/integration_developer/workflow-plan.mdc"


def test_route_command_custom_prefix(tmp_path: Path) -> None:
    """AC+2 / cp2: route_command with custom video pack."""
    rules_dir = tmp_path / "packs" / "video" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "workflow-plan.mdc").write_text("# Plan", encoding="utf-8")

    video_pack = WorkflowPack(
        id="video-prod",
        roles=["script", "edit", "render"],
        command_prefixes=["SCRIPT", "EDIT", "RENDER"],
        phase_registry="packs/video/phases.yaml",
        memory_bank="memory-bank/video",
        rules_root="packs/video/rules",
        artifact_layout="software-epic-v1",
        description="Video production",
    )

    route = route_command(video_pack, "SCRIPT PLAN", hub_root=tmp_path)
    assert route.ok is True
    assert route.normalized_phase == "PLAN"
    assert route.rules_mdc_rel == "packs/video/rules/workflow-plan.mdc"


def test_route_command_passthrough() -> None:
    """AC−1 / cp3: route_command unknown or raw phase -> pass-through, rules_mdc_rel=None."""
    software_pack = WorkflowPack(
        id="dev-hub-software",
        roles=["back", "front", "integration"],
        command_prefixes=["BACK", "FRONT", "INTEG"],
        phase_registry="loop/schemas/phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
        artifact_layout="software-epic-v1",
    )

    route_unknown = route_command(software_pack, "UNKNOWN")
    assert route_unknown.normalized_phase == "UNKNOWN"
    assert route_unknown.rules_mdc_rel is None

    route_empty = route_command(software_pack, "")
    assert route_empty.normalized_phase == ""
    assert route_empty.rules_mdc_rel is None


def test_route_command_case() -> None:
    """tdd: case-insensitive command matching."""
    software_pack = WorkflowPack(
        id="dev-hub-software",
        roles=["back", "front", "integration"],
        command_prefixes=["BACK", "FRONT", "INTEG"],
        phase_registry="loop/schemas/phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
        artifact_layout="software-epic-v1",
    )

    route = route_command(software_pack, "back implement")
    assert route.normalized_phase == "IMPLEMENT"
    assert route.rules_mdc_rel == ".cursor/rules/back_developer/workflow-implement.mdc"
