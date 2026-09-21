from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from ..config import LoopSettings
from ..config import activate_loop_process
from .engine import LoopEngine, TransitionError
from .boundary import BoundaryService
from .analyze import latest_analyze_with_path
from .index import bugfix_queue_path, bugfix_report_paths, implement_path, load_queue
from .runtime import runtime_for
from .session import SessionOutcome, SessionSupervisor
from .store import LoopPaths
from .verdict import SCHEMA_GATE_VERDICT, validate_boundary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="single-cursor loop")
    parser.add_argument("command", nargs="?", default="run", choices=("run", "start", "finish", "halt", "rewind", "status", "doctor", "scope", "validate", "validate-verdict"))
    parser.add_argument("--project", "--cwd", dest="project")
    parser.add_argument("--epic")
    parser.add_argument("--role", default="back")
    parser.add_argument("--runtime", choices=("claude", "codex"), default=None)
    parser.add_argument("--model")
    parser.add_argument("--step")
    parser.add_argument("--phase", choices=("DECOMPOSE", "ANALYZE", "AUDIT", "QA", "BUGFIX"))
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


def _print_step_banner(*, runtime: str, model: str, model_source: str, cursor, settings: LoopSettings) -> None:
    print("\n┌─ loop session ─────────────────────────────────────────────")
    print(f"│ runtime: {runtime} | model: {model} | source: {model_source}")
    print(f"│ epic: {cursor.epic_id} | role: {cursor.role} | phase: {cursor.phase} | step: {cursor.step_id}")
    print(f"│ attempt: {cursor.attempt + 1} | session: {cursor.session_id}")
    heartbeat = f"{settings.status_heartbeat}s" if settings.status_heartbeat is not None else "off"
    idle = f"{settings.stream_idle_timeout}s" if settings.stream_idle_timeout is not None else "off"
    print(
        f"│ limits: timeout={settings.session_timeout}s | heartbeat={heartbeat} | "
        f"idle_timeout={idle} | kill_grace={settings.session_kill_grace}s"
    )
    print("└────────────────────────────────────────────────────────────")


def _normalize_legacy_args(argv: list[str]) -> list[str]:
    """Keep the pre-Python-entrypoint ``<epic> <model>`` invocation working."""
    commands = {"run", "start", "finish", "halt", "rewind", "status", "doctor", "scope", "validate", "validate-verdict"}
    if len(argv) >= 2 and argv[0] not in commands and not argv[0].startswith("-"):
        return ["run", "--epic", argv[0], "--model", argv[1], *argv[2:]]
    return argv


def _phase_instruction(cursor, project: Path) -> str:
    role = cursor.role.upper()
    epic = cursor.epic_id
    if cursor.phase == "DECOMPOSE":
        return (
            f"Run {role} DECOMPOSE for plan {epic}. "
            f"Read the plan at {project / 'memory-bank' / cursor.role / 'plan' / epic / 'md' / 'plan.md'}. "
            "Create the canonical yaml/decompose-index.yaml and yaml/steps/sNN-*.yaml artifacts, "
            "run the structural and traceability gates, and do not write production code. "
        )
    if cursor.phase == "ANALYZE":
        return (
            f"Run {role} ANALYZE for plan {epic}. "
            "Read the canonical plan and decompose tree, create exactly one completed "
            f"analyze artifact under memory-bank/{cursor.role}/analyze/{epic}/ "
            "with metrics.critical_count=0 when the plan is implementable, and do not write production code. "
        )
    if cursor.phase in {"IMPLEMENT", "TASK", "REFACTOR"}:
        return (
            "Read the canonical YAML queue and current step artifact. Make the requested changes. "
            f"The implement artifact belongs under memory-bank/{cursor.role}/implement/{epic}/ "
            "without an implement- prefix on the epic directory. "
        )
    if cursor.phase == "BUGFIX":
        return (
            f"Run {role} BUGFIX for {epic}. Read bugfix-queue.yaml first, take only the first open or "
            "in_progress item, fix the root cause with regression evidence, and update the queue. "
        )
    if cursor.phase == "QA":
        return (
            f"Run {role} QA for {epic}. Run the required full verification checks, complete the entire "
            "check matrix, create one canonical qa-*.yaml artifact, and create or merge the bugfix queue "
            "when the verdict is FAIL or BLOCKED. "
        )
    if cursor.phase == "AUDIT":
        return (
            f"Run {role} AUDIT for {epic}. Audit only the current iteration against the bounded plan, "
            "decompose index, and completed implementation artifacts. Create audit.yaml with a complete "
            "check_matrix; do not change plan, code, or run tests. "
        )
    return "Read the canonical YAML queue and current phase artifact. Complete the phase contract. "


def _phase_gate_agent(phase: str) -> str | None:
    return LoopEngine._required_gate_agent(phase)


def _relative_paths(project: Path, paths: list[Path]) -> str:
    values: list[str] = []
    for path in paths:
        if not path.is_file():
            continue
        value = path.resolve().relative_to(project.resolve()).as_posix()
        if value not in values:
            values.append(value)
    return "\n".join(f"- {value}" for value in values)


