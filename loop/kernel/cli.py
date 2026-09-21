from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..config import LoopSettings
from ..config import activate_loop_process
from .engine import LoopEngine, TransitionError
from .boundary import BoundaryService
from .runtime import runtime_for
from .session import SessionOutcome, SessionSupervisor
from .store import LoopPaths
from .verdict import SCHEMA_GATE_VERDICT, validate_boundary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="single-cursor loop")
    parser.add_argument("command", nargs="?", default="run", choices=("run", "start", "finish", "halt", "status", "doctor", "scope", "validate", "validate-verdict"))
    parser.add_argument("--project", "--cwd", dest="project")
    parser.add_argument("--epic")
    parser.add_argument("--role", default="back")
    parser.add_argument("--runtime", choices=("claude", "codex"), default=None)
    parser.add_argument("--model")
    parser.add_argument("--step")
    parser.add_argument("--reason", default="manual halt")
    parser.add_argument("--payload")
    parser.add_argument("--schema")
    parser.add_argument("--timeout", type=int)
    parser.add_argument("--max-attempts", type=int)
    parser.add_argument("--max-steps", type=int)
    parser.add_argument("--backoff", type=float)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--status", action="store_true")
    return parser


def _print(value: object, as_json: bool = True) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(value)


def _report_failure(
    args: argparse.Namespace,
    cursor,
    *,
    reason: str,
    status: str,
    attempt: int,
    runtime: str,
    model: str,
    cursor_path: Path,
    result=None,
) -> None:
    payload = {
        "ok": False,
        "error": reason,
        "status": status,
        "runtime": runtime,
        "model": model,
        "epic_id": cursor.epic_id,
        "role": cursor.role,
        "phase": cursor.phase,
        "step_id": cursor.step_id,
        "attempt": attempt,
        "cursor_path": str(cursor_path),
    }
    if result is not None:
        payload["exit_code"] = result.exit_code
        payload["session_log"] = str(result.log_path)
        if result.message:
            payload["detail"] = result.message
    if args.json:
        _print(payload, True)
        return
    print("loop error:", file=sys.stderr)
    for key in ("error", "runtime", "model", "epic_id", "role", "phase", "step_id", "attempt", "status", "exit_code", "detail", "session_log", "cursor_path"):
        if key in payload:
            print(f"  {key}: {payload[key]}", file=sys.stderr)


def _epic(args: argparse.Namespace, engine: LoopEngine) -> str:
    if args.epic:
        return args.epic
    cursor = engine.store.read()
    if cursor:
        return cursor.epic_id
    raise TransitionError("--epic is required when cursor.json does not exist")


