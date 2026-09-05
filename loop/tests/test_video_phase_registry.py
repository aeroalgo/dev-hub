"""Tests for video workflow pack phase registry (T-HUB-051: s02)."""
from __future__ import annotations

from pathlib import Path
import yaml
import pytest

from loop.epic_transition import load_phase_registry, get_phase_config, get_verify_agent


def test_load_phase_registry_video() -> None:
    """Test that load_phase_registry parses video pack phase_registry without error."""
    repo_root = Path(__file__).resolve().parents[2]
    registry = load_phase_registry(pack_id="video-production", cwd=repo_root)
    assert isinstance(registry, dict)
    assert "phases" in registry
    phases = registry["phases"]
    expected_phases = ["BRIEF", "SCRIPT", "STORYBOARD", "SHOOT", "EDIT", "PUBLISH"]
    for p in expected_phases:
        assert p in phases, f"Expected phase {p} in video phase registry"


def test_edit_external_gates() -> None:
    """Test that EDIT phase contains external_gates: [render]."""
    repo_root = Path(__file__).resolve().parents[2]
    phase_file = repo_root / "workflows" / "video" / "phase_registry.yaml"
    data = yaml.safe_load(phase_file.read_text(encoding="utf-8"))
    edit_phase = data["phases"]["EDIT"]
    assert edit_phase.get("external_gates") == ["render"]
    assert edit_phase.get("verify_agent") == "verify-edit"
    assert edit_phase.get("arm_template") == "implement"


def test_script_vs_edit_arm_template() -> None:
    """Test that SCRIPT and EDIT have different arm_template configs (SC-002)."""
    repo_root = Path(__file__).resolve().parents[2]
    phase_file = repo_root / "workflows" / "video" / "phase_registry.yaml"
    data = yaml.safe_load(phase_file.read_text(encoding="utf-8"))
    script_phase = data["phases"]["SCRIPT"]
    edit_phase = data["phases"]["EDIT"]
    assert script_phase["arm_template"] != edit_phase["arm_template"]
    assert script_phase["arm_template"] == "pre_implement"
    assert edit_phase["arm_template"] == "implement"
    assert script_phase.get("verify_agent") == "verify-script"


def test_video_verify_agents() -> None:
    """Test get_verify_agent resolution for video production phases."""
    repo_root = Path(__file__).resolve().parents[2]
    assert get_verify_agent("SCRIPT", pack_id="video-production", cwd=repo_root) == "verify-script"
    assert get_verify_agent("EDIT", pack_id="video-production", cwd=repo_root) == "verify-edit"
    assert get_verify_agent("PUBLISH", pack_id="video-production", cwd=repo_root) == "verify-publish"
    assert get_verify_agent("SHOOT", pack_id="video-production", cwd=repo_root) is None
    assert get_verify_agent("BRIEF", pack_id="video-production", cwd=repo_root) is None
