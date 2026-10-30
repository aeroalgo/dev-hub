from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from ..config import LoopSettings
from ..config import activate_loop_process
from ..diagnostics import capture_exception
from .engine import LoopEngine, TransitionError
from .boundary import BoundaryService
from .evidence import evidence_file_ref
from .index import (
    bugfix_queue_path,
    bugfix_queue_state,
    sync_bugfix_queue_evidence,
    bugfix_report_paths,
    decompose_yaml_problems,
    execute_path,
    implement_path,
    index_path,
    load_queue,
    phase_artifacts,
    phase_payload,
    plan_path,
    resolve_epic_kind,
    resolve_epic_role,
)
from .runtime import runtime_for
from .session import SessionOutcome, SessionSupervisor
from .store import LoopPaths
from .pre_emit import write_pre_emit_stamp
from .verdict import SCHEMA_GATE_VERDICT, validate_boundary
from ..board_projection.docs_publish import publish_board_docs
from ..board_projection.project_docs import publish_project_docs
from ..board_projection.service import project_after_transition, project_epic_phase


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="single-cursor loop")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=(
            "run",
            "start",
            "finish",
            "halt",
            "rewind",
            "status",
            "doctor",
            "scope",
            "check-bugfix-queue",
            "sync-bugfix-queue",
            "validate",
            "validate-verdict",
            "implement-flush",
            "board-sync",
            "board-docs",
            "project-docs",
        ),
    )
    parser.add_argument("--project", "--cwd", dest="project")
    parser.add_argument("--epic")
    parser.add_argument("--role", default="auto", help="back|front|app|integration(legacy)|auto (discover under memory-bank/<role>/{,refactor/,security/}plan/<epic>)")
    parser.add_argument(
        "--kind",
        choices=("feature", "refactor", "security"),
        default=None,
        help="feature|refactor|security (layout under memory-bank/<role>/{,refactor/,security/}plan/<epic>)",
    )
    parser.add_argument("--runtime", choices=("claude", "codex"), default=None)
    parser.add_argument("--model")
    parser.add_argument(
        "--effort",
        "--model-reasoning-effort",
        dest="effort",
        choices=("low", "medium", "high", "xhigh"),
        default=None,
        help="Codex model_reasoning_effort override (omit = use ~/.codex/config.toml)",
    )
    parser.add_argument("--step")
    parser.add_argument(
        "--phase",
        choices=("DECOMPOSE", "CREATIVE", "QA", "BUGFIX", "SECURITY", "DONE", "PLAN", "IMPLEMENT", "HALT"),
        help="rewind target phase; board-sync may pass DONE/BUGFIX to force column",
    )
    parser.add_argument("--reason", default="manual halt")
    parser.add_argument("--payload")
    parser.add_argument("--schema")
    parser.add_argument("--timeout", type=int)
    parser.add_argument("--max-attempts", type=int)
    parser.add_argument("--max-steps", type=int)
    parser.add_argument("--backoff", type=float)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument(
        "--no-plan",
        action="store_true",
        help="board-docs: attach only prompt.md (skip plan.md)",
    )
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="board-docs: attach only plan.md (skip prompt.md)",
    )
    parser.add_argument(
        "--file",
        action="append",
        dest="docs_files",
        default=[],
        help="project-docs: extra repo-relative file to publish (repeatable)",
    )
    parser.add_argument(
        "--folder",
        default=None,
        help="project-docs: Disk/pages folder name (default from config project_docs.folder_name)",
    )
    parser.add_argument(
        "--title",
        default="",
        help="board-sync: card title (skip prompt.md ## Board when set with --summary)",
    )
    parser.add_argument(
        "--summary",
        default="",
        help="board-sync: card description/summary (in-memory; no prompt.md required)",
    )
    return parser


def _print(value: object, as_json: bool = True) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(value)


def _project_transition(
    *,
    project_root: Path,
    epic_id: str,
    phase: str,
    role: str,
    kind: str | None = None,
    status: object | None = None,
    metadata: dict[str, object] | None = None,
    source: str = "transition",
):
    """Mirror every committed cursor transition to the external board."""
    if not epic_id:
        return None
    status_value = getattr(status, "value", status)
    phase_to_project = (
        "DONE"
        if phase == "DONE" or status_value == "complete"
        else phase
    )
    try:
        return project_after_transition(
            project_root=project_root,
            epic_id=epic_id,
            phase=phase_to_project,
            role=role,
            kind=kind,
        )
    except Exception as exc:
        # The local cursor is the source of truth; board projection is a
        # recoverable mirror and must not undo a committed transition.
        report = capture_exception(
            exc,
            operation="board_projection.transition",
            project_root=project_root,
            context={
                "epic_id": epic_id,
                "phase": phase_to_project,
                "role": role,
                "source": source,
            },
        )
        sys.stderr.write(
            f"Board projection error after {source}: {exc} "
            f"[diagnostic {report['error_id']}]\n"
        )
        return None


def _projection_fields(result) -> dict[str, object]:
    if result is None:
        return {}
    fields = {
        "projection_status": result.status,
        "projection_disabled_reason": result.disabled_reason,
    }
    if result.diagnostic_id:
        fields["projection_diagnostic_id"] = result.diagnostic_id
    if result.diagnostic_path:
        fields["projection_diagnostic_path"] = result.diagnostic_path
    if result.error:
        fields["projection_error"] = result.error
    return fields


def _project_cursor_transition(*, project_root: Path, cursor_before, cursor_after, transition=None, source: str):
    """Project a committed cursor change, including implicit boundary changes.

    At a roadmap boundary the old epic becomes DONE while the new cursor phase
    belongs to the next epic. Boundary hooks can commit that change before the
    session supervisor returns, so ``transition`` may be unavailable; the
    before/after cursors remain the source of truth in that case.
    """
    if (
        cursor_before is not None
        and cursor_after is not None
        and cursor_before.epic_id
        and cursor_after.epic_id
        and cursor_before.epic_id != cursor_after.epic_id
    ):
        completed_projection = _project_transition(
            project_root=project_root,
            epic_id=cursor_before.epic_id,
            phase="DONE",
            role=cursor_before.role,
            kind=cursor_before.kind,
            source=f"{source}:completed-epic",
        )
        active_projection = _project_transition(
            project_root=project_root,
            epic_id=cursor_after.epic_id,
            phase=cursor_after.phase,
            role=cursor_after.role,
            kind=cursor_after.kind,
            status=cursor_after.status,
            source=f"{source}:next-epic",
        )
        return active_projection, completed_projection

    if cursor_before is None or not cursor_before.epic_id:
        return None, None

    phase = transition.phase if transition is not None else cursor_after.phase
    status = transition.status if transition is not None else cursor_after.status
    metadata = transition.metadata if transition is not None else None
    projection = _project_transition(
        project_root=project_root,
        epic_id=cursor_before.epic_id,
        phase=phase,
        role=cursor_before.role,
        kind=cursor_before.kind,
        status=status,
        metadata=metadata,
        source=source,
    )
    return projection, None


def _project_finish_transition(*, project_root: Path, cursor_before, cursor_after, transition):
    """Project both sides when an explicit finish advances the roadmap."""
    return _project_cursor_transition(
        project_root=project_root,
        cursor_before=cursor_before,
        cursor_after=cursor_after,
        transition=transition,
        source="finish",
    )


def _print_step_banner(
    *,
    runtime: str,
    model: str,
    model_source: str,
    cursor,
    settings: LoopSettings,
    effort: str | None = None,
) -> None:
    print("\n┌─ loop session ─────────────────────────────────────────────")
    effort_label = effort if effort else "config"
    print(f"│ runtime: {runtime} | model: {model} | effort: {effort_label} | source: {model_source}")
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
    commands = {
        "run",
        "start",
        "finish",
        "halt",
        "rewind",
        "status",
        "doctor",
        "scope",
        "check-bugfix-queue",
        "sync-bugfix-queue",
        "validate",
        "validate-verdict",
        "implement-flush",
        "board-sync",
        "board-docs",
        "project-docs",
    }
    if len(argv) >= 2 and argv[0] not in commands and not argv[0].startswith("-"):
        return ["run", "--epic", argv[0], "--model", argv[1], *argv[2:]]
    return argv


