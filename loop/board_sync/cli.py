"""Command-line interface for memory-bank task-board synchronization."""

from __future__ import annotations

import argparse
import os
import re
import shlex
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = "loop.board_sync"

import yaml

from loop.board_launch.arm import ArmResult, arm_from_card
from loop.board_launch.loop_argv import BridgeConfig, LoopArgvResult, build_loop_argv
from loop.board_launch.loop_run import (
    ExecutionResult,
    LoopRunError,
    execution_result_from_error,
    loop_run,
)
from loop.board_launch.metadata import LaunchCard, parse_launch_metadata
from loop.board_launch.pipeline import PipelineResult, arm_loop_from_card

from .client import (
    BoardClientError,
    HttpHostClient,
    LedgerFileClient,
    TaskBoardClient,
    execution_record,
)
from .diff import BoardTask
from .host_url import default_dsh_home, default_host_url
from .sync import SyncResult, run_sync
from .workspaces import WorkspacesError, discover

_LOOP_ARG_RE = re.compile(r"^[a-zA-Z0-9._/-]+$")
_DEFAULT_RUNTIME = "claude"

ArmFn = Callable[[LaunchCard], ArmResult]
LoopRunner = Callable[[LaunchCard, LoopArgvResult, BridgeConfig], ExecutionResult]

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hub-board",
        description="Synchronize memory-bank work with the DSH task board.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync", help="sync active memory-bank work")
    sync_parser.add_argument("--dry-run", action="store_true", help="print operations without writing")
    sync_parser.add_argument("--workspace-id", help="sync only one registered workspace")
    sync_parser.add_argument(
        "--dsh-home",
        type=Path,
        default=default_dsh_home(),
        help="DSH home containing storages/workspace.json",
    )
    sync_parser.add_argument(
        "--offline-ledger",
        type=Path,
        metavar="PATH",
        help="use a local JSON ledger instead of the live Host API",
    )
    sync_parser.add_argument(
        "--host-url",
        default=default_host_url(),
        help="DSH Host base URL",
    )

    status_parser = subparsers.add_parser("status", help="show the last sync summary")
    status_parser.add_argument(
        "--offline-ledger",
        type=Path,
        metavar="PATH",
        help="read the summary from a local JSON ledger",
    )
    status_parser.add_argument(
        "--host-url",
        default=default_host_url(),
        help="DSH Host base URL",
    )

    for command, help_text in (
        ("arm", "arm a board task into its product loop"),
        ("loop", "run a board task through the product loop"),
        ("arm-loop", "arm and run a board task through the product loop"),
    ):
        launch_parser = subparsers.add_parser(command, help=help_text)
        launch_parser.add_argument("--task-id", required=True, help="board task identifier")
        launch_parser.add_argument(
            "--ledger", "--offline-ledger", dest="offline_ledger", type=Path,
            metavar="PATH", help="read the task from a local JSON ledger",
        )
        launch_parser.add_argument(
            "--from-state", dest="offline_ledger", type=Path, metavar="PATH",
            help=argparse.SUPPRESS,
        )
        launch_parser.add_argument("--host-url", default=default_host_url())
        if command != "arm":
            launch_parser.add_argument("--loop-args", metavar="TOKEN", help="one whitelisted loop argument")
            launch_parser.add_argument(
                "--runtime", choices=("claude", "dsh", "codex"), default=_DEFAULT_RUNTIME,
                help="loop runtime family (default: claude)",
            )
        if command != "loop":
            launch_parser.add_argument(
                "--allow-roadmap-advance", action="store_true",
                help="allow ROADMAP gates only with explicit epic metadata",
            )
        launch_parser.add_argument("--dry-run", action="store_true", help="print the launch plan without executing")
    return parser


def _launch_config() -> BridgeConfig:
    dev_hub = os.getenv("DEV_HUB", "")
    if not dev_hub:
        raise ValueError("DEV_HUB is required for board launch commands")
    hub = Path(dev_hub).expanduser()
    if not hub.exists() or not hub.is_dir():
        raise ValueError(f"DEV_HUB does not exist: {hub}")
    return BridgeConfig(loop_bin=hub / "bin" / "loop", default_runtime=_DEFAULT_RUNTIME)


