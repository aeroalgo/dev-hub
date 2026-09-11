"""Command-line parsing and routing for the Python loop supervisor."""

from __future__ import annotations

import fnmatch
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from loop.runner.config import (
    ConfigResolutionError,
    resolve_hub_root,
    resolve_project_root,
    resolve_runner_config,
    run_preflight_checks,
)

USAGE_TEXT = """Usage: ./loop/loop.sh [EPIC] [MODEL] [MODE] [options]

Context-first автоцикл. Курсор = memory-bank/activeContext.md.

EPIC (опционально): T-HUB-027 | plan-<epic>.md | decompose-<id> | memory-bank/.../plan/...
  → arm via resolver (PLAN / DECOMPOSE / ANALYZE / IMPLEMENT по состоянию эпика).
  → Прошлый activeContext игнорируется.
Без EPIC: продолжение с текущего activeContext.

Examples:
  ./bin/loop . gpt
  ./bin/loop . --epic T-HUB-027 agy/gemini-3.6-flash-medium
  ./bin/loop . plan-T-HUB-027-back-plan-gstack-adapt.md agy/gemini-3.6-flash-medium
  ./bin/loop . decompose-v1-portal gpt implement

MODE:
  implement
      Force the activeContext cursor to run an IMPLEMENT step.
  ./loop/loop.sh --status

Options:
  --epic EPIC_ID
      Arm epic via arm_epic (e.g. T-HUB-016).
  -m, --model NAME
      --phase GAP_FANOUT
          Arm the next dependency-ready epic from loop/dag/*.yaml.
      --dag-generate PIPELINE
          Generate a DAG manifest from memory-bank/integration/gap/.
      --permission-mode MODE
      --interactive | --headless
      --verbose
      --status
  -h, --help
"""


@dataclass(frozen=True)
class CliArgs:
    """Parsed command line arguments."""

    command: str = "run"  # "run", "help", "status", "doctor", "dashboard", "dag-generate", "gap-fanout"
    epic_spec: str | None = None
    epic_id: str | None = None
    model: str | None = None
    mode: str | None = None
    permission_mode: str | None = None
    headless: bool = True
    interactive: bool = False
    verbose: bool = False
    dag_pipeline: str | None = None
    project_dir: str | None = None
    extra_args: tuple[str, ...] = field(default_factory=tuple)
    subcommand_args: tuple[str, ...] = field(default_factory=tuple)


def is_epic_spec(arg: str) -> bool:
    """Check if an argument looks like an epic spec / plan / decompose path."""
    patterns = [
        "decompose-*",
        "plan-*",
        "T-*",
        "memory-bank/*/plan/decompose-*",
        "memory-bank/*/plan/plan-*",
        "memory-bank/*/plan/decompose-*/index.md",
        "*/decompose-*",
        "*/plan-*",
    ]
    for pat in patterns:
        if fnmatch.fnmatch(arg, pat):
            return True
    return False


