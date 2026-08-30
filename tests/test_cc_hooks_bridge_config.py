from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "dsh" / "patches" / "cc-hooks-bridge.yml"
PROFILES = sorted((ROOT / "dsh" / "profiles").glob("epic-*/cordis.patch.yml"))


@pytest.fixture(scope="module")
def bridge_config() -> dict:
    return yaml.load(BRIDGE.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)[0]


def test_bridge_fragment_has_plugin_id(bridge_config: dict) -> None:
    assert "dsh-hooks-claude-code" in bridge_config["id"]


def test_bridge_fragment_has_config_path(bridge_config: dict) -> None:
    assert "configPath" in bridge_config["config"]


def test_bridge_fragment_has_project_dir(bridge_config: dict) -> None:
    assert "projectDir" in bridge_config["config"]


def test_profiles_have_bridge_and_no_reserved_slot() -> None:
    assert PROFILES
    for profile in PROFILES:
        text = profile.read_text(encoding="utf-8")
        assert "cc-hooks-bridge" in text
        assert "reserved include slot" not in text
