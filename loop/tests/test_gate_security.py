import json
from pathlib import Path
import pytest

from loop.config import PHASES, PHASE_ENV_NAMES, LoopSettings
from loop.kernel.model import Cursor
from loop.kernel.store import LoopPaths
from loop.kernel.engine import LoopEngine, TransitionError, _PHASE_GATE_AGENTS
from loop.kernel.verdict import GateVerdict
from loop.kernel.cli import _gate_protocol, _phase_instruction


def test_security_prompt_requires_workflow_bootstrap(tmp_path: Path) -> None:
    """SECURITY execute must force workflow-security + gates; never implement-bootstrap."""
    paths = LoopPaths(project=tmp_path, hub=tmp_path / "hub")
    cursor = Cursor(
        epic_id="T-HUB-999-sec",
        role="back",
        kind="security",
        phase="SECURITY",
        step_id="a01",
        session_id="s-test",
    )
    instruction = _phase_instruction(cursor, tmp_path)
    assert "HARD SECURITY bootstrap" in instruction
    assert ".cursor/rules/back_developer/workflow-security.mdc" in instruction
    assert ".cursor/rules/shared/_lean/security.mdc" in instruction
    assert ".cursor/rules/back_developer/isolation_rules/_lean/security.mdc" in instruction
    assert ".cursor/rules/shared/workflow-security-epic.mdc" in instruction
    assert "implement-bootstrap.mdc" in instruction
    assert "do not use implement-bootstrap.mdc" in instruction
    assert "memory-bank/back/security/plan/" in instruction
    assert "memory-bank/back/security/implement/" in instruction
    assert "verify-security" in instruction
    assert "code_changed: no" in instruction


def test_security_phase_model() -> None:
    assert "SECURITY" in PHASES
    assert PHASE_ENV_NAMES.get("SECURITY") == "PROJECT_LOOP_SECURITY_MODEL"

    settings = LoopSettings(
        security_model="anthropic/claude-3-7-sonnet",
    )
    assert settings.security_model == "anthropic/claude-3-7-sonnet"

    selection = settings.model_for(phase="SECURITY", step_id="a01")
    assert selection.source == "phase_env"
    assert selection.model == "anthropic/claude-3-7-sonnet"
    assert selection.env_name == "PROJECT_LOOP_SECURITY_MODEL"


def test_security_gate_agent(tmp_path: Path) -> None:
    assert _PHASE_GATE_AGENTS.get("SECURITY") == "verify-security"
    assert LoopEngine._required_gate_agent("SECURITY") == "verify-security"

    paths = LoopPaths(project=tmp_path, hub=tmp_path)
    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    paths.cursor.parent.mkdir(parents=True, exist_ok=True)

    plan_dir = tmp_path / "memory-bank" / "back" / "security" / "plan" / "T-HUB-999-sec"
    (plan_dir / "yaml" / "steps").mkdir(parents=True, exist_ok=True)
    (plan_dir / "yaml" / "decompose-index.yaml").write_text(
        "schema: epic-decompose-index/v1\nplan_id: T-HUB-999-sec\nsteps:\n  - id: a01\n    file: a01-auth.yaml\n    status: pending\n"
    )
    (plan_dir / "yaml" / "steps" / "a01-auth.yaml").write_text("schema: epic-decompose/v1\nstep_id: a01\n")

    cursor = Cursor(
        role="back",
        epic_id="T-HUB-999-sec",
        step_id="a01",
        phase="SECURITY",
        kind="security",
        session_id="session-test-sec",
        phase_epoch=1,
        revision=1,
    )
    paths.cursor.write_text(json.dumps(cursor.to_dict()))
    engine = LoopEngine(paths)

    wrong_pass = GateVerdict(
        schema="loop-gate-verdict/v1",
        agent_id="verify-implement",
        verdict="PASS",
        step_id="a01",
        session_id="session-test-sec",
        epic_id="T-HUB-999-sec",
        recorded_at="2026-10-24T12:00:00+00:00",
    )

    with pytest.raises(TransitionError, match="cannot finish SECURITY: verify-security PASS is required before finish"):
        engine.finish(step_id="a01")

    with pytest.raises(TransitionError, match="verdict agent mismatch for SECURITY: expected=verify-security, received=verify-implement"):
        engine.accept_verdict(wrong_pass)


def test_security_gate_protocol(tmp_path: Path) -> None:
    cursor = Cursor(
        role="back",
        epic_id="T-HUB-999-sec",
        step_id="a01",
        phase="SECURITY",
        kind="security",
        session_id="session-test-sec",
        phase_epoch=1,
        revision=1,
    )
    # Set up security plan & decompose structure
    plan_dir = tmp_path / "memory-bank" / "back" / "security" / "plan" / "T-HUB-999-sec"
    (plan_dir / "md").mkdir(parents=True, exist_ok=True)
    (plan_dir / "yaml" / "steps").mkdir(parents=True, exist_ok=True)
    (plan_dir / "md" / "plan.md").write_text("# Plan\n")
    (plan_dir / "yaml" / "decompose-index.yaml").write_text(
        "schema: epic-decompose-index/v1\nplan_id: T-HUB-999-sec\nsteps:\n  - id: a01\n    file: a01-auth.yaml\n    status: pending\n"
    )
    (plan_dir / "yaml" / "steps" / "a01-auth.yaml").write_text("schema: epic-decompose/v1\nstep_id: a01\n")

    impl_dir = tmp_path / "memory-bank" / "back" / "security" / "implement" / "T-HUB-999-sec"
    impl_dir.mkdir(parents=True, exist_ok=True)
    (impl_dir / "a01-auth.yaml").write_text("schema: epic-security/v1\nstep_id: a01\n")

    prompt = _gate_protocol(cursor, tmp_path, "verify-security")
    assert "agent_type=verify-security" in prompt
    assert "Required sections in the verify-security spawn prompt:" in prompt
    assert "memory-bank/back/security/implement/T-HUB-999-sec/a01-auth.yaml" in prompt
    assert "memory-bank/back/security/plan/T-HUB-999-sec/yaml/steps/a01-auth.yaml" in prompt
