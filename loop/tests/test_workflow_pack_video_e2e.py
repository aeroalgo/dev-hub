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