_ROLE_RULES_DIR = {
    "back": "back_developer",
    "front": "front_developer",
    "app": "app_developer",
    # legacy memory-bank/integration/* epics still resolve role=integration; rules = FRONT (wire)
    "integration": "front_developer",
    "integ": "front_developer",
}


def _role_rules_dir(role: str) -> str:
    key = str(role or "back").strip().lower()
    return _ROLE_RULES_DIR.get(key, f"{key}_developer")


def _code_phase_bootstrap(cursor, project: Path) -> str:
    """Force sole code-phase load order (implement-bootstrap.mdc) — do not rely on AGENTS alone."""
    role_rules = _role_rules_dir(cursor.role)
    mode = str(cursor.phase or "IMPLEMENT").strip().lower()
    bootstrap = ".cursor/rules/shared/_lean/implement-bootstrap.mdc"
    lean = f".cursor/rules/{role_rules}/isolation_rules/_lean/{mode}.mdc"
    workflow = f".cursor/rules/{role_rules}/workflow-{mode}.mdc"
    scope_lock = ".cursor/rules/shared/workflow-implement-scope-lock.mdc"
    active = project / "memory-bank" / "activeContext.md"
    epic = cursor.epic_id
    step = cursor.step_id
    role_mb = cursor.role
    return (
        f"HARD bootstrap BEFORE any exploration, coding, or tests "
        f"(sole SoT: {bootstrap} — do not skip; do not load mainrule.mdc monolith): "
        f"1) Read {bootstrap}. "
        f"2) Read {active} and ONLY its load_now paths. "
        f"3) Read {lean} (Gates). "
        f"4) Read {scope_lock}. "
        f"5) Read the ## Hot path section of {workflow} "
        "(role delta only; do not load the full workflow file unless Hot path is missing/FAIL). "
        f"6) Read the current step shard for {step} under "
        f"memory-bank/{role_mb}/plan/{epic}/yaml/steps/ (or the exact load_now shard path); "
        "follow its plan_jumps (bounded), files:, verify:, checkpoints, tdd:, skills.impl. "
        "FORBIDDEN until those bootstrap Reads exist in this session: repo-wide find/ls tourism, "
        "git status as discovery, `bin/pytest -q` / full suite without path or -k, any test command "
        "not listed in the current step verify:/checkpoints. "
        f"ALLOWED tests during {cursor.phase}: only the exact targeted commands from the current step "
        "verify: and checkpoints[].verify. "
        f"Full suite is QA only — never {cursor.phase}. "
        "After bootstrap: make the requested changes. "
        f"The implement artifact belongs under memory-bank/{role_mb}/implement/{epic}/ "
        "without an implement- prefix on the epic directory. "
    )


def _security_phase_bootstrap(cursor, project: Path) -> str:
    """Force SECURITY execute load order — workflow + gates; never implement-bootstrap."""
    role_rules = _role_rules_dir(cursor.role)
    role = str(cursor.role or "back").strip().upper()
    workflow = f".cursor/rules/{role_rules}/workflow-security.mdc"
    lean_shared = ".cursor/rules/shared/_lean/security.mdc"
    lean_role = f".cursor/rules/{role_rules}/isolation_rules/_lean/security.mdc"
    epic_paths = ".cursor/rules/shared/workflow-security-epic.mdc"
    active = project / "memory-bank" / "activeContext.md"
    epic = cursor.epic_id
    step = cursor.step_id
    role_mb = cursor.role
    return (
        f"HARD SECURITY bootstrap BEFORE any exploration or audit evidence "
        f"(do not skip; do not use implement-bootstrap.mdc; do not load mainrule.mdc monolith): "
        f"1) Read {workflow} — section C SECURITY execute is SoT. "
        f"2) Read {lean_shared} and {lean_role} (Gates). "
        f"3) Read {epic_paths} (path rule: epic → only security/implement/…/aNN-*.yaml). "
        f"4) Read {active} and ONLY its load_now paths. "
        f"5) Read the current decompose step shard for {step} under "
        f"memory-bank/{role_mb}/security/plan/{epic}/yaml/steps/ "
        "(or the exact load_now shard path); follow audit_surface, scope, threats, checkpoints, "
        "and Audit skills listed on the step — Read those SKILL.md paths before auditing. "
        f"6) Write/update findings only in memory-bank/{role_mb}/security/implement/{epic}/"
        f"{step}-*.yaml (schema: epic-security/v1). "
        f"Run {role} SECURITY for {epic} step {step}: audit only; code_changed: no. "
        "FORBIDDEN until those bootstrap Reads exist in this session: repo-wide find/ls tourism, "
        "git status as discovery, production code edits, root security-audit-*.md while an epic "
        "YAML tree is active, dual-writing implement + root audit. "
        "Before finish: spawn verify-security, then "
        f"`python3 $DEV_HUB/bin/loop.py finish --project <cwd> --step {step}`. "
    )


def _phase_instruction(cursor, project: Path, engine: LoopEngine | None = None) -> str:
    role = cursor.role.upper()
    epic = cursor.epic_id
    if cursor.phase == "DECOMPOSE":
        return (
            f"Run {role} DECOMPOSE for plan {epic}. "
            f"Read the plan at {project / 'memory-bank' / cursor.role / 'plan' / epic / 'md' / 'plan.md'}. "
            "Create yaml/decompose-index.yaml + yaml/steps/sNN-*.yaml (L1→1 / L2→2 / L3→3 sNN_cap). "
            "Prefer single-quoted or block scalars for rg patterns. One index step ↔ one steps file. "
            "HARD before promotion: spawn verify-decompose (ALLOW READ: plan + index + shards). "
            "The agent performs both structural and semantic/traceability checks; its PASS "
            "atomically promotes DECOMPOSE → IMPLEMENT/CREATIVE and ends this parent session; "
            "do not call loop.py finish after the gate. "
            "No separate user review phase. Do not write production code. "
        )
    if cursor.phase in {"ANALYZE", "AUDIT", "CONTEXT_SYNC"}:
        return (
            f"{cursor.phase} is not a loop phase for {epic}. "
            "Use the current DECOMPOSE/verify-decompose and QA/context-sync contracts; "
            "the next valid product gate is QA. "
        )
    if cursor.phase == "CREATIVE":
        return (
            f"Run {role} CREATIVE for plan {epic} step {cursor.step_id}. "
            "Resolve the open design CR (needs_creative) for this work shard: write "
            f"memory-bank/{cursor.role}/creative/{epic}/creative-*.md, then rewire the shard to "
            "`needs_creative: yes (CR-…) — **closed**` (index `yes (CR-…) ✅`) and keep the same "
            "step pending — do not mark it completed and do not write production code. "
            "FORBIDDEN: spawn verify agents for CREATIVE. Finish only after the gate is closed. "
        )
    if cursor.phase in {"IMPLEMENT", "TASK", "REFACTOR"}:
        return _code_phase_bootstrap(cursor, project)
    if cursor.phase == "SECURITY":
        return _security_phase_bootstrap(cursor, project)
    if cursor.phase == "BUGFIX":
        return (
            f"Run {role} BUGFIX for {epic}. "
            + _bugfix_swarm_protocol(cursor, project)
        )
    if cursor.phase == "QA":
        if engine is not None and engine.qa_context_sync_pending(cursor):
            return (
                f"QA PASS is already accepted for {epic}. Do not spawn verify-qa again. "
                "Spawn exactly one agent_type=context-sync with fork_context=false, let it write "
                f"memory-bank/{cursor.role}/context-sync/{epic}/sync-*.md, and do not call finish; "
                "a valid done result atomically completes QA and ends this parent session. "
                "The final response MUST contain exactly one fenced JSON object: opening fence "
                "```json, schema loop-context-sync-result/v1, and closing fence ```; emit no bare JSON "
                "and no prose outside the fence. Run loop.py validate with that exact payload before emitting it. "
            )
        if cursor.role == "app":
            return (
                f"Run APP QA for {epic}. HARD order: "
                "1) Freeze the mixed charter: backend, frontend_build, browser, live_smoke, and "
                "wire_journey when required. "
                "1b) Set suite_scope: app_lanes in the app-qa/v1 artifact; APP QA never uses "
                "suite_scope: full. "
                "1c) If a runtime lane rewrites an evidence_file already referenced by BUGFIX, "
                "the BUGFIX preflight/gate automatically refreshes its typed anchors before finish QA. "
                "1a) Build test_plan from .cursor/templates/qa/test-catalog.yaml and the current "
                "implement shard/contract/diff; account for every catalog item as selected, "
                "not_applicable with a reason, or not_run with a next action. Keep concrete "
                "commands and runtime details in shards, stack profiles, and lanes. "
                "2) Run every required lane as separate parent-owned evidence; suite_wrong_stack "
                "does not reject the backend+frontend mix inside APP. "
                "3) Write ONE app-qa/v1 qa-*.yaml with verdict pass|fail|blocked before verify-qa. "
                "4) fail|blocked → app bugfix-queue + verify-qa + finish QA → APP BUGFIX "
                "(bugfix-fix×≤3). "
                "5) pass → verify-qa PASS, then spawn agent_type=context-sync "
                f"(write memory-bank/{cursor.role}/context-sync/{epic}/sync-*.md); context-sync done "
                "atomically finishes APP QA → DONE/next epic, so the parent must not call finish afterward. "
                "No separate integration phase. FORBIDDEN: finish APP QA before context-sync result. "
            )
        return (
            f"Run {role} QA for {epic}. HARD order: "
            "1) Iteration contract: every FR/AC/delete of current iteration has evidence. "
            "1a) Build test_plan from .cursor/templates/qa/test-catalog.yaml and the current "
            "implement shard/contract/diff; account for every catalog item as selected, "
            "not_applicable with a reason, or not_run with a next action. Keep concrete "
            "commands and runtime details in shards, stack profiles, and lanes. "
            "2) Full verification suite (+ live_smoke when BACK). "
            "3) Write ONE qa-*.yaml with verdict pass|fail|blocked before verify-qa. "
            "4) fail|blocked → bugfix-queue + verify-qa + finish QA → BUGFIX (bugfix-fix×≤3). "
            "5) pass → verify-qa PASS, then spawn agent_type=context-sync "
            f"(write memory-bank/{cursor.role}/context-sync/{epic}/sync-*.md); context-sync done "
            "atomically finishes QA → DONE/next epic, so the parent must not call finish afterward. "
            "No separate review or sync phase. FORBIDDEN: finish QA before context-sync result. "
        )
    return "Read the canonical YAML queue and current phase artifact. Complete the phase contract. "



