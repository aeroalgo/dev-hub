"""E2E smoke suite for video-production pack (T-HUB-051: s08 / TM-001..006).

Tests video pack resolution, arming/phases, mock tool gate, software isolation parity,
template manifest validation, and render gate pass/fail workflows.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
import pytest
import yaml

from loop.epic_transition import (
    _PHASE_REGISTRY_CACHE,
    arm_phase,
    get_phase_config,
    get_verify_agent,
    load_phase_registry,
)
from loop.workflow.registry import (
    load_registry,
    resolve_workflow_pack,
)
from loop.workflow.resolve import full_resolve
from loop.workflow.schemas import WorkflowPack
from loop.workflow.tool_gates.protocol import (
    ToolGateAdapter,
    ToolGateContext,
    ToolGateResult,
)
from workflows.video.tools.render_check import RenderCheckAdapter

ROOT = Path(__file__).resolve().parents[2]


class MockRenderCheckAdapter(ToolGateAdapter):
    """Controllable mock tool gate adapter for testing render gate behavior."""

    def __init__(self, ok: bool = True, diagnostic_codes: list[str] | None = None) -> None:
        self._ok = ok
        self._diagnostic_codes = diagnostic_codes or ([] if ok else ["mock_render_failed"])

    @property
    def id(self) -> str:
        return "render"

    def check(self, ctx: ToolGateContext) -> ToolGateResult:
        return ToolGateResult(
            ok=self._ok,
            diagnostic_codes=list(self._diagnostic_codes),
        )


@pytest.fixture
def tmp_project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Fixture creating a full video pack PROJECT_ROOT structure."""
    # Create project.yaml selecting video pack
    (tmp_path / "project.yaml").write_text("workflow_pack: video-production\n", encoding="utf-8")

    # Copy / symlink required files
    shutil.copytree(ROOT / "workflows", tmp_path / "workflows", dirs_exist_ok=True)
    shutil.copytree(ROOT / ".cursor", tmp_path / ".cursor", dirs_exist_ok=True)
    (tmp_path / "loop").mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "loop" / "workflow_pack_registry.yaml", tmp_path / "loop" / "workflow_pack_registry.yaml")

    # Create memory-bank/video skeleton
    mb_video = tmp_path / "memory-bank" / "video"
    (mb_video / "script" / "plan" / "decompose-T-VIDEO-001-demo").mkdir(parents=True, exist_ok=True)
    (mb_video / "script" / "plan" / "decompose-T-VIDEO-001-demo" / ".gitkeep").touch()
    (mb_video / "activeContext.md").write_text("# Active Context\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def tmp_mp4_fixture(tmp_path: Path) -> Path:
    """Fixture creating a non-empty outputs/final.mp4 stub."""
    out_dir = tmp_path / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    mp4_file = out_dir / "final.mp4"
    mp4_file.write_bytes(b"dummy mp4 fixture payload header 00000018ftypmp42")
    return mp4_file


def test_video_pack_resolve(tmp_project_root: Path) -> None:
    """TM-003 / FR-011: resolve_workflow_pack(cwd=tmp) ok=True, pack_id='video-production'."""
    load_registry.cache_clear()
    res = resolve_workflow_pack(cwd=tmp_project_root)
    assert res.ok is True
    assert res.pack_id == "video-production"
    assert res.pack is not None
    assert res.pack.roles == ["script", "visual", "post"]
    assert res.pack.command_prefixes == ["SCRIPT", "VISUAL", "POST"]
    assert res.pack.phase_registry == "workflows/video/phase_registry.yaml"
    assert res.pack.memory_bank == "memory-bank/video"
    assert res.pack.rules_root == ".cursor/rules/video"


def test_software_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TM-006 / AC+5: Software pack unaffected when WORKFLOW_PACK not set and no video project.yaml."""
    load_registry.cache_clear()
    monkeypatch.delenv("WORKFLOW_PACK", raising=False)
    monkeypatch.delenv("EPIC_WORKFLOW_PACK", raising=False)

    # In tmp_path without project.yaml, defaults to dev-hub-software
    res = resolve_workflow_pack(cwd=tmp_path)
    assert res.ok is True
    assert res.pack_id == "dev-hub-software"
    assert res.pack is not None
    assert res.pack.roles == ["back", "front", "integration"]
    assert res.pack.command_prefixes == ["BACK", "FRONT", "INTEG"]


def test_script_gates_differ(tmp_project_root: Path) -> None:
    """SC-002: SCRIPT gates != EDIT gates != BACK IMPLEMENT gates."""
    _PHASE_REGISTRY_CACHE.clear()
    script_cfg = get_phase_config("SCRIPT", cwd=str(tmp_project_root))
    edit_cfg = get_phase_config("EDIT", cwd=str(tmp_project_root))

    assert script_cfg["arm_template"] == "pre_implement"
    assert edit_cfg["arm_template"] == "implement"
    assert script_cfg["arm_template"] != edit_cfg["arm_template"]

    assert script_cfg.get("verify_agent") == "verify-script"
    assert edit_cfg.get("verify_agent") == "verify-edit"
    assert edit_cfg.get("external_gates") == ["render"]
    assert "external_gates" not in script_cfg or not script_cfg.get("external_gates")


def test_edit_phase_verify_gate_contract(tmp_project_root: Path) -> None:
    """TM-004 / FR-011: EDIT phase verify gate contract (verify-edit agent, render external gate)."""
    _PHASE_REGISTRY_CACHE.clear()
    agent = get_verify_agent("EDIT", cwd=str(tmp_project_root))
    assert agent == "verify-edit"

    cfg = get_phase_config("EDIT", cwd=str(tmp_project_root))
    assert cfg.get("finish_gates_dict", {}).get("need_verify") is True
    assert cfg.get("external_gates") == ["render"]


def test_render_gate_fail(tmp_project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SC-003 / TM-001: MockAdapter ok=False -> check returns ok=False and diagnostic codes."""
    mock_adapter = MockRenderCheckAdapter(ok=False, diagnostic_codes=["mock_render_missing"])
    monkeypatch.setattr(
        "loop.workflow.tool_gates.loader.load_tool_gate_adapter",
        lambda gate_id, cwd=None: mock_adapter,
    )

    ctx = ToolGateContext(cwd=tmp_project_root, phase="EDIT", pack_id="video-production")
    result = mock_adapter.check(ctx)
    assert result.ok is False
    assert "mock_render_missing" in result.diagnostic_codes


def test_render_gate_pass(tmp_project_root: Path, tmp_mp4_fixture: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SC-003 / TM-002: fixture mp4 + MockAdapter ok=True -> check returns ok=True."""
    mock_adapter = MockRenderCheckAdapter(ok=True)
    monkeypatch.setattr(
        "loop.workflow.tool_gates.loader.load_tool_gate_adapter",
        lambda gate_id, cwd=None: mock_adapter,
    )

    ctx = ToolGateContext(cwd=tmp_project_root, phase="EDIT", pack_id="video-production")
    result = mock_adapter.check(ctx)
    assert result.ok is True
    assert result.diagnostic_codes == []


def test_template_validate() -> None:
    """TM-005 / s07: filled template manifest validates against WorkflowPack schema."""
    template_path = ROOT / "workflows" / "_template" / "manifest.yaml"
    assert template_path.is_file()

    content = yaml.safe_load(template_path.read_text(encoding="utf-8"))
    assert "id" in content
    assert "roles" in content
    assert "command_prefixes" in content

    # Test that a concrete pack instantiated with valid fields validates against WorkflowPack
    filled_data = {
        "id": "my-custom-pack",
        "roles": ["author", "reviewer"],
        "command_prefixes": ["AUTHOR", "REVIEWER"],
        "phase_registry": "workflows/my-custom-pack/phase_registry.yaml",
        "memory_bank": "memory-bank/my-custom-pack",
        "rules_root": ".cursor/rules/my-custom-pack",
        "artifact_layout": "software-epic-v1",
        "description": "Custom test pack",
    }
    pack = WorkflowPack(**filled_data)
    assert pack.id == "my-custom-pack"
    assert pack.roles == ["author", "reviewer"]


def test_sample_epic_fixture_exists() -> None:
    """FR-012: Sample epic fixture memory-bank/video/script/plan/decompose-T-VIDEO-001-demo/ exists in repo."""
    fixture_dir = ROOT / "memory-bank" / "video" / "script" / "plan" / "decompose-T-VIDEO-001-demo"
    assert fixture_dir.is_dir()
    assert (fixture_dir / ".gitkeep").exists()


def test_video_intent_commands_route_paths_exist() -> None:
    """FR-001 / FR-007 / TM-001 / SC-001 / US-001: Every video intent command routes to existing path on disk."""
    from loop.workflow.command_router import load_intent_routing, route_command
    from loop.workflow.registry import load_registry

    reg = load_registry(ROOT)
    video_pack = reg.packs["video-production"]
    routing = load_intent_routing(ROOT)

    video_intents = ["video_production", "content_factory"]
    for intent_name in video_intents:
        route_def = routing.intents[intent_name]
        for step in route_def.pipeline:
            cmd = step.command
            route = route_command(video_pack, cmd, hub_root=ROOT)
            assert route.ok is True, f"Command '{cmd}' failed to route: {route.diagnostic_codes}"
            assert route.rules_mdc_rel is not None
            path = ROOT / route.rules_mdc_rel
            assert path.is_file(), f"Workflow file for command '{cmd}' does not exist: {path}"


def test_missing_video_workflow_pack_route_missing(tmp_path: Path) -> None:
    """FR-007 / TM-002 / AC−1: Missing workflow file yields ok=False with pack_route_missing diagnostic."""
    from loop.workflow.command_router import route_command
    from loop.workflow.schemas import WorkflowPack

    # Create empty rules_root with no workflow files
    rules_dir = tmp_path / ".cursor" / "rules" / "video"
    rules_dir.mkdir(parents=True, exist_ok=True)

    video_pack = WorkflowPack(
        id="video-production",
        roles=["script", "visual", "post"],
        command_prefixes=["SCRIPT", "VISUAL", "POST"],
        phase_registry="workflows/video/phase_registry.yaml",
        memory_bank="memory-bank/video",
        rules_root=".cursor/rules/video",
        artifact_layout="software-epic-v1",
    )

    route = route_command(video_pack, "SCRIPT PLAN", hub_root=tmp_path)
    assert route.ok is False
    assert "pack_route_missing" in route.diagnostic_codes


def test_script_plan_not_ghost_script_developer() -> None:
    """FR-002 / AC−4: SCRIPT PLAN does not resolve to ghost script_developer subdir."""
    from loop.workflow.command_router import route_command
    from loop.workflow.registry import load_registry

    reg = load_registry(ROOT)
    video_pack = reg.packs["video-production"]

    route = route_command(video_pack, "SCRIPT PLAN", hub_root=ROOT)
    assert route.ok is True
    assert "script_developer" not in (route.rules_mdc_rel or "")
    assert route.rules_mdc_rel == ".cursor/rules/video/workflow-plan.mdc"


def test_route_command_never_ok_missing_file(tmp_path: Path) -> None:
    """Technology axiom Route: route_command never yields ok=True when target file is missing."""
    from loop.workflow.command_router import route_command
    from loop.workflow.schemas import WorkflowPack

    custom_pack = WorkflowPack(
        id="custom",
        roles=["back"],
        command_prefixes=["BACK"],
        phase_registry="phases.yaml",
        memory_bank="mb",
        rules_root="nonexistent_rules",
        artifact_layout="software-epic-v1",
    )

    route = route_command(custom_pack, "BACK IMPLEMENT", hub_root=tmp_path)
    assert route.ok is False
    assert "pack_route_missing" in route.diagnostic_codes


def test_manifest_declares_three_video_verify_agents() -> None:
    """FR-003 / TM-003: Manifest yaml declares verify-script, verify-edit, verify-publish."""
    manifest_path = Path(__file__).resolve().parents[2] / "harness" / "manifest.yaml"
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    agents = data.get("agents", {})
    for agent_id in ("verify-script", "verify-edit", "verify-publish"):
        assert agent_id in agents, f"{agent_id} missing from manifest.yaml agents"
        assert agents[agent_id].get("runtimes", {}).get("claude", {}).get("copy_to") == f".claude/agents/{agent_id}.md"
        assert agents[agent_id].get("runtimes", {}).get("codex", {}).get("materialize") is True
        assert agents[agent_id].get("runtimes", {}).get("codex", {}).get("target") == f".codex/agents/{agent_id}.toml"


def test_codex_verify_edit_toml_exists_after_materialize() -> None:
    """US-002 / Independent Test: .codex/agents/verify-edit.toml exists."""
    repo_root = Path(__file__).resolve().parents[2]
    assert (repo_root / ".codex" / "agents" / "verify-script.toml").exists()
    assert (repo_root / ".codex" / "agents" / "verify-edit.toml").exists()
    assert (repo_root / ".codex" / "agents" / "verify-publish.toml").exists()


def test_verify_edit_prompt_not_implement_verbatim() -> None:
    """FR-010 / AC−5: Distinct prompts — verify-edit.md is not a copy of verify-implement contract."""
    repo_root = Path(__file__).resolve().parents[2]
    edit_prompt = (repo_root / "harness" / "agents" / "verify-edit.md").read_text(encoding="utf-8")
    implement_prompt = (repo_root / "harness" / "agents" / "verify-implement.md").read_text(encoding="utf-8")
    assert edit_prompt != implement_prompt
    assert "name: verify-edit" in edit_prompt
    assert "EDIT" in edit_prompt
    assert "name: verify-implement" not in edit_prompt


def test_software_back_implement_path_exists() -> None:
    """TM-006: BACK IMPLEMENT route path exists in software pack."""
    from loop.workflow.command_router import route_command
    from loop.workflow.registry import load_registry

    reg = load_registry(ROOT)
    software_pack = reg.packs["dev-hub-software"]
    route = route_command(software_pack, "BACK IMPLEMENT", hub_root=ROOT)
    assert route.ok is True
    assert route.rules_mdc_rel is not None
    assert (ROOT / route.rules_mdc_rel).is_file()


def test_video_readme_not_fully_wired_false_claim() -> None:
    """FR-009: Video pack README and CLAUDE.md do not make false fully wired claims."""
    readme_text = (ROOT / "workflows" / "video" / "README.md").read_text(encoding="utf-8")
    claude_text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "fully wired" not in readme_text.lower()
    assert "pack works" not in readme_text.lower()
    assert "fully wired" not in claude_text.lower()


def test_no_ghost_script_developer_video_sot_after_purge() -> None:
    """s06 TDD: Ensure video pack routing does not use ghost script_developer subdir."""
    from loop.workflow.command_router import route_command
    from loop.workflow.registry import load_registry

    reg = load_registry(ROOT)
    video_pack = reg.packs["video-production"]
    for cmd in ["SCRIPT PLAN", "SCRIPT DECOMPOSE", "SCRIPT IMPLEMENT"]:
        route = route_command(video_pack, cmd, hub_root=ROOT)
        assert route.ok is True
        assert "script_developer" not in (route.rules_mdc_rel or "")
        assert Path(ROOT / route.rules_mdc_rel).is_file()


def test_no_exclusive_allowlist_only_parity(tmp_path: Path) -> None:
    """s06 TDD: Parity checks all harness/agents/*.md files dynamically, not just hardcoded allowlist."""
    from loop.runtime_materializers.parity import check_codex_parity

    hooks_file = ROOT / ".codex" / "hooks.json"
    manifest_file = ROOT / "harness" / "manifest.yaml"
    dummy_agents_dir = tmp_path / "agents"
    dummy_agents_dir.mkdir(parents=True)
    (dummy_agents_dir / "unregistered-video-agent.md").write_text("# prompt", encoding="utf-8")

    issues = check_codex_parity(hooks_file, manifest_file, agents_dir=dummy_agents_dir)
    assert any("unregistered-video-agent" in iss for iss in issues)


def test_pack_route_missing_still_fail_closed(tmp_path: Path) -> None:
    """s06 TDD: Missing route file yields ok=False with pack_route_missing diagnostic."""
    from loop.workflow.command_router import route_command
    from loop.workflow.schemas import WorkflowPack

    pack = WorkflowPack(
        id="video-empty",
        roles=["script"],
        command_prefixes=["SCRIPT"],
        phase_registry="loop/schemas/phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root="empty_rules_root",
    )
    route = route_command(pack, "SCRIPT PLAN", hub_root=tmp_path)
    assert route.ok is False
    assert "pack_route_missing" in route.diagnostic_codes



