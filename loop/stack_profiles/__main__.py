"""CLI entrypoint for loop.stack_profiles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import List, Optional

from loop.stack_profiles.doctor import doctor_project_profiles
from loop.stack_profiles.execution import (
    CapabilityCheckSpec,
    CapabilityExecutionResult,
    execute_capability,
)
from loop.stack_profiles.resolver import resolve_capability
from loop.stack_profiles.schemas import CapabilityName, CapabilityResolution, Diagnostic, DoctorReport


def _exit_code_for_execution(res: CapabilityExecutionResult) -> int:
    """Map CapabilityExecutionResult status and diagnostics to CLI exit codes.
    Status mapping:
      - 'succeeded' -> 0
      - 'resolution_failed' -> 2
      - 'spawn_failed' -> 3
      - 'timed_out' -> 4
      - 'failed' -> child exit code if 1..125, else 1
    """
    if res.ok and res.status == "succeeded":
        return 0
    if res.status == "resolution_failed":
        return 2
    if res.status == "spawn_failed":
        return 3
    if res.status == "timed_out":
        return 4
    if res.status == "failed":
        if res.exit_code is not None and 1 <= res.exit_code <= 125:
            return res.exit_code
        return 1
    return 1


def _exit_code_for_resolution(res: CapabilityResolution) -> int:
    """Map CapabilityResolution diagnostics to exit codes.
    Exit: 0 complete; 2 config/profile diagnostics; 3 missing/probe-failed tool; 1 unexpected.
    """
    if res.ok:
        return 0
    # Check if diagnostics contain tool issues
    for diag in res.diagnostics:
        if diag.code in ("tool_missing", "tool_probe_failed"):
            return 3
    # Any other validation/config diagnostic
    return 2


def _exit_code_for_doctor(rep: DoctorReport) -> int:
    """Map DoctorReport diagnostics and checks to exit codes."""
    if rep.ok:
        return 0
    for diag in rep.diagnostics:
        if diag.code in ("tool_missing", "tool_probe_failed"):
            return 3
    return 2


def main(argv: Optional[List[str]] = None) -> int:
    """Run stack profiles CLI returning JSON on stdout."""
    parser = argparse.ArgumentParser(prog="python -m loop.stack_profiles")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # resolve subcommand
    resolve_parser = subparsers.add_parser("resolve")
    resolve_parser.add_argument("--project-root", type=str, required=True, help="Path to project workspace root")
    resolve_parser.add_argument("--target", type=str, default=None, help="Target name in dev-hub.project.yaml")
    resolve_parser.add_argument("--capability", type=str, required=True, help="Capability name to resolve")
    resolve_parser.add_argument("--selector", type=str, default=None, help="Optional test selector or argument")

    # doctor subcommand
    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("--project-root", type=str, required=True, help="Path to project workspace root")
    doctor_parser.add_argument("--target", type=str, default=None, help="Optional target name")

    # execute subcommand
    execute_parser = subparsers.add_parser("execute")
    execute_parser.add_argument("--project-root", type=str, required=True, help="Path to project workspace root")
    execute_parser.add_argument("--target", type=str, required=True, help="Target name in dev-hub.project.yaml")
    execute_parser.add_argument("--capability", type=str, required=True, help="Capability name to execute")
    execute_parser.add_argument("--selector", type=str, default=None, help="Optional test selector or argument")

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # Malformed CLI arguments - emit JSON diagnostic and exit 2
        code = exc.code if isinstance(exc.code, int) else 2
        if code != 0:
            diag_res = CapabilityResolution(
                ok=False,
                target=None,
                profile=None,
                capability=None,
                cwd="",
                argv=[],
                diagnostics=[
                    Diagnostic(
                        code="project_manifest_invalid",
                        message="Invalid CLI arguments passed to stack_profiles",
                    )
                ],
            )
            print(json.dumps(diag_res.model_dump(by_alias=True, exclude_none=True), indent=2))
            return 2
        return 0

    try:
        project_root = Path(args.project_root)

        if args.command == "resolve":
            res = resolve_capability(
                project_root,
                args.capability,
                target=args.target,
                selector=args.selector,
            )
            print(json.dumps(res.model_dump(by_alias=True, exclude_none=True), indent=2))
            return _exit_code_for_resolution(res)

        elif args.command == "doctor":
            rep = doctor_project_profiles(
                project_root,
                target=args.target,
            )
            print(json.dumps(rep.model_dump(by_alias=True, exclude_none=True), indent=2))
            return _exit_code_for_doctor(rep)

        elif args.command == "execute":
            try:
                spec = CapabilityCheckSpec(
                    target=args.target,
                    capability=args.capability,
                    selector=args.selector,
                )
            except Exception as decl_exc:
                diag_res = CapabilityExecutionResult(
                    ok=False,
                    target=args.target,
                    capability=args.capability,
                    status="resolution_failed",
                    diagnostics=[
                        Diagnostic(
                            code="project_manifest_invalid",
                            message=f"Invalid capability check declaration: {decl_exc}",
                        )
                    ],
                )
                print(json.dumps(diag_res.model_dump(by_alias=True, exclude_none=True), indent=2))
                return 2

            exec_res = execute_capability(
                project_root=project_root,
                declaration=spec,
            )
            print(json.dumps(exec_res.model_dump(by_alias=True, exclude_none=True), indent=2))
            return _exit_code_for_execution(exec_res)

        return 1
    except Exception as exc:
        # Unexpected internal error
        err_res = {
            "schema": "stack-profiles-error/v1",
            "ok": False,
            "error": str(exc),
        }
        print(json.dumps(err_res, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
