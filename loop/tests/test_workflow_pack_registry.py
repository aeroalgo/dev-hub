"""Pytest test matrix for workflow pack registry (T-HUB-048: TM-001..TM-006)."""
from __future__ import annotations

import os
from pathlib import Path
import pytest
import yaml

from loop.workflow.registry import (
    load_registry,
    resolve_workflow_pack,
)
from loop.workflow.resolve import full_resolve, validate_pack_paths
from loop.workflow.schemas import PackResolveResult, WorkflowPackRegistry
from loop.context_loop import WorkflowConfig, prepare_session


def test_unknown_pack_fail_closed(tmp_path: Path) -> None:
    """TM-001 / AC+1 / FR-004: WORKFLOW_PACK=unknown -> full_resolve -> ok=False, invalid_workflow_pack in diagnostic_codes."""
    # Ensure memory_bank and phase_registry dummy structures exist in tmp_path
    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    phase_reg = tmp_path / "loop" / "schemas" / "phase_registry.yaml"
    phase_reg.parent.mkdir(parents=True, exist_ok=True)
    phase_reg.write_text("dummy: true", encoding="utf-8")

    # Pass WORKFLOW_PACK environment override
    old_env = os.environ.get("WORKFLOW_PACK")
    try:
        os.environ["WORKFLOW_PACK"] = "unknown_pack_slug_12345"
        res = full_resolve(cwd=tmp_path)
        assert not res.ok
        assert "invalid_workflow_pack" in res.diagnostic_codes
        assert res.pack is None
    finally:
        if old_env is None:
            os.environ.pop("WORKFLOW_PACK", None)
        else:
            os.environ["WORKFLOW_PACK"] = old_env


def test_default_pack_paths(tmp_path: Path) -> None:
    """TM-002 / AC+2 / FR-009: Unset env -> resolve -> ok=True, pack_id=dev-hub-software, paths exist."""
    # Create required paths for dev-hub-software pack
    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    phase_reg = tmp_path / "loop" / "schemas" / "phase_registry.yaml"
    phase_reg.parent.mkdir(parents=True, exist_ok=True)
    phase_reg.write_text("dummy: true", encoding="utf-8")

    old_env_wp = os.environ.pop("WORKFLOW_PACK", None)
    old_env_ewp = os.environ.pop("EPIC_WORKFLOW_PACK", None)
    try:
        res = full_resolve(cwd=tmp_path)
        assert res.ok
        assert res.pack_id == "dev-hub-software"
        assert res.pack is not None
        assert res.pack.id == "dev-hub-software"
        assert "back" in res.pack.roles
        assert "BACK" in res.pack.command_prefixes
        assert len(res.diagnostic_codes) == 0
    finally:
        if old_env_wp is not None:
            os.environ["WORKFLOW_PACK"] = old_env_wp
        if old_env_ewp is not None:
            os.environ["EPIC_WORKFLOW_PACK"] = old_env_ewp


def test_corrupt_registry_yaml(tmp_path: Path) -> None:
    """TM-003 / FR-003: Malformed yaml in registry -> load_registry -> Exception / validation failure."""
    corrupt_registry_dir = tmp_path / "loop"
    corrupt_registry_dir.mkdir(parents=True, exist_ok=True)
    corrupt_file = corrupt_registry_dir / "workflow_pack_registry.yaml"
    corrupt_file.write_text("schema: workflow-pack-registry/v1\ndefault: 12345\npacks: [invalid_list]\n", encoding="utf-8")

    load_registry.cache_clear()
    with pytest.raises(Exception):
        load_registry(hub_root=tmp_path)
    load_registry.cache_clear()


def test_prepare_workflow_pack_field(tmp_path: Path) -> None:
    """TM-004 / FR-008: prepare_session(cwd) -> dict with workflow_pack key + pack_id=dev-hub-software."""
    # Setup mock activeContext and minimal memory bank layout
    mb = tmp_path / "memory-bank"
    mb.mkdir(parents=True, exist_ok=True)
    act_ctx = mb / "activeContext.md"
    act_ctx.write_text(
        "# Active Context\n\n"
        "## Current Focus\n"
        "Testing prepare_session.\n\n"
        "## Next Steps\n"
        "- [ ] Test\n\n"
        "## Active Decisions\n"
        "- none\n",
        encoding="utf-8",
    )
    phase_reg = tmp_path / "loop" / "schemas" / "phase_registry.yaml"
    phase_reg.parent.mkdir(parents=True, exist_ok=True)
    phase_reg.write_text("dummy: true", encoding="utf-8")

    old_env_wp = os.environ.pop("WORKFLOW_PACK", None)
    old_env_ewp = os.environ.pop("EPIC_WORKFLOW_PACK", None)
    try:
        prep = prepare_session(tmp_path)
        assert prep.get("ok") is True
        wf_pack_res = prep.get("workflow_pack")
        assert isinstance(wf_pack_res, dict)
        assert wf_pack_res.get("pack_id") == "dev-hub-software"
        pack_obj = wf_pack_res.get("pack")
        assert isinstance(pack_obj, dict)
        assert pack_obj.get("id") == "dev-hub-software"
        assert pack_obj.get("phase_registry") == "loop/schemas/phase_registry.yaml"
    finally:
        if old_env_wp is not None:
            os.environ["WORKFLOW_PACK"] = old_env_wp
        if old_env_ewp is not None:
            os.environ["EPIC_WORKFLOW_PACK"] = old_env_ewp


