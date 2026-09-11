"""Configuration bootstrap, path normalization, environment loading, and preflight checks."""

from __future__ import annotations

import os
import py_compile
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from harness.hooks._lib import (
    RuntimeConfig,
    RuntimeConfigError,
    load_project_env,
    resolve_runtime_config as _lib_resolve_runtime_config,
)
from loop.runner import PreflightCheckResult, RunnerConfig


class ConfigResolutionError(RuntimeError):
    """Raised when configuration, paths, or environment cannot be resolved."""

    def __init__(self, message: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def resolve_hub_root(hub_dir: str | Path | None = None) -> Path:
    """Resolve the canonical dev-hub repository root."""
    if hub_dir is not None:
        candidate = Path(hub_dir).resolve()
        if candidate.is_dir():
            return candidate

    env_hub = os.environ.get("HUB_ROOT") or os.environ.get("DEV_HUB")
    if env_hub:
        candidate = Path(env_hub).resolve()
        if candidate.is_dir() and (candidate / "loop" / "context_loop.py").is_file():
            return candidate

    return Path(__file__).resolve().parents[2]


def resolve_project_root(
    project_dir: str | Path | None = None,
    *,
    hub_root: Path | None = None,
) -> Path:
    """Resolve the canonical product repository root containing memory-bank/."""
    if project_dir is not None and str(project_dir).strip():
        candidate = Path(project_dir).resolve()
        if candidate.is_dir() and (candidate / "memory-bank").is_dir():
            return candidate
        raise ConfigResolutionError(
            f"==> ERROR: PROJECT_ROOT required (product repo with memory-bank/)\n"
            f"    Specified path is invalid: {candidate}",
            exit_code=2,
        )

    env_proj = os.environ.get("PROJECT_ROOT") or os.environ.get("EPIC_PROJECT_ROOT")
    if env_proj and env_proj.strip():
        candidate = Path(env_proj).resolve()
        if candidate.is_dir() and (candidate / "memory-bank").is_dir():
            return candidate
        raise ConfigResolutionError(
            f"==> ERROR: PROJECT_ROOT required (product repo with memory-bank/)\n"
            f"    Env PROJECT_ROOT is invalid: {candidate}",
            exit_code=2,
        )

    cwd = Path.cwd().resolve()
    if cwd.is_dir() and (cwd / "memory-bank").is_dir():
        return cwd

    hub = hub_root or resolve_hub_root()
    raise ConfigResolutionError(
        f"==> ERROR: PROJECT_ROOT required (product repo with memory-bank/)\n"
        f"    Example: PROJECT_ROOT=/path/to/project {hub}/bin/loop gpt",
        exit_code=2,
    )


def resolve_state_dir(project_root: Path, hub_root: Path) -> Path:
    """Resolve canonical runtime state directory: HUB_ROOT/runtime/<slug>/epic."""
    slug = project_root.name
    return hub_root / "runtime" / slug / "epic"


def load_project_environment(
    project_root: Path,
    hub_root: Path,
    *,
    runtime_name: str | None = None,
    verbose: bool = False,
) -> list[str]:
    """Export canonical environment variables and load .claude/project.env files."""
    os.environ["HUB_ROOT"] = str(hub_root)
    os.environ["DEV_HUB"] = str(hub_root)
    os.environ["PROJECT_ROOT"] = str(project_root)
    os.environ["EPIC_PROJECT_ROOT"] = str(project_root)
    os.environ["EPIC_LOOP"] = "1"
    os.environ.setdefault("CLAUDE_CODE_ENABLE_TASKS", "0")

    runtime = runtime_name or os.environ.get("EPIC_RUNTIME", "claude")
    if runtime == "dsh":
        os.environ["DSH_HOOKS_BRIDGE"] = "1"
        os.environ["CLAUDE_PROJECT_DIR"] = str(project_root)
    else:
        os.environ.pop("DSH_HOOKS_BRIDGE", None)
        os.environ["CLAUDE_PROJECT_DIR"] = str(hub_root)

    applied_keys: list[str] = []
    # Load hub .claude/project.env
    applied_keys.extend(load_project_env(hub_root))
    # Load product project.env overrides if distinct
    if project_root != hub_root:
        applied_keys.extend(load_project_env(project_root))

    if verbose and (os.environ.get("EPIC_VERBOSE_ENV") == "1" or verbose):
        sys.stderr.write("==> loaded hub .claude/project.env exports\n")
        sys.stderr.flush()

    return applied_keys


def resolve_runner_config(
    project_dir: str | Path | None = None,
    *,
    hub_dir: str | Path | None = None,
    cli_model: str | None = None,
    epic_spec: str | None = None,
    epic_id: str | None = None,
    mode: str | None = None,
    permission_mode: str | None = None,
    headless: bool = True,
    interactive: bool = False,
    verbose: bool = False,
    extra_args: Sequence[str] | None = None,
    load_env: bool = True,
) -> RunnerConfig:
    """Construct an immutable RunnerConfig with path, env, and runtime resolution."""
    hub_root = resolve_hub_root(hub_dir)
    project_root = resolve_project_root(project_dir, hub_root=hub_root)
    state_dir = resolve_state_dir(project_root, hub_root)

    if load_env:
        load_project_environment(project_root, hub_root, verbose=verbose)

    try:
        runtime_config = _lib_resolve_runtime_config(project_root)
    except RuntimeConfigError as exc:
        raise ConfigResolutionError(
            f"==> ERROR: invalid_runtime_config {exc.diagnostics}",
            exit_code=2,
        ) from exc

    effective_perm_mode = (
        permission_mode
        or runtime_config.permission_mode
        or os.environ.get("EPIC_PERMISSION_MODE", "dontAsk")
    )

    combined_extra: list[str] = []
    epic_claude_args = os.environ.get("EPIC_CLAUDE_ARGS")
    if epic_claude_args:
        combined_extra.extend(shlex.split(epic_claude_args))
    if extra_args:
        combined_extra.extend(extra_args)

    return RunnerConfig(
        hub_root=hub_root,
        project_root=project_root,
        state_dir=state_dir,
        runtime=runtime_config,
        permission_mode=effective_perm_mode,
        headless=headless,
        interactive=interactive,
        verbose=verbose,
        cli_model=cli_model,
        epic_spec=epic_spec,
        epic_id=epic_id,
        mode=mode,
        extra_args=tuple(combined_extra),
    )


# Attach classmethod from_environment to RunnerConfig if not already bound
def _from_environment(
    cls: type[RunnerConfig],
    project_dir: str | Path | None = None,
    **kwargs: Any,
) -> RunnerConfig:
    return resolve_runner_config(project_dir, **kwargs)


setattr(RunnerConfig, "from_environment", classmethod(_from_environment))


def run_preflight_checks(
    config: RunnerConfig,
    *,
    check_doctor: bool | None = None,
) -> PreflightCheckResult:
    """Perform smoke py_compile and doctor preflight checks before session launch."""
    hub_root = config.hub_root

    smoke_files = [
        hub_root / "loop" / "context_loop.py",
        hub_root / "harness" / "hooks" / "session_resilience.py",
        hub_root / "harness" / "hooks" / "epic_lib.py",
        hub_root / "harness" / "hooks" / "stop-gate.py",
    ]

    for file_path in smoke_files:
        if not file_path.is_file():
            return PreflightCheckResult(
                ok=False,
                reason=f"loop smoke FAIL: required file missing: {file_path}",
                exit_code=2,
                diagnostic_code="MISSING_FILE",
                details={"file": str(file_path)},
            )
        try:
            py_compile.compile(str(file_path), doraise=True)
        except py_compile.PyCompileError as exc:
            return PreflightCheckResult(
                ok=False,
                reason=f"loop smoke FAIL: does not compile: {file_path}\n{exc}",
                exit_code=2,
                diagnostic_code="COMPILE_ERROR",
                details={"file": str(file_path), "error": str(exc)},
            )

    should_doctor = (
        check_doctor
        if check_doctor is not None
        else (os.environ.get("EPIC_LOOP_DOCTOR_PREFLIGHT", "0") == "1")
    )
    if should_doctor:
        try:
            from loop.incidents.doctor import run_doctor

            rep = run_doctor(config.project_root, auto_repair=False, format="json")
            if rep.exit_code != 0:
                return PreflightCheckResult(
                    ok=False,
                    reason=f"doctor preflight failed (rc={rep.exit_code})",
                    exit_code=rep.exit_code,
                    diagnostic_code="DOCTOR_FAIL",
                    details={"exit_code": rep.exit_code},
                )
        except Exception as exc:
            return PreflightCheckResult(
                ok=False,
                reason=f"doctor preflight exception: {exc}",
                exit_code=2,
                diagnostic_code="DOCTOR_EXCEPTION",
                details={"error": str(exc)},
            )

    return PreflightCheckResult(ok=True)


__all__ = [
    "ConfigResolutionError",
    "load_project_environment",
    "resolve_hub_root",
    "resolve_project_root",
    "resolve_runner_config",
    "resolve_state_dir",
    "run_preflight_checks",
]
