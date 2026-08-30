from __future__ import annotations

from pathlib import Path

import yaml

from loop.board_launch.arm import ArmResult
from loop.board_launch.loop_argv import LoopArgvResult
from loop.board_launch.loop_run import ExecutionResult, FakeLoopRunner, LoopRunError
from loop.board_sync.cli import main
from loop.board_sync.client import FakeClient
from loop.board_sync.diff import BoardTask


def _task(project_root: Path) -> BoardTask:
    metadata = {
        "schema": "mb-board-card/v1",
        "card_kind": "step",
        "project_root": str(project_root),
        "workspace_id": "ws-1",
        "role": "back",
        "epic_id": "T-DEMO",
        "step_id": "s01",
        "decompose_rel": "memory-bank/back/plan/decompose-demo/index.yaml",
        "phase": "IMPLEMENT",
        "sync_generation": 1,
    }
    return BoardTask(
        id="mb-demo",
        title="demo",
        description=yaml.safe_dump(metadata, sort_keys=False),
        prompt="BACK IMPLEMENT",
        workspace_id="ws-1",
    )


def _client(tmp_path: Path) -> FakeClient:
    return FakeClient([_task(tmp_path / "project")])


def test_subcommand_help(capsys) -> None:
    for command in ("arm", "loop", "arm-loop"):
        assert main([command, "--help"]) == 0
        assert command in capsys.readouterr().out


def test_dry_run_no_spawn(tmp_path: Path, monkeypatch, capsys) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    monkeypatch.setenv("DEV_HUB", str(hub))
    runner = FakeLoopRunner()
    monkeypatch.setattr("loop.board_sync.cli.loop_run", runner)

    result = main(
        ["arm-loop", "--task-id", "mb-demo", "--dry-run"],
        client=_client(tmp_path),
    )

    assert result == 0
    output = capsys.readouterr().out
    assert "argv=" in output
    assert runner.calls == []


