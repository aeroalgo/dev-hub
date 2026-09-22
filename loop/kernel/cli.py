from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from ..config import LoopSettings
from ..config import activate_loop_process
from .engine import LoopEngine, TransitionError
from .boundary import BoundaryService
from .analyze import latest_analyze_with_path
from .index import (
    bugfix_queue_path,
    bugfix_report_paths,
    implement_path,
    load_queue,
    phase_artifacts,
    phase_payload,
)
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
    collaboration = (
        f"{settings.collaboration_wait_timeout}s"
        if settings.collaboration_wait_timeout is not None
        else "off"
    )
    print(
        f"│ limits: timeout={settings.session_timeout}s | heartbeat={heartbeat} | "
        f"idle_timeout={idle} | collab_wait={collaboration} | "
        f"kill_grace={settings.session_kill_grace}s"
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
            "in_progress item, fix the root cause with regression evidence, update the queue, and create or "
            "update one bugfix-*.md report with concrete changed paths, AC+/AC− evidence, and verification "
            "before spawning verify-bugfix. Mark a completed queue item as done; do not introduce a new "
            "status value such as closed. "
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


def _qa_prompt_items(payload: dict[str, object], key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, (str, int, float)) and str(item).strip()]


def _qa_gate_context(project: Path, cursor) -> tuple[list[str], list[Path]]:
    qa_artifacts = phase_artifacts(project, cursor.role, cursor.epic_id, "qa")
    qa_path = qa_artifacts[-1] if qa_artifacts else None
    payload = phase_payload(qa_path) if qa_path is not None else None
    if qa_path is None or payload is None:
        return [
            "suite_scope: full",
            "Suite results:",
            "- missing: parent must provide the exact suite command and observed result",
            "## Frozen QA checklist",
            "checklist_sha256: <missing>",
            "### AC+",
            "- none",
            "### AC−",
            "- none",
            "### §0.11",
            "- none",
            "### Prior blockers",
            "- none",
        ], [qa_path] if qa_path is not None else []

    verify_scope = str(payload.get("verify_scope") or "full").strip().lower()
    suite_scope = str(payload.get("suite_scope") or ("targeted" if verify_scope == "prior_only" else "full"))
    lines = [f"suite_scope: {suite_scope}", "Suite results:"]
    suite = _qa_prompt_items(payload, "suite")
    lines.extend(f"- {item}" for item in suite or ["missing: parent must provide the exact suite command and observed result"])
    lines.extend(
        [
            "## Frozen QA checklist",
            f"checklist_sha256: {str(payload.get('checklist_sha256') or '<missing>')}",
        ]
    )
    for heading, key in (("AC+", "ac_plus"), ("AC−", "ac_minus"), ("§0.11", "section_011"), ("Prior blockers", "prior_blockers")):
        lines.append(f"### {heading}")
        items = _qa_prompt_items(payload, key)
        lines.extend(f"- {item}" for item in items or ["none"])
    return lines, [qa_path]


