from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / ".claude" / "hooks" / "agent_policy.py"
LIB_PATH = ROOT / ".claude" / "hooks" / "_lib.py"


def _load(path: Path, name: str):
    sys.path.insert(0, str(ROOT / ".claude" / "hooks"))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def policy():
    return _load(POLICY_PATH, "agent_policy_test")


def test_chat_and_loop_scopes_resolve_independently(policy) -> None:
    chat = policy.resolve_agent_policy(
        "writer",
        policy.AgentContext.CHAT,
        env={
            "PROJECT_AGENT_WRITER_MODEL_CHAT": "1",
            "PROJECT_AGENT_WRITER_MODEL_LOOP": "0",
        },
    )
    loop = policy.resolve_agent_policy(
        "writer",
        policy.AgentContext.LOOP,
        env={
            "PROJECT_AGENT_WRITER_MODEL_CHAT": "1",
            "PROJECT_AGENT_WRITER_MODEL_LOOP": "0",
        },
    )

    assert chat.enabled is True
    assert loop.enabled is False
    assert chat.context is policy.AgentContext.CHAT
    assert loop.context is policy.AgentContext.LOOP


def test_model_loop_selector_is_boolean_not_model(policy) -> None:
    result = policy.resolve_agent_policy(
        "verify",
        "loop",
        env={
            "PROJECT_AGENT_VERIFY_MODEL": "sonnet",
            "PROJECT_AGENT_VERIFY_MODEL_LOOP": "1",
            "PROJECT_AGENT_VERIFY_MODEL_CHAT": "0",
        },
    )

    assert result.enabled is True
    assert result.model == "sonnet"
    assert result.reason == policy.PolicyReason.EXPLICIT_SELECTOR


def test_absent_scope_uses_legacy_loop_true_chat_false(policy) -> None:
    assert policy.resolve_agent_policy("writer", "chat").enabled is False
    assert policy.resolve_agent_policy("writer", "loop").enabled is True


def test_process_env_beats_local_and_project_layers(policy) -> None:
    result = policy.resolve_agent_policy(
        "writer",
        "loop",
        env={"PROJECT_AGENT_WRITER_MODEL": "process-model"},
        project_env_local={"PROJECT_AGENT_WRITER_MODEL": "local-model"},
        project_env={"PROJECT_AGENT_WRITER_MODEL": "project-model"},
    )

    assert result.model == "process-model"
    assert result.source == "process"


def test_metadata_precedes_compatibility(policy) -> None:
    result = policy.resolve_agent_policy(
        "writer",
        "loop",
        metadata={"enabled_loop": "1", "model": "metadata-model"},
        compatibility={"enabled": False, "model": "compat-model"},
    )

    assert result.enabled is True
    assert result.model == "metadata-model"
    assert result.source == "metadata"


def test_inherit_is_valid_and_does_not_pin_model(policy) -> None:
    result = policy.resolve_agent_policy(
        "writer",
        "loop",
        env={"PROJECT_AGENT_WRITER_MODEL": "inherit"},
        metadata={"model": "metadata-model"},
    )

    assert result.model is None
    assert result.reason == policy.PolicyReason.INHERIT
    assert result.error is None


@pytest.mark.parametrize(
    "value",
    ["bad model", "claude;rm", "claude$(id)", "claude\nmodel", "x" * 129],
)
def test_invalid_model_fails_closed(policy, value: str) -> None:
    result = policy.resolve_agent_policy(
        "writer", "loop", env={"PROJECT_AGENT_WRITER_MODEL": value}
    )

    assert result.enabled is False
    assert result.model is None
    assert result.error == policy.PolicyErrorCode.MODEL_INVALID


def test_invalid_boolean_fails_closed_for_only_affected_context(policy) -> None:
    chat = policy.resolve_agent_policy(
        "writer",
        "chat",
        env={"PROJECT_AGENT_WRITER_MODEL_CHAT": "maybe"},
    )
    loop = policy.resolve_agent_policy(
        "writer",
        "loop",
        env={"PROJECT_AGENT_WRITER_MODEL_CHAT": "maybe"},
    )

    assert chat.enabled is False
    assert chat.error == policy.PolicyErrorCode.BOOLEAN_INVALID
    assert loop.enabled is True
    assert loop.error is None


def test_invalid_agent_and_context_are_typed_failures(policy) -> None:
    agent = policy.resolve_agent_policy("bad name!", "loop")
    context = policy.resolve_agent_policy("writer", "session")

    assert agent.error == policy.PolicyErrorCode.AGENT_INVALID
    assert context.error == policy.PolicyErrorCode.SCOPE_INVALID
    assert agent.enabled is False
    assert context.enabled is False


def test_model_alias_and_provider_id_validation(policy) -> None:
    alias = policy.resolve_agent_policy(
        "writer", "loop", env={"PROJECT_AGENT_WRITER_MODEL": "sonnet"}
    )
    provider = policy.resolve_agent_policy(
        "writer", "loop", env={"PROJECT_AGENT_WRITER_MODEL": "openai/gpt-4.1"}
    )

    assert alias.model == policy.MODEL_ALIASES["sonnet"]
    assert provider.model == "openai/gpt-4.1"


def test_compatibility_helpers_delegate_to_policy(tmp_path: Path, monkeypatch) -> None:
    lib = _load(LIB_PATH, "policy_lib_test")
    env_dir = tmp_path / ".claude"
    env_dir.mkdir()
    (env_dir / "project.env").write_text(
        "PROJECT_AGENT_EXPLORER_MODEL=openai/gpt-4.1\n"
        "PROJECT_AGENT_EXPLORER_MODEL_LOOP=0\n"
        "PROJECT_AGENT_EXPLORER_MODEL_CHAT=0\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("PROJECT_AGENT_EXPLORER_MODEL", raising=False)
    monkeypatch.delenv("PROJECT_AGENT_EXPLORER_MODEL_LOOP", raising=False)
    monkeypatch.delenv("PROJECT_AGENT_EXPLORER_MODEL_CHAT", raising=False)
    monkeypatch.setenv("EPIC_LOOP", "1")

    assert lib.agent_enabled("explorer", tmp_path) is False
    assert lib.agent_model_from_project_env("explorer", tmp_path) == "openai/gpt-4.1"
    assert "explorer" not in lib.active_overlay(tmp_path)