def _task_for(args: argparse.Namespace, client: TaskBoardClient | None) -> BoardTask:
    board_client = client or _client_for(args)
    task = next((item for item in board_client.list_tasks() if item.id == args.task_id), None)
    if task is None:
        raise ValueError(f"task not found: {args.task_id}")
    return task


def _record_execution(
    client: TaskBoardClient | None,
    args: argparse.Namespace,
    result: ExecutionResult,
) -> None:
    board_client = client or _client_for(args)
    board_client.record_execution(execution_record(args.task_id, result))


def _launch_card(task: BoardTask) -> LaunchCard:
    try:
        return parse_launch_metadata({"metadata": yaml.safe_load(task.description)})
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid task metadata: {exc}") from exc


def _preset_id(raw: str | None) -> str | None:
    if raw is None:
        return None
    if not _LOOP_ARG_RE.fullmatch(raw):
        raise ValueError("--loop-args must contain one safe token")
    return raw


def _print_result(result: Any) -> None:
    if isinstance(result, LoopArgvResult):
        print("argv=" + shlex.join(result.argv))
        print("env=" + repr(result.env_extra))
        print("model_source=" + result.model_source)
        if result.model_env is not None:
            print("model_env=" + result.model_env)
    elif isinstance(result, ExecutionResult):
        print(f"status={result.status}")
        print(f"exit_code={result.exit_code}")
        if result.model_source is not None:
            print("model_source=" + result.model_source)
        if result.model_env is not None:
            print("model_env=" + result.model_env)
    elif isinstance(result, ArmResult):
        print(f"armed step_id={result.step_id} epic_id={result.armed_epic}")

def _print_result_legacy(result: Any) -> None:
    if isinstance(result, LoopArgvResult):
        print("argv=" + shlex.join(result.argv))
        print("env=" + repr(result.env_extra))
        print("model_source=" + result.model_source)
    elif isinstance(result, ArmResult):
        print(f"armed step_id={result.step_id} epic_id={result.armed_epic}")
    elif isinstance(result, PipelineResult):
        print(f"status={result.status} loop_invoked={result.loop_invoked}")
        if result.loop is not None:
            print(f"exit_code={result.loop.exit_code}")
            if result.loop.model_source is not None:
                print(f"model_source={result.loop.model_source}")
            if result.loop.model_env is not None:
                print(f"model_env={result.loop.model_env}")
        elif result.model_source is not None:
            print(f"model_source={result.model_source}")
            if result.model_env is not None:
                print(f"model_env={result.model_env}")
        if result.sync_warning:
            print(f"warning={result.sync_warning}", file=sys.stderr)
    else:
        print(result)


def _arm(args: argparse.Namespace, client: TaskBoardClient | None) -> int:
    config = _launch_config()
    card = _launch_card(_task_for(args, client))
    if args.dry_run:
        _print_result(_arm_plan(card, config))
        return 0
    _print_result(arm_from_card(card, config=config))
    return 0


def _loop(args: argparse.Namespace, client: TaskBoardClient | None) -> int:
    config = _launch_config()
    card = _launch_card(_task_for(args, client))
    argv_result = build_loop_argv(
        card.project_root,
        _card_phase(card),
        config,
        preset_id=_preset_id(args.loop_args),
        runtime=args.runtime,
    )
    if args.dry_run:
        _print_result(argv_result)
        return 0
    try:
        result = loop_run(card, argv_result, config)
    except LoopRunError as exc:
        result = execution_result_from_error(exc, argv_result)
    _record_execution(client, args, result)
    _print_result(result)
    return 0 if result.status == "succeeded" else 1


