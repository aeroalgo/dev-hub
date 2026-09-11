"""Tests for loop.runner CLI argument parsing, environment loading, and preflight checks."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from loop.runner.cli import (
    CliArgs,
    CliParseError,
    USAGE_TEXT,
    is_epic_spec,
    main,
    parse_cli,
)
from loop.runner.config import (
    ConfigResolutionError,
    load_project_environment,
    resolve_hub_root,
    resolve_project_root,
    resolve_runner_config,
    resolve_state_dir,
    run_preflight_checks,
)


class TestIsEpicSpec:
    @pytest.mark.parametrize(
        ("arg", "expected"),
        [
            ("T-HUB-027", True),
            ("T-001", True),
            ("plan-T-HUB-027-back-plan.md", True),
            ("decompose-v1-portal", True),
            ("memory-bank/back/plan/decompose-s01.yaml", True),
            ("memory-bank/front/plan/plan-main.md", True),
            ("memory-bank/back/plan/decompose-v1/index.md", True),
            ("foo/decompose-bar", True),
            ("foo/plan-bar", True),
            ("gpt", False),
            ("claude-3-5-sonnet", False),
            ("implement", False),
            ("--epic", False),
            ("", False),
        ],
    )
    def test_is_epic_spec_matching(self, arg: str, expected: bool) -> None:
        assert is_epic_spec(arg) is expected


class TestCliParsing:
    def test_default_empty_args(self) -> None:
        args = parse_cli([])
        assert args.command == "run"
        assert args.model is None
        assert args.epic_spec is None
        assert args.mode is None
        assert args.headless is True
        assert args.interactive is False
        assert args.verbose is False

    def test_help_flags(self) -> None:
        assert parse_cli(["-h"]).command == "help"
        assert parse_cli(["--help"]).command == "help"
        assert parse_cli(["help"]).command == "help"

    def test_status_flag_and_command(self) -> None:
        assert parse_cli(["--status"]).command == "status"
        assert parse_cli(["status"]).command == "status"

    def test_doctor_and_dashboard_commands(self) -> None:
        assert parse_cli(["doctor"]).command == "doctor"
        assert parse_cli(["dashboard"]).command == "dashboard"

    def test_dag_generate(self) -> None:
        args = parse_cli(["--dag-generate", "pipeline-1"])
        assert args.command == "dag-generate"
        assert args.dag_pipeline == "pipeline-1"

        args2 = parse_cli(["dag-generate", "pipeline-2"])
        assert args2.command == "dag-generate"
        assert args2.dag_pipeline == "pipeline-2"

        with pytest.raises(CliParseError, match="missing value for --dag-generate"):
            parse_cli(["--dag-generate"])

    def test_gap_fanout(self) -> None:
        args1 = parse_cli(["--gap-fanout"])
        assert args1.command == "gap-fanout"

        args2 = parse_cli(["--phase", "GAP_FANOUT"])
        assert args2.command == "gap-fanout"

        with pytest.raises(CliParseError, match="missing value for --phase"):
            parse_cli(["--phase"])

        with pytest.raises(CliParseError, match="unsupported phase"):
            parse_cli(["--phase", "INVALID_PHASE"])

    def test_positional_model_and_project(self, tmp_path: Path) -> None:
        proj = tmp_path / "my-project"
        proj.mkdir()
        (proj / "memory-bank").mkdir()

        args = parse_cli([str(proj), "gpt"])
        assert args.project_dir == str(proj)
        assert args.model == "gpt"
        assert args.epic_spec is None
        assert args.mode is None

    def test_positional_epic_spec_and_model(self) -> None:
        args = parse_cli(["T-HUB-027", "gpt"])
        assert args.epic_spec == "T-HUB-027"
        assert args.model == "gpt"
        assert args.mode is None

        # Reversed order: model first, then epic spec
        args2 = parse_cli(["gpt", "plan-T-HUB-027.md"])
        assert args2.model == "gpt"
        assert args2.epic_spec == "plan-T-HUB-027.md"

    def test_positional_mode_implement(self) -> None:
        args = parse_cli(["decompose-v1-portal", "gpt", "implement"])
        assert args.epic_spec == "decompose-v1-portal"
        assert args.model == "gpt"
        assert args.mode == "implement"

    def test_mode_implement_requires_epic_spec(self) -> None:
        with pytest.raises(CliParseError, match="requires an EPIC spec"):
            parse_cli(["gpt", "implement"])

    def test_multiple_epic_specs_fails(self) -> None:
        with pytest.raises(CliParseError, match="multiple epic specs"):
            parse_cli(["T-HUB-001", "T-HUB-002", "gpt"])

    def test_unexpected_positional_fails(self) -> None:
        with pytest.raises(CliParseError, match="unexpected positional argument"):
            parse_cli(["T-HUB-001", "gpt", "unknown_mode"])

    def test_flags_epic_and_model(self) -> None:
        args = parse_cli(["--epic", "T-HUB-050", "-m", "claude-3-7-sonnet"])
        assert args.epic_id == "T-HUB-050"
        assert args.model == "claude-3-7-sonnet"

        with pytest.raises(CliParseError, match="missing value for --epic"):
            parse_cli(["--epic"])

        with pytest.raises(CliParseError, match="missing value for -m"):
            parse_cli(["-m"])

    def test_permission_mode_and_interactive_flags(self) -> None:
        args = parse_cli(["--permission-mode", "ask", "--interactive", "--verbose"])
        assert args.permission_mode == "ask"
        assert args.interactive is True
        assert args.headless is False
        assert args.verbose is True

        args2 = parse_cli(["--headless"])
        assert args2.headless is True
        assert args2.interactive is False

        with pytest.raises(CliParseError, match="missing value for --permission-mode"):
            parse_cli(["--permission-mode"])

    def test_passthrough_extra_args(self) -> None:
        args = parse_cli(["gpt", "--", "--dangerously-skip-permissions", "--verbose"])
        assert args.model == "gpt"
        assert args.extra_args == ("--dangerously-skip-permissions", "--verbose")

    def test_unknown_flag_fails(self) -> None:
        with pytest.raises(CliParseError, match="unknown option: --bogus"):
            parse_cli(["--bogus"])


class TestPathAndConfigResolution:
    def test_resolve_hub_root(self) -> None:
        hub = resolve_hub_root()
        assert hub.is_dir()
        assert (hub / "loop").is_dir()
        assert (hub / "harness").is_dir()

    def test_resolve_project_root_success_and_failure(self, tmp_path: Path) -> None:
        valid_proj = tmp_path / "valid_proj"
        valid_proj.mkdir()
        (valid_proj / "memory-bank").mkdir()

        resolved = resolve_project_root(valid_proj)
        assert resolved == valid_proj.resolve()

        invalid_proj = tmp_path / "no_mb"
        invalid_proj.mkdir()
        with pytest.raises(ConfigResolutionError, match="PROJECT_ROOT required"):
            resolve_project_root(invalid_proj)

    def test_resolve_state_dir(self, tmp_path: Path) -> None:
        hub = tmp_path / "hub"
        proj = tmp_path / "my_app"
        state = resolve_state_dir(proj, hub)
        assert state == hub / "runtime" / "my_app" / "epic"

    def test_load_project_environment(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        env_backup = dict(os.environ)
        try:
            hub = tmp_path / "hub"
            hub.mkdir()
            (hub / ".claude").mkdir()
            (hub / ".claude" / "project.env").write_text("FOO_HUB=bar_hub\n", encoding="utf-8")

            proj = tmp_path / "proj"
            proj.mkdir()
            (proj / "memory-bank").mkdir()
            (proj / ".claude").mkdir()
            (proj / ".claude" / "project.env").write_text("FOO_PROJ=bar_proj\n", encoding="utf-8")

            applied = load_project_environment(proj, hub, runtime_name="claude")
            assert os.environ["HUB_ROOT"] == str(hub)
            assert os.environ["PROJECT_ROOT"] == str(proj)
            assert os.environ["EPIC_LOOP"] == "1"
            assert os.environ["CLAUDE_PROJECT_DIR"] == str(hub)
            assert "DSH_HOOKS_BRIDGE" not in os.environ
            assert os.environ.get("FOO_HUB") == "bar_hub"
            assert os.environ.get("FOO_PROJ") == "bar_proj"
        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_load_project_environment_dsh_bridge(self, tmp_path: Path) -> None:
        env_backup = dict(os.environ)
        try:
            hub = tmp_path / "hub"
            hub.mkdir()
            proj = tmp_path / "proj"
            proj.mkdir()

            load_project_environment(proj, hub, runtime_name="dsh")
            assert os.environ["DSH_HOOKS_BRIDGE"] == "1"
            assert os.environ["CLAUDE_PROJECT_DIR"] == str(proj)
        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_resolve_runner_config_precedence(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        hub = resolve_hub_root()
        proj = tmp_path / "test_proj"
        proj.mkdir()
        (proj / "memory-bank").mkdir()

        monkeypatch.setenv("EPIC_SESSION_TIMEOUT_SEC", "400")
        monkeypatch.setenv("EPIC_CLAUDE_ARGS", "--foo bar")

        config = resolve_runner_config(
            proj,
            hub_dir=hub,
            cli_model="claude-3-7",
            permission_mode="ask",
            extra_args=["--extra"],
            load_env=False,
        )

        assert config.project_root == proj.resolve()
        assert config.hub_root == hub.resolve()
        assert config.cli_model == "claude-3-7"
        assert config.permission_mode == "ask"
        assert config.extra_args == ("--foo", "bar", "--extra")
        assert config.runtime.session_timeout_sec == 400

    def test_invalid_runtime_config_fails_closed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        hub = resolve_hub_root()
        proj = tmp_path / "test_proj"
        proj.mkdir()
        (proj / "memory-bank").mkdir()

        monkeypatch.setenv("EPIC_SESSION_TIMEOUT_SEC", "not_an_int")

        with pytest.raises(ConfigResolutionError, match="invalid_runtime_config"):
            resolve_runner_config(proj, hub_dir=hub, load_env=False)


class TestPreflightChecks:
    def test_preflight_checks_pass(self, tmp_path: Path) -> None:
        hub = resolve_hub_root()
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "memory-bank").mkdir()

        config = resolve_runner_config(proj, hub_dir=hub, load_env=False)
        result = run_preflight_checks(config, check_doctor=False)
        assert result.ok is True
        assert result.exit_code == 0

    def test_preflight_checks_fail_missing_smoke_file(self, tmp_path: Path) -> None:
        fake_hub = tmp_path / "fake_hub"
        fake_hub.mkdir()
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "memory-bank").mkdir()

        config = resolve_runner_config(proj, hub_dir=fake_hub, load_env=False)
        result = run_preflight_checks(config, check_doctor=False)
        assert result.ok is False
        assert result.exit_code == 2
        assert result.diagnostic_code == "MISSING_FILE"


class TestMainExecution:
    def test_main_help_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["--help"])
        assert code == 0
        captured = capsys.readouterr()
        assert "Usage:" in captured.out

    def test_main_invalid_args_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["--invalid-option"])
        assert code == 2
        captured = capsys.readouterr()
        assert "unknown option: --invalid-option" in captured.err

    def test_main_status_command(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "memory-bank").mkdir()
        (proj / "memory-bank" / "activeContext.md").write_text("# Active Context\n", encoding="utf-8")

        monkeypatch.setenv("PROJECT_ROOT", str(proj))
        code = main(["--status"])
        assert code == 0
        captured = capsys.readouterr()
        assert "{" in captured.out

    def test_main_run_invokes_loop_runner(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from loop.runner import RunAction, RunOutcome

        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "memory-bank").mkdir()
        (proj / "memory-bank" / "activeContext.md").write_text(
            "---\nschema: loop-handoff/v1\nrole: BACK\nmode: IMPLEMENT\n"
            "epic_id: T-01\nstep_id: s01\n---\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("PROJECT_ROOT", str(proj))
        monkeypatch.setenv("EPIC_RUNTIME", "claude")

        calls: list[Any] = []

        class _FakeRunner:
            def __init__(self, config: Any, **kwargs: Any) -> None:
                calls.append(("init", config, kwargs))

            def run(self) -> RunOutcome:
                calls.append(("run",))
                return RunOutcome(action=RunAction.COMPLETE, exit_code=0, reason="test")

        monkeypatch.setattr("loop.runner.orchestrator.LoopRunner", _FakeRunner)
        monkeypatch.setattr(
            "loop.runner.cli.run_preflight_checks",
            lambda config, **kwargs: type(
                "PF",
                (),
                {"ok": True, "reason": None, "exit_code": 0},
            )(),
        )

        code = main(["gpt-test-model"])
        assert code == 0
        assert any(c[0] == "run" for c in calls)
        assert any(c[0] == "init" for c in calls)