def _bugfix_open_item_ids(project: Path, role: str, epic_id: str) -> list[str]:
    path = bugfix_queue_path(project, role, epic_id)
    payload = phase_payload(path)
    if not isinstance(payload, dict):
        return []
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    open_ids: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").strip().lower()
        if status not in {"open", "in_progress"}:
            continue
        item_id = str(item.get("id") or "").strip()
        if item_id:
            open_ids.append(item_id)
    return open_ids


def _bugfix_swarm_protocol(cursor, project: Path) -> str:
    """Parent BUGFIX contract: spawn named bugfix-fix workers (≤3), then verify-bugfix."""
    queue = bugfix_queue_path(project, cursor.role, cursor.epic_id)
    try:
        queue_rel = str(queue.relative_to(project))
    except ValueError:
        queue_rel = str(queue)
    open_ids = _bugfix_open_item_ids(project, cursor.role, cursor.epic_id)
    open_line = ", ".join(open_ids) if open_ids else "(read queue — no open ids parsed yet)"
    return (
        f"Close ALL open/in_progress items in this single parent session. "
        f"Queue SoT: {queue_rel}. Open/in_progress now: {open_line}. "
        "SWARM (HARD): spawn managed agent_type=bugfix-fix (alias bugfix) with fork_context=false; "
        "max 3 concurrent; each child gets exactly ONE QUEUE_ITEM. "
        "Wave only disjoint ALLOW WRITE paths; overlapping paths → next wave (still ≤3). "
        "After each child loop-bugfix-fix-result/v1 status=done: merge queue (item done+done_at+evidence) "
        "and append to one bugfix-*.md. "
        "RUNTIME TIMESTAMP CONTRACT (HARD): evidence_file.timestamp is the only SoT clock. "
        "Copy that exact ISO timestamp into item.done_at and verification.last_run_at. "
        "RUNTIME ANCHOR REFRESH (HARD): if a later browser/live/HTTP VERIFY rewrites a declared "
        "evidence_file, `check-bugfix-queue` automatically copies the new valid evidence timestamp "
        "into affected done_at/last_run_at anchors and never moves an anchor backwards. Use "
        "`sync-bugfix-queue` only for an explicit diagnostic/reconciliation pass. "
        "FORBIDDEN: wall-clock done_at/last_run_at; preserving an old evidence.timestamp across a new VERIFY run; "
        "spawn verify-bugfix while anchors disagree with evidence.timestamp. "
        "After queue close: run "
        "`python3 $DEV_HUB/bin/loop.py check-bugfix-queue --project \"$PROJECT_ROOT\" --json` "
        "and require ok:true before spawning verify-bugfix. "
        "Spawn template per item:\n"
        "  agent_type=bugfix-fix\n"
        f"  GATE_IDENTITY session_id={cursor.session_id} epic_id={cursor.epic_id} step_id=BUGFIX\n"
        "  QUEUE_ITEM: <id>\n"
        f"  QUEUE: {queue_rel}\n"
        "  ALLOW WRITE:\n"
        "  - <paths for this bug only ≤10>\n"
        "  VERIFY:\n"
        "  - <targeted command>\n"
        "  SYMPTOM: <optional>\n"
        "Child validates via `loop.py validate --schema loop-bugfix-fix-result/v1`. "
        "FORBIDDEN: invent other fix agent types; one child fixing 2+ items; parent exit while open remain; "
        "PROGRESS_CONTINUE. When ALL items terminal and check-bugfix-queue ok:true: spawn verify-bugfix, "
        "accepted PASS atomically advances BUGFIX to re-QA; do not call finish again for BUGFIX "
        "after the gate has been accepted. "
    )


def _phase_gate_agent(phase: str) -> str | None:
    return LoopEngine._required_gate_agent(phase)


def _relative_paths(project: Path, paths: list[Path]) -> str:
    values: list[str] = []
    for path in paths:
        if not path.is_file():
            continue
        try:
            # Preserve the project-visible path for symlinked harness files
            # (for example, product/.cursor/templates -> dev-hub/harness).
            value = path.absolute().relative_to(project.absolute()).as_posix()
        except ValueError:
            try:
                value = path.resolve().relative_to(project.resolve()).as_posix()
            except ValueError:
                value = str(path.resolve())
        if value not in values:
            values.append(value)
    return "\n".join(f"- {value}" for value in values)


def _qa_prompt_items(payload: dict[str, object], key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, (str, int, float)) and str(item).strip()]


