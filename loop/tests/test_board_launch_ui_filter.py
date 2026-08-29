from pathlib import Path


PLUGIN_SRC = Path(__file__).parents[2] / "dsh" / "plugins" / "mb-bridge" / "src"


def test_filter_cards_contract_is_typescript_only() -> None:
    source = (PLUGIN_SRC / "board-filter.ts").read_text(encoding="utf-8")

    assert "export function filterCards" in source
    assert "workspace_id" in source
    assert ".filter(" in source


def test_board_controls_expose_persistent_whitelisted_controls() -> None:
    source = (PLUGIN_SRC / "board-controls.tsx").read_text(encoding="utf-8")

    assert "mb-bridge.workspaceFilter" in source
    assert "mb-bridge.runtime" in source
    assert "mb-bridge.modelPreset" in source
    assert "config.modelPresets" in source
    assert "spawnHubBoard('sync'" in source or 'spawnHubBoard("sync"' in source
    assert "workspace-id" in source
    assert 'input type="text"' not in source


def test_bridge_supports_sync_workspace_argument() -> None:
    source = (PLUGIN_SRC / "python-bridge.ts").read_text(encoding="utf-8")

    assert "'sync'" in source or '"sync"' in source
    assert "workspaceId" in source
    assert "EPIC_RUNTIME" in source