def _gate_protocol(cursor, project: Path, gate_agent: str | None) -> str:
    role_root = project / "memory-bank" / cursor.role
    plan = role_root / "plan" / cursor.epic_id / "md" / "plan.md"
    index = role_root / "plan" / cursor.epic_id / "yaml" / "decompose-index.yaml"
    paths: list[Path] = [plan, index]
    try:
        queue = load_queue(project, cursor.role, cursor.epic_id)
    except (FileNotFoundError, ValueError):
        queue = None
    if queue is not None:
        for step in queue.steps:
            if step.shard:
                paths.append(queue.path.parent / "steps" / Path(step.shard).name)
    lines = [
        "",
        "Managed gate protocol (mandatory):",
        f"agent_type={gate_agent or 'parent-driven-audit'}",
        f"GATE_IDENTITY session_id={cursor.session_id} epic_id={cursor.epic_id} step_id={cursor.step_id}",
        "Copy the GATE_IDENTITY values verbatim into every machine result. Never derive session_id from epic_id, agent id, thread id, or directory name.",
    ]
    if gate_agent:
        lines.append(
            f"The required {gate_agent} spawn_agent call must put the exact first line "
            f"agent_type={gate_agent} in the child prompt. If recovery requires "
            "gate-repair, that child prompt must instead begin with agent_type=gate-repair."
        )
    if gate_agent == "verify-decompose":
        lines.extend(
            [
                "Required sections in the verify-decompose spawn prompt:",
                "ALLOW READ:",
                _relative_paths(project, paths),
                "The verifier must return one fenced loop-gate-verdict/v1 JSON object.",
            ]
        )
    elif gate_agent == "analyze-verify":
        analyze_path, _ = latest_analyze_with_path(project, cursor.role, cursor.epic_id)
        if analyze_path is not None:
            paths.insert(0, analyze_path)
        lines.extend(
            [
                "Required sections in the analyze-verify spawn prompt:",
                "FINDINGS:",
                "- List every finding id from the exact analyze artifact; write none only when the artifact proves zero findings.",
                "COVERAGE:",
                "- Verify the plan, decompose index, every referenced shard, index fingerprint, and metrics.critical_count.",
                "ALLOW READ:",
                _relative_paths(project, paths),
                "The verifier must return one fenced loop-gate-verdict/v1 JSON object.",
            ]
        )
    elif gate_agent == "verify-implement":
        current_step = None
        if queue is not None:
            current_step = next((step for step in queue.steps if step.step_id == cursor.step_id), None)
        if current_step is not None:
            paths.extend(
                [
                    implement_path(project, queue.role, queue.epic_id, current_step),
                    queue.path.parent / "steps" / Path(current_step.shard or f"{current_step.step_id}.yaml").name,
                ]
            )
        lines.extend(
            [
                "Required sections in the verify-implement spawn prompt:",
                "ALLOW READ:",
                _relative_paths(project, paths),
                "Add each concrete touched code or test file; never use a directory or glob.",
                "The verifier must return one fenced loop-gate-verdict/v1 JSON object.",
            ]
        )
    elif gate_agent == "verify-bugfix":
        paths = [bugfix_queue_path(project, cursor.role, cursor.epic_id), *bugfix_report_paths(project, cursor.role, cursor.epic_id), *paths]
        lines.extend(
            [
                "Required sections in the verify-bugfix spawn prompt:",
                "ALLOW READ:",
                _relative_paths(project, paths),
                "The verifier must return one fenced loop-gate-verdict/v1 JSON object.",
            ]
        )
    elif gate_agent == "verify-qa":
        qa_root = role_root / "qa" / cursor.epic_id
        qa_artifacts = sorted(qa_root.glob("qa-*.yaml")) if qa_root.is_dir() else []
        paths = [*qa_artifacts[-1:], bugfix_queue_path(project, cursor.role, cursor.epic_id), *paths]
        lines.extend(
            [
                "Required sections in the verify-qa spawn prompt:",
                "Suite results:",
                "- Include the exact parent-run command and its observed result; the verifier must not rerun the suite.",
                "ALLOW READ:",
                _relative_paths(project, paths),
                "The verifier must return one fenced loop-gate-verdict/v1 JSON object.",
            ]
        )
    lines.extend(
        [
            "",
            "Recovery protocol:",
            "1. A valid PASS is the only result that can cross the gate; do not call finish separately after a PASS.",
            "2. A content FAIL or BLOCKED with concrete product blockers requires gate-repair. Spawn gate-repair with:",
            "BLOCKERS:",
            "- <blocker_id> | <concrete_file> | <concrete_fix>",
            "ALLOW WRITE:",
            "- the same concrete files only",
            "VERIFY:",
            "- one exact verification command or typed capability check",
            "ALLOW READ:",
            "- optional concrete context files only",
            "Wait for one fenced loop-repair-result/v1 result, then rerun this same verifier. Do not finish between repair and re-verify.",
            "3. Protocol failures such as prompt_incomplete, verdict session mismatch, or verdict_transition_rejected are parent handoff failures. Fix the exact GATE_IDENTITY or required sections and respawn the same verifier; do not invent a product blocker and do not send protocol failures to gate-repair.",
            "4. AUDIT has no separate verify agent: an actionable audit finding follows the same gate-repair BLOCKERS/ALLOW WRITE/VERIFY contract, then the parent reruns AUDIT until audit.yaml is converged with no findings.",
        ]
    )
    return "\n".join(lines) + "\n"