def _qa_prompt_value(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if value is None:
        return "missing: parent must provide this QA section"
    if isinstance(value, (dict, list)):
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        rendered = str(value).strip()
    return rendered[:12000] or "missing: parent must provide this QA section"


def _qa_gate_context(project: Path, cursor) -> tuple[list[str], list[Path]]:
    role = str(getattr(cursor, "role", "") or "").strip().lower()
    default_suite_scope = "app_lanes" if role == "app" else "full"
    qa_artifacts = phase_artifacts(project, cursor.role, cursor.epic_id, "qa")
    qa_path = qa_artifacts[-1] if qa_artifacts else None
    payload = phase_payload(qa_path) if qa_path is not None else None
    if qa_path is None or payload is None:
        return [
            f"suite_scope: {default_suite_scope}",
            *(["QA role: app", "APP QA contract: suite_scope must be app_lanes; explicit full is invalid."] if role == "app" else []),
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
            "## Test plan",
            "missing: parent must provide scope-driven selected/not_applicable/not_run catalog entries",
            "## QA evidence packs",
            "### coverage_map",
            "missing: parent must provide AC/BN → browser/API scenario → evidence",
            "### review",
            "missing: parent must provide review status/findings",
            "### test_audit",
            "missing: parent must provide weakened-test/mock/skip/CI audit",
            "### browser",
            "missing: parent must provide browser stack/journey/artifacts or explicit skip reason",
            "### retro",
            "missing: parent must provide missed defect, redundant gate, flaky test, next-cycle change",
        ], [qa_path] if qa_path is not None else []

    verify_scope = str(payload.get("verify_scope") or "full").strip().lower()
    suite_scope = str(
        payload.get("suite_scope")
        or ("app_lanes" if role == "app" else ("targeted" if verify_scope == "prior_only" else "full"))
    ).strip().lower()
    lines = [f"suite_scope: {suite_scope}"]
    if role == "app":
        lines.extend(
            [
                "QA role: app",
                "APP QA contract: suite_scope must be app_lanes; explicit full is invalid.",
            ]
        )
    lines.append("Suite results:")
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
    lines.extend(
        [
            "## Test plan",
            _qa_prompt_value(payload, "test_plan"),
            "## QA evidence packs",
            "### coverage_map",
            _qa_prompt_value(payload, "coverage_map"),
            "### review",
            _qa_prompt_value(payload, "review"),
            "### test_audit",
            _qa_prompt_value(payload, "test_audit"),
            "### browser",
            _qa_prompt_value(payload, "browser"),
            "### retro",
            _qa_prompt_value(payload, "retro"),
        ]
    )
    evidence_paths: list[Path] = [qa_path]
    catalog_path = project / ".cursor/templates/qa/test-catalog.yaml"
    if not catalog_path.is_file():
        catalog_path = Path(__file__).resolve().parents[2] / "harness/cursor/templates/qa/test-catalog.yaml"
    if catalog_path.is_file():
        evidence_paths.append(catalog_path)
    for section_name in ("live_smoke", "browser"):
        section = payload.get(section_name)
        reference = evidence_file_ref(section)
        if reference:
            candidate = Path(reference)
            evidence_paths.append(candidate if candidate.is_absolute() else project / candidate)
    coverage_map = payload.get("coverage_map")
    if isinstance(coverage_map, list):
        for row in coverage_map:
            reference = evidence_file_ref(row)
            if reference:
                candidate = Path(reference)
                evidence_paths.append(candidate if candidate.is_absolute() else project / candidate)
    test_plan = payload.get("test_plan")
    if isinstance(test_plan, dict):
        for group_name in ("selected", "not_run"):
            entries = test_plan.get(group_name)
            if not isinstance(entries, list):
                continue
            for row in entries:
                reference = evidence_file_ref(row)
                if reference:
                    candidate = Path(reference)
                    evidence_paths.append(candidate if candidate.is_absolute() else project / candidate)
    return lines, evidence_paths


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
    payload = phase_payload(queue_path)
    if isinstance(payload, dict):
        verification = payload.get("verification")
        evidence_path = evidence_file_ref(verification)
        if evidence_path:
            candidate = Path(evidence_path)
            add(candidate if candidate.is_absolute() else project / candidate)
        items = payload.get("items")
        if isinstance(items, list):
            for item in items:
                evidence_path = evidence_file_ref(item)
                if evidence_path:
                    candidate = Path(evidence_path)
                    add(candidate if candidate.is_absolute() else project / candidate)
    reports = bugfix_report_paths(project, role, epic_id)
    for report in reports:
        add(report)

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
    if not gate_agent:
        raise ValueError(
            "gate_agent is required for managed gate protocol; "
            "legacy/CREATIVE paths must not invent a parent-driven gate"
        )
    kind = getattr(cursor, "kind", "feature") or "feature"
    plan = plan_path(project, cursor.role, cursor.epic_id, kind=kind)
    index = index_path(project, cursor.role, cursor.epic_id, kind=kind)
    paths: list[Path] = [index, plan]
    try:
        queue = load_queue(project, cursor.role, cursor.epic_id, kind=kind)
    except (FileNotFoundError, ValueError):
        queue = None
    if queue is not None:
        for step in queue.steps:
            if step.shard:
                paths.append(queue.path.parent / "steps" / Path(step.shard).name)
    lines = [
        "",
        "Managed gate protocol (mandatory):",
        f"agent_type={gate_agent}",
        f"GATE_IDENTITY session_id={cursor.session_id} epic_id={cursor.epic_id} step_id={cursor.step_id}",
        "For loop-gate-verdict/v1 only: copy GATE_IDENTITY into session_id/epic_id/step_id. "
        "For loop-repair-result/v1: copy session_id into parent_evidence_id only — "
        "FORBIDDEN to put session_id/epic_id/step_id keys in the repair fence. "
        "Never derive session_id from epic_id, agent id, thread id, or directory name.",
        "",
        "Parent discipline (HARD — do not wander):",
        f"- Hub tools live under $DEV_HUB (currently required entrypoint: python3 $DEV_HUB/bin/loop.py …). FORBIDDEN: search product tree for epic_resolve.py, validate-verdict binaries, or .claude/hooks/epic_resolve.py.",
        "- Parent may run only: `python3 $DEV_HUB/bin/loop.py scope --project \"$PROJECT_ROOT\" --json` and the exact VERIFY command from the implement shard. FORBIDDEN as parent: `loop.py validate` / `validate-verdict` without --payload '<json>'; `validate --epic/--step` (that is not step validation); inventing evidence_sha256 requirements.",
        "- evidence_sha256 is OPTIONAL on loop-gate-verdict/v1. A fence without it is valid. Never FAIL/respawn because evidence_sha256 is missing.",
        "- Codex spawn_agent: set agent_type/subagent_type to the gate agent AND fork_context=false (self-contained prompt). FORBIDDEN: full-history fork together with agent_type (Codex error: Full-history forked agents inherit the parent agent type).",
        "- After a boundary-accepted FAIL/BLOCKED (verdict_recorded), do NOT respawn the verifier to chase schema/optional fields. Spawn gate-repair with concrete BLOCKERS/ALLOW WRITE/VERIFY, wait for loop-repair-result/v1, then respawn the same verifier once.",
        "- After pre_emit_validate_missing / pre_emit_validate_mismatch / schema_extra_forbidden: the CHILD must re-run validate-verdict; parent only respawns the same verifier with exact GATE_IDENTITY + ALLOW READ. Do not invent product blockers for protocol errors.",
        "- HARD: `gate … handoff rejected` / `schema_retry_exhausted` / `step_restarted` means the boundary did NOT accept the verdict. FORBIDDEN: claim Готово / PASS / фаза завершена / step closed. On `step_restarted`: end session — loop re-arms the same step from scratch. Else respawn or NEED_HUMAN.",
        f"The required {gate_agent} spawn_agent call must put the exact first line "
        f"agent_type={gate_agent} in the child prompt, with fork_context=false. If recovery requires "
        "gate-repair, that child prompt must instead begin with agent_type=gate-repair.",
    ]
    if gate_agent == "verify-decompose":
        lines.extend(
            [
                "Required sections in the verify-decompose spawn prompt:",
                "ALLOW READ:",
                _relative_paths(project, paths),
                "The verifier must return one fenced loop-gate-verdict/v1 JSON object.",
                "Read yaml/decompose-index.yaml first, then the plan and every indexed shard.",
                "Check structural and semantic closure: requirements, stages, "
                "outcomes, replacement cleanup, plan_contract/layout, skills, traceability, "
                "dilution, optional-SoT, ambiguity, and unresolved critical gaps.",
                "PASS is the complete DECOMPOSE gate and atomically promotes to IMPLEMENT/CREATIVE; "
                "do not request or expect a legacy analysis artifact, parent-packed FINDINGS, or a second gate.",
                "Before PASS: every indexed shard must parse with yaml.safe_load. Loop auto-repairs "
                "invalid double-quoted escapes and purges orphan steps/*.yaml not listed in the index; "
                "re-load after repair if a shard was rewritten.",
            ]
        )
    elif gate_agent in {"verify-implement", "verify-security"}:
        current_step = None
        if queue is not None:
            current_step = next((step for step in queue.steps if step.step_id == cursor.step_id), None)
        if current_step is not None:
            paths.extend(
                [
                    execute_path(project, queue.role, queue.epic_id, current_step, kind=kind),
                    queue.path.parent / "steps" / Path(current_step.shard or f"{current_step.step_id}.yaml").name,
                ]
            )
        lines.extend(
            [
                f"Required sections in the {gate_agent} spawn prompt:",
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
                "Any passing live_smoke/browser/wire claim must include an evidence_file "
                "with typed runtime capture; unit tests and static/mock traces do not close a live claim. "
                "If this QA run rewrites an evidence_file already referenced by BUGFIX, the "
                "queue preflight/gate refreshes anchors to the new typed timestamp before finish.",
                "The verifier must return one fenced loop-gate-verdict/v1 JSON object.",
            ]
        )
    lines.extend(
        [
            "",
            "Recovery protocol:",
            "1. A valid PASS crosses the gate atomically; do not call finish separately after a PASS. "
            "QA PASS is the exception: it records PASS and keeps QA active until context-sync returns done.",
            "1a. verify-qa FAIL is a product QA result, not a gate-repair request and not an IMPLEMENT-style 'cannot finish'. "
            "Write/update qa-*.yaml (verdict: fail|blocked) + eligible blockers/fix_plan, create/merge open bugfix-queue.yaml, "
            "then MUST run `python3 $DEV_HUB/bin/loop.py finish --project <cwd> --step QA` once. "
            "Finish with those artifacts routes QA→BUGFIX (PASS is not required). Do not gate-repair a product QA FAIL. "
            "Exiting with only a prose report → finish_not_committed and a useless QA retry.",
            "1b. verify-qa BLOCKED, or QA FAIL without a valid QA artifact/queue, requires the parent to fix the missing contract/artifact and respawn verify-qa; do not invent a blocker.",
            "2. A content FAIL or BLOCKED for other gates with concrete product blockers requires gate-repair. Spawn gate-repair with:",
            "agent_type=gate-repair",
            f"GATE_IDENTITY session_id={cursor.session_id} epic_id={cursor.epic_id} step_id={cursor.step_id}",
            f"PARENT_EVIDENCE_ID={cursor.session_id}",
            "BLOCKERS:",
            "- <blocker_id> | <concrete_file> | <concrete_fix>",
            "ALLOW WRITE:",
            "- the same concrete files only",
            "VERIFY:",
            "- one exact verification command or typed capability check",
            "ALLOW READ:",
            "- optional concrete context files only",
            "PARENT BLOCKERS QUALITY (HARD): one stable canon per blocker_id — never flip "
            "--ds-radius-md <-> --ds-radius-sm or opposite fixes across repair cycles. "
            "If FAIL is computed-style/Playwright and source already has the token rule, BLOCKERS "
            "must name the competing rule path OR an explicit runtime sync/build step in VERIFY/"
            "ALLOW WRITE — do not ask gate-repair to 'add another selector'. "
            "If gate-repair returns fail with runtime_not_source / focus_visible_mismatch, fix runtime "
            "or the probe/spec once; do not respawn the same CSS cosmetic repair.",
            "PARENT_EVIDENCE_ID is copied by gate-repair into result parent_evidence_id; it is not a prompt section the child can mark prompt_incomplete.",
            "gate-repair fence allowed keys ONLY: schema, agent_id, parent_evidence_id, status, "
            "fixed_blockers, remaining_blockers, recorded_at. "
            "FORBIDDEN in repair fence: session_id, epic_id, step_id, blockers, changed_paths, "
            "verification, repair_status. Child validates with "
            "`loop.py validate --schema loop-repair-result/v1`, not validate-verdict.",
            "Wait for one accepted fenced loop-repair-result/v1 result (boundary rejects invented prompt_incomplete:parent_evidence_id), then rerun this same verifier. Do not finish between repair and re-verify. Do not silently DIY the ALLOW WRITE fixes and skip a valid repair cycle unless gate-repair already recorded done/partial.",
            "2b. repair_result_rejected (schema_* / missing keys) is a repair emit protocol error, not a product blocker and not finish_not_committed. "
            "Respawn the same gate-repair once with the same BLOCKERS/ALLOW WRITE/VERIFY plus an explicit Allowed keys reminder; "
            "do not restart the whole IMPLEMENT step and do not claim progress until repair_recorded.",
            "3. Protocol failures such as prompt_incomplete, verdict_transition_rejected, pre_emit_validate_missing, pre_emit_validate_mismatch, or schema_extra_forbidden on a *verifier* fence are parent handoff / child emit failures. Fix GATE_IDENTITY / ALLOW READ / exact JSON via validate-verdict and respawn the same verifier; do not invent a product blocker and do not send verifier protocol failures to gate-repair. "
            "stale_verdict_ignored / stale_repair_ignored mean a delayed child from a previous session_id — discard, do not respawn repair and do not gate-repair.",
            "4. QA owns contract/review findings; actionable product gaps use the normal BUGFIX queue, while protocol errors remain BLOCKED.",
            "5. FORBIDDEN parent busywork after gate spawn: reading finish-block.mdc / finish-doc-router.mdc, hunting epic_resolve.py, running loop.py validate without JSON payload, or treating optional evidence_sha256 as required.",
        ]
    )
    return "\n".join(lines) + "\n"


def _gate_recovery_prompt(cursor, engine: LoopEngine) -> str:
    event = engine.store.latest_event_any(
        {
            "verdict_transition_rejected",
            "verdict_rejected",
            "repair_result_rejected",
            "repair_recorded",
            "verdict_recorded",
        }
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
    if event_name == "repair_result_rejected":
        codes = event.get("diagnostic_codes") or []
        errors = event.get("errors") or []
        detail = ""
        if codes or errors:
            detail = (
                " Last reject diagnostic_codes="
                + ",".join(str(code) for code in codes)
                + "; errors="
                + " | ".join(str(error)[:160] for error in errors[:3])
                + "."
            )
        return (
            "\nRecovery state: gate-repair fence was rejected by the boundary "
            "(repair_result_rejected). This is a repair JSON/schema protocol error, "
            "not a product blocker and not grounds to finish_not_committed / restart the step. "
            "Respawn gate-repair once with the same BLOCKERS / ALLOW WRITE / VERIFY. "
            "Child must emit loop-repair-result/v1 with ONLY "
            "schema,agent_id,parent_evidence_id,status,fixed_blockers,remaining_blockers,recorded_at "
            f"and validate via `loop.py validate --schema loop-repair-result/v1`.{detail} "
            "FORBIDDEN repair keys: session_id,epic_id,step_id,blockers,changed_paths,"
            "verification,repair_status. Do not finish before repair_recorded + verifier PASS.\n"
        )
    if event_name in {"verdict_transition_rejected", "verdict_rejected"}:
        codes = event.get("diagnostic_codes") or []
        errors = event.get("errors") or []
        detail = ""
        if codes or errors:
            detail = (
                " Last reject diagnostic_codes="
                + ",".join(str(code) for code in codes)
                + "; errors="
                + " | ".join(str(error)[:160] for error in errors[:3])
                + "."
            )
        return (
            "\nRecovery state: the previous gate handoff was rejected by the boundary. "
            "This is a protocol error, not a product blocker. "
            "The child MUST Bash `validate-verdict` until valid:true, copy `emit_exactly` "
            "from the CLI JSON (recorded_at may differ; all other fields must match), "
            "emit only allowed keys "
            "(schema,agent_id,verdict,step_id,session_id,epic_id,recorded_at,evidence_sha256), "
            "and keep GATE_IDENTITY verbatim."
            f"{detail} "
            "Handoff reject is NOT a PASS. Then respawn the same verifier. Do not call gate-repair "
            "for prompt/session/transition/schema errors and do not finish.\n"
        )
    if event_name == "repair_recorded":
        remaining = event.get("remaining_blockers") or []
        remaining_text = ", ".join(str(item) for item in remaining) if remaining else "(none)"
        return (
            f"\nRecovery state: gate-repair reported {event.get('status')} "
            f"(remaining_blockers: {remaining_text}). "
            "If status is done or partial, re-run the same verifier now with the same GATE_IDENTITY. "
            "If status is fail with concrete product remaining_blockers, either respawn gate-repair "
            "with the same BLOCKERS/ALLOW WRITE/VERIFY or apply those exact ALLOW WRITE fixes yourself, "
            "then re-run the same verifier. Do not finish before a fresh PASS. "
            "Never treat prompt_incomplete:parent_evidence_id as a completed repair cycle.\n"
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
            f"\nRecovery state: {agent} already returned {event.get('verdict')} and the boundary recorded it. "
            "This is a product/content result, not a schema problem. "
            "Do not finish, do not hunt evidence_sha256, do not re-validate empty loop.py validate flags, "
            "and do not respawn the verifier only to re-emit the same FAIL. "
            "Classify the verifier's concrete finding: "
            "prompt/contract failures (prompt_incomplete, missing ALLOW READ, pre_emit_*, schema_extra_forbidden, "
            "session/transition mismatch) → fix handoff and respawn the same verifier; "
            "a concrete product blocker → spawn gate-repair with structured BLOCKERS, concrete ALLOW WRITE, "
            "exact VERIFY, optional ALLOW READ; wait for loop-repair-result/v1; then respawn the same verifier "
            "once with the same GATE_IDENTITY.\n"
        )
    return ""


def _decompose_retry_context(cursor, project: Path) -> str:
    if cursor.phase != "DECOMPOSE":
        return ""
    problems = decompose_yaml_problems(project, cursor.role, cursor.epic_id)
    index = project / "memory-bank" / cursor.role / "plan" / cursor.epic_id / "yaml" / "decompose-index.yaml"
    steps = index.parent / "steps"
    existing = []
    if index.is_file():
        existing.append(str(index.relative_to(project)))
    if steps.is_dir():
        existing.extend(
            str(path.relative_to(project)) for path in sorted(steps.glob("*.yaml"))
        )
    if not existing and not problems:
        return (
            "\nDECOMPOSE status: no yaml/decompose-index.yaml yet — create a clean tree from the plan. "
            "Do not claim prior attempt artifacts exist.\n"
        )
    lines = [
        "\nDECOMPOSE status (retry recognition): prior attempt left artifacts on disk. "
        "Do NOT restart from AGENTS as if the epic were empty — inspect and fix these paths first:",
        *[f"- {path}" for path in existing[:40]],
    ]
    if problems:
        lines.append("Current validate problems (MUST fix before verify-decompose PASS / finish):")
        lines.extend(f"- {item}" for item in problems[:20])
        lines.append(
            "Loop auto-repairs unknown double-quoted escapes and purges orphan steps on validate; "
            "remaining problems are structural (schema/fields/role) — fix those before finish."
        )
    else:
        lines.append(
            "Tree parses. Run verify-decompose; its PASS performs the complete structural and semantic "
            "DECOMPOSE check and promotes atomically. FORBIDDEN exit with only a prose 'завершён' "
            "after a previous finish_not_committed."
        )
    return "\n".join(lines) + "\n"


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
    role = resolve_epic_role(paths.project, epic_id, args.role, kind=args.kind)
    cursor = engine.start(epic_id, role)
    _project_transition(
        project_root=paths.project,
        epic_id=cursor.epic_id,
        phase=cursor.phase,
        role=cursor.role,
        kind=cursor.kind,
        status=cursor.status,
        source="start",
    )
    if cursor.status.value == "complete":
        _print(engine.status(), args.json)
        return 0
    cli_model = args.model
    cli_effort = getattr(args, "effort", None)
    runtime_name = args.runtime or settings.runtime
    runtime = runtime_for(
        runtime_name,
        settings=settings,
        progress=not args.json,
        effort=cli_effort,
    )
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
                "effort": cli_effort,
            }
        )
        prompt = (
            f"You are operating epic {cursor.epic_id}, role {cursor.role}.\n"
            f"Current phase: {cursor.phase}; step: {cursor.step_id}.\n"
            f"GATE_IDENTITY session_id={cursor.session_id} epic_id={cursor.epic_id} step_id={cursor.step_id}\n"
            "Execution policy: approvals are disabled. Never request escalation, require_escalated permissions, "
            "or a second sandbox; run commands with the permissions already available and report a real denial.\n"
        )
        prompt += _phase_instruction(cursor, paths.project, engine)
        context_sync_pending = cursor.phase == "QA" and engine.qa_context_sync_pending(cursor)
        gate_agent = None if context_sync_pending else _phase_gate_agent(cursor.phase)
        if cursor.phase == "CREATIVE":
            prompt += (
                "When CREATIVE is complete (artifact written and needs_creative closed on the same step), "
                "finish with `python3 $DEV_HUB/bin/loop.py finish --project <cwd> --step "
                f"{cursor.step_id}`. Do not edit cursor.json or generated activeContext.md. "
                "CREATIVE has no verifier gate — do not spawn verify-* agents. "
                "Do not mark the step completed; IMPLEMENT owns that after code lands."
            )
        elif context_sync_pending:
            prompt += (
                "QA PASS is accepted and context-sync is the only remaining worker. "
                "Spawn agent_type=context-sync with fork_context=false; do not spawn verify-qa "
                "and do not call finish. The context-sync done result closes QA atomically. "
                "Do not edit cursor.json or generated activeContext.md. "
                "The final response MUST contain exactly one fenced JSON object: opening fence "
                "```json, schema loop-context-sync-result/v1, and closing fence ```; emit no bare JSON "
                "and no prose outside the fence. Run loop.py validate with that exact payload before emitting it."
            )
        elif cursor.phase not in {"DECOMPOSE", "PLAN", "CLARIFY", "CREATIVE", "IMPLEMENT", "TASK", "REFACTOR", "SECURITY", "QA", "BUGFIX"}:
            prompt += (
                "Do not edit cursor.json or generated activeContext.md. "
                "This legacy cursor value is not a live user phase — let the parent normalize it. "
                "The context-sync done result closes QA atomically, so do not add a parent finish after it. "
                "Do not search the product repo for hub scripts; use python3 $DEV_HUB/bin/loop.py only."
            )
        else:
            prompt += (
                "When the phase work is genuinely complete, spawn the required gate before any finish attempt. "
                "Do not edit cursor.json or generated activeContext.md. "
                "A managed gate subagent PASS is validated by the boundary hook. In DECOMPOSE, "
                "verify-decompose PASS performs the complete structural and semantic check and promotes the phase atomically. "
                "For other non-QA gates, PASS finishes the phase atomically; "
                "for non-QA gates a direct finish without the required PASS is rejected and prose verdicts are not machine state. "
                "HARD: handoff REJECTED / verdict_json_fence_missing / qa_artifact_required_before_pass means "
                "NOT accepted — fix artifact + ```json fence "
                "(child runs validate-verdict until valid:true) and respawn the same gate. "
                "QA exception: after verify-qa FAIL, writing qa-*.yaml (fail|blocked) + open bugfix-queue.yaml and calling "
                "`loop.py finish --step QA` is required and routes to BUGFIX — do not wait for a PASS. "
                "Do not search the product repo for hub scripts; use python3 $DEV_HUB/bin/loop.py only."
            )
        if gate_agent:
            prompt += (
                f" This phase requires exactly one {gate_agent} pre-finish gate before finish. "
                f"Spawn it with fork_context=false and agent_type={gate_agent} after the phase work; "
                "the child owns validate-verdict + the JSON fence. "
                "Parent must not run validate-verdict for the child and must not require evidence_sha256."
            )
            if cursor.phase == "QA":
                prompt += (
                    " After verify-qa FAIL: do not treat FAIL as 'cannot finish'. "
                    "Persist qa artifact + bugfix-queue, then call finish once to enter BUGFIX."
                )
            if cursor.phase == "BUGFIX":
                prompt += (
                    " BUGFIX gate timing: spawn verify-bugfix only when every queue item is terminal, "
                    "verification.status=pass, and "
                    "`python3 $DEV_HUB/bin/loop.py check-bugfix-queue --project \"$PROJECT_ROOT\" --json` "
                    "returns ok:true (done_at/last_run_at copied from evidence_file.timestamp). "
                    "Accepted verify-bugfix PASS atomically advances BUGFIX to re-QA; do not call "
                    "`finish --step BUGFIX` again after the gate is accepted. "
                    "This phase is one session for the whole queue — do not leave open items. "
                    "Exiting with open items or without finish after full close is finish_not_committed."
                )
            prompt += _gate_protocol(cursor, paths.project, gate_agent)
        if cursor.phase != "CREATIVE":
            prompt += _gate_recovery_prompt(cursor, engine)
        if cursor.phase == "DECOMPOSE":
            prompt += _decompose_retry_context(cursor, paths.project)
        prompt = f"{prompt}\n\n{engine.boundary.context(cursor)}"
        if not args.json:
            _print_step_banner(
                runtime=runtime_name,
                model=model,
                model_source=selection.source,
                cursor=cursor,
                settings=settings,
                effort=cli_effort,
            )
        session_run = supervisor.run_step(prompt, model=model, project=paths.project, session_id=cursor.session_id)
        cursor_after = engine.store.read()
        if session_run.transition is not None and session_run.transition.changed:
            _project_cursor_transition(
                project_root=paths.project,
                cursor_before=cursor,
                cursor_after=cursor_after,
                transition=session_run.transition,
                source="run",
            )
        elif cursor_after is not None and cursor_after.revision != cursor.revision:
            _project_cursor_transition(
                project_root=paths.project,
                cursor_before=cursor,
                cursor_after=cursor_after,
                source="run:implicit-transition",
            )
        if session_run.outcome == SessionOutcome.COMMITTED:
            return 0
        if session_run.outcome == SessionOutcome.PROGRESS_CONTINUE:
            # Reserved outcome (legacy partial BUGFIX). Current canon: one BUGFIX session
            # closes the whole queue — supervisors should not emit this for open items.
            continue
        if session_run.outcome == SessionOutcome.SESSION_ROTATED:
            # Soft retry minted a new session_id — rebuild GATE_IDENTITY prompt and
            # start a new runtime process. FORBIDDEN: reuse the prior session prompt.
            continue
        if session_run.outcome == SessionOutcome.STEP_RESTARTED:
            # Same step from scratch after exhausted verify/repair or session attempts.
            continue
        if session_run.outcome == SessionOutcome.STATE_CHANGED and session_run.result is not None:
            continue
        transition = session_run.transition
        status = transition.status.value if transition is not None else "halted"
        attempt = transition.attempt if transition is not None else cursor.attempt
        _report_failure(args, cursor, reason=session_run.reason, status=status, attempt=attempt, runtime=runtime_name, model=model, cursor_path=paths.cursor, result=session_run.result)
        return session_run.return_code
    halted = engine.halt("max_steps_exceeded")
    if cursor and cursor.epic_id:
        _project_transition(
            project_root=paths.project,
            epic_id=cursor.epic_id,
            phase="HALT",
            role=cursor.role,
            kind=cursor.kind,
            status=halted.status,
            source="halt",
        )
    _report_failure(args, cursor, reason="max_steps_exceeded", status=halted.status.value, attempt=halted.attempt, runtime=runtime_name, model=model, cursor_path=paths.cursor)
    return 1


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    args = _parser().parse_args(_normalize_legacy_args(raw_argv))
    paths: LoopPaths | None = None
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
                _print(
                    {
                        "ok": False,
                        "error": "--payload is required",
                        "hint": (
                            "validate / validate-verdict check a JSON fence payload, not an implement yaml step. "
                            "Example: python3 $DEV_HUB/bin/loop.py validate-verdict --project \"$PROJECT_ROOT\" "
                            "--payload '{\"schema\":\"loop-gate-verdict/v1\",...}'. "
                            "For touched-path scope use: python3 $DEV_HUB/bin/loop.py scope --project \"$PROJECT_ROOT\" --json. "
                            "Do not pass --epic/--step alone; those flags do not select a step artifact here."
                        ),
                    },
                    True,
                )
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
            output = result.as_dict()
            if result.valid and args.project:
                try:
                    raw = json.loads(args.payload) if isinstance(args.payload, str) else args.payload
                except (TypeError, json.JSONDecodeError):
                    raw = None
                if isinstance(raw, dict):
                    stamp = write_pre_emit_stamp(paths, raw)
                    if stamp is not None:
                        output["pre_emit_stamp"] = stamp.as_dict()
                        output["emit_exactly"] = stamp.payload
                        output["binding_sha256"] = stamp.payload_sha256
                        output["emit_note"] = (
                            "Final fence must match emit_exactly on schema,agent_id,verdict,"
                            "step_id,session_id,epic_id,evidence_sha256. recorded_at may differ "
                            "without re-validate. Any other change requires a new validate-verdict."
                        )
            _print(output, True)
            return 0 if result.valid else 2
        if args.command == "scope":
            cursor = engine.store.read()
            if cursor is None:
                _print({"ok": False, "error": "cursor_missing"}, True)
                return 2
            result = BoundaryService(paths).scope(cursor)
            _print(result, args.json)
            return 0 if result["ok"] else 1
        if args.command in {"check-bugfix-queue", "sync-bugfix-queue"}:
            cursor = engine.store.read()
            epic_id = args.epic or (cursor.epic_id if cursor else None)
            if not epic_id:
                _print(
                    {
                        "ok": False,
                        "error": "epic_required",
                        "hint": "Pass --epic or run while a BUGFIX cursor is active.",
                    },
                    True,
                )
                return 2
            role = args.role
            if role in {"", "auto"}:
                if cursor and cursor.epic_id == epic_id:
                    role = cursor.role
                else:
                    role = resolve_epic_role(paths.project, epic_id, "auto", kind=args.kind)
            if args.command == "sync-bugfix-queue":
                ready, reason = sync_bugfix_queue_evidence(paths.project, role, epic_id)
                payload = {
                    "ok": ready,
                    "epic_id": epic_id,
                    "role": role,
                    "reason": reason,
                    "contract": (
                        "new runtime evidence timestamps are copied into item.done_at and "
                        "verification.last_run_at; older evidence never moves an anchor backwards."
                    ),
                }
                _print(payload, True)
                return 0 if ready else 1
            sync_ready, sync_reason = sync_bugfix_queue_evidence(paths.project, role, epic_id)
            if sync_ready:
                ready, reason = bugfix_queue_state(paths.project, role, epic_id)
            else:
                ready, reason = False, sync_reason
            payload = {
                "ok": ready,
                "epic_id": epic_id,
                "role": role,
                "reason": reason,
                "sync_reason": sync_reason,
                "contract": (
                    "item.done_at and verification.last_run_at must equal evidence_file.timestamp "
                    "(±15s). A valid newer evidence file is reconciled automatically before this "
                    "check; stale or invalid evidence still fails closed."
                ),
            }
            _print(payload, True)
            return 0 if ready else 1
        if args.command == "start":
            epic_id = _epic(args, engine)
            role = resolve_epic_role(paths.project, epic_id, args.role, kind=args.kind)
            cursor = engine.start(epic_id, role)
            projection_result = _project_transition(
                project_root=paths.project,
                epic_id=cursor.epic_id,
                phase=cursor.phase,
                role=cursor.role,
                kind=cursor.kind,
                status=cursor.status,
                source="start",
            )
            payload = cursor.to_dict()
            payload.update(_projection_fields(projection_result))
            _print(payload, args.json)
            return 0
        if args.command == "implement-flush":
            from .implement_schema import flush_implement_for_verify
            from .index import implement_path, load_queue

            cursor = engine.store.read()
            if cursor is None:
                _print({"ok": False, "error": "cursor_missing"}, True)
                return 2
            queue = load_queue(paths.project, cursor.role, cursor.epic_id)
            step = next((item for item in queue.steps if item.step_id == cursor.step_id), None)
            if step is None:
                _print(
                    {"ok": False, "error": f"step_missing:{cursor.step_id}"},
                    True,
                )
                return 2
            path = implement_path(paths.project, queue.role, queue.epic_id, step)
            model = flush_implement_for_verify(
                path,
                expected_step_id=cursor.step_id,
                expected_plan_id=queue.epic_id,
            )
            _print(
                {
                    "ok": True,
                    "event": "implement_flushed",
                    "path": str(path),
                    "status": model.status,
                    "checkpoints": [{"id": cp.id, "status": cp.status} for cp in model.checkpoints],
                },
                args.json,
            )
            return 0
        if args.command == "board-sync":
            cursor = engine.store.read()
            target_epic = args.epic or (cursor.epic_id if cursor else None)
            if not target_epic:
                _print({"ok": False, "error": "--epic is required when no active cursor exists"}, args.json)
                return 2

            active_cursor = cursor is not None and cursor.epic_id == target_epic
            role = cursor.role if active_cursor else args.role
            if not active_cursor and role == "auto":
                try:
                    role = resolve_epic_role(paths.project, target_epic, role="auto", kind=args.kind)
                except (FileNotFoundError, ValueError):
                    role = "back"

            kind = cursor.kind if active_cursor else args.kind
            if not active_cursor and kind is None:
                try:
                    kind = resolve_epic_kind(paths.project, target_epic, role=role)
                except (FileNotFoundError, ValueError):
                    kind = None

            phase = cursor.phase if active_cursor else "QUEUED"
            if not phase:
                phase = "QUEUED"

            from ..board_projection.mapping import load_board_epic_map, resolve_map_path
            map_path = resolve_map_path(paths.project)
            current_map = load_board_epic_map(map_path)
            entry = current_map.epics.get(target_epic)
            if args.phase:
                # Explicit override (e.g. closed BUGFIX → DONE without inventing plan/).
                phase = args.phase
            elif entry and entry.last_phase and not active_cursor:
                phase = entry.last_phase
            elif not active_cursor and plan_path(
                paths.project,
                role,
                target_epic,
                kind=kind or "feature",
            ).is_file():
                phase = "PLAN"

            result = project_epic_phase(
                project_root=paths.project,
                epic_id=target_epic,
                phase=phase,
                role=role,
                kind=kind,
                title=str(args.title or ""),
                description=str(args.summary or ""),
            )
            success = result.status in {"success", "disabled"}
            payload = {
                "ok": success,
                "epic_id": target_epic,
                "status": result.status,
                "phase": phase,
                "external_id": result.external_id,
                "disabled_reason": result.disabled_reason,
                "error": result.error,
            }
            payload.update(_projection_fields(result))
            _print(payload, args.json)
            return 0 if success else 1
        if args.command == "board-docs":
            cursor = engine.store.read()
            target_epic = args.epic or (cursor.epic_id if cursor else None)
            if not target_epic:
                _print({"ok": False, "error": "--epic is required when no active cursor exists"}, args.json)
                return 2
            role = cursor.role if (cursor and cursor.epic_id == target_epic) else args.role
            kind = cursor.kind if (cursor and cursor.epic_id == target_epic) else args.kind
            result = publish_board_docs(
                project_root=paths.project,
                epic_id=target_epic,
                role=role,
                kind=kind,
                include_plan=not args.no_plan,
                include_prompt=not args.no_prompt,
            )
            success = result.status == "success"
            payload = {
                "ok": success,
                "epic_id": result.epic_id,
                "status": result.status,
                "external_id": result.external_id,
                "local_path": result.local_path,
                "attached": result.attached,
                "disabled_reason": result.disabled_reason,
                "error": result.error,
            }
            _print(payload, args.json)
            return 0 if success else 1
        if args.command == "project-docs":
            result = publish_project_docs(
                project_root=paths.project,
                files=list(args.docs_files or []),
                folder_name=args.folder,
            )
            success = result.status == "success"
            payload = {
                "ok": success,
                "status": result.status,
                "published": result.published,
                "disabled_reason": result.disabled_reason,
                "error": result.error,
            }
            _print(payload, args.json)
            return 0 if success else 1
        if args.command == "finish":
            cursor_before = engine.store.read()
            transition = engine.finish(step_id=args.step)
            cursor_after = engine.store.read()
            projection_result, completed_projection = _project_finish_transition(
                project_root=paths.project,
                cursor_before=cursor_before,
                cursor_after=cursor_after,
                transition=transition,
            )
            payload = {
                "event": transition.event,
                "status": transition.status.value,
                "phase": transition.phase,
                "step_id": transition.step_id,
            }
            payload.update(_projection_fields(projection_result))
            if completed_projection is not None and cursor_before is not None:
                payload.update(
                    {
                        "completed_epic_id": cursor_before.epic_id,
                        "completed_external_id": completed_projection.external_id,
                        "completed_projection_status": completed_projection.status,
                        "completed_projection_error": completed_projection.error,
                    }
                )
            _print(payload, args.json)
            return 0
        if args.command == "halt":
            cursor_before = engine.store.read()
            transition = engine.halt(args.reason)
            projection_result = _project_transition(
                project_root=paths.project,
                epic_id=cursor_before.epic_id if cursor_before else "",
                phase="HALT",
                role=cursor_before.role if cursor_before else "back",
                kind=cursor_before.kind if cursor_before else None,
                status=transition.status,
                source="halt",
            )
            payload = {
                "event": transition.event,
                "status": transition.status.value,
                "phase": transition.phase,
                "step_id": transition.step_id,
            }
            payload.update(_projection_fields(projection_result))
            _print(payload, args.json)
            return 0
        if args.command == "rewind":
            if not args.phase:
                _print({"ok": False, "error": "--phase is required for rewind"}, args.json)
                return 2
            cursor_before = engine.store.read()
            transition = engine.rewind(args.phase, reason=args.reason, step_id=args.step)
            projection_result = _project_transition(
                project_root=paths.project,
                epic_id=cursor_before.epic_id if cursor_before else "",
                phase=transition.phase,
                role=cursor_before.role if cursor_before else "back",
                kind=cursor_before.kind if cursor_before else None,
                status=transition.status,
                source="rewind",
            )
            payload = {
                "event": transition.event,
                "status": transition.status.value,
                "phase": transition.phase,
                "step_id": transition.step_id,
            }
            payload.update(_projection_fields(projection_result))
            _print(payload, args.json)
            return 0
        return run(args)
    except (ValueError, FileNotFoundError, TransitionError) as exc:
        report = capture_exception(
            exc,
            operation=f"cli.{args.command}",
            project_root=paths.project if paths is not None else None,
            context={
                "command": args.command,
                "epic_id": args.epic,
                "phase": args.phase,
            },
        )
        _print(
            {
                "ok": False,
                "error": str(exc),
                "diagnostic_id": report["error_id"],
                "diagnostic_path": report.get("diagnostic_path"),
            },
            True,
        )
        return 2
    except Exception as exc:
        report = capture_exception(
            exc,
            operation=f"cli.{args.command}",
            project_root=paths.project if paths is not None else None,
            context={
                "command": args.command,
                "epic_id": args.epic,
                "phase": args.phase,
            },
        )
        _print(
            {
                "ok": False,
                "error": str(exc),
                "diagnostic_id": report["error_id"],
                "diagnostic_path": report.get("diagnostic_path"),
            },
            True,
        )
        return 1
        return 2
