from __future__ import annotations

from pathlib import Path

from loop.board_launch.loop_argv import BridgeConfig, LoopArgvResult
from loop.board_launch.loop_run import ExecutionResult, FakeLoopRunner, loop_run
from loop.board_launch.metadata import LaunchCard
from loop.board_sync.card_model import CardKind


def _card(tmp_path: Path) -> LaunchCard:
    return LaunchCard(
        project_root=str(tmp_path),
        decompose_rel="memory-bank/back/plan/decompose-demo/index.yaml",
        step_id="s01",
        gate_phase=None,
        workspace_id="ws-1",
        card_kind=CardKind.STEP,
        raw={},
    )


def _argv() -> LoopArgvResult:
    return LoopArgvResult(
        argv=["/bin/loop", "/tmp/project", "--default"],
        env_extra={"EPIC_RUNTIME": "dsh"},
        model_source="default",
    )


def _config() -> BridgeConfig:
    return BridgeConfig(loop_bin="/bin/loop")


def test_fake_loop_success(tmp_path: Path) -> None:
    card = _card(tmp_path)
    argv_result = _argv()
    runner = FakeLoopRunner(exit_code=0)

    result = runner(card, argv_result, _config())

    assert isinstance(result, ExecutionResult)
    assert result.status == "succeeded"
    assert result.exit_code == 0
    assert runner.calls == [(card, argv_result, _config())]


def test_fake_loop_failure(tmp_path: Path) -> None:
    result = FakeLoopRunner(exit_code=1)(_card(tmp_path), _argv(), _config())

    assert result.status == "failed"
    assert result.exit_code == 1


def test_no_shell_true(tmp_path: Path, monkeypatch) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    class Process:
        returncode = 0

        def communicate(self, timeout: float):
            return "stdout", "stderr"

    def popen(argv, **kwargs):
        calls.append((argv, kwargs))
        return Process()

    monkeypatch.setenv("DEV_HUB", str(tmp_path / "hub"))
    monkeypatch.setattr("loop.board_launch.loop_run.subprocess.Popen", popen)

    result = loop_run(
        _card(tmp_path),
        _argv(),
        _config(),
        loop_bin_override=Path("/override/loop"),
    )

    argv, kwargs = calls[0]
    assert argv == ["/override/loop", "/tmp/project", "--default"]
    assert kwargs["cwd"] == str(tmp_path)
    assert kwargs["env"]["EPIC_RUNTIME"] == "dsh"
    assert kwargs.get("shell", False) is False
    assert result.status == "succeeded"


def test_lock_conflict(tmp_path: Path, monkeypatch) -> None:
    class Process:
        returncode = 1

        def communicate(self, timeout: float):
            return "", "another loop runner is already active\n"

    monkeypatch.setenv("DEV_HUB", str(tmp_path / "hub"))
    monkeypatch.setattr(
        "loop.board_launch.loop_run.subprocess.Popen",
        lambda *_args, **_kwargs: Process(),
    )

    result = loop_run(_card(tmp_path), _argv(), _config())

    assert result.status == "failed"
    assert result.diagnostic_code == "lock_conflict"


def test_log_path_in_result(tmp_path: Path, monkeypatch) -> None:
    class Process:
        returncode = 0

        def communicate(self, timeout: float):
            return "hello\n", "warning\n"

    monkeypatch.setenv("DEV_HUB", str(tmp_path / "hub"))
    monkeypatch.setattr(
        "loop.board_launch.loop_run.subprocess.Popen",
        lambda *_args, **_kwargs: Process(),
    )

    result = loop_run(_card(tmp_path), _argv(), _config())

    assert result.log_path is not None
    assert result.log_path.is_file()
    assert result.log_path.read_text(encoding="utf-8") == "hello\nwarning\n"


def test_project_root_in_argv(tmp_path: Path, monkeypatch) -> None:
    seen: list[list[str]] = []

    class Process:
        returncode = 0

        def communicate(self, timeout: float):
            return "", ""

    def popen(argv, **_kwargs):
        seen.append(argv)
        return Process()

    monkeypatch.setenv("DEV_HUB", str(tmp_path / "hub"))
    monkeypatch.setattr("loop.board_launch.loop_run.subprocess.Popen", popen)

    loop_run(
        _card(tmp_path),
        LoopArgvResult(["/bin/loop", str(tmp_path)], {}, "bare"),
        _config(),
    )

    assert seen[0][1] == str(tmp_path)
