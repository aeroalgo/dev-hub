from __future__ import annotations

from pathlib import Path

import pytest

from loop.board_launch.bridge import (
    MB_STOCK_RUN_ERROR,
    StockRunDeniedError,
    build_hub_board_argv,
    intercept_card_run,
    load_bridge_config,
)
from loop.board_launch.loop_argv import BridgeConfig


PLUGIN_ROOT = Path(__file__).parents[2] / "dsh" / "plugins" / "mb-bridge"


def test_live_stock_run_mount_is_wired() -> None:
    source = (PLUGIN_ROOT / "src" / "index.ts").read_text(encoding="utf-8")

    assert "createStockRunAdapter" in source
    assert "STOCK_RUN_SLOT" in source
    assert "ctx.inject?.(STOCK_RUN_SLOT, createStockRunAdapter(config))" in source
    assert "task-board.stock-run-prompt" not in source


def test_python_bridge_fixed_argv() -> None:
    source = (PLUGIN_ROOT / "src" / "python-bridge.ts").read_text(encoding="utf-8")

    assert build_hub_board_argv("arm-loop", "mb-demo") == [
        "hub-board",
        "arm-loop",
        "--task-id",
        "mb-demo",
    ]
    assert "spawn(" in source
    assert "shell: true" not in source
    assert "shell=True" not in source


def test_intercept_mb_vs_non_mb() -> None:
    calls: list[str] = []

    def stock(task: dict[str, object]) -> str:
        calls.append(f"stock:{task['id']}")
        return "stock"

    def bridge(task: dict[str, object]) -> str:
        calls.append(f"bridge:{task['id']}")
        return "loop"

    assert intercept_card_run({"id": "mb-demo"}, stock, bridge) == "loop"
    assert intercept_card_run({"id": "task-demo"}, stock, bridge) == "stock"
    assert calls == ["bridge:mb-demo", "stock:task-demo"]


def test_stock_run_denied_mb() -> None:
    with pytest.raises(StockRunDeniedError, match=MB_STOCK_RUN_ERROR):
        intercept_card_run({"id": "mb-demo"}, lambda _task: "stock")


def test_non_mb_passthrough() -> None:
    marker = object()

    assert intercept_card_run({"id": "task-demo"}, lambda _task: marker) is marker


def test_config_load() -> None:
    config = load_bridge_config(
        {
            "mb-bridge": {
                "enabled": True,
                "devHub": "/srv/dev-hub",
                "loopBin": "bin/loop",
                "syncAfterLoop": False,
                "allowRoadmapAdvance": True,
                "defaultRuntime": "dsh",
                "defaultLoopArgs": ["gpt"],
            }
        }
    )

    assert isinstance(config, BridgeConfig)
    assert config.loop_bin == Path("/srv/dev-hub/bin/loop")
    assert config.default_runtime == "dsh"
    assert config.default_loop_args == ["gpt"]
    assert config.sync_after_loop is False
    assert config.allow_roadmap_advance is True


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({"mb-bridge": {"enabled": "yes"}}, "enabled must be a boolean"),
        ({"mb-bridge": {"allowRoadmapAdvance": "yes"}}, "allowRoadmapAdvance must be a boolean"),
        ({"mb-bridge": {"syncAfterLoop": "yes"}}, "syncAfterLoop must be a boolean"),
    ],
)
def test_config_load_rejects_ambiguous_booleans(
    raw: dict[str, object], message: str
) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        load_bridge_config(raw)


def test_config_load_disabled_fails_closed() -> None:
    with pytest.raises(ValueError, match="mb-bridge is disabled"):
        load_bridge_config({"mb-bridge": {"enabled": False}})


def test_stub_removed() -> None:
    board_sync = Path(__file__).parents[1] / "board_sync"
    assert not any(
        "T-HUB-015 later" in path.read_text(encoding="utf-8", errors="ignore")
        for path in board_sync.rglob("*")
        if path.is_file()
    )


def test_bridge_action_argv_rejects_unsafe_values() -> None:
    with pytest.raises(ValueError):
        build_hub_board_argv("arm-loop", "mb demo")
    with pytest.raises(ValueError):
        build_hub_board_argv("sh -c rm", "mb-demo")