class CliParseError(ValueError):
    """Raised on invalid CLI arguments or options."""

    def __init__(self, message: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def parse_cli(argv: Sequence[str] | None = None) -> CliArgs:
    """Parse raw CLI arguments matching loop.sh positional and flag semantics."""
    if argv is None:
        argv = sys.argv[1:]
    else:
        argv = list(argv)

    if not argv:
        return CliArgs()

    # Check for project dir prefix (e.g. from bin/loop or direct path if it has memory-bank)
    project_dir: str | None = None
    idx = 0
    if len(argv) > 0 and not argv[0].startswith("-"):
        cand = Path(argv[0])
        if (cand.is_dir() and (cand / "memory-bank").is_dir()) or argv[0] == ".":
            project_dir = argv[0]
            argv = argv[1:]

    if not argv:
        return CliArgs(project_dir=project_dir)

    first = argv[0]
    if first in ("-h", "--help", "help"):
        return CliArgs(command="help", project_dir=project_dir)

    # Handle direct subcommand shortcuts
    if first == "status":
        return CliArgs(command="status", project_dir=project_dir, subcommand_args=tuple(argv[1:]))
    if first == "doctor":
        return CliArgs(command="doctor", project_dir=project_dir, subcommand_args=tuple(argv[1:]))
    if first == "dashboard":
        return CliArgs(command="dashboard", project_dir=project_dir, subcommand_args=tuple(argv[1:]))
    if first == "dag-generate":
        if len(argv) < 2:
            raise CliParseError("missing value for --dag-generate")
        pipeline = argv[1]
        if pipeline == "--pipeline" and len(argv) >= 3:
            pipeline = argv[2]
        return CliArgs(command="dag-generate", dag_pipeline=pipeline, project_dir=project_dir, subcommand_args=tuple(argv[2:]))

    model: str | None = None
    epic_spec: str | None = None
    epic_id_flag: str | None = None
    mode: str | None = None
    perm_mode: str | None = os.environ.get("EPIC_PERMISSION_MODE")
    headless = True
    interactive = False
    verbose = False
    do_status = False
    do_fanout = False
    generate_dag = False
    dag_pipeline: str | None = None
    extra_args: list[str] = []
    positionals: list[str] = []

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            return CliArgs(command="help")
        elif arg == "--status":
            do_status = True
            i += 1
        elif arg in ("--gap-fanout", "--phase"):
            if arg == "--phase":
                if i + 1 >= len(argv):
                    raise CliParseError("missing value for --phase")
                phase_val = argv[i + 1]
                if phase_val != "GAP_FANOUT":
                    raise CliParseError(f"unsupported phase: {phase_val}")
                i += 2
            else:
                i += 1
            do_fanout = True
        elif arg == "--dag-generate":
            if i + 1 >= len(argv):
                raise CliParseError("missing value for --dag-generate")
            generate_dag = True
            dag_pipeline = argv[i + 1]
            i += 2
        elif arg == "--epic":
            if i + 1 >= len(argv):
                raise CliParseError("missing value for --epic")
            epic_id_flag = argv[i + 1]
            i += 2
        elif arg in ("-m", "--model"):
            if i + 1 >= len(argv):
                raise CliParseError(f"missing value for {arg}")
            model = argv[i + 1]
            i += 2
        elif arg == "--permission-mode":
            if i + 1 >= len(argv):
                raise CliParseError("missing value for --permission-mode")
            perm_mode = argv[i + 1]
            i += 2
        elif arg == "--headless":
            headless = True
            interactive = False
            i += 1
        elif arg == "--interactive":
            interactive = True
            headless = False
            i += 1
        elif arg == "--verbose":
            verbose = True
            i += 1
        elif arg == "--":
            extra_args.extend(argv[i + 1:])
            break
        elif arg.startswith("-"):
            raise CliParseError(f"unknown option: {arg}")
        else:
            positionals.append(arg)
            i += 1

    for pos in positionals:
        if is_epic_spec(pos):
            if epic_spec is not None:
                raise CliParseError(f"==> ERROR: multiple epic specs: '{epic_spec}' and '{pos}'")
            epic_spec = pos
            continue
        if model is None:
            model = pos
            continue
        if mode is None and pos == "implement":
            mode = pos
            continue
        raise CliParseError(f"==> ERROR: unexpected positional argument '{pos}' (expected MODE=implement)")

    if mode:
        if not epic_spec and not epic_id_flag:
            raise CliParseError(f"==> ERROR: MODE={mode} requires an EPIC spec to select the activeContext cursor")
        if not model:
            raise CliParseError(f"==> ERROR: MODE={mode} requires a MODEL")

    cmd = "run"
    if do_status:
        cmd = "status"
    elif generate_dag:
        cmd = "dag-generate"
    elif do_fanout:
        cmd = "gap-fanout"

    return CliArgs(
        command=cmd,
        epic_spec=epic_spec,
        epic_id=epic_id_flag,
        model=model,
        mode=mode,
        permission_mode=perm_mode,
        headless=headless,
        interactive=interactive,
        verbose=verbose,
        dag_pipeline=dag_pipeline,
        project_dir=project_dir,
        extra_args=tuple(extra_args),
    )


def execute_non_session_command(args: CliArgs, project_root: Path) -> int:
    """Execute non-session subcommands (status, doctor, dashboard, dag-generate, gap-fanout)."""
    import loop.context_loop as cl

    if args.command == "status":
        res = cl.status(project_root)
        sys.stdout.write(json.dumps(res, indent=2) + "\n")
        sys.stdout.flush()
        return 0

    if args.command == "doctor":
        from loop.incidents.doctor import run_doctor
        rep = run_doctor(project_root, auto_repair=False, format="text")
        return rep.exit_code

    if args.command == "dashboard":
        from loop.dashboard.renderer import render_dashboard
        return render_dashboard(project_root)

    if args.command == "dag-generate":
        if not args.dag_pipeline:
            sys.stderr.write("==> ERROR: missing pipeline for dag-generate\n")
            return 2
        res = cl._cmd_dag_generate(project_root, args.dag_pipeline)
        sys.stdout.write(json.dumps(res, indent=2) + "\n")
        sys.stdout.flush()
        return 0 if res.get("ok") else 1

    if args.command == "gap-fanout":
        res = cl.dag_fanout(project_root)
        sys.stdout.write(json.dumps(res, indent=2) + "\n")
        sys.stdout.flush()
        return 0 if res.get("ok") else 1

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Main CLI entrypoint for loop supervisor."""
    try:
        args = parse_cli(argv)
    except CliParseError as exc:
        sys.stderr.write(f"{exc}\n{USAGE_TEXT}\n")
        sys.stderr.flush()
        return exc.exit_code

    if args.command == "help":
        sys.stdout.write(USAGE_TEXT)
        sys.stdout.flush()
        return 0

    try:
        hub_root = resolve_hub_root()
        project_root = resolve_project_root(args.project_dir, hub_root=hub_root)
    except ConfigResolutionError as exc:
        sys.stderr.write(f"{exc}\n")
        sys.stderr.flush()
        return exc.exit_code

    if args.command in ("status", "doctor", "dashboard", "dag-generate", "gap-fanout"):
        return execute_non_session_command(args, project_root)

    try:
        config = resolve_runner_config(
            project_root,
            hub_dir=hub_root,
            cli_model=args.model,
            epic_spec=args.epic_spec,
            epic_id=args.epic_id,
            mode=args.mode,
            permission_mode=args.permission_mode,
            headless=args.headless,
            interactive=args.interactive,
            verbose=args.verbose,
            extra_args=args.extra_args,
        )
    except ConfigResolutionError as exc:
        sys.stderr.write(f"{exc}\n")
        sys.stderr.flush()
        return exc.exit_code

    preflight = run_preflight_checks(config)
    if not preflight.ok:
        sys.stderr.write(f"==> ERROR: {preflight.reason}\n")
        sys.stderr.flush()
        return preflight.exit_code or 2

    import loop.context_loop as cl
    from loop.runner.orchestrator import LoopRunner
    from loop.runner.ownership import RunnerLockContendedError

    target_epic = args.epic_id or args.epic_spec
    if target_epic:
        if args.verbose:
            sys.stdout.write(f"==> arm epic={target_epic} (via resolver)\n")
            sys.stdout.flush()
        arm_res = cl.arm_epic(project_root, target_epic)
        if not arm_res.get("ok"):
            sys.stderr.write(f"==> ERROR: arming epic failed: {arm_res.get('error', 'unknown')}\n")
            sys.stderr.flush()
            return 1

    try:
        outcome = LoopRunner(config).run()
    except RunnerLockContendedError as exc:
        sys.stderr.write(f"{exc}\n")
        sys.stderr.flush()
        return int(getattr(exc, "exit_code", 1) or 1)

    return int(outcome.exit_code)


__all__ = [
    "CliArgs",
    "CliParseError",
    "USAGE_TEXT",
    "execute_non_session_command",
    "is_epic_spec",
    "main",
    "parse_cli",
]
