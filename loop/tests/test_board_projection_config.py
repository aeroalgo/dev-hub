from __future__ import annotations

from pathlib import Path
import pytest
import yaml

from loop.board_projection.errors import ProjectionConfigError, ProjectionError
from loop.board_projection.protocol import (
    BoardProjectionAdapter,
    EpicRef,
    ProjectionResult,
)
from loop.board_projection.config import (
    BoardProjectionConfig,
    Bitrix24Config,
    PlaneConfig,
    load_projection_config,
)
from loop.board_projection.registry import (
    get_adapter,
    register_adapter,
    unregister_adapter,
)


def test_projection_models_defined():
    # CP1: Models defined, Protocol runtime-checkable, dataclasses work
    epic = EpicRef(epic_id="T-HUB-108", title="Board Projection", phase="IMPLEMENT")
    assert epic.epic_id == "T-HUB-108"
    assert epic.phase == "IMPLEMENT"

    res = ProjectionResult(status="ok", external_id="123")
    assert res.status == "ok"
    assert res.external_id == "123"

    # Verify Protocol is runtime checkable
    class DummyAdapter:
        @property
        def provider_name(self) -> str:
            return "dummy"

        def ensure_card(self, epic: EpicRef) -> str:
            return "card_1"

        def move_card(self, external_id: str, phase: str) -> None:
            pass

    dummy = DummyAdapter()
    assert isinstance(dummy, BoardProjectionAdapter)

    # Models check
    b24 = Bitrix24Config(webhook_url="https://test.bitrix24.ru/rest/1/abc/", group_id=10, stage_map={"backlog": "1"})
    assert b24.group_id == 10
    plane = PlaneConfig(base_url="https://plane.example.com", api_key="secret", workspace_slug="ws", project_id="proj")
    assert plane.workspace_slug == "ws"


def test_missing_config_disabled(tmp_path: Path):
    # CP2: Missing config returns disabled with reason="missing_config"
    non_existent = tmp_path / ".loop" / "board-projection.yaml"
    cfg, disabled_reason = load_projection_config(config_path=non_existent)
    assert cfg is None or cfg.provider == "none"
    assert disabled_reason == "missing_config"


def test_unknown_provider_fail_closed(tmp_path: Path):
    # CP3: Unknown provider fail-closed raises ProjectionConfigError
    bad_config = tmp_path / "board-projection.yaml"
    bad_config.write_text(yaml.dump({"provider": "jira"}))
    with pytest.raises(ProjectionConfigError) as exc_info:
        load_projection_config(config_path=bad_config)
    assert "unknown provider" in str(exc_info.value).lower() or "jira" in str(exc_info.value).lower()


def test_incomplete_config_and_roles(tmp_path: Path):
    # CP4: Incomplete provider config -> disabled with incomplete_provider_config
    # and role check TM-010
    inc_plane = tmp_path / "plane-inc.yaml"
    inc_plane.write_text(yaml.dump({
        "provider": "plane",
        "providers": {
            "plane": {
                "base_url": "https://plane.example.com"
                # missing api_key, workspace_slug, project_id
            }
        }
    }))
    cfg, disabled_reason = load_projection_config(config_path=inc_plane)
    assert disabled_reason == "incomplete_provider_config"

    # Valid config with custom role_allowlist
    valid_cfg_file = tmp_path / "valid.yaml"
    valid_cfg_file.write_text(yaml.dump({
        "provider": "bitrix24",
        "role_allowlist": ["back", "front"],
        "providers": {
            "bitrix24": {
                "webhook_url": "https://test.bitrix24.ru/rest/1/abc/",
                "group_id": 5,
                "stage_map": {"backlog": "10"}
            }
        }
    }))
    cfg, disabled_reason = load_projection_config(config_path=valid_cfg_file)
    assert disabled_reason is None
    assert cfg is not None
    assert cfg.is_role_allowed("back") is True
    assert cfg.is_role_allowed("front") is True
    assert cfg.is_role_allowed("qa") is False

    # Default role_allowlist is ['back']
    default_role_file = tmp_path / "default_roles.yaml"
    default_role_file.write_text(yaml.dump({
        "provider": "none"
    }))
    cfg, _ = load_projection_config(config_path=default_role_file)
    assert cfg.is_role_allowed("back") is True
    assert cfg.is_role_allowed("front") is False


def test_invalid_yaml_raises_projection_config_error(tmp_path: Path):
    # FR-001: invalid YAML raises ProjectionConfigError
    bad_yaml = tmp_path / "broken.yaml"
    bad_yaml.write_text("invalid: yaml: [broken")
    with pytest.raises(ProjectionConfigError):
        load_projection_config(config_path=bad_yaml)


def test_adapter_registry():
    # Registry test: register, get, unregister
    class MockAdapter:
        def __init__(self, cfg):
            self.cfg = cfg

        @property
        def provider_name(self) -> str:
            return "mock"

        def ensure_card(self, epic: EpicRef) -> str:
            return "mock-1"

        def move_card(self, external_id: str, phase: str) -> None:
            pass

    register_adapter("mock", lambda cfg: MockAdapter(cfg))
    mock_cfg = BoardProjectionConfig(provider="mock")
    adapter = get_adapter(mock_cfg)
    assert adapter is not None
    assert adapter.provider_name == "mock"

    unregister_adapter("mock")
    with pytest.raises(ProjectionConfigError):
        get_adapter(mock_cfg)

    # Provider none returns None
    none_cfg = BoardProjectionConfig(provider="none")
    assert get_adapter(none_cfg) is None
