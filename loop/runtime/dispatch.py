from __future__ import annotations

import argparse
import json
import subprocess
import sys
import shlex
from pathlib import Path
from typing import Any, List, Optional

from loop.runtime.registry import InvalidRuntimeConfig, get_runtime_adapter
from loop.runtime_adapters.base import SessionContext


def _instantiate_adapter(runtime_id: str) -> Any:
    obj = get_runtime_adapter(runtime_id)
    if isinstance(obj, type):
        return obj()
    # It's a module, look for class
    attr_name = f"{runtime_id.capitalize()}Adapter"
    if hasattr(obj, attr_name):
        cls = getattr(obj, attr_name)
        return cls()
    # Fallback to scanning module for RuntimeAdapter class
    for name in dir(obj):
        if name.endswith("Adapter") and name != "RuntimeAdapter":
            cls = getattr(obj, name)
            if isinstance(cls, type):
                return cls()
    raise InvalidRuntimeConfig(f"No adapter class found for runtime '{runtime_id}' in module {obj}")


def build_command(
    runtime_id: str,
    prompt: str,
    phase: str = "IMPLEMENT",
    model: Optional[str] = None,
    extras: Optional[dict[str, Any]] = None,
) -> List[str]:
    """Build argv command list using adapter for the given runtime_id."""
    adapter = _instantiate_adapter(runtime_id)
    ctx = SessionContext(
        prompt=prompt,
        phase=phase,
        model=model,
        runtime_id=runtime_id,
        extras=extras or {},
    )
    return adapter.build_command(ctx)


def print_argv(
    runtime_id: str,
    prompt_file: Path | str,
    phase: str = "IMPLEMENT",
    model: Optional[str] = None,
    extras: Optional[dict[str, Any]] = None,
) -> int:
    """Print argv as JSON array (prompt may contain newlines)."""
    prompt_path = Path(prompt_file)
    try:
        prompt = prompt_path.read_text(encoding="utf-8")
    except Exception as e:
        sys.stderr.write(f"Error reading prompt file {prompt_path}: {e}\n")
        return 1

    try:
        cmd = build_command(
            runtime_id=runtime_id,
            prompt=prompt,
            phase=phase,
            model=model,
            extras=extras,
        )
    except InvalidRuntimeConfig as e:
        diag = {
            "error": "unknown_runtime",
            "runtime_id": runtime_id,
            "message": str(e),
        }
        sys.stderr.write(json.dumps(diag) + "\n")
        return 2
    except Exception as e:
        sys.stderr.write(f"adapter_error: {e}\n")
        return 1

    sys.stdout.write(json.dumps(cmd, ensure_ascii=False))
    return 0


def run_session(
    runtime_id: str,
    prompt_file: Path | str,
    phase: str = "IMPLEMENT",
    model: Optional[str] = None,
    extras: Optional[dict[str, Any]] = None,
    dry_run: bool = False,
) -> int:
    """Read prompt, build command via runtime adapter, and execute or print."""
    prompt_path = Path(prompt_file)
    try:
        prompt = prompt_path.read_text(encoding="utf-8")
    except Exception as e:
        sys.stderr.write(f"Error reading prompt file {prompt_path}: {e}\n")
        return 1

    try:
        cmd = build_command(
            runtime_id=runtime_id,
            prompt=prompt,
            phase=phase,
            model=model,
            extras=extras,
        )
    except InvalidRuntimeConfig as e:
        diag = {
            "error": "unknown_runtime",
            "runtime_id": runtime_id,
            "message": str(e),
        }
        sys.stderr.write(json.dumps(diag) + "\n")
        return 2
    except Exception as e:
        diag = {
            "error": "adapter_error",
            "runtime_id": runtime_id,
            "message": str(e),
        }
        sys.stderr.write(json.dumps(diag) + "\n")
        return 1

    if dry_run:
        print(shlex.join(cmd))
        return 0

    run_kwargs: dict[str, Any] = {}
    if runtime_id == "codex":
        run_kwargs["input"] = prompt.encode("utf-8")

    res = subprocess.run(cmd, **run_kwargs)
    return res.returncode


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="CLI dispatch for runtime adapters")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    run_parser = subparsers.add_parser("run_session", help="Run runtime session")
    run_parser.add_argument("--runtime", required=True, help="Runtime ID")
    run_parser.add_argument("--prompt-file", required=True, help="Path to prompt file")
    run_parser.add_argument("--phase", default="IMPLEMENT", help="Execution phase")
    run_parser.add_argument("--model", default=None, help="Optional model ID")
    run_parser.add_argument("--extras-json", default=None, help="JSON string with extras")
    run_parser.add_argument("--dry-run", action="store_true", help="Print argv without executing")

    argv_parser = subparsers.add_parser(
        "print-argv", help="Print argv JSON array (loop orchestration)"
    )
    argv_parser.add_argument("--runtime", required=True, help="Runtime ID")
    argv_parser.add_argument("--prompt-file", required=True, help="Path to prompt file")
    argv_parser.add_argument("--phase", default="IMPLEMENT", help="Execution phase")
    argv_parser.add_argument("--model", default=None, help="Optional model ID")
    argv_parser.add_argument("--extras-json", default=None, help="JSON string with extras")

    args = parser.parse_args(argv)

    extras = None
    if getattr(args, "extras_json", None):
        try:
            extras = json.loads(args.extras_json)
        except Exception as e:
            sys.stderr.write(f"Invalid extras-json: {e}\n")
            sys.exit(1)

    if args.subcommand == "print-argv":
        code = print_argv(
            runtime_id=args.runtime,
            prompt_file=args.prompt_file,
            phase=args.phase,
            model=args.model,
            extras=extras,
        )
        sys.exit(code)

    if args.subcommand == "run_session":
        extras = None
        if args.extras_json:
            try:
                extras = json.loads(args.extras_json)
            except Exception as e:
                sys.stderr.write(f"Invalid extras-json: {e}\n")
                sys.exit(1)

        code = run_session(
            runtime_id=args.runtime,
            prompt_file=args.prompt_file,
            phase=args.phase,
            model=args.model,
            extras=extras,
            dry_run=args.dry_run,
        )
        sys.exit(code)


if __name__ == "__main__":
    main()