def test_dev_hub_missing(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.delenv("DEV_HUB", raising=False)

    result = main(["arm", "--task-id", "mb-demo"], client=_client(tmp_path))

    assert result == 1
    assert "DEV_HUB" in capsys.readouterr().err


def test_runtime_flag(tmp_path: Path, monkeypatch) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    monkeypatch.setenv("DEV_HUB", str(hub))
    seen: list[LoopArgvResult] = []

    def fake_pipeline(card, config, *, preset_id=None, runtime=None):
        del card, config, preset_id
        seen.append(
            LoopArgvResult(
                argv=["loop"],
                env_extra={"EPIC_RUNTIME": runtime} if runtime == "dsh" else {},
                model_source="bare",
            )
        )
        return type("Result", (), {"status": "succeeded", "loop_invoked": True, "loop": None, "sync_warning": None})()

    monkeypatch.setattr("loop.board_sync.cli.arm_loop_from_card", fake_pipeline)

    assert main(
        ["arm-loop", "--task-id", "mb-demo", "--runtime", "dsh"],
        client=_client(tmp_path),
    ) == 0
    assert seen[0].env_extra == {"EPIC_RUNTIME": "dsh"}


def test_loop_result_prints_model_source_and_env_key(tmp_path: Path, monkeypatch, capsys) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    monkeypatch.setenv("DEV_HUB", str(hub))
    result = ExecutionResult(
        "succeeded",
        0,
        model_source="env",
        model_env="PROJECT_LOOP_IMPLEMENT_MODEL",
    )
    monkeypatch.setattr("loop.board_sync.cli.loop_run", lambda *_args: result)

    assert main(["loop", "--task-id", "mb-demo"], client=_client(tmp_path)) == 0

    output = capsys.readouterr().out
    assert "model_source=env" in output
    assert "model_env=PROJECT_LOOP_IMPLEMENT_MODEL" in output


def test_loop_records_success_on_board(tmp_path: Path, monkeypatch) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    monkeypatch.setenv("DEV_HUB", str(hub))
    result = ExecutionResult("succeeded", 0, Path("/tmp/" + "a" * 1200))
    monkeypatch.setattr("loop.board_sync.cli.loop_run", lambda *_args: result)
    client = _client(tmp_path)

    assert main(["loop", "--task-id", "mb-demo"], client=client) == 0

    assert len(client.execution_records) == 1
    record = client.execution_records[0]
    assert record.task_id == "mb-demo"
    assert record.status == "succeeded"
    assert record.exit_code == 0
    assert len(record.log_path or "") == 1000


def test_loop_records_failure_diagnostic_without_retry(tmp_path: Path, monkeypatch) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    monkeypatch.setenv("DEV_HUB", str(hub))
    calls: list[str] = []
    error = LoopRunError(
        "timed out",
        diagnostic_code="timeout",
        log_path=Path("/tmp/" + "t" * 1200),
    )

    def run(*_args):
        calls.append("loop")
        raise error

    monkeypatch.setattr("loop.board_sync.cli.loop_run", run)
    client = _client(tmp_path)

    assert main(["loop", "--task-id", "mb-demo"], client=client) == 1

    assert calls == ["loop"]
    assert client.execution_records[0].diagnostic_code == "timeout"
    assert client.execution_records[0].exit_code is None


def test_loop_records_spawn_error_result(tmp_path: Path, monkeypatch) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    monkeypatch.setenv("DEV_HUB", str(hub))
    monkeypatch.setattr(
        "loop.board_sync.cli.loop_run",
        lambda *_args: (_ for _ in ()).throw(LoopRunError("spawn", diagnostic_code="spawn_error")),
    )
    client = _client(tmp_path)

    assert main(["loop", "--task-id", "mb-demo"], client=client) == 1

    record = client.execution_records[0]
    assert record.status == "failed"
    assert record.diagnostic_code == "spawn_error"


def test_loop_records_only_once_without_arm_or_retry(tmp_path: Path, monkeypatch) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    monkeypatch.setenv("DEV_HUB", str(hub))
    calls: list[str] = []

    def run(*_args):
        calls.append("loop")
        return ExecutionResult("failed", 7, None, "loop_error")

    monkeypatch.setattr("loop.board_sync.cli.loop_run", run)
    monkeypatch.setattr("loop.board_sync.cli.arm_from_card", lambda *_args: calls.append("arm"))
    client = _client(tmp_path)

    assert main(["loop", "--task-id", "mb-demo"], client=client) == 1

    assert calls == ["loop"]
    assert len(client.execution_records) == 1


def test_loop_args_flag(tmp_path: Path, monkeypatch) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    monkeypatch.setenv("DEV_HUB", str(hub))
    captured: dict[str, object] = {}

    def fake_build(project_root, phase, config, *, preset_id=None, runtime=None):
        captured.update(project_root=project_root, phase=phase, preset_id=preset_id, runtime=runtime)
        return LoopArgvResult(["loop", str(project_root), "gpt"], {}, "preset")

    monkeypatch.setattr("loop.board_sync.cli.build_loop_argv", fake_build)
    monkeypatch.setattr(
        "loop.board_sync.cli.loop_run",
        lambda *_args: ExecutionResult("succeeded", 0),
    )

    assert main(
        ["loop", "--task-id", "mb-demo", "--loop-args", "gpt"],
        client=_client(tmp_path),
    ) == 0
    assert captured["preset_id"] == "gpt"


def test_arm_subcommand_calls_arm_from_card(tmp_path: Path, monkeypatch) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    monkeypatch.setenv("DEV_HUB", str(hub))
    calls: list[str] = []

    def fake_arm(card, *, config):
        calls.append(card.step_id or "")
        assert config.allow_roadmap_advance is False
        return ArmResult("s01", "T-DEMO")

    monkeypatch.setattr("loop.board_sync.cli.arm_from_card", fake_arm)

    assert main(["arm", "--task-id", "mb-demo"], client=_client(tmp_path)) == 0
    assert calls == ["s01"]


def test_arm_loop_subcommand_calls_pipeline(tmp_path: Path, monkeypatch) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    monkeypatch.setenv("DEV_HUB", str(hub))
    calls: list[str] = []

    def fake_pipeline(card, config, *, preset_id=None, runtime=None):
        calls.append(card.step_id or "")
        return type("Result", (), {"status": "succeeded", "loop_invoked": True, "loop": None, "sync_warning": None})()

    monkeypatch.setattr("loop.board_sync.cli.arm_loop_from_card", fake_pipeline)

    assert main(["arm-loop", "--task-id", "mb-demo"], client=_client(tmp_path)) == 0
    assert calls == ["s01"]
