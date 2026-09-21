from __future__ import annotations

from pathlib import Path

from loop.config import LoopSettings


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_settings_loads_root_env_and_project_override(
    tmp_path: Path, monkeypatch
) -> None:
    hub = tmp_path / "hub"
    project = tmp_path / "product"
    write(
        hub / ".env",
        "\n".join(
            (
                "EPIC_RUNTIME=codex",
                "LOOP_MODEL_IMPLEMENT=phase-model",
                'LOOP_STEP_MODELS={"S01":"step-model"}',
                "LOOP_MAX_STEPS=7",
            )
        ),
    )
    write(project / ".env", "LOOP_MAX_STEPS=11\n")

    monkeypatch.setenv("LOOP_MAX_STEPS", "13")
    settings = LoopSettings.load(hub_root=hub, project_root=project)

    assert settings.runtime == "codex"
    assert settings.max_steps == 13
    assert settings.model_for(phase="IMPLEMENT", step_id="s01").model == "step-model"


def test_model_precedence_is_cli_then_step_then_phase_then_default() -> None:
    settings = LoopSettings(
        model="default-model",
        step_models={"S01": "step-model"},
        implement_model="phase-model",
    )

    assert settings.model_for(phase="IMPLEMENT", step_id="s01", cli_model="cli").source == "cli"
    assert settings.model_for(phase="IMPLEMENT", step_id="s01").source == "step_env"
    assert settings.model_for(phase="IMPLEMENT", step_id="s02").source == "phase_env"
    assert settings.model_for(phase="QA", step_id="QA").source == "default_env"


def test_missing_model_is_fail_closed() -> None:
    selection = LoopSettings().model_for(phase="IMPLEMENT", step_id="s01")

    assert selection.model is None
    assert selection.source == "missing"
    assert selection.env_name == "PROJECT_LOOP_IMPLEMENT_MODEL"