def _gate_recovery_prompt(cursor, engine: LoopEngine) -> str:
    event = engine.store.latest_event_any(
        {"verdict_transition_rejected", "verdict_rejected", "repair_recorded", "verdict_recorded"}
    )
    if event is None:
        return ""
    if str(event.get("phase") or "") != cursor.phase or str(event.get("step_id") or "") != cursor.step_id:
        return ""
    event_name = str(event.get("event") or "")
    if event_name in {"verdict_transition_rejected", "verdict_rejected"}:
        return (
            "\nRecovery state: the previous gate handoff was rejected by the boundary. "
            "This is a protocol error, not a product blocker. Fix the exact parent prompt sections "
            "and the exact GATE_IDENTITY values, then respawn the same verifier. Do not call gate-repair "
            "for prompt/session/transition errors and do not finish.\n"
        )
    if event_name == "repair_recorded":
        return (
            f"\nRecovery state: gate-repair reported {event.get('status')}. "
            "Re-run the same verifier now with the same GATE_IDENTITY. Do not finish before a fresh PASS.\n"
        )
    if event_name == "verdict_recorded" and str(event.get("verdict") or "") in {"FAIL", "BLOCKED"}:
        agent = str(event.get("agent_id") or "the verifier")
        return (
            f"\nRecovery state: {agent} already returned {event.get('verdict')}. "
            "Do not finish or merely summarize the failure. Immediately spawn gate-repair with the "
            "structured BLOCKERS, concrete ALLOW WRITE, exact VERIFY, and optional ALLOW READ sections. "
            "Wait for loop-repair-result/v1, then respawn the same verifier with the same exact identity.\n"
        )
    return ""


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
        payload["elapsed_sec"] = result.elapsed_sec
        payload["heartbeat_count"] = result.heartbeat_count
        payload["hung"] = result.hung
        if result.message:
            payload["detail"] = result.message
    if args.json:
        _print(payload, True)
        return
    print("loop error:", file=sys.stderr)
    for key in (
        "error", "runtime", "model", "epic_id", "role", "phase", "step_id",
        "attempt", "status", "exit_code", "elapsed_sec", "heartbeat_count",
        "hung", "detail", "session_log", "cursor_path",
    ):
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
    os.environ.setdefault("DEV_HUB", str(paths.hub))
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
    runtime = runtime_for(runtime_name, settings=settings, progress=not args.json)
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
            "Execution policy: approvals are disabled. Never request escalation, require_escalated permissions, "
            "or a second sandbox; run commands with the permissions already available and report a real denial.\n"
        )
        prompt += _phase_instruction(cursor, paths.project)
        gate_agent = _phase_gate_agent(cursor.phase)
        prompt += (
            "When the phase work is genuinely complete, spawn the required gate before any finish attempt. "
            "Do not edit cursor.json or generated activeContext.md. "
            "A managed gate subagent PASS is validated by the boundary hook and finishes this phase atomically; "
            "a direct finish without the required PASS is rejected and prose verdicts are not machine state."
        )
        if gate_agent:
            prompt += (
                f" This phase requires exactly one {gate_agent} pre-finish gate before finish. "
                f"Spawn it after the phase work; its response must contain one valid loop-gate-verdict/v1 JSON fence."
            )
            prompt += _gate_protocol(cursor, paths.project, gate_agent)
        elif cursor.phase == "AUDIT":
            prompt += " AUDIT has no verifier gate: actionable findings require gate-repair and a repeated AUDIT before QA."
            prompt += _gate_protocol(cursor, paths.project, None)
        prompt += _gate_recovery_prompt(cursor, engine)
        prompt = f"{prompt}\n\n{engine.boundary.context(cursor)}"
        if not args.json:
            _print_step_banner(
                runtime=runtime_name,
                model=model,
                model_source=selection.source,
                cursor=cursor,
                settings=settings,
            )
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
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    args = _parser().parse_args(_normalize_legacy_args(raw_argv))
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
            schema = args.schema
            if args.command == "validate-verdict":
                try:
                    candidate = json.loads(args.payload)
                except (TypeError, json.JSONDecodeError):
                    candidate = {}
                schema = str(candidate.get("schema") or SCHEMA_GATE_VERDICT) if isinstance(candidate, dict) else SCHEMA_GATE_VERDICT
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
        if args.command == "rewind":
            if not args.phase:
                _print({"ok": False, "error": "--phase is required for rewind"}, args.json)
                return 2
            transition = engine.rewind(args.phase, reason=args.reason)
            _print(
                {"event": transition.event, "status": transition.status.value, "phase": transition.phase, "step_id": transition.step_id},
                args.json,
            )
            return 0
        return run(args)
    except (ValueError, FileNotFoundError, TransitionError) as exc:
        _print({"ok": False, "error": str(exc)}, True)
        return 2
