from __future__ import annotations

from pathlib import Path

import pytest

from loop.board_launch.loop_argv import (
    BridgeConfig,
    LoopArgvResult,
    PresetEntry,
    PresetError,
    build_loop_argv,
)


@pytest.fixture
def config() -> BridgeConfig:
    return BridgeConfig(
        loop_bin=Path("/bin/loop"),
        model_presets=[PresetEntry("gpt", "GPT", ["--model", "gpt-5"])],
        default_loop_args=["--default"],
        default_runtime="host",
        allow_roadmap_advance=False,
        sync_after_loop=False,
    )


def test_preset_wins_when_env_unset(
    tmp_path: Path, config: BridgeConfig
) -> None:
    result = build_loop_argv(tmp_path, "IMPLEMENT", config, preset_id="gpt")

    assert isinstance(result, LoopArgvResult)
    assert result.argv == ["/bin/loop", str(tmp_path), "--model", "gpt-5"]
    assert result.model_source == "preset"


def test_env_wins_over_preset(tmp_path: Path, config: BridgeConfig) -> None:
    env_dir = tmp_path / ".claude"
    env_dir.mkdir()
    (env_dir / "project.env").write_text(
        "PROJECT_LOOP_IMPLEMENT_MODEL=agy/claude-sonnet-4-6\n",
        encoding="utf-8",
    )

    result = build_loop_argv(tmp_path, "IMPLEMENT", config, preset_id="gpt")

    assert result.argv == ["/bin/loop", str(tmp_path)]
    assert result.model_source == "env"


def test_default_loop_args_fallback(tmp_path: Path, config: BridgeConfig) -> None:
    result = build_loop_argv(tmp_path, "IMPLEMENT", config)

    assert result.argv == ["/bin/loop", str(tmp_path), "--default"]
    assert result.model_source == "default"


def test_bare_argv_fallback(tmp_path: Path) -> None:
    config = BridgeConfig(
        loop_bin="/bin/loop",
        model_presets=[],
        default_loop_args=[],
        default_runtime="host",
        allow_roadmap_advance=False,
        sync_after_loop=False,
    )

    result = build_loop_argv(tmp_path, "IMPLEMENT", config)

    assert result.argv == ["/bin/loop", str(tmp_path)]
    assert result.model_source == "bare"


def test_preset_whitelist_validation(tmp_path: Path, config: BridgeConfig) -> None:
    bad_entry = PresetEntry("bad", "Bad", ["--model", "safe-value"])
    bad_entry.args.append("bad value")
    bad_config = BridgeConfig(
        loop_bin=config.loop_bin,
        model_presets=[bad_entry],
        default_loop_args=[],
        default_runtime=config.default_runtime,
        allow_roadmap_advance=False,
        sync_after_loop=False,
    )

    with pytest.raises(PresetError, match="invalid token"):
        build_loop_argv(tmp_path, "IMPLEMENT", bad_config, preset_id="bad")


def test_unknown_preset_id_raises(tmp_path: Path, config: BridgeConfig) -> None:
    with pytest.raises(PresetError, match="unknown preset"):
        build_loop_argv(tmp_path, "IMPLEMENT", config, preset_id="unknown")


def test_runtime_env_override(tmp_path: Path, config: BridgeConfig) -> None:
    result = build_loop_argv(tmp_path, "IMPLEMENT", config, runtime="dsh")

    assert result.env_extra == {"EPIC_RUNTIME": "dsh"}
    assert result.argv == ["/bin/loop", str(tmp_path), "--default"]


def test_task_mode_not_read(tmp_path: Path, config: BridgeConfig) -> None:
    assert not hasattr(config, "task_mode")

    result = build_loop_argv(tmp_path, "IMPLEMENT", config)

    assert result.model_source == "default"
    assert result.argv[-1] == "--default"


def test_max_8_presets() -> None:
    with pytest.raises(ValueError, match="at most 8"):
        BridgeConfig(
            loop_bin="/bin/loop",
            model_presets=[PresetEntry(str(i), str(i), []) for i in range(9)],
            default_loop_args=[],
            default_runtime="host",
            allow_roadmap_advance=False,
            sync_after_loop=False,
        )


def test_model_source_diagnostic(tmp_path: Path, config: BridgeConfig) -> None:
    assert build_loop_argv(tmp_path, "IMPLEMENT", config).model_source == "default"
    assert (
        build_loop_argv(tmp_path, "IMPLEMENT", config, preset_id="gpt").model_source
        == "preset"
    )


def test_empty_env_value_does_not_override(tmp_path: Path, config: BridgeConfig) -> None:
    env_dir = tmp_path / ".claude"
    env_dir.mkdir()
    (env_dir / "project.env").write_text(
        "PROJECT_LOOP_IMPLEMENT_MODEL=\n",
        encoding="utf-8",
    )

    result = build_loop_argv(tmp_path, "IMPLEMENT", config, preset_id="gpt")

    assert result.model_source == "preset"
