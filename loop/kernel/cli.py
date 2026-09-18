from __future__ import annotations

import argparse
import json
import os
import sys
import time

from .engine import LoopEngine, TransitionError
from .runtime import runtime_for
from .store import LoopPaths


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="single-cursor loop")
    parser.add_argument("command", nargs="?", default="run", choices=("run", "start", "finish", "halt", "status", "doctor"))
    parser.add_argument("model_pos", nargs="?")
    parser.add_argument("--project", "--cwd", dest="project")
    parser.add_argument("--epic")
    parser.add_argument("--role", default="back")
    parser.add_argument("--runtime", choices=("claude", "codex"), default=None)
    parser.add_argument("--model")
    parser.add_argument("--step")
    parser.add_argument("--reason", default="manual halt")
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("LOOP_SESSION_TIMEOUT", "3600")))
    parser.add_argument("--max-attempts", type=int, default=int(os.environ.get("LOOP_MAX_ATTEMPTS", "3")))
    parser.add_argument("--max-steps", type=int, default=int(os.environ.get("LOOP_MAX_STEPS", "100")))
    parser.add_argument("--backoff", type=float, default=float(os.environ.get("LOOP_RETRY_BACKOFF", "2")))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--status", action="store_true")
    return parser


def _print(value: object, as_json: bool = True) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(value)


def _normalize_legacy_args(argv: list[str]) -> list[str]:
    commands = {"run", "start", "finish", "halt", "status", "doctor"}
    if len(argv) >= 2 and argv[0] not in commands and not argv[0].startswith("-"):
        return ["run", "--epic", argv[0], "--model", argv[1], *argv[2:]]
    return argv


def _epic(args: argparse.Namespace, engine: LoopEngine) -> str:
    if args.epic:
        return args.epic
    cursor = engine.store.read()
    if cursor:
        return cursor.epic_id
    raise TransitionError("--epic is required when cursor.json does not exist")


def run(args: argparse.Namespace) -> int:
    paths = LoopPaths.for_project(args.project)
    engine = LoopEngine(paths)
    epic_id = _epic(args, engine)
    cursor = engine.start(epic_id, args.role)
    if cursor.status.value == "complete":
        _print(engine.status(), args.json)
        return 0
    model = args.model or args.model_pos or os.environ.get("LOOP_MODEL") or os.environ.get("PROJECT_LOOP_MODEL")
    if not model:
        _print({"ok": False, "error": "model is required: use --model or LOOP_MODEL"}, True)
        return 2
    runtime_name = args.runtime or os.environ.get("EPIC_RUNTIME", "claude")
    runtime = runtime_for(runtime_name)
    for _ in range(max(1, args.max_steps)):
        cursor = engine.store.read()
        if cursor is None:
            raise TransitionError("cursor disappeared")
        if cursor.status.value == "complete":
            return 0
        if cursor.status.value == "halted":
            return 1
        prompt = (
            f"You are operating epic {cursor.epic_id}, role {cursor.role}.\n"
            f"Current phase: {cursor.phase}; step: {cursor.step_id}.\n"
            "Read the canonical YAML queue and current artifact. Make the requested changes. "
            f"When the step is genuinely complete, run `bin/loop finish --project {paths.project} --step {cursor.step_id}`. "
            "Do not edit cursor.json or generated activeContext.md."
        )
        session_id = cursor.session_id or f"session-{cursor.revision}"
        result = runtime.run(prompt, model=model, project=paths.project, log_path=engine.store.session_log(session_id), timeout=args.timeout)
        updated = engine.store.read()
        if updated is None:
            raise TransitionError("cursor disappeared after session")
        if updated.revision > cursor.revision:
            if updated.status.value == "complete":
                return 0
            continue
        if result.interrupted or result.exit_code in (130, 143):
            engine.halt("user_interrupt")
            return 130
        if result.ok:
            reason = "finish_not_committed"
            retry = engine.retry(reason)
            if retry.attempt >= args.max_attempts:
                engine.halt(reason)
                return 1
            time.sleep(args.backoff * (2 ** max(0, retry.attempt - 1)))
            continue
        reason = "session_timeout" if result.timed_out else f"runtime_exit_{result.exit_code}"
        retry = engine.retry(reason)
        if retry.attempt >= args.max_attempts:
            engine.halt(reason)
            return 1
        time.sleep(args.backoff * (2 ** max(0, retry.attempt - 1)))
    engine.halt("max_steps_exceeded")
    return 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(_normalize_legacy_args(list(sys.argv[1:] if argv is None else argv)))
    try:
        paths = LoopPaths.for_project(args.project)
        engine = LoopEngine(paths)
        if args.status or args.command == "status":
            _print(engine.status(), args.json)
            return 0
        if args.command == "doctor":
            result = engine.doctor()
            _print(result, args.json)
            return 0 if result.get("ok") else 1
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
