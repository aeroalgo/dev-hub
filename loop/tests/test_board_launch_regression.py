from __future__ import annotations

from pathlib import Path

import pytest

from loop.board_launch import arm, loop_argv, loop_run, metadata, pipeline
from loop.board_sync import card_model, cli, client, diff, scan_gates, scan_mb, sync, workspaces

ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize(
    "module",
    [arm, loop_argv, loop_run, metadata, pipeline, card_model, cli, client, diff, scan_gates, scan_mb, sync, workspaces],
)
def test_board_launch_and_sync_modules_import(module: object) -> None:
    assert module.__name__.startswith("loop.board_")


def test_board_sync_card_model_remains_canonical() -> None:
    from loop.board_launch.metadata import CardKind as launch_card_kind

    assert launch_card_kind is card_model.CardKind
    assert card_model.stable_id(
        kind="step",
        ws_id="ws-1",
        role="back",
        epic_id="T-HUB-015",
        step_id="s10",
    ).startswith("mb-ws-1-back-t-hub-015-s10")


def test_required_s10_files_are_present() -> None:
    assert (ROOT / "dsh" / "README.md").is_file()
    assert (ROOT / "dsh" / "scripts" / "install-mb-bridge.sh").is_file()
    assert (ROOT / "dsh" / "plugins" / "mb-bridge" / "package.json").is_file()
