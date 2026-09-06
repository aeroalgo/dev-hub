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


def test_brief_storyboard_shoot_no_gate_reason() -> None:
    """FR-006 / SC-004: BRIEF/STORYBOARD/SHOOT have machine field no_gate_reason."""
    repo_root = Path(__file__).resolve().parents[2]
    phase_file = repo_root / "workflows" / "video" / "phase_registry.yaml"
    data = yaml.safe_load(phase_file.read_text(encoding="utf-8"))
    phases = data["phases"]
    for phase_name in ["BRIEF", "STORYBOARD", "SHOOT"]:
        cfg = phases[phase_name]
        assert "no_gate_reason" in cfg, f"{phase_name} missing no_gate_reason"
        assert isinstance(cfg["no_gate_reason"], str) and len(cfg["no_gate_reason"].strip()) > 0
        assert cfg.get("verify_agent") is None, f"{phase_name} must have verify_agent null"


def test_shoot_not_need_verify_without_agent() -> None:
    """Failure TM-004: SHOOT cannot have need_verify true with null verify_agent."""
    repo_root = Path(__file__).resolve().parents[2]
    phase_file = repo_root / "workflows" / "video" / "phase_registry.yaml"
    data = yaml.safe_load(phase_file.read_text(encoding="utf-8"))
    shoot = phases = data["phases"]["SHOOT"]
    assert shoot.get("verify_agent") is None
    finish_gates = shoot.get("finish_gates", {})
    finish_gates_dict = shoot.get("finish_gates_dict", {})
    assert finish_gates.get("need_verify") is not True
    assert finish_gates_dict.get("need_verify") is not True


def test_verify_edit_in_stop_validate_set() -> None:
    """TM-005 / US-003: verify-edit is in VERIFY_FINISH_AGENTS."""
    from loop.mb_finish.verify_hint import VERIFY_FINISH_AGENTS
    assert "verify-edit" in VERIFY_FINISH_AGENTS


def test_verify_script_publish_in_stop_set() -> None:
    """FR-005: verify-script and verify-publish are in VERIFY_FINISH_AGENTS."""
    from loop.mb_finish.verify_hint import VERIFY_FINISH_AGENTS
    assert "verify-script" in VERIFY_FINISH_AGENTS
    assert "verify-publish" in VERIFY_FINISH_AGENTS


def test_video_verify_not_silent_skip(tmp_path: Path) -> None:
    """AC-3 / FR-010: SubagentStop validates loop-gate-verdict/v1 for video verify agents and rejects invalid schema."""
    import subprocess
    import json
    import sys
    hook_path = Path(__file__).resolve().parents[2] / "harness" / "hooks" / "subagent-stop.py"

    # Send an invalid gate verdict (missing required verdict / fields) from verify-edit
    invalid_data = {
        "agent_type": "verify-edit",
        "message": "```json\n{\"schema\": \"loop-gate-verdict/v1\"}\n```",
        "session_id": "test-video-stop-sess",
        "cwd": str(tmp_path),
    }
    res = subprocess.run(
        [Path(sys.executable), str(hook_path)],
        input=json.dumps(invalid_data),
        text=True,
        capture_output=True,
        cwd=str(tmp_path),
    )
    # Must reject with schema validation error, NOT silently pass / skip
    assert res.returncode == 2
    assert "verify-edit: schema validation failed" in res.stderr