def run(args: argparse.Namespace) -> int:
    paths = LoopPaths.for_project(args.project)
    settings = LoopSettings.load(hub_root=paths.hub, project_root=paths.project)
    settings.apply_environment()
    engine = LoopEngine(paths)
    epic_id = _epic(args, engine)
    cursor = engine.start(epic_id, args.role)
    if cursor.status.value == "complete":
        _print(engine.status(), args.json)
        return 0
    cli_model = args.model
    runtime_name = args.runtime or settings.runtime
    runtime = runtime_for(runtime_name, settings=settings)
    timeout = args.timeout if args.timeout is not None else settings.session_timeout
    max_attempts = args.max_attempts if args.max_attempts is not None else settings.max_attempts
    max_steps = args.max_steps if args.max_steps is not None else settings.max_steps
    backoff = args.backoff if args.backoff is not None else settings.retry_backoff
    supervisor = SessionSupervisor(engine, runtime, timeout=timeout, max_attempts=max_attempts, backoff=backoff)
    model = ""
    for _ in range(max(1, max_steps)):
        cursor = engine.store.read()
        if cursor is None:
            raise TransitionError("cursor disappeared")
        if cursor.status.value == "complete":
            return 0
        if cursor.status.value == "halted":
            return 1
        activate_loop_process(project_root=paths.project, session_id=cursor.session_id)
        selection = settings.model_for(
            phase=cursor.phase,
            step_id=cursor.step_id,
            role=cursor.role,
            cli_model=cli_model,
        )
        model = selection.model
        if not model:
            _print(
                {
                    "ok": False,
                    "error": "model_required",
                    "reason": f"set {selection.env_name} or pass --model",
                    **selection.as_dict(),
                },
                args.json,
            )
            return 2
        engine.record_event(
            {
                "event": "model_selected",
                "phase": cursor.phase,
                "step_id": cursor.step_id,
                "model": model,
                "model_source": selection.source,
            }
        )
        prompt = (
            f"You are operating epic {cursor.epic_id}, role {cursor.role}.\n"
            f"Current phase: {cursor.phase}; step: {cursor.step_id}.\n"
            f"GATE_IDENTITY session_id={cursor.session_id} epic_id={cursor.epic_id} step_id={cursor.step_id}\n"
        )
        if cursor.phase == "DECOMPOSE":
            prompt += (
                f"Run {cursor.role.upper()} DECOMPOSE for plan {cursor.epic_id}. "
                f"Read the plan at {paths.project / 'memory-bank' / cursor.role / 'plan' / cursor.epic_id / 'md' / 'plan.md'}. "
                "The canonical decompose index does not exist yet by design. "
                "Create the canonical yaml/decompose-index.yaml and yaml/steps/sNN-*.yaml artifacts, "
                "run the required validation gates, and do not write production code. "
            )
        elif cursor.phase == "ANALYZE":
            prompt += (
                f"Run {cursor.role.upper()} ANALYZE for plan {cursor.epic_id}. "
                "Read the canonical plan and decompose tree, create the required analyze artifact, "
                "and do not write production code. "
            )
        else:
            prompt += "Read the canonical YAML queue and current artifact. Make the requested changes. "
        prompt += (
            f"When the phase is genuinely complete, run `python3 $DEV_HUB/bin/loop.py finish --project {paths.project} --step {cursor.step_id}`. "
            "Do not edit cursor.json or generated activeContext.md. "
            "A managed gate subagent PASS is validated by the boundary hook and may finish this step atomically; prose verdicts are not machine state."
        )
        prompt = f"{prompt}\n\n{engine.boundary.context(cursor)}"
        session_run = supervisor.run_step(prompt, model=model, project=paths.project, session_id=cursor.session_id)
        if session_run.outcome == SessionOutcome.COMMITTED:
            return 0
        if session_run.outcome == SessionOutcome.STATE_CHANGED and session_run.result is not None:
            continue
        transition = session_run.transition
        status = transition.status.value if transition is not None else "halted"
        attempt = transition.attempt if transition is not None else cursor.attempt
        _report_failure(args, cursor, reason=session_run.reason, status=status, attempt=attempt, runtime=runtime_name, model=model, cursor_path=paths.cursor, result=session_run.result)
        return session_run.return_code
    halted = engine.halt("max_steps_exceeded")
    _report_failure(args, cursor, reason="max_steps_exceeded", status=halted.status.value, attempt=halted.attempt, runtime=runtime_name, model=model, cursor_path=paths.cursor)
    return 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        paths = LoopPaths.for_project(args.project)
        settings = LoopSettings.load(hub_root=paths.hub, project_root=paths.project)
        settings.apply_environment()
        engine = LoopEngine(paths)
        if args.status or args.command == "status":
            _print(engine.status(), args.json)
            return 0
        if args.command == "doctor":
            result = engine.doctor()
            _print(result, args.json)
            return 0 if result.get("ok") else 1
        if args.command in {"validate", "validate-verdict"}:
            if not args.payload:
                _print({"ok": False, "error": "--payload is required"}, True)
                return 2
            schema = SCHEMA_GATE_VERDICT if args.command == "validate-verdict" else args.schema
            if not schema:
                _print({"ok": False, "error": "--schema is required"}, True)
                return 2
            result = validate_boundary(schema, args.payload)
            _print(result.as_dict(), True)
            return 0 if result.valid else 2
        if args.command == "scope":
            cursor = engine.store.read()
            if cursor is None:
                _print({"ok": False, "error": "cursor_missing"}, True)
                return 2
            result = BoundaryService(paths).scope(cursor)
            _print(result, args.json)
            return 0 if result["ok"] else 1
        if args.command == "start":
            cursor = engine.start(_epic(args, engine), args.role)
            _print(cursor.to_dict(), args.json)
            return 0
        if args.command == "finish":
            transition = engine.finish(step_id=args.step)
            _print({"event": transition.event, "status": transition.status.value, "phase": transition.phase, "step_id": transition.step_id}, args.json)
            return 0
        if args.command == "halt":
            transition = engine.halt(args.reason)
            _print({"event": transition.event, "status": transition.status.value, "phase": transition.phase, "step_id": transition.step_id}, args.json)
            return 0
        return run(args)
    except (ValueError, FileNotFoundError, TransitionError) as exc:
        _print({"ok": False, "error": str(exc)}, True)
        return 2