def _arm_loop(args: argparse.Namespace, client: TaskBoardClient | None) -> int:
    config = _launch_config()
    card = _launch_card(_task_for(args, client))
    preset_id = _preset_id(args.loop_args)
    argv_result = build_loop_argv(
        card.project_root,
        _card_phase(card),
        config,
        preset_id=preset_id,
        runtime=args.runtime,
    )
    if args.dry_run:
        _print_result(_arm_plan(card, config))
        _print_result(argv_result)
        return 0
    try:
        result = arm_loop_from_card(card, config, preset_id=preset_id, runtime=args.runtime)
    except LoopRunError as exc:
        loop_result = execution_result_from_error(exc, argv_result)
        _record_execution(client, args, loop_result)
        _print_result(loop_result)
        return 1
    if result.loop is not None:
        _record_execution(client, args, result.loop)
    _print_result(result)
    return 0 if result.status == "succeeded" else 1


def _card_phase(card: LaunchCard) -> str:
    raw_phase = card.raw.get("phase")
    return raw_phase if isinstance(raw_phase, str) and raw_phase.strip() else (card.gate_phase or "IMPLEMENT")


def _arm_plan(card: LaunchCard, config: BridgeConfig) -> LoopArgvResult:
    return LoopArgvResult(
        argv=[str(Path(os.environ["DEV_HUB"]) / "loop" / "context_loop.py"), "--cwd", card.project_root, "arm", "--epic", card.decompose_rel],
        env_extra={},
        model_source="arm",
    )


def _launch(args: argparse.Namespace, client: TaskBoardClient | None) -> int:
    if args.command == "arm":
        return _arm(args, client)
    if args.command == "loop":
        return _loop(args, client)
    return _arm_loop(args, client)


def _status_or_launch(args: argparse.Namespace, client: TaskBoardClient | None) -> int:
    if args.command in {"arm", "loop", "arm-loop"}:
        return _launch(args, client)
    return _dispatch_legacy(args, client)


def main(
    argv: Sequence[str] | None = None,
    *,
    client: TaskBoardClient | None = None,
) -> int:
    raw_argv = list(argv) if argv is not None else None
    if raw_argv in (['--help'], ['-h']):
        build_parser().parse_args(raw_argv)
    try:
        args = build_parser().parse_args(raw_argv)
    except SystemExit as exc:
        return int(exc.code)
    try:
        return _status_or_launch(args, client)
    except (BoardClientError, WorkspacesError, OSError, ValueError) as exc:

        print(f"hub-board: {exc}", file=sys.stderr)
        return 1


def _dispatch_legacy(args: argparse.Namespace, client: TaskBoardClient | None) -> int:
    if args.command == "sync":
        return _sync(args, client)
    return _status(args, client)


# Keep legacy handlers named and isolated for callers importing them directly.


def _sync(args: argparse.Namespace, client: TaskBoardClient | None) -> int:
    refs = discover(args.dsh_home)
    board_client = client or _client_for(args)
    result = run_sync(
        refs,
        board_client,
        dry_run=args.dry_run,
        workspace_id_filter=args.workspace_id,
    )
    _print_operations(result)
    for error in result.errors:
        print(f"error: {error}", file=sys.stderr)
    return 1 if result.errors else 0


def _status(args: argparse.Namespace, client: TaskBoardClient | None) -> int:
    board_client = client or _client_for(args)
    tasks = board_client.list_tasks()
    generation = 0
    upsert = archive = 0
    for task in tasks:
        if not task.id.startswith("mb-"):
            continue
        try:
            from .card_model import parse_metadata

            generation = max(generation, parse_metadata(task.description).sync_generation)
        except (TypeError, ValueError):
            continue
        if task.status == "archived":
            archive += 1
        else:
            upsert += 1
    print(f"generation={generation} upsert={upsert} archive={archive} noop=0")
    return 0


def _client_for(args: argparse.Namespace) -> TaskBoardClient:
    if args.offline_ledger is not None:
        return LedgerFileClient(args.offline_ledger)
    return HttpHostClient(args.host_url)


def _print_operations(result: SyncResult) -> None:
    print(
        f"generation={result.sync_generation} upsert={result.created + result.updated} "
        f"archive={result.archived} noop={len(result.operations) - result.created - result.updated - result.archived}"
    )
    for operation in result.operations:
        if operation.kind == "archive":
            print(f"archive {operation.task_id}")
        elif operation.card is not None:
            print(f"{operation.kind} {operation.card.id} {operation.card.title}")


if __name__ == "__main__":
    raise SystemExit(main())