def _bugfix_gate_paths(project: Path, role: str, epic_id: str) -> tuple[list[Path], bool]:
    """Pack the bounded evidence set required by verify-bugfix.

    The verifier needs the queue, its report, the source QA artifact, and the
    concrete files named by the queue. Plan/index shards are not part of this
    gate contract and can make ALLOW READ exceed the protocol limit.
    """
    queue_path = bugfix_queue_path(project, role, epic_id)
    paths: list[Path] = []
    seen: set[str] = set()

    def add(path: Path | None) -> None:
        if path is None or len(paths) >= 10:
            return
        resolved = path.resolve()
        key = str(resolved)
        if key not in seen:
            seen.add(key)
            paths.append(path)

    add(queue_path)
    reports = bugfix_report_paths(project, role, epic_id)
    for report in reports:
        add(report)

    payload = phase_payload(queue_path)
    if isinstance(payload, dict):
        source_qa = payload.get("source_qa")
        if isinstance(source_qa, str) and source_qa.strip():
            source_path = Path(source_qa.strip())
            add(source_path if source_path.is_absolute() else project / source_path)

    for report in reports:
        try:
            report_lines = report.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        in_target_section = False
        for line in report_lines:
            normalized = line.strip().lower()
            if "target files" in normalized or normalized in {"## changed files", "### changed files"}:
                in_target_section = True
                continue
            if in_target_section and normalized.startswith("#"):
                in_target_section = False
            if not in_target_section or not line.lstrip().startswith("-"):
                continue
            for target in re.findall(r"`([^`]+)`", line):
                if "/" not in target or target.startswith(("http://", "https://")):
                    continue
                target_path = Path(target.strip())
                add(target_path if target_path.is_absolute() else project / target_path)

    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                targets = item.get("targets")
                if not isinstance(targets, list):
                    continue
                for target in targets:
                    if isinstance(target, str) and target.strip():
                        target_path = Path(target.strip())
                        add(target_path if target_path.is_absolute() else project / target_path)

    return paths, bool(reports)


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
        paths, report_ready = _bugfix_gate_paths(project, cursor.role, cursor.epic_id)
        lines.extend(
            [
                (
                    "BUGFIX gate precondition: create or update bugfix-queue.yaml and one bugfix-*.md "
                    "report before spawning verify-bugfix."
                    if not report_ready
                    else "BUGFIX gate evidence is packed below; do not add plan/index/step paths to ALLOW READ."
                ),
                "Required sections in the verify-bugfix spawn prompt:",
                "ALLOW READ:",
                _relative_paths(project, paths),
                "The verifier must return one fenced loop-gate-verdict/v1 JSON object.",
            ]
        )
    elif gate_agent == "verify-qa":
        qa_context, qa_paths = _qa_gate_context(project, cursor)
        paths = [*qa_paths, bugfix_queue_path(project, cursor.role, cursor.epic_id), *paths]
        lines.extend(
            [
                "Required sections in the verify-qa spawn prompt:",
                *qa_context,
                "ALLOW READ:",
                _relative_paths(project, paths),
                "The verifier must return one fenced loop-gate-verdict/v1 JSON object.",
            ]
        )
    lines.extend(
        [
            "",
            "Recovery protocol:",
            "1. A valid PASS crosses the gate atomically; do not call finish separately after a PASS.",
            "1a. verify-qa FAIL is a product QA result, not a gate-repair request. When the QA artifact is FAIL/BLOCKED and bugfix-queue.yaml is valid, the boundary routes QA to BUGFIX atomically.",
            "1b. verify-qa BLOCKED, or QA FAIL without a valid QA artifact/queue, requires the parent to fix the missing contract/artifact and respawn verify-qa; do not invent a blocker.",
            "2. A content FAIL or BLOCKED for other gates with concrete product blockers requires gate-repair. Spawn gate-repair with:",
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
    event_phase = str(event.get("phase") or event.get("source_phase") or "")
    if event_phase and event_phase != cursor.phase:
        return ""
    if str(event.get("step_id") or "") != cursor.step_id:
        return ""
    if not event_phase and not all(
        str(event.get(field) or "") == expected
        for field, expected in (
            ("session_id", cursor.session_id),
            ("epic_id", cursor.epic_id),
        )
    ):
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
        if cursor.phase == "QA" and str(event.get("verdict") or "") == "FAIL":
            return (
                f"\nRecovery state: {agent} returned FAIL, but the QA failure could not be routed to BUGFIX yet. "
                "Write/update the canonical qa-*.yaml with verdict: fail and eligible blockers, create or merge "
                "bugfix-queue.yaml, then call the generated Handoff finish command once. The boundary will reconcile "
                "the recorded FAIL and route QA to BUGFIX atomically; only respawn verify-qa if the artifact or queue "
                "is invalid. Do not send a product QA failure to gate-repair.\n"
            )
        return (
            f"\nRecovery state: {agent} already returned {event.get('verdict')}. "
            "Do not finish or merely summarize the failure. Classify the verifier's concrete finding first: "
            "prompt/contract failures (prompt_incomplete, missing or oversized ALLOW READ, missing artifact, "
            "schema, session or transition mismatch) are fixed by the parent and sent back to the same verifier; "
            "a concrete product or repairable runtime blocker requires gate-repair with structured BLOCKERS, "
            "concrete ALLOW WRITE, exact VERIFY, and optional ALLOW READ. After gate-repair, wait for "
            "loop-repair-result/v1 and respawn the same verifier with the same exact identity.\n"
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
