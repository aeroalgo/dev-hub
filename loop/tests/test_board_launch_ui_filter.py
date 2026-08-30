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


def test_workspace_list_options_are_loaded_from_host() -> None:
    index_source = (PLUGIN_SRC / "index.ts").read_text(encoding="utf-8")
    adapter_source = (PLUGIN_SRC / "workspace-list.ts").read_text(encoding="utf-8")
    controls_source = (PLUGIN_SRC / "board-controls.tsx").read_text(encoding="utf-8")

    assert "workspace.list" in index_source
    assert "createWorkspaceListAdapter" in index_source
    assert "parseWorkspaceListResponse" in adapter_source
    assert "workspaceId" in adapter_source
    assert "title" in adapter_source
    assert 'value={ALL_WORKSPACES}' in controls_source
    assert "workspaceState" in controls_source
    assert "resolvedWorkspaceState.options" in controls_source


def test_workspace_list_invalid_response_is_explicit() -> None:
    adapter_source = (PLUGIN_SRC / "workspace-list.ts").read_text(encoding="utf-8")
    controls_source = (PLUGIN_SRC / "board-controls.tsx").read_text(encoding="utf-8")

    assert "WorkspaceListValidationError" in adapter_source
    assert "status: 'invalid'" in adapter_source
    assert "status: 'unavailable'" in adapter_source
    assert "data-workspace-error" in controls_source
    assert "resolvedWorkspaceState.error" in controls_source


def test_workspace_filter_remains_client_side_and_persistent() -> None:
    controls_source = (PLUGIN_SRC / "board-controls.tsx").read_text(encoding="utf-8")
    filter_source = (PLUGIN_SRC / "board-filter.ts").read_text(encoding="utf-8")

    assert "mb-bridge.workspaceFilter" in controls_source
    assert "filterCards(cards, workspaceFilter || null)" in controls_source
    assert "workspace_id" in filter_source
    assert "return cards.filter" in filter_source
    assert "ledger" not in controls_source.lower()
    assert "spawnHubBoard('sync'" in controls_source


def test_model_source_contract_reaches_host_ui() -> None:
    bridge_source = (PLUGIN_SRC / "python-bridge.ts").read_text(encoding="utf-8")
    controls_source = (PLUGIN_SRC / "board-controls.tsx").read_text(encoding="utf-8")

    assert "modelSource" in bridge_source
    assert "modelEnv" in bridge_source
    assert "setEffectiveModelSource" in controls_source
    assert "result.modelSource" in controls_source
    assert "data-model-source" in controls_source
    assert "env overrides" in controls_source


def test_workspace_list_without_host_does_not_mutate_board() -> None:
    adapter_source = (PLUGIN_SRC / "workspace-list.ts").read_text(encoding="utf-8")
    filter_source = (PLUGIN_SRC / "board-filter.ts").read_text(encoding="utf-8")

    assert "Host workspace.list capability is unavailable" in adapter_source
    assert "return cards.filter" in filter_source
    assert "cards.splice" not in filter_source
    assert "cards.sort" not in filter_source
    assert "spawnHubBoard" not in adapter_source
