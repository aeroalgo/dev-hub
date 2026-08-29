from __future__ import annotations

from pathlib import Path

import pytest

from loop.board_launch.arm import ArmResult, StepMismatchError
from loop.board_launch.loop_argv import BridgeConfig, LoopArgvResult
from loop.board_launch.loop_run import ExecutionResult, FakeLoopRunner
from loop.board_launch.metadata import LaunchCard
from loop.board_launch.pipeline import PipelineResult, arm_loop_from_card
from loop.board_sync.card_model import CardKind


def _card(tmp_path: Path, *, workspace_id: str | None = "ws-1") -> LaunchCard:
    return LaunchCard(
        project_root=str(tmp_path),
        decompose_rel="memory-bank/back/plan/decompose-demo/index.yaml",
        step_id="s01",
        gate_phase=None,
        workspace_id=workspace_id,
        card_kind=CardKind.STEP,
        raw={},
    )


def _arm(card: LaunchCard) -> ArmResult:
    return ArmResult(step_id=card.step_id or "", armed_epic="T-DEMO")


def test_arm_loop_success(tmp_path: Path) -> None:
    runner = FakeLoopRunner(0)
    result = arm_loop_from_card(
        _card(tmp_path),
        BridgeConfig(loop_bin="/bin/loop"),
        loop_runner=runner,
        arm_fn=_arm,
    )

    assert isinstance(result, PipelineResult)
    assert result.status == "succeeded"
    assert result.arm == _arm(_card(tmp_path))
    assert result.loop is not None
    assert result.loop.exit_code == 0
    assert result.loop_invoked is True


def test_arm_fails_loop_not_called(tmp_path: Path) -> None:
    runner = FakeLoopRunner(0)

    def fail_arm(_card: LaunchCard) -> ArmResult:
        raise StepMismatchError("wrong step")

    result = arm_loop_from_card(
        _card(tmp_path),
        BridgeConfig(loop_bin="/bin/loop"),
        loop_runner=runner,
        arm_fn=fail_arm,
    )

    assert result.status == "arm_failed"
    assert result.loop_invoked is False
    assert result.arm is None
    assert result.loop is None
    assert runner.calls == []


def test_loop_fails_pipeline_status_failed(tmp_path: Path) -> None:
    result = arm_loop_from_card(
        _card(tmp_path),
        BridgeConfig(loop_bin="/bin/loop"),
        loop_runner=FakeLoopRunner(1),
        arm_fn=_arm,
    )

    assert result.status == "failed"
    assert result.loop is not None
    assert result.loop.exit_code == 1


def test_sync_after_loop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def run(argv: list[str], **_kwargs: object):
        calls.append(argv)
        return type("Process", (), {"returncode": 1, "stdout": "", "stderr": "sync unavailable"})()

    monkeypatch.setattr("loop.board_launch.pipeline.subprocess.run", run)
    result = arm_loop_from_card(
        _card(tmp_path),
        BridgeConfig(loop_bin="/bin/loop", sync_after_loop=True),
        loop_runner=FakeLoopRunner(1),
        arm_fn=_arm,
    )

    assert calls == [["hub-board", "sync", "--workspace-id", "ws-1"]]
    assert result.status == "failed"
    assert result.sync_warning is not None
    assert "sync unavailable" in result.sync_warning


def test_no_sync_after_loop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fail_if_called(*_args: object, **_kwargs: object) -> None:
        pytest.fail("sync must not be invoked")

    monkeypatch.setattr("loop.board_launch.pipeline.subprocess.run", fail_if_called)
    result = arm_loop_from_card(
        _card(tmp_path),
        BridgeConfig(loop_bin="/bin/loop", sync_after_loop=False),
        loop_runner=FakeLoopRunner(0),
        arm_fn=_arm,
    )

    assert result.status == "succeeded"
    assert result.sync_warning is None


def test_sync_failure_is_warning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "loop.board_launch.pipeline.subprocess.run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("not found")),
    )

    result = arm_loop_from_card(
        _card(tmp_path),
        BridgeConfig(loop_bin="/bin/loop", sync_after_loop=True),
        loop_runner=FakeLoopRunner(0),
        arm_fn=_arm,
    )

    assert result.status == "succeeded"
    assert result.sync_warning is not None
    assert "not found" in result.sync_warning
