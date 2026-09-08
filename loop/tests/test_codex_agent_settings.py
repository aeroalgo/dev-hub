from pathlib import Path

import pytest

from loop.runtime_materializers.codex_agent_settings import (
    CodexAgentSettingsError,
    load_codex_agent_settings,
    resolve_codex_agent_settings,
)


def test_load_codex_agent_settings_resolves_native_and_workflow_layers(tmp_path: Path) -> None:
    config_dir = tmp_path / "codex"
    config_dir.mkdir()
    (config_dir / "agents.config.toml").write_text(
        """schema_version = \"codex-agent-settings/v1\"

[defaults]
model = \"cx/default\"
model_reasoning_effort = \"high\"
max_concurrent_threads_per_session = 4
max_depth = 1

[agents.\"gate-repair\"]
model_reasoning_effort = \"medium\"
sandbox_mode = \"workspace-write\"
workflow_mode = \"repair\"
max_turns = 16
requires_model = true
allow_worktree = false
verdict = \"none\"
""",
        encoding="utf-8",
    )

    native, workflow = resolve_codex_agent_settings(tmp_path, "gate-repair")

    assert native == {
        "model": "cx/default",
        "model_reasoning_effort": "medium",
        "sandbox_mode": "workspace-write",
    }
    assert workflow["workflow_mode"] == "repair"
    assert workflow["max_turns"] == 16


def test_codex_agent_settings_fail_closed_on_unknown_field(tmp_path: Path) -> None:
    config_dir = tmp_path / "codex"
    config_dir.mkdir()
    (config_dir / "agents.config.toml").write_text(
        """schema_version = \"codex-agent-settings/v1\"
[agents.explorer]
made_up_codex_flag = true
""",
        encoding="utf-8",
    )

    with pytest.raises(CodexAgentSettingsError, match="unsupported"):
        load_codex_agent_settings(tmp_path)