def test_project_override_workflow_pack(tmp_path: Path) -> None:
    """TM-005 / FR-005: project.yaml with workflow_pack=custom -> precedence over default/env."""
    # 1. Valid custom pack in project.yaml (if defined in registry)
    project_yaml = tmp_path / "project.yaml"
    project_yaml.write_text("workflow_pack: dev-hub-software\n", encoding="utf-8")

    res = resolve_workflow_pack(cwd=tmp_path)
    assert res.ok
    assert res.pack_id == "dev-hub-software"

    # 2. Unknown custom pack
    project_yaml.write_text("workflow_pack: unknown_custom_pack\n", encoding="utf-8")
    res_err = resolve_workflow_pack(cwd=tmp_path)
    assert not res_err.ok
    assert res_err.pack_id == "unknown_custom_pack"
    assert "invalid_workflow_pack" in res_err.diagnostic_codes


def test_cli_workflow_resolve() -> None:
    """Test CLI subcommand 'workflow resolve' and exit code contract."""
    import subprocess
    import json

    # 1. Known pack -> exit code 0
    cmd_ok = ["python3", "harness/hooks/epic_resolve.py", "workflow", "resolve", "--pack", "dev-hub-software"]
    res_ok = subprocess.run(cmd_ok, capture_output=True, text=True)
    assert res_ok.returncode == 0
    data_ok = json.loads(res_ok.stdout)
    assert data_ok["ok"] is True
    assert data_ok["pack_id"] == "dev-hub-software"

    # 2. Unknown pack -> exit code 2
    cmd_err = ["python3", "harness/hooks/epic_resolve.py", "workflow", "resolve", "--pack", "non_existent_pack_xyz"]
    res_err = subprocess.run(cmd_err, capture_output=True, text=True)
    assert res_err.returncode == 2
    data_err = json.loads(res_err.stdout)
    assert data_err["ok"] is False
    assert "invalid_workflow_pack" in data_err["diagnostic_codes"]


def test_zero_regression_existing_smoke() -> None:
    """TM-006 / AC+5: Ensure WorkflowConfig and resolve integrations do not break existing schemas."""
    wf_config = WorkflowConfig.resolve()
    assert wf_config.pack.ok is True
    assert wf_config.pack.pack_id == "dev-hub-software"
    assert wf_config.pack.pack is not None
    assert wf_config.pack.pack.id == "dev-hub-software"
    assert wf_config.pack.pack.artifact_layout == "software-epic-v1"
    assert "back" in wf_config.pack.pack.roles


def test_video_pack_resolves() -> None:
    """AC+1 / SC-001 / FR-001 / FR-003: Video pack is resolvable via resolve_workflow_pack."""
    load_registry.cache_clear()
    old_env = os.environ.get("WORKFLOW_PACK")
    try:
        os.environ["WORKFLOW_PACK"] = "video-production"
        res = resolve_workflow_pack()
        assert res.ok is True
        assert res.pack_id == "video-production"
        assert res.pack is not None
        assert res.pack.id == "video-production"
        assert res.pack.roles == ["script", "visual", "post"]
        assert res.pack.command_prefixes == ["SCRIPT", "VISUAL", "POST"]
        assert res.pack.memory_bank == "memory-bank/video"
        assert res.pack.phase_registry == "workflows/video/phase_registry.yaml"
        assert res.pack.rules_root == ".cursor/rules/video"
        assert res.pack.artifact_layout == "software-epic-v1"
        assert len(res.diagnostic_codes) == 0
    finally:
        load_registry.cache_clear()
        if old_env is None:
            os.environ.pop("WORKFLOW_PACK", None)
        else:
            os.environ["WORKFLOW_PACK"] = old_env


def test_software_pack_unaffected() -> None:
    """AC+5 / AC-3 / TM-003: Software pack remains default when no override is set."""
    load_registry.cache_clear()
    old_env_wp = os.environ.pop("WORKFLOW_PACK", None)
    old_env_ewp = os.environ.pop("EPIC_WORKFLOW_PACK", None)
    try:
        res = resolve_workflow_pack()
        assert res.ok is True
        assert res.pack_id == "dev-hub-software"
        assert res.pack is not None
        assert res.pack.id == "dev-hub-software"
        assert res.pack.roles == ["back", "front", "integration"]
        assert res.pack.command_prefixes == ["BACK", "FRONT", "INTEG"]
    finally:
        load_registry.cache_clear()
        if old_env_wp is not None:
            os.environ["WORKFLOW_PACK"] = old_env_wp
        if old_env_ewp is not None:
            os.environ["EPIC_WORKFLOW_PACK"] = old_env_ewp

