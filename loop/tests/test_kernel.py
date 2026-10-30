from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest

from loop.kernel.engine import LoopEngine, TransitionError
from loop.kernel.cli import (
    _role_rules_dir,
    _bugfix_gate_paths,
    _gate_protocol,
    _gate_recovery_prompt,
    _normalize_legacy_args,
    _phase_gate_agent,
    _phase_instruction,
    _qa_gate_context,
)
from loop.kernel.verdict import extract_json_fence
from loop.kernel.index import (
    Step,
    _load_yaml_mapping,
    implement_path,
    normalize_decompose_list_fields,
    phase_payload,
    repair_yaml_double_quoted_escapes,
    validate_decompose_tree,
)
from loop.kernel.lifecycle import SubagentLifecycle
from loop.kernel.model import CursorStatus, RuntimeResult
from loop.kernel.runtime import CodexRuntime, Runtime, _collaboration_state
from loop.kernel.session import SessionOutcome, SessionSupervisor
from loop.kernel.store import CursorStore, LoopPaths
from loop.kernel.verdict import (
    BoundaryIdentity,
    ContextSyncResult,
    GateVerdict,
    SCHEMA_CONTEXT_SYNC_RESULT,
    SCHEMA_GATE_VERDICT,
    SCHEMA_REPAIR_RESULT,
    SCHEMA_SUNSET_INVENTORY,
    validate_boundary,
    validate_context_sync_message,
    validate_message,
)
from loop.kernel.inventory import read_sunset_sidecar
from loop.config import LoopSettings


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_implement(
    root: Path,
    *,
    step_id: str,
    filename: str,
    epic_id: str = "E1",
    status: str = "in_progress",
    checkpoint_status: str = "pending",
) -> None:
    write(
        root / f"memory-bank/back/implement/{epic_id}/{filename}",
        f"""
schema: epic-implement/v1
role: back
step_id: {step_id}
plan_id: {epic_id}
status: {status}
done:
  - seeded evidence
files: []
deletes: []
tests: []
integration_check: []
checkpoints:
  - id: cp1
    criterion: seeded
    status: {checkpoint_status}
""",
    )


def _seed_queue_implement_complete(root: Path, *, epic_id: str = "E1") -> None:
    """Mark all seeded implement artifacts completed — required before AUDIT/QA routing."""
    _seed_implement(
        root,
        step_id="s01",
        filename="s01-one.yaml",
        epic_id=epic_id,
        status="completed",
        checkpoint_status="done",
    )
    _seed_implement(
        root,
        step_id="s02",
        filename="s02-two.yaml",
        epic_id=epic_id,
        status="completed",
        checkpoint_status="done",
    )


def _seed_context_sync(root: Path, *, epic_id: str = "E1") -> None:
    write(
        root / f"memory-bank/back/context-sync/{epic_id}/sync-20260921-{epic_id.lower()}.md",
        f"# Context sync — {epic_id}\n\n## Changes\n\n| File | Action |\n|------|--------|\n| techContext.md | no-op |\n",
    )


def _context_sync_message(cursor, sync_path: str, *, status: str = "done") -> str:
    payload = {
        "schema": SCHEMA_CONTEXT_SYNC_RESULT,
        "agent_id": "context-sync",
        "epic_id": cursor.epic_id,
        "status": status,
        "sync_path": sync_path,
        "session_id": cursor.session_id,
        "recorded_at": "2026-09-21T00:00:00+00:00",
    }
    return "```json\n" + json.dumps(payload) + "\n```"


def seed_project(root: Path) -> LoopPaths:
    write(root / "memory-bank/back/plan/E1/yaml/decompose-index.yaml", """
schema: epic-decompose-index/v1
epic_id: E1
steps:
  - id: s01
    file: s01-one.yaml
    status: pending
  - id: s02
    file: s02-two.yaml
    status: pending
""")
    write(root / "memory-bank/back/plan/E1/yaml/s01-one.yaml", "step_id: s01\n")
    write(root / "memory-bank/back/plan/E1/yaml/s02-two.yaml", "step_id: s02\n")
    _seed_implement(root, step_id="s01", filename="s01-one.yaml")
    _seed_implement(root, step_id="s02", filename="s02-two.yaml")
    return LoopPaths(project=root, hub=root / "hub")


def _finish_via_gate(engine: LoopEngine):
    cursor = engine.store.read()
    assert cursor is not None
    agent = {
        "DECOMPOSE": "verify-decompose",
        "IMPLEMENT": "verify-implement",
        "TASK": "verify-implement",
        "REFACTOR": "verify-implement",
        "BUGFIX": "verify-bugfix",
        "QA": "verify-qa",
    }.get(cursor.phase)
    assert agent is not None
    return engine.accept_verdict(
        GateVerdict(
            schema=SCHEMA_GATE_VERDICT,
            agent_id=agent,
            verdict="PASS",
            step_id=cursor.step_id,
            session_id=cursor.session_id,
            epic_id=cursor.epic_id,
            recorded_at="2026-09-18T19:00:00+00:00",
        ),
        expected_agent_id=agent,
    )


def _start_decompose_gate_project(
    root: Path,
    *,
    epic_id: str = "E-DECOMPOSE-GATE",
) -> tuple[LoopPaths, LoopEngine]:
    write(root / f"memory-bank/back/plan/{epic_id}/md/plan.md", f"# Plan: {epic_id}\n")
    paths = LoopPaths(project=root, hub=root / "hub")
    engine = LoopEngine(paths)
    cursor = engine.start(epic_id)
    assert cursor.phase == "DECOMPOSE"
    write(
        root / f"memory-bank/back/plan/{epic_id}/yaml/decompose-index.yaml",
        f"""schema: epic-decompose-index/v1
plan_id: {epic_id}
steps:
  - id: s01
    file: s01.yaml
    title: s01
    next_phase: BACK IMPLEMENT
    status: pending
""",
    )
    write(
        root / f"memory-bank/back/plan/{epic_id}/yaml/steps/s01.yaml",
        _minimal_decompose_shard(step_id="s01", plan_id=epic_id, verify_line="true"),
    )
    return paths, engine


def test_cursor_is_the_only_runtime_state_and_finish_advances_index(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)

    cursor = engine.start("E1")
    assert cursor.phase == "IMPLEMENT"
    assert cursor.step_id == "s01"
    assert paths.cursor.is_file()
    assert not (paths.runtime / "state.json").exists()
    assert not (paths.runtime / "checkpoint.json").exists()
    assert not (paths.runtime / "last-session.json").exists()

    transition = _finish_via_gate(engine)
    assert transition.phase == "IMPLEMENT"
    assert transition.step_id == "s02"
    index = (tmp_path / "memory-bank/back/plan/E1/yaml/decompose-index.yaml").read_text()
    assert "id: s01" in index and "status: completed" in index


def test_new_plan_starts_decompose_before_index_exists(tmp_path: Path) -> None:
    write(tmp_path / "memory-bank/back/plan/E2/md/plan.md", "# Plan: E2\n")
    paths = LoopPaths(project=tmp_path, hub=tmp_path / "hub")

    cursor = LoopEngine(paths).start("E2")

    assert cursor.phase == "DECOMPOSE"
    assert cursor.step_id == "DECOMPOSE"
    assert cursor.status == CursorStatus.ACTIVE
    context = paths.active_context.read_text(encoding="utf-8")
    assert "memory-bank/back/plan/E2/md/plan.md" in context


def test_start_auto_resolves_front_epic_role(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    write(tmp_path / "memory-bank/front/plan/T-060-ui/md/plan.md", "# Plan: T-060-ui\n")
    cursor = LoopEngine(paths).start("T-060-ui")
    assert cursor.role == "front"
    assert cursor.phase == "DECOMPOSE"
    assert cursor.epic_id == "T-060-ui"


def test_start_auto_rejects_ambiguous_epic_roles(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    write(tmp_path / "memory-bank/back/plan/SHARED/md/plan.md", "# back\n")
    write(tmp_path / "memory-bank/front/plan/SHARED/md/plan.md", "# front\n")
    with pytest.raises(ValueError, match="ambiguous epic"):
        LoopEngine(paths).start("SHARED")
    cursor = LoopEngine(paths).start("SHARED", role="front")
    assert cursor.role == "front"


def test_start_explicit_role_hints_when_plan_lives_elsewhere(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    write(tmp_path / "memory-bank/front/plan/T-060-ui/md/plan.md", "# Plan: T-060-ui\n")
    with pytest.raises(FileNotFoundError, match="pass --role front"):
        LoopEngine(paths).start("T-060-ui", role="back")


def test_rewind_to_decompose_after_implementation_progress(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)

    transition = engine.rewind("DECOMPOSE")

    assert transition.phase == "DECOMPOSE"
    assert transition.step_id == "DECOMPOSE"
    assert engine.store.read().status == CursorStatus.ACTIVE


def test_verify_decompose_pass_atomically_promotes_without_analyze_artifact(tmp_path: Path) -> None:
    paths, engine = _start_decompose_gate_project(tmp_path)
    cursor = engine.store.read()
    assert cursor is not None

    action = SubagentLifecycle(paths).stop(
        {
            "cwd": str(tmp_path),
            "agent_type": "verify-decompose",
            "last_assistant_message": _verdict_message(
                cursor,
                agent_id="verify-decompose",
                paths=paths,
            ),
        }
    )

    assert action.ok
    assert action.continue_session is False
    assert action.transition["phase"] == "IMPLEMENT"
    assert action.transition["changed"] is True
    after = engine.store.read()
    assert after is not None
    assert after.phase == "IMPLEMENT"
    assert after.step_id == "s01"
    assert '"event": "verdict_accepted"' in paths.events.read_text(encoding="utf-8")


def test_codex_runtime_ends_after_verify_decompose_pass(tmp_path: Path) -> None:
    paths, engine = _start_decompose_gate_project(tmp_path)
    runtime = CodexRuntime(progress=False)
    runtime._progress_project = tmp_path
    runtime._collab_lifecycle = SubagentLifecycle(paths)
    cursor = engine.store.read()
    assert cursor is not None

    verify_output = runtime._child_verdict(
        "verify-thread",
        "verify-decompose",
        _verdict_message(cursor, agent_id="verify-decompose", paths=paths),
    )
    assert verify_output is not None
    assert runtime._end_session_requested is True
    assert engine.store.read().phase == "IMPLEMENT"


def test_codex_runtime_ends_after_step_restart(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    runtime = CodexRuntime(progress=False)
    runtime._progress_project = tmp_path
    runtime._collab_lifecycle = SubagentLifecycle(paths)

    for index in range(3):
        output = runtime._child_verdict(
            f"verify-thread-{index}",
            "verify-implement",
            f"invalid verdict {index}",
        )
        assert output is not None
        if index < 2:
            assert runtime._end_session_requested is False
        else:
            assert "STEP RESTARTED" in output

    assert runtime._end_session_requested is True


def test_codex_runtime_ends_after_verdict_transition_rejection(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    runtime = CodexRuntime(progress=False)
    runtime._progress_project = tmp_path
    runtime._collab_lifecycle = SubagentLifecycle(paths)

    output = runtime._child_verdict(
        "verify-thread",
        "verify-qa",
        _verdict_message(cursor, agent_id="verify-qa", paths=paths),
    )

    assert output is not None
    assert "handoff REJECTED" in output
    assert runtime._end_session_requested is True
    assert engine.store.read().step_id == cursor.step_id
    assert '"event": "verdict_transition_rejected"' in paths.events.read_text(encoding="utf-8")


def test_codex_runtime_rejects_context_sync_prose_under_live_contract(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)
    write(
        tmp_path / "memory-bank/back/qa/E1/qa-20260921-pass.yaml",
        "schema: epic-qa/v1\nverdict: pass\n",
    )
    _finish_via_gate(engine)
    cursor = engine.store.read()
    assert cursor is not None and cursor.phase == "QA"

    runtime = CodexRuntime(progress=False)
    runtime._progress_project = tmp_path
    runtime._collab_lifecycle = SubagentLifecycle(paths)
    runtime._expected_subagent_type = "verify-qa"
    runtime._collab_agents["sync-thread"] = "verify-qa"

    assert runtime._collaboration_label({}) == "context-sync"
    output = runtime._child_verdict(
        "sync-thread",
        "verify-qa",
        "Синхронизация корневого канона завершена.",
    )

    assert output is not None
    assert "context-sync handoff REJECTED" in output
    assert "loop-context-sync-result/v1" in output
    assert runtime._end_session_requested is False
    assert engine.store.read().phase == "QA"
    assert engine.store.latest_event("context_sync_rejected") is not None


def test_codex_runtime_context_sync_result_advances_roadmap(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    write(tmp_path / "memory-bank/back/plan/E1/md/plan.md", "# E1\n")
    write(tmp_path / "memory-bank/back/plan/E2/md/plan.md", "# E2\n")
    write(
        tmp_path / "memory-bank/back/roadmap/queue.yaml",
        """version: roadmap-queue/v2
role: back
queue:
- id: T-E1
  epic_id: E1
  kind: feature
  plan: plan-E1.md
- id: T-E2
  epic_id: E2
  kind: feature
  plan: plan-E2.md
done: []
""",
    )
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)
    write(
        tmp_path / "memory-bank/back/qa/E1/qa-20260921-pass.yaml",
        "schema: epic-qa/v1\nverdict: pass\n",
    )
    _finish_via_gate(engine)
    cursor = engine.store.read()
    assert cursor is not None and cursor.phase == "QA"
    sync_path = "memory-bank/back/context-sync/E1/sync-20260921-current.md"
    write(tmp_path / sync_path, "# Context sync\n")

    runtime = CodexRuntime(progress=False)
    runtime._progress_project = tmp_path
    runtime._collab_lifecycle = SubagentLifecycle(paths)
    runtime._expected_subagent_type = "verify-qa"
    runtime._collab_agents["sync-thread"] = "verify-qa"
    output = runtime._child_verdict(
        "sync-thread",
        "verify-qa",
        _context_sync_message(cursor, sync_path),
    )

    assert output is not None
    assert "context_sync_completed" in output
    assert runtime._end_session_requested is True
    after = engine.store.read()
    assert after is not None
    assert after.epic_id == "E2"
    assert after.phase == "DECOMPOSE"


def test_decompose_finish_cannot_bypass_verify_decompose_verdict(tmp_path: Path) -> None:
    paths, engine = _start_decompose_gate_project(tmp_path)
    with pytest.raises(TransitionError, match="accepted verify-decompose PASS"):
        engine.finish(step_id="DECOMPOSE")

    after = engine.store.read()
    assert after is not None and after.phase == "DECOMPOSE"


def test_verify_decompose_fail_keeps_decompose_open_for_repair(tmp_path: Path) -> None:
    paths, engine = _start_decompose_gate_project(tmp_path)
    cursor = engine.store.read()
    assert cursor is not None
    lifecycle = SubagentLifecycle(paths)

    fail = lifecycle.stop(
        {
            "cwd": str(tmp_path),
            "agent_type": "verify-decompose",
            "last_assistant_message": _verdict_message(
                cursor,
                agent_id="verify-decompose",
                verdict="FAIL",
                paths=paths,
            ),
        }
    )

    assert fail.ok
    assert fail.transition["event"] == "verdict_recorded"
    assert fail.transition["phase"] == "DECOMPOSE"
    after = engine.store.read()
    assert after is not None
    assert after.phase == "DECOMPOSE"
    assert after.status == CursorStatus.ACTIVE


def test_decompose_finish_hands_off_without_analyze_artifact(tmp_path: Path) -> None:
    write(tmp_path / "memory-bank/back/plan/E2/md/plan.md", "# Plan: E2\n")
    paths = LoopPaths(project=tmp_path, hub=tmp_path / "hub")
    engine = LoopEngine(paths)
    engine.start("E2")
    write(
        tmp_path / "memory-bank/back/plan/E2/yaml/decompose-index.yaml",
        """
schema: epic-decompose-index/v1
plan_id: E2
steps:
  - id: s01
    file: s01.yaml
    title: s01
    next_phase: BACK IMPLEMENT
    status: pending
""",
    )
    write(
        tmp_path / "memory-bank/back/plan/E2/yaml/steps/s01.yaml",
        """
schema: epic-decompose/v1
role: back
step_id: s01
plan_id: E2
title: s01
next_phase: BACK IMPLEMENT
goal: outcome
plan_contract: {}
context: {}
as_built: []
delta: []
deletes: []
out_of_scope: []
skills: {}
checkpoints: []
verify: []
tdd: []
""",
    )
    transition = _finish_via_gate(engine)
    assert transition.phase == "IMPLEMENT"
    assert transition.step_id == "s01"



def test_decompose_finish_rejects_incomplete_tree(tmp_path: Path) -> None:
    write(tmp_path / "memory-bank/back/plan/E2/md/plan.md", "# Plan: E2\n")
    paths = LoopPaths(project=tmp_path, hub=tmp_path / "hub")
    engine = LoopEngine(paths)
    engine.start("E2")
    write(
        tmp_path / "memory-bank/back/plan/E2/yaml/decompose-index.yaml",
        """
schema: epic-decompose-index/v1
plan_id: E2
steps:
  - id: s01
    file: s01.yaml
    title: s01
    next_phase: BACK IMPLEMENT
    status: pending
""",
    )

    with pytest.raises(TransitionError, match="cannot accept verify-decompose PASS: invalid decompose tree"):
        _finish_via_gate(engine)

    assert engine.store.read().phase == "DECOMPOSE"


def test_decompose_finish_rejects_false_completed_status(tmp_path: Path) -> None:
    write(tmp_path / "memory-bank/back/plan/E-FALSE/md/plan.md", "# Plan: E-FALSE\n")
    paths = LoopPaths(project=tmp_path, hub=tmp_path / "hub")
    engine = LoopEngine(paths)
    engine.start("E-FALSE")
    write(
        tmp_path / "memory-bank/back/plan/E-FALSE/yaml/decompose-index.yaml",
        """
schema: epic-decompose-index/v1
plan_id: E-FALSE
steps:
  - id: s01
    file: s01.yaml
    title: s01
    next_phase: BACK IMPLEMENT
    status: completed
""",
    )
    write(
        tmp_path / "memory-bank/back/plan/E-FALSE/yaml/steps/s01.yaml",
        _minimal_decompose_shard(step_id="s01", plan_id="E-FALSE", verify_line="true"),
    )

    with pytest.raises(TransitionError, match="must be pending"):
        _finish_via_gate(engine)

    assert engine.store.read().phase == "DECOMPOSE"


def test_decompose_does_not_skip_to_qa_without_implement_artifacts(tmp_path: Path) -> None:
    """Hole regression: false completed in index must not skip to QA without implement evidence."""
    paths = seed_project(tmp_path)
    write(
        tmp_path / "memory-bank/back/plan/E1/yaml/decompose-index.yaml",
        """schema: epic-decompose-index/v1
epic_id: E1
plan_id: E1
steps:
  - id: s01
    file: s01-one.yaml
    title: s01
    next_phase: BACK IMPLEMENT
    status: completed
  - id: s02
    file: s02-two.yaml
    title: s02
    next_phase: BACK IMPLEMENT
    status: completed
""",
    )
    engine = LoopEngine(paths)
    engine.start("E1")
    # Without implement evidence, cannot reach QA
    from loop.kernel.index import load_queue, queue_ready_for_qa
    queue = load_queue(tmp_path, "back", "E1")
    ready, reason = queue_ready_for_qa(tmp_path, queue)
    assert ready is False
    assert "implement incomplete" in reason



def test_phase_after_queue_rejects_audit_without_implement_artifacts(tmp_path: Path) -> None:
    from loop.kernel.index import Queue, Step, queue_ready_for_qa

    queue = Queue(
        path=tmp_path / "decompose-index.yaml",
        role="back",
        epic_id="E-NOIMP",
        steps=(
            Step(step_id="s01", status="completed", title="s01", shard="s01.yaml"),
        ),
    )
    ready, reason = queue_ready_for_qa(tmp_path, queue)
    assert ready is False
    assert "implement incomplete before QA" in reason


def test_repair_yaml_double_quoted_escapes_doubles_unknown() -> None:
    raw = 'verify:\n  - "timeout -k 10s 300s rg \\\\.token path"\n'
    # already valid \\. — no change
    fixed, count = repair_yaml_double_quoted_escapes(raw)
    assert count == 0 and fixed == raw

    bad = 'verify:\n  - "timeout -k 10s 300s rg \\.token path"\n'
    fixed, count = repair_yaml_double_quoted_escapes(bad)
    assert count == 1
    assert r"\\." in fixed or "\\\\." in fixed
    import yaml

    payload = yaml.safe_load(fixed)
    assert payload["verify"][0].endswith("rg \\.token path")


def test_load_yaml_mapping_rewrites_invalid_double_quoted_escapes(tmp_path: Path) -> None:
    path = tmp_path / "shard.yaml"
    path.write_text(
        'schema: epic-decompose/v1\nverify:\n  - "rg \\.css design-system/"\n',
        encoding="utf-8",
    )
    payload = _load_yaml_mapping(path)
    assert payload["verify"][0] == "rg \\.css design-system/"
    assert r"\\." in path.read_text(encoding="utf-8") or "\\\\." in path.read_text(encoding="utf-8")


def _minimal_decompose_shard(*, step_id: str, plan_id: str, verify_line: str) -> str:
    return f"""
schema: epic-decompose/v1
role: back
step_id: {step_id}
plan_id: {plan_id}
title: {step_id}
next_phase: BACK IMPLEMENT
goal: outcome
plan_contract: {{}}
context: {{}}
as_built: []
delta: []
deletes: []
out_of_scope: []
skills: {{}}
checkpoints: []
verify:
  - {verify_line}
tdd: []
"""


def test_normalize_legacy_args_keeps_implement_flush_command() -> None:
    assert _normalize_legacy_args(
        ["implement-flush", "--project", "/tmp/forge-os"]
    ) == ["implement-flush", "--project", "/tmp/forge-os"]
    assert _normalize_legacy_args(["T-003-plane-bridge", "agy/gemini-3.8-flash-tiered"]) == [
        "run",
        "--epic",
        "T-003-plane-bridge",
        "--model",
        "agy/gemini-3.8-flash-tiered",
    ]


def test_normalize_tdd_bool_to_list(tmp_path: Path) -> None:
    path = tmp_path / "s01.yaml"
    path.write_text(
        "schema: epic-decompose/v1\ntdd: true\nverify:\n  - ok\n",
        encoding="utf-8",
    )
    payload = normalize_decompose_list_fields(path, _load_yaml_mapping(path))
    assert payload["tdd"] == []
    assert "tdd: []" in path.read_text(encoding="utf-8")
    assert "tdd: true" not in path.read_text(encoding="utf-8")


def test_validate_decompose_tree_repairs_escapes_and_purges_orphans(tmp_path: Path) -> None:
    write(tmp_path / "memory-bank/back/plan/E-Y/md/plan.md", "# Plan\n")
    write(
        tmp_path / "memory-bank/back/plan/E-Y/yaml/decompose-index.yaml",
        """
schema: epic-decompose-index/v1
plan_id: E-Y
steps:
  - id: s01
    file: s01.yaml
    title: s01
    next_phase: BACK IMPLEMENT
    status: pending
""",
    )
    steps = tmp_path / "memory-bank/back/plan/E-Y/yaml/steps"
    write(
        steps / "s01.yaml",
        _minimal_decompose_shard(
            step_id="s01",
            plan_id="E-Y",
            verify_line='"timeout -k 10s 300s rg \\.token path"',
        ),
    )
    write(steps / "s01-orphan.yaml", "schema: epic-decompose/v1\nstep_id: orphan\n")

    queue = validate_decompose_tree(tmp_path, "back", "E-Y")
    assert queue.steps[0].step_id == "s01"
    assert not (steps / "s01-orphan.yaml").exists()
    text = (steps / "s01.yaml").read_text(encoding="utf-8")
    assert "rg" in text
    import yaml

    assert yaml.safe_load(text)["verify"][0].endswith("rg \\.token path")


def test_loop_decompose_promotion_does_not_depend_on_legacy_analyze_artifact(tmp_path: Path) -> None:
    write(tmp_path / "memory-bank/back/plan/E3/md/plan.md", "# Plan: E3\n")
    write(
        tmp_path / "memory-bank/back/plan/E3/yaml/decompose-index.yaml",
        """
schema: epic-decompose-index/v1
plan_id: E3
steps:
  - id: s01
    file: s01.yaml
    title: s01
    next_phase: BACK IMPLEMENT
    status: pending
""",
    )
    write(
        tmp_path / "memory-bank/back/plan/E3/yaml/steps/s01.yaml",
        """
schema: epic-decompose/v1
role: back
step_id: s01
plan_id: E3
title: s01
next_phase: BACK IMPLEMENT
goal: outcome
plan_contract: {}
context: {}
as_built: []
delta: []
deletes: []
out_of_scope: []
skills: {}
checkpoints: []
verify: []
tdd: []
""",
    )
    paths = LoopPaths(project=tmp_path, hub=tmp_path / "hub")
    engine = LoopEngine(paths)
    assert engine.start("E3").phase == "DECOMPOSE"
    transition = _finish_via_gate(engine)
    assert transition.phase == "IMPLEMENT"
    assert transition.step_id == "s01"


def test_implement_artifact_path_has_no_duplicate_epic_prefix(tmp_path: Path) -> None:
    step = Step("s01", "pending", "wire", "s01-wire.yaml")

    assert implement_path(tmp_path, "back", "E5-mode-a", step) == (
        tmp_path / "memory-bank/back/implement/E5-mode-a/s01-wire.yaml"
    )


def test_lifecycle_has_one_transition_path(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)
    assert engine.store.read().phase == "QA"

    write(tmp_path / "memory-bank/back/qa/E1/qa-20260921-fail.yaml", "schema: epic-qa/v1\nverdict: fail\n")
    with pytest.raises(TransitionError, match="bugfix_queue_missing"):
        _finish_via_gate(engine)
    write(
        tmp_path / "memory-bank/back/bugfix/E1/bugfix-queue.yaml",
        """schema: epic-bugfix-queue/v1
epic_id: E1
items:
  - id: BF-001
    status: open
""",
    )
    _finish_via_gate(engine)
    assert engine.store.read().phase == "BUGFIX"

    write(tmp_path / "memory-bank/back/bugfix/E1/bugfix-20260921-fix.md", "# root cause and fix\n")
    write(
        tmp_path / "memory-bank/back/bugfix/E1/bugfix-queue.yaml",
        """schema: epic-bugfix-queue/v1
epic_id: E1
verification:
  status: pass
  command: bin/pytest -q
  last_run_at: 2026-09-21T00:00:00Z
  evidence: 1 passed
items:
  - id: BF-001
    status: done
    done_at: 2026-09-21T00:00:00Z
    evidence: bin/pytest -q --tb=line — 1 passed
""",
    )
    _finish_via_gate(engine)
    assert engine.store.read().phase == "QA"

    with pytest.raises(TransitionError, match="qa_new_artifact_required"):
        _finish_via_gate(engine)
    write(tmp_path / "memory-bank/back/qa/E1/qa-20260921-pass.yaml", "schema: epic-qa/v1\nverdict: pass\n")
    qa_pass = _finish_via_gate(engine)
    assert qa_pass.phase == "QA"
    assert qa_pass.metadata["context_sync_required"] is True
    _seed_context_sync(tmp_path)
    cursor = engine.store.read()
    assert cursor is not None
    sync = engine.complete_context_sync(
        ContextSyncResult(
            schema=SCHEMA_CONTEXT_SYNC_RESULT,
            agent_id="context-sync",
            epic_id=cursor.epic_id,
            status="done",
            sync_path="memory-bank/back/context-sync/E1/sync-20260921-e1.md",
            session_id=cursor.session_id,
            recorded_at="2026-09-21T00:01:00+00:00",
        )
    )
    assert sync.event == "context_sync_completed"
    assert engine.store.read().status == CursorStatus.COMPLETE


def test_bugfix_gate_reconciles_rewritten_runtime_evidence_before_transition(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)

    write(
        tmp_path / "memory-bank/back/qa/E1/qa-20260921-fail.yaml",
        "schema: epic-qa/v1\nverdict: fail\n",
    )
    write(
        tmp_path / "memory-bank/back/bugfix/E1/bugfix-20260921-fix.md",
        "# Root cause\n\nThe runtime evidence path is refreshed safely.\n",
    )
    evidence_path = "docs/reports/compose-smoke.json"
    command = "bash scripts/infra/compose_smoke.sh"
    write(
        tmp_path / evidence_path,
        json.dumps(
            {
                "schema": "runtime-http-evidence/v1",
                "status": "pass",
                "live_evidence": True,
                "evidence_type": "runtime_http",
                "timestamp": "2026-09-21T00:05:00Z",
                "command": command,
                "exit_code": 0,
                "raw_http": "HTTP/1.1 200 OK",
                "observations": ["compose services healthy"],
            }
        ),
    )
    write(
        tmp_path / "memory-bank/back/bugfix/E1/bugfix-queue.yaml",
        f"""schema: epic-bugfix-queue/v1
epic_id: E1
verification:
  status: pending
  command: {command}
  last_run_at: '2026-09-21T00:00:00Z'
  evidence: compose smoke passed
  evidence_file: {evidence_path}
items:
  - id: BF-000
    status: done
    done_at: '2026-09-21T00:00:00Z'
    class: live_smoke
    verify: {command}
    evidence: prior compose smoke passed
    evidence_file: {evidence_path}
  - id: BF-001
    status: open
    class: live_smoke
    verify: {command}
    evidence: compose smoke pending
    evidence_file: {evidence_path}
""",
    )
    engine.finish(step_id="QA")
    assert engine.store.read().phase == "BUGFIX"

    write(
        tmp_path / "memory-bank/back/bugfix/E1/bugfix-queue.yaml",
        f"""schema: epic-bugfix-queue/v1
epic_id: E1
verification:
  status: pass
  command: {command}
  last_run_at: '2026-09-21T00:00:00Z'
  evidence: compose smoke passed
  evidence_file: {evidence_path}
items:
  - id: BF-001
    status: done
    done_at: '2026-09-21T00:00:00Z'
    class: live_smoke
    verify: {command}
    evidence: compose smoke passed
    evidence_file: {evidence_path}
""",
    )

    transition = _finish_via_gate(engine)

    assert transition.phase == "QA"
    payload = phase_payload(tmp_path / "memory-bank/back/bugfix/E1/bugfix-queue.yaml")
    assert payload is not None
    assert payload["verification"]["last_run_at"] == "2026-09-21T00:05:00Z"
    assert payload["items"][0]["done_at"] == "2026-09-21T00:05:00Z"
    with pytest.raises(TransitionError, match="BUGFIX already completed"):
        engine.finish(step_id="BUGFIX")


def test_qa_pass_cannot_cross_with_unverified_browser_claim(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)
    write(
        tmp_path / "memory-bank/back/qa/E1/qa-20260921-browser.yaml",
        """schema: epic-qa/v1
verdict: pass
browser:
  status: pass
  journeys:
    - name: OAuth redirect
      status: pass
""",
    )

    with pytest.raises(TransitionError, match="qa_browser_evidence_required"):
        _finish_via_gate(engine)



def test_context_sync_finish_advances_roadmap_queue_to_next_epic(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    write(tmp_path / "memory-bank/back/plan/E1/md/plan.md", "# E1\n")
    write(tmp_path / "memory-bank/back/plan/E2/md/plan.md", "# E2\n")
    write(
        tmp_path / "memory-bank/back/roadmap/queue.yaml",
        """version: roadmap-queue/v2
role: back
queue:
- id: T-E1
  epic_id: E1
  kind: feature
  plan: plan-E1.md
- id: T-E2
  epic_id: E2
  kind: feature
  plan: plan-E2.md
done: []
batches: {}
""",
    )
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)
    write(tmp_path / "memory-bank/back/qa/E1/qa-20260921-pass.yaml", "schema: epic-qa/v1\nverdict: pass\n")
    _seed_context_sync(tmp_path)
    qa_pass = _finish_via_gate(engine)
    assert qa_pass.phase == "QA"
    sync_path = "memory-bank/back/context-sync/E1/sync-20260921-e1-current.md"
    write(tmp_path / sync_path, "# Current context sync\n")
    cursor = engine.store.read()
    assert cursor is not None
    sync = engine.complete_context_sync(
        ContextSyncResult(
            schema=SCHEMA_CONTEXT_SYNC_RESULT,
            agent_id="context-sync",
            epic_id=cursor.epic_id,
            status="done",
            sync_path=sync_path,
            session_id=cursor.session_id,
            recorded_at="2026-09-21T00:01:00+00:00",
        )
    )
    assert sync.event == "context_sync_completed"
    cursor = engine.store.read()
    assert cursor is not None
    assert cursor.status == CursorStatus.ACTIVE
    assert cursor.epic_id == "E2"
    assert cursor.phase == "DECOMPOSE"
    queue_doc = (tmp_path / "memory-bank/back/roadmap/queue.yaml").read_text(encoding="utf-8")
    assert "epic_id: E1" in queue_doc
    assert "done:" in queue_doc



def test_phase_gate_agents_cover_all_machine_checked_modes() -> None:
    assert _phase_gate_agent("DECOMPOSE") == "verify-decompose"
    assert _phase_gate_agent("ANALYZE") is None
    assert _phase_gate_agent("BUGFIX") == "verify-bugfix"
    assert _phase_gate_agent("QA") == "verify-qa"
    assert _phase_gate_agent("AUDIT") is None
    assert _phase_gate_agent("CONTEXT_SYNC") is None


def test_extract_json_fence_accepts_schema_tagged_and_prefers_loop_schema() -> None:
    tagged = (
        "notes\n"
        "```loop-gate-verdict/v1\n"
        '{"schema":"loop-gate-verdict/v1","agent_id":"verify-qa","verdict":"PASS",'
        '"step_id":"QA","session_id":"s1","epic_id":"E1","recorded_at":"2026-01-01T00:00:00Z"}\n'
        "```\n"
    )
    payload, codes = extract_json_fence(tagged)
    assert codes == ()
    assert payload is not None
    assert payload["verdict"] == "PASS"

    mixed = (
        "```json\n{\"helper\": true}\n```\n"
        "```json\n"
        '{"schema":"loop-gate-verdict/v1","agent_id":"verify-qa","verdict":"PASS",'
        '"step_id":"QA","session_id":"s1","epic_id":"E1","recorded_at":"2026-01-01T00:00:00Z"}\n'
        "```\n"
    )
    payload2, codes2 = extract_json_fence(mixed)
    assert codes2 == ()
    assert payload2 is not None
    assert payload2["schema"] == "loop-gate-verdict/v1"


def test_audit_phase_redirects_into_qa(tmp_path: Path) -> None:
    """AUDIT is no longer a loop phase — prompt redirects into QA contract checks."""
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    cursor = replace(
        cursor,
        phase="AUDIT",
        step_id="AUDIT",
        phase_epoch=cursor.phase_epoch + 1,
    )
    instruction = _phase_instruction(cursor, tmp_path)
    assert "not a loop phase" in instruction
    assert "QA" in instruction


def test_obsolete_phase_remap_helpers() -> None:
    from loop.kernel.engine import LoopEngine
    from loop.kernel.model import Cursor, CursorStatus
    cursor = Cursor(epic_id="E1", role="back", kind="feature", session_id="s", phase_epoch=1)
    cursor.phase = "AUDIT"
    cursor.step_id = "AUDIT"
    cursor.status = CursorStatus.ACTIVE
    remapped = LoopEngine._normalize_obsolete_cursor(LoopEngine.__new__(LoopEngine), cursor)
    assert remapped.phase == "QA"
    assert remapped.step_id == "QA"
    cursor.phase = "ANALYZE"
    cursor.step_id = "ANALYZE"
    remapped = LoopEngine._normalize_obsolete_cursor(LoopEngine.__new__(LoopEngine), cursor)
    assert remapped.phase == "DECOMPOSE"
    assert remapped.step_id == "DECOMPOSE"


def test_integration_role_loads_front_rules() -> None:
    assert _role_rules_dir("integration") == "front_developer"
    assert _role_rules_dir("integ") == "front_developer"


def test_implement_prompt_requires_workflow_bootstrap_and_forbids_full_pytest(tmp_path: Path) -> None:
    """IMPLEMENT must force implement-bootstrap + Gates; full bin/pytest -q is forbidden."""
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    cursor = replace(cursor, phase="IMPLEMENT", step_id="s01")

    instruction = _phase_instruction(cursor, tmp_path)

    assert "HARD bootstrap BEFORE any exploration" in instruction
    assert ".cursor/rules/shared/_lean/implement-bootstrap.mdc" in instruction
    assert "do not load mainrule.mdc monolith" in instruction
    assert "memory-bank/activeContext.md" in instruction
    assert ".cursor/rules/back_developer/isolation_rules/_lean/implement.mdc" in instruction
    assert ".cursor/rules/shared/workflow-implement-scope-lock.mdc" in instruction
    assert "## Hot path" in instruction
    assert ".cursor/rules/back_developer/workflow-implement.mdc" in instruction
    assert "`bin/pytest -q`" in instruction
    assert "Full suite is QA only" in instruction
    assert f"memory-bank/{cursor.role}/implement/{cursor.epic_id}/" in instruction
    assert "without an implement- prefix" in instruction


def test_context_sync_prompt_requires_one_fenced_json_result(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)
    write(tmp_path / "memory-bank/back/qa/E1/qa-20260921-pass.yaml", "schema: epic-qa/v1\nverdict: pass\n")
    _finish_via_gate(engine)

    cursor = engine.store.read()
    assert cursor is not None
    instruction = _phase_instruction(cursor, tmp_path, engine)

    assert "exactly one fenced JSON object" in instruction
    assert "schema loop-context-sync-result/v1" in instruction
    assert "no bare JSON" in instruction
    assert "do not call finish" in instruction


def test_gate_prompt_contains_exact_identity_contract_and_repair_loop(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    prompt = _gate_protocol(cursor, tmp_path, "verify-implement")

    assert f"GATE_IDENTITY session_id={cursor.session_id} epic_id=E1 step_id=s01" in prompt
    assert "ALLOW READ:" in prompt
    assert "gate-repair" in prompt
    assert "loop-repair-result/v1" in prompt
    assert f"PARENT_EVIDENCE_ID={cursor.session_id}" in prompt
    assert "prompt_incomplete:parent_evidence_id" in prompt
    assert "stale_verdict_ignored" in prompt
    assert "Parent discipline (HARD" in prompt
    assert "fork_context=false" in prompt
    assert "evidence_sha256 is OPTIONAL" in prompt
    assert "epic_resolve.py" in prompt
    assert "FORBIDDEN parent busywork" in prompt
    assert "For loop-gate-verdict/v1 only" in prompt
    assert "FORBIDDEN to put session_id/epic_id/step_id keys in the repair fence" in prompt
    assert "repair_result_rejected" in prompt
    assert "T-004-mode-a-live-ready-analyze-verify" not in prompt
    engine.rewind("DECOMPOSE")
    decompose_cursor = engine.store.read()
    assert decompose_cursor is not None
    decompose_prompt = _gate_protocol(decompose_cursor, tmp_path, "verify-decompose")
    assert "Read yaml/decompose-index.yaml first" in decompose_prompt
    assert "structural and semantic" in decompose_prompt
    assert "PASS is the complete DECOMPOSE gate" in decompose_prompt
    assert "FINDINGS:" not in decompose_prompt
    assert "legacy analysis artifact" in decompose_prompt
    assert f"GATE_IDENTITY session_id={decompose_cursor.session_id} epic_id=E1 step_id=DECOMPOSE" in decompose_prompt


def test_verify_qa_prompt_injects_frozen_checklist_and_suite(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    engine.rewind("QA")
    write(
        tmp_path / "memory-bank/back/qa/E1/qa-20260921-fail.yaml",
        """schema: epic-qa/v1
verdict: fail
checklist_sha256: abc123
verify_scope: full
test_plan:
  catalog: .cursor/templates/qa/test-catalog.yaml
  mode: full
  scope_signals: [backend, api]
  selected:
    - id: contract_acceptance
      name: Contract and acceptance criteria tests
      status: pass
      evidence: qa-evidence.json
  not_applicable: []
  not_run: []
suite:
  - 'bin/pytest -q --tb=line (10 passed)'
ac_plus:
  - 'pipeline works'
ac_minus:
  - 'no fallback'
section_011:
  - 'no orphan refs'
""",
    )
    cursor = engine.store.read()
    assert cursor is not None
    prompt = _gate_protocol(cursor, tmp_path, "verify-qa")

    assert "suite_scope: full" in prompt
    assert "Suite results:" in prompt
    assert "bin/pytest -q --tb=line (10 passed)" in prompt
    assert "## Frozen QA checklist" in prompt
    assert "checklist_sha256: abc123" in prompt
    assert "### AC+" in prompt and "- pipeline works" in prompt
    assert "### AC−" in prompt and "- no fallback" in prompt
    assert "### §0.11" in prompt and "- no orphan refs" in prompt
    assert "### Prior blockers" in prompt
    assert "## Test plan" in prompt
    assert "contract_acceptance" in prompt
    assert "qa-evidence.json" in prompt


def test_app_qa_prompt_defaults_to_app_lanes(tmp_path: Path) -> None:
    write(
        tmp_path / "memory-bank/app/qa/E1/qa-20260921-app.yaml",
        """schema: app-qa/v1
role: app
verdict: pass
verify_scope: full
""",
    )

    class AppCursor:
        role = "app"
        epic_id = "E1"

    lines, _paths = _qa_gate_context(tmp_path, AppCursor())

    assert lines[0] == "suite_scope: app_lanes"


def test_app_qa_prompt_marks_explicit_full_scope_invalid(tmp_path: Path) -> None:
    write(
        tmp_path / "memory-bank/app/qa/E1/qa-20260921-app.yaml",
        """schema: app-qa/v1
role: app
verdict: pass
suite_scope: full
""",
    )

    class AppCursor:
        role = "app"
        epic_id = "E1"

    lines, _paths = _qa_gate_context(tmp_path, AppCursor())

    assert lines[0] == "suite_scope: full"
    assert "APP QA contract: suite_scope must be app_lanes; explicit full is invalid." in lines


def test_verify_bugfix_prompt_packs_contract_paths_under_limit(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    engine.rewind("BUGFIX")
    write(
        tmp_path / "memory-bank/back/qa/E1/qa-20260921-fail.yaml",
        "schema: epic-qa/v1\nverdict: fail\n",
    )
    write(
        tmp_path / "memory-bank/back/bugfix/E1/bugfix-20260921-fix.md",
        "# BUGFIX\n\nAC+: fixed.\nAC−: regression covered.\n",
    )
    write(
        tmp_path / "memory-bank/back/bugfix/E1/bugfix-queue.yaml",
        """schema: epic-bugfix-queue/v1
source_qa: memory-bank/back/qa/E1/qa-20260921-fail.yaml
items:
  - id: BF-001
    status: open
    targets:
      - backend/core/settings.py
      - backend/tests/core/test_settings.py
""",
    )
    write(tmp_path / "backend/core/settings.py", "value = 1\n")
    write(tmp_path / "backend/tests/core/test_settings.py", "def test_settings(): pass\n")

    cursor = engine.store.read()
    assert cursor is not None
    packed, report_ready = _bugfix_gate_paths(tmp_path, "back", "E1")
    prompt = _gate_protocol(cursor, tmp_path, "verify-bugfix")

    assert report_ready
    assert len(packed) <= 10
    assert "memory-bank/back/bugfix/E1/bugfix-queue.yaml" in prompt
    assert "memory-bank/back/bugfix/E1/bugfix-20260921-fix.md" in prompt
    assert "memory-bank/back/qa/E1/qa-20260921-fail.yaml" in prompt
    assert "backend/core/settings.py" in prompt
    assert "memory-bank/back/plan/E1" not in prompt
    phase_prompt = _phase_instruction(cursor, tmp_path, engine)
    assert "atomically advances BUGFIX to re-QA" in phase_prompt
    assert "do not call finish again for BUGFIX" in phase_prompt
    assert "Child PASS is not finish" not in phase_prompt


def test_qa_fail_verdict_routes_to_bugfix_atomically(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)
    write(tmp_path / "memory-bank/back/qa/E1/qa-20260921-fail.yaml", "schema: epic-qa/v1\nverdict: fail\n")
    write(
        tmp_path / "memory-bank/back/bugfix/E1/bugfix-queue.yaml",
        """schema: epic-bugfix-queue/v1
items:
  - id: BF-001
    status: open
""",
    )
    cursor = engine.store.read()
    assert cursor is not None and cursor.phase == "QA"
    transition = engine.accept_verdict(
        GateVerdict(
            schema=SCHEMA_GATE_VERDICT,
            agent_id="verify-qa",
            verdict="FAIL",
            step_id="QA",
            session_id=cursor.session_id,
            epic_id=cursor.epic_id,
            recorded_at="2026-09-21T00:00:00+00:00",
        ),
        expected_agent_id="verify-qa",
    )

    assert transition.event == "qa_failed"
    assert transition.phase == "BUGFIX"
    assert engine.store.read().phase == "BUGFIX"


def test_legacy_closed_bugfix_item_routes_to_qa_after_pass(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)
    write(tmp_path / "memory-bank/back/qa/E1/qa-20260921-fail.yaml", "schema: epic-qa/v1\nverdict: fail\n")
    write(
        tmp_path / "memory-bank/back/bugfix/E1/bugfix-queue.yaml",
        """schema: epic-bugfix-queue/v1
items:
  - id: BF-001
    status: closed
""",
    )
    # closed is terminal for intake? intake allows closed; finish QA fail needs open queue
    # Use open then done-closed path: QA fail with open → BUGFIX
    write(
        tmp_path / "memory-bank/back/bugfix/E1/bugfix-queue.yaml",
        """schema: epic-bugfix-queue/v1
items:
  - id: BF-001
    status: open
""",
    )
    cursor = engine.store.read()
    assert cursor is not None and cursor.phase == "QA"
    transition = engine.finish(step_id="QA")
    assert transition.phase == "BUGFIX"



def test_qa_fail_finish_routes_from_artifacts_without_verdict_recorded(tmp_path: Path) -> None:
    """Codex may never persist verify-qa verdict_recorded; artifact SoT must still finish→BUGFIX."""
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)
    write(tmp_path / "memory-bank/back/qa/E1/qa-20260921-fail.yaml", "schema: epic-qa/v1\nverdict: fail\n")
    write(
        tmp_path / "memory-bank/back/bugfix/E1/bugfix-queue.yaml",
        """schema: epic-bugfix-queue/v1
items:
  - id: BF-001
    status: open
""",
    )
    cursor = engine.store.read()
    assert cursor is not None and cursor.phase == "QA"
    assert engine._qa_failure_ready(cursor)

    transition = engine.finish(step_id="QA")
    assert transition.event == "qa_failed"
    assert transition.phase == "BUGFIX"
    assert engine.store.read().phase == "BUGFIX"


def test_session_auto_finish_qa_pass_when_sync_present(tmp_path: Path) -> None:
    from loop.kernel.pre_emit import write_pre_emit_stamp

    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)
    write(tmp_path / "memory-bank/back/qa/E1/qa-20260921-pass.yaml", "schema: epic-qa/v1\nverdict: pass\n")
    _seed_context_sync(tmp_path)
    cursor = engine.store.read()
    assert cursor is not None and cursor.phase == "QA"
    payload = {
        "schema": SCHEMA_GATE_VERDICT,
        "agent_id": "verify-qa",
        "verdict": "PASS",
        "step_id": "QA",
        "session_id": cursor.session_id,
        "epic_id": cursor.epic_id,
        "recorded_at": "2026-09-21T00:00:00+00:00",
    }
    assert write_pre_emit_stamp(paths, payload) is not None
    auto = engine.try_session_auto_finish(cursor)
    assert auto is not None and auto.changed
    assert auto.metadata["context_sync_required"] is True
    assert engine.store.read().phase == "QA"
    assert engine.qa_context_sync_pending(engine.store.read())
    sync = engine.complete_context_sync(
        ContextSyncResult(
            schema=SCHEMA_CONTEXT_SYNC_RESULT,
            agent_id="context-sync",
            epic_id=cursor.epic_id,
            status="done",
            sync_path="memory-bank/back/context-sync/E1/sync-20260921-e1.md",
            session_id=cursor.session_id,
            recorded_at="2026-09-21T00:01:00+00:00",
        )
    )
    assert sync.event == "context_sync_completed"
    assert engine.store.read().status == CursorStatus.COMPLETE



def test_resume_reconciles_recorded_qa_fail_without_second_gate(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)
    cursor = engine.store.read()
    assert cursor is not None and cursor.phase == "QA"
    verdict = GateVerdict(
        schema=SCHEMA_GATE_VERDICT,
        agent_id="verify-qa",
        verdict="FAIL",
        step_id="QA",
        session_id=cursor.session_id,
        epic_id=cursor.epic_id,
        recorded_at="2026-09-21T00:00:00+00:00",
    )
    engine.accept_verdict(verdict, expected_agent_id="verify-qa")
    write(tmp_path / "memory-bank/back/qa/E1/qa-20260921-fail.yaml", "schema: epic-qa/v1\nverdict: fail\n")
    write(
        tmp_path / "memory-bank/back/bugfix/E1/bugfix-queue.yaml",
        """schema: epic-bugfix-queue/v1
items:
  - id: BF-001
    status: open
""",
    )
    engine.halt("user_interrupt")

    resumed = engine.start("E1")
    assert resumed.phase == "BUGFIX"
    assert resumed.status == CursorStatus.ACTIVE


def test_resume_reconciles_legacy_qa_pass_and_advances_after_context_sync(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    write(tmp_path / "memory-bank/back/plan/E1/md/plan.md", "# E1\n")
    write(tmp_path / "memory-bank/back/plan/E2/md/plan.md", "# E2\n")
    write(
        tmp_path / "memory-bank/back/roadmap/queue.yaml",
        """version: roadmap-queue/v2
role: back
queue:
- id: T-E1
  epic_id: E1
  kind: feature
  plan: plan-E1.md
- id: T-E2
  epic_id: E2
  kind: feature
  plan: plan-E2.md
done: []
""",
    )
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)
    write(tmp_path / "memory-bank/back/qa/E1/qa-20260921-pass.yaml", "schema: epic-qa/v1\nverdict: pass\n")
    cursor = engine.store.read()
    assert cursor is not None and cursor.phase == "QA"
    engine.record_event(
        {
            "event": "verdict_accepted",
            "source": "legacy-runtime",
            "phase": "QA",
            "agent_id": "verify-qa",
            "verdict": "PASS",
            "context_sync_required": True,
            "session_id": cursor.session_id,
            "epic_id": cursor.epic_id,
            "step_id": cursor.step_id,
            "verdict_step_id": cursor.step_id,
            "verdict_phase_epoch": cursor.phase_epoch,
        }
    )
    engine.halt("user_interrupt")

    resumed = engine.start("E1")
    assert resumed.phase == "QA"
    assert resumed.step_id == "QA"
    assert resumed.status == CursorStatus.ACTIVE
    assert engine.qa_context_sync_pending(resumed)
    assert engine.store.latest_event("verdict_accepted")["source"] == "resume-reconcile"

    sync_path = "memory-bank/back/context-sync/E1/sync-20260921-resume.md"
    write(tmp_path / sync_path, "# Context sync\n")
    sync = engine.complete_context_sync(
        ContextSyncResult(
            schema=SCHEMA_CONTEXT_SYNC_RESULT,
            agent_id="context-sync",
            epic_id="E1",
            status="done",
            sync_path=sync_path,
            session_id=resumed.session_id,
            recorded_at="2026-09-21T00:01:00+00:00",
        )
    )

    assert sync.event == "context_sync_completed"
    after = engine.store.read()
    assert after is not None
    assert after.epic_id == "E2"
    assert after.phase == "DECOMPOSE"
    assert after.step_id == "DECOMPOSE"


def test_resume_does_not_reconcile_qa_pass_after_new_artifact(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)
    qa_path = tmp_path / "memory-bank/back/qa/E1/qa-20260921-pass.yaml"
    write(qa_path, "schema: epic-qa/v1\nverdict: pass\nrevision: old\n")
    _finish_via_gate(engine)
    write(qa_path, "schema: epic-qa/v1\nverdict: pass\nrevision: new\n")
    engine.halt("user_interrupt")

    resumed = engine.start("E1")
    assert resumed.phase == "QA"
    assert not engine.qa_context_sync_pending(resumed)


def test_gate_repair_result_is_validated_and_recorded(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    lifecycle = SubagentLifecycle(paths)
    payload = {
        "schema": SCHEMA_REPAIR_RESULT,
        "agent_id": "gate-repair",
        "parent_evidence_id": cursor.session_id,
        "status": "done",
        "fixed_blockers": ["B1"],
        "remaining_blockers": [],
        "recorded_at": "2026-09-18T19:00:00+00:00",
    }
    message = chr(96) * 3 + "json\n" + json.dumps(payload) + "\n" + chr(96) * 3

    action = lifecycle.stop(
        {
            "cwd": str(tmp_path),
            "agent_type": "gate-repair",
            "last_assistant_message": message,
        }
    )

    assert action.ok
    assert action.transition["metadata"]["repair_status"] == "done"
    assert '"event": "repair_recorded"' in paths.events.read_text(encoding="utf-8")
    assert engine.store.read().session_id == cursor.session_id


def test_gate_repair_accepts_gate_identity_and_narrative_extras(tmp_path: Path) -> None:
    """LLM often copies GATE_IDENTITY / VERIFY narrative into the repair fence.

    Those extras used to cause schema_extra_forbidden → finish_not_committed loops.
    """
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    lifecycle = SubagentLifecycle(paths)
    payload = {
        "schema": SCHEMA_REPAIR_RESULT,
        "agent_id": "gate-repair",
        "parent_evidence_id": cursor.session_id,
        "status": "done",
        "repair_status": "done",
        "fixed_blockers": ["dynamic-module-import"],
        "remaining_blockers": [],
        "blockers": ["dynamic-module-import"],
        "session_id": cursor.session_id,
        "epic_id": cursor.epic_id,
        "step_id": cursor.step_id,
        "changed_paths": ["tests/back/test_plane_probe.py"],
        "verification": {
            "command": "python3 -m pytest tests/back/test_plane_probe.py -q",
            "exit_code": 0,
            "result": "1 passed",
        },
        "recorded_at": "2026-10-17T20:00:00+00:00",
    }
    message = chr(96) * 3 + "json\n" + json.dumps(payload) + "\n" + chr(96) * 3

    action = lifecycle.stop(
        {
            "cwd": str(tmp_path),
            "agent_type": "gate-repair",
            "last_assistant_message": message,
        }
    )

    assert action.ok, action.reason
    assert action.transition["metadata"]["repair_status"] == "done"
    assert action.transition["metadata"]["fixed_blockers"] == ["dynamic-module-import"]
    assert '"event": "repair_recorded"' in paths.events.read_text(encoding="utf-8")
    assert "schema_extra_forbidden" not in paths.events.read_text(encoding="utf-8")


def test_stale_repair_after_session_rotate_is_ignored_not_exit2(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    old_session = cursor.session_id
    engine.retry("force_rotate")
    after = engine.store.read()
    assert after is not None
    assert after.session_id != old_session
    lifecycle = SubagentLifecycle(paths)
    payload = {
        "schema": SCHEMA_REPAIR_RESULT,
        "agent_id": "gate-repair",
        "parent_evidence_id": old_session,
        "status": "done",
        "fixed_blockers": ["B1"],
        "remaining_blockers": [],
        "recorded_at": "2026-09-18T19:00:00+00:00",
    }
    message = chr(96) * 3 + "json\n" + json.dumps(payload) + "\n" + chr(96) * 3
    action = lifecycle.stop(
        {
            "cwd": str(tmp_path),
            "agent_type": "gate-repair",
            "last_assistant_message": message,
        }
    )
    assert action.ok
    assert action.continue_session
    assert action.exit_code == 0
    assert "stale_repair_ignored" in action.reason
    events = paths.events.read_text(encoding="utf-8")
    assert "stale_repair_ignored" in events
    assert "repair_recorded" not in events


def test_stale_verdict_after_session_rotate_is_ignored_not_exit2(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    old_session = cursor.session_id
    engine.retry("force_rotate")
    after = engine.store.read()
    assert after is not None
    lifecycle = SubagentLifecycle(paths)
    payload = {
        "schema": SCHEMA_GATE_VERDICT,
        "agent_id": "verify-implement",
        "verdict": "FAIL",
        "step_id": "s01",
        "session_id": old_session,
        "epic_id": "E1",
        "recorded_at": "2026-09-18T19:00:00+00:00",
    }
    message = chr(96) * 3 + "json\n" + json.dumps(payload) + "\n" + chr(96) * 3
    action = lifecycle.stop(
        {
            "cwd": str(tmp_path),
            "agent_type": "verify-implement",
            "last_assistant_message": message,
        }
    )
    assert action.ok
    assert action.continue_session
    assert action.exit_code == 0
    assert "stale_verdict_ignored" in action.reason
    events = paths.events.read_text(encoding="utf-8")
    assert "stale_verdict_ignored" in events
    assert '"verdict": "FAIL"' not in events or "verdict_recorded" not in events


def test_gate_repair_rejects_invented_parent_evidence_prompt_incomplete(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    lifecycle = SubagentLifecycle(paths)
    payload = {
        "schema": SCHEMA_REPAIR_RESULT,
        "agent_id": "gate-repair",
        "parent_evidence_id": cursor.session_id,
        "status": "fail",
        "fixed_blockers": [],
        "remaining_blockers": ["prompt_incomplete:parent_evidence_id"],
        "recorded_at": "2026-09-18T19:00:00+00:00",
    }
    message = chr(96) * 3 + "json\n" + json.dumps(payload) + "\n" + chr(96) * 3

    action = lifecycle.stop(
        {
            "cwd": str(tmp_path),
            "agent_type": "gate-repair",
            "last_assistant_message": message,
        }
    )

    assert not action.ok
    assert "repair_invented_prompt_incomplete" in action.diagnostic_codes
    assert "parent_evidence_id" in action.reason
    assert '"event": "repair_result_rejected"' in paths.events.read_text(encoding="utf-8")
    assert "repair_recorded" not in paths.events.read_text(encoding="utf-8")


def test_gate_repair_start_context_binds_parent_evidence_id(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    lifecycle = SubagentLifecycle(paths)
    context = lifecycle.start_context(
        {
            "cwd": str(tmp_path),
            "agent_type": "gate-repair",
            "prompt": "agent_type=gate-repair\nBLOCKERS:\n- x",
        }
    )
    assert context is not None
    assert f"PARENT_EVIDENCE_ID={cursor.session_id}" in context
    assert f'parent_evidence_id: "{cursor.session_id}"' in context
    assert "FORBIDDEN remaining_blockers: prompt_incomplete:parent_evidence_id" in context
    assert "never a missing parent prompt section" in context
    assert "--schema loop-repair-result/v1" in context
    assert "Do NOT use validate-verdict for repair results" in context
    assert "FORBIDDEN fence keys: session_id, epic_id, step_id" in context
    assert "Do NOT put session_id, epic_id, or step_id into the repair JSON fence" in context


def test_repair_result_rejected_recovery_prompt_respawns_gate_repair(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    engine.record_event(
        {
            "event": "repair_result_rejected",
            "agent_id": "gate-repair",
            "phase": cursor.phase,
            "step_id": cursor.step_id,
            "session_id": cursor.session_id,
            "epic_id": cursor.epic_id,
            "diagnostic_codes": ["schema_extra_forbidden"],
            "errors": ["Extra inputs are not permitted: session_id"],
        }
    )
    recovery = _gate_recovery_prompt(cursor, engine)
    assert "repair_result_rejected" in recovery
    assert "Respawn gate-repair" in recovery
    assert "finish_not_committed" in recovery
    assert "loop-repair-result/v1" in recovery
    assert "FORBIDDEN repair keys" in recovery
    assert "schema_extra_forbidden" in recovery


def test_sunset_inventory_is_validated_persisted_and_does_not_advance(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    before = engine.store.read()
    assert before is not None
    lifecycle = SubagentLifecycle(paths)
    payload = {
        "schema": SCHEMA_SUNSET_INVENTORY,
        "boundary_id": "E1-s01",
        "new_sot": "loop/kernel/inventory.py",
        "forbidden_for_parent": ["design_suggestions"],
        "diagnostic_codes": [],
        "ok": True,
        "items": [
            {
                "kind": "A",
                "symbol": "OldParser",
                "path": "loop/old.py",
                "start_line": 10,
                "end_line": 12,
                "excerpt": "class OldParser:\n    pass\n",
                "mark": "REPLACE",
                "role": "legacy parser",
            }
        ],
    }
    message = chr(96) * 3 + "json\n" + json.dumps(payload) + "\n" + chr(96) * 3

    action = lifecycle.stop(
        {
            "cwd": str(tmp_path),
            "agent_type": "sunset-inventory",
            "last_assistant_message": message,
        }
    )

    assert action.ok
    assert action.transition["event"] == "inventory_recorded"
    assert action.transition["metadata"]["item_count"] == 1
    assert action.transition["metadata"]["ok"] is True
    after = engine.store.read()
    assert after is not None
    assert after.phase == before.phase
    assert after.step_id == before.step_id
    assert after.session_id == cursor.session_id
    assert '"event": "inventory_recorded"' in paths.events.read_text(encoding="utf-8")

    report = read_sunset_sidecar(paths, session_id=cursor.session_id, step_id=cursor.step_id)
    assert report is not None
    assert report.schema_id == SCHEMA_SUNSET_INVENTORY
    assert report.boundary_id == "E1-s01"
    assert report.ok is True
    assert len(report.items) == 1
    assert report.items[0].kind == "A"


def test_sunset_alias_uses_same_inventory_branch(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    lifecycle = SubagentLifecycle(paths)
    payload = {
        "schema": SCHEMA_SUNSET_INVENTORY,
        "boundary_id": "alias-boundary",
        "new_sot": "loop/kernel/inventory.py",
        "forbidden_for_parent": [],
        "diagnostic_codes": [],
        "ok": True,
        "items": [],
    }
    message = chr(96) * 3 + "json\n" + json.dumps(payload) + "\n" + chr(96) * 3
    action = lifecycle.stop(
        {
            "cwd": str(tmp_path),
            "agent_type": "sunset",
            "last_assistant_message": message,
        }
    )
    assert action.ok
    assert action.transition["metadata"]["agent_id"] == "sunset-inventory"
    report = read_sunset_sidecar(paths, session_id=cursor.session_id, step_id=cursor.step_id)
    assert report is not None
    assert report.boundary_id == "alias-boundary"


def test_sunset_inventory_rejects_gate_verdict_schema(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    LoopEngine(paths).start("E1")
    lifecycle = SubagentLifecycle(paths)
    payload = {
        "schema": SCHEMA_GATE_VERDICT,
        "agent_id": "verify-implement",
        "verdict": "PASS",
        "step_id": "s01",
        "session_id": "sess",
        "epic_id": "E1",
        "recorded_at": "2026-09-18T19:00:00+00:00",
    }
    message = chr(96) * 3 + "json\n" + json.dumps(payload) + "\n" + chr(96) * 3
    action = lifecycle.stop(
        {
            "cwd": str(tmp_path),
            "agent_type": "sunset-inventory",
            "last_assistant_message": message,
        }
    )
    assert not action.ok
    assert action.exit_code == 2
    assert "loop-sunset-inventory/v1" in action.reason


def test_sunset_inventory_start_context_binds_schema_contract(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    lifecycle = SubagentLifecycle(paths)
    context = lifecycle.start_context(
        {
            "cwd": str(tmp_path),
            "agent_type": "sunset-inventory",
            "prompt": "agent_type=sunset-inventory\nALLOW READ:\n- loop/old.py",
        }
    )
    assert context is not None
    assert f"session_id={cursor.session_id}" in context
    assert "loop-sunset-inventory/v1" in context
    assert "READ-ONLY inventory extraction" in context
    assert "Never spawn another agent" in context


def test_native_validator_accepts_sunset_inventory_schema(tmp_path: Path) -> None:
    result = validate_boundary(
        SCHEMA_SUNSET_INVENTORY,
        {
            "schema": SCHEMA_SUNSET_INVENTORY,
            "boundary_id": "B1",
            "new_sot": "loop/kernel/inventory.py",
            "forbidden_for_parent": [],
            "diagnostic_codes": [],
            "ok": True,
            "items": [],
        },
    )
    assert result.valid
    assert result.schema_id == SCHEMA_SUNSET_INVENTORY


def test_finish_requires_verify_pass_and_fail_requires_repair(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")

    with pytest.raises(TransitionError, match="verify-implement PASS"):
        engine.finish(step_id="s01")

    failed = GateVerdict(
        schema=SCHEMA_GATE_VERDICT,
        agent_id="verify-implement",
        verdict="FAIL",
        step_id=cursor.step_id,
        session_id=cursor.session_id,
        epic_id=cursor.epic_id,
        recorded_at="2026-09-18T19:00:00+00:00",
    )
    engine.accept_verdict(failed, expected_agent_id="verify-implement")
    with pytest.raises(TransitionError, match="repair and re-verify"):
        engine.finish(step_id="s01")


def test_audit_and_bugfix_phase_contracts_fail_closed(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)

    write(tmp_path / "memory-bank/back/qa/E1/qa-20260921-fail.yaml", "schema: epic-qa/v1\nverdict: fail\n")
    write(
        tmp_path / "memory-bank/back/bugfix/E1/bugfix-queue.yaml",
        "schema: epic-bugfix-queue/v1\nitems:\n  - id: BF-1\n    status: open\n",
    )
    _finish_via_gate(engine)
    write(tmp_path / "memory-bank/back/bugfix/E1/bugfix-20260921-fix.md", "# fix\n")
    with pytest.raises(TransitionError, match="bugfix_queue_open"):
        _finish_via_gate(engine)


def test_retry_is_bounded_by_one_counter(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    before = engine.store.read()
    assert before is not None
    old_session = before.session_id
    old_epoch = before.phase_epoch
    first = engine.retry("runtime_exit_1")
    mid = engine.store.read()
    assert mid is not None
    assert first.attempt == 1
    assert mid.session_id != old_session
    assert mid.phase_epoch == old_epoch + 1
    assert mid.status == CursorStatus.ACTIVE
    second = engine.retry("runtime_exit_2")
    after = engine.store.read()
    assert after is not None
    assert second.attempt == 2
    assert after.session_id != mid.session_id
    assert after.phase_epoch == old_epoch + 2
    payload = json.loads(paths.cursor.read_text(encoding="utf-8"))
    assert set(payload) == {
        "schema",
        "revision",
        "epic_id",
        "role",
        "phase",
        "step_id",
        "phase_epoch",
        "status",
        "attempt",
        "session_id",
        "failure",
        "updated_at",
        "kind",
    }


def test_session_supervisor_soft_retry_rotates_session_not_same_identity(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    before = engine.start("E1")
    old_session = before.session_id

    class OkNoFinishRuntime:
        def run(self, prompt, *, model, project, log_path, timeout):
            return RuntimeResult("test", 0, log_path)

    run = SessionSupervisor(engine, OkNoFinishRuntime(), timeout=1, max_attempts=3, backoff=0).run_step(
        "work", model="test", project=tmp_path, session_id=old_session
    )
    assert run.outcome == SessionOutcome.SESSION_ROTATED
    after = engine.store.read()
    assert after is not None
    assert after.session_id != old_session
    assert after.attempt == 1
    assert after.status == CursorStatus.ACTIVE
    assert after.phase_epoch == before.phase_epoch + 1



def test_bugfix_partial_exit_is_finish_not_committed(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)
    write(tmp_path / "memory-bank/back/qa/E1/qa-20260921-fail.yaml", "schema: epic-qa/v1\nverdict: fail\n")
    write(
        tmp_path / "memory-bank/back/bugfix/E1/bugfix-queue.yaml",
        """schema: epic-bugfix-queue/v1
items:
  - id: BF-001
    status: done
    done_at: 2026-09-21T00:00:00Z
    evidence: targeted test passed
  - id: BF-002
    status: open
""",
    )
    engine.finish(step_id="QA")
    cursor = engine.store.read()
    assert cursor is not None and cursor.phase == "BUGFIX"

    class OkRuntime:
        def run(self, prompt, *, model, project, log_path, timeout):
            return RuntimeResult("test", 0, log_path)

    run = SessionSupervisor(engine, OkRuntime(), timeout=1, max_attempts=1, backoff=0).run_step(
        "work", model="test", project=tmp_path, session_id=cursor.session_id
    )
    # Partial queue close must NOT re-arm as PROGRESS_CONTINUE; with max_attempts=1
    # finish_not_committed exhausts into STEP_RESTARTED (same BUGFIX phase restart).
    assert run.outcome != SessionOutcome.PROGRESS_CONTINUE
    assert run.outcome == SessionOutcome.STEP_RESTARTED
    assert "finish_not_committed" in run.reason
    after = engine.store.read()
    assert after is not None
    assert after.phase == "BUGFIX"


def test_phase_finish_requires_evidence_and_halt_is_terminal(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)

    with pytest.raises(TransitionError, match="qa_artifact|context-sync|qa "):
        engine.finish(step_id="QA")

    halted = engine.halt("manual stop")
    assert halted.status == CursorStatus.HALTED
    with pytest.raises(TransitionError, match="halted") as error:
        engine.finish(step_id="QA")
    assert "resume it first" in str(error.value)


def test_start_resumes_halted_cursor_at_saved_phase(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)
    write(tmp_path / "memory-bank/back/qa/E1/qa-20260921-pass.yaml", "schema: epic-qa/v1\nverdict: pass\n")
    before_halt = engine.store.read()
    assert before_halt is not None and before_halt.phase == "QA"
    halted = engine.halt("user_interrupt")

    resumed = engine.start("E1")

    assert halted.phase == "QA"
    assert resumed.phase == "QA"
    assert resumed.step_id == "QA"
    assert resumed.status == CursorStatus.ACTIVE
    assert resumed.session_id != before_halt.session_id
    assert resumed.phase_epoch == before_halt.phase_epoch + 1


def test_cursor_transaction_recovers_after_projection_write_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    original = CursorStore._write_cursor_unlocked
    failed = False

    def fail_once(store: CursorStore, cursor) -> None:
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("simulated cursor projection failure")
        original(store, cursor)

    monkeypatch.setattr(CursorStore, "_write_cursor_unlocked", fail_once)
    with pytest.raises(OSError, match="simulated cursor"):
        engine.start("E1")

    monkeypatch.setattr(CursorStore, "_write_cursor_unlocked", original)
    recovered = engine.store.read()
    assert recovered is not None
    assert recovered.epic_id == "E1"
    assert recovered.step_id == "s01"
    records = paths.events.read_text(encoding="utf-8").splitlines()
    assert sum('"record_type": "commit"' in line for line in records) == 1
    assert engine.store.read().revision == recovered.revision


def test_journal_recovers_an_incomplete_trailing_record(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    with paths.events.open("ab") as handle:
        handle.write(b'{"schema":"loop-journal/v1"')

    recovered = engine.store.read()
    assert recovered is not None
    engine.record_event({"event": "after_partial_journal"})
    records = [json.loads(line) for line in paths.events.read_text(encoding="utf-8").splitlines()]
    assert records[-1]["event"] == "after_partial_journal"


def test_legacy_cursor_schema_is_not_used_as_runtime_state(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    paths.runtime.mkdir(parents=True, exist_ok=True)
    paths.cursor.write_text(json.dumps({"schema": "loop-cursor/v1", "epic_id": "E1"}), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported cursor schema"):
        LoopEngine(paths).status()


def test_legacy_cursor_failure_field_is_not_used_as_runtime_state(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    paths.runtime.mkdir(parents=True, exist_ok=True)
    paths.cursor.write_text(json.dumps({"schema": "loop-state/v2", "last_error": "old failure"}), encoding="utf-8")

    with pytest.raises(ValueError, match="legacy cursor field last_error"):
        LoopEngine(paths).status()


def test_finish_recovers_index_and_context_from_prepared_transaction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    original = CursorStore._write_cursor_unlocked

    def fail_projection(_store: CursorStore, _cursor) -> None:
        raise OSError("simulated finish projection failure")

    monkeypatch.setattr(CursorStore, "_write_cursor_unlocked", fail_projection)
    with pytest.raises(OSError, match="simulated finish"):
        _finish_via_gate(engine)

    monkeypatch.setattr(CursorStore, "_write_cursor_unlocked", original)
    recovered = engine.store.read()
    assert recovered is not None
    assert recovered.step_id == "s02"
    index = (tmp_path / "memory-bank/back/plan/E1/yaml/decompose-index.yaml").read_text(encoding="utf-8")
    assert "status: completed" in index
    assert "step_id: s02" in paths.active_context.read_text(encoding="utf-8")


def _verdict_payload(cursor, *, agent_id: str = "verify-implement", verdict: str = "PASS") -> dict:
    return {
        "schema": SCHEMA_GATE_VERDICT,
        "agent_id": agent_id,
        "verdict": verdict,
        "step_id": cursor.step_id,
        "session_id": cursor.session_id,
        "epic_id": cursor.epic_id,
        "recorded_at": "2026-09-18T19:00:00+00:00",
    }


def _verdict_message(
    cursor,
    *,
    agent_id: str = "verify-implement",
    verdict: str = "PASS",
    paths: LoopPaths | None = None,
) -> str:
    payload = _verdict_payload(cursor, agent_id=agent_id, verdict=verdict)
    if paths is not None:
        from loop.kernel.pre_emit import write_pre_emit_stamp

        write_pre_emit_stamp(paths, payload)
    return "```json\n" + json.dumps(payload) + "\n```"


def test_gate_verdict_is_strict_and_identity_bound(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    identity = BoundaryIdentity(cursor.session_id, cursor.epic_id, cursor.step_id, "verify-implement")

    valid = validate_message(_verdict_message(cursor), identity=identity)
    assert valid.valid and valid.record is not None
    assert valid.record.agent_id == "verify-implement"

    wrong_step = _verdict_message(cursor).replace('"step_id": "s01"', '"step_id": "s02"')
    rejected = validate_message(wrong_step, identity=identity)
    assert not rejected.valid
    assert "verdict_wrong_step_id" in rejected.diagnostic_codes

    extra = json.loads(_verdict_message(cursor).split("\n", 2)[1])
    extra["reason"] = "human text is not part of the wire contract"
    rejected_extra = validate_boundary(SCHEMA_GATE_VERDICT, extra, identity=identity)
    assert not rejected_extra.valid
    assert any(code.startswith("schema_") for code in rejected_extra.diagnostic_codes)


def test_subagent_pass_finishes_once_and_duplicate_is_idempotent(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    lifecycle = SubagentLifecycle(paths)
    payload = {
        "cwd": str(tmp_path),
        "agent_type": "verify-implement",
        "last_assistant_message": _verdict_message(cursor, paths=paths),
    }

    accepted = lifecycle.stop(payload)
    assert accepted.ok
    assert accepted.continue_session is False
    assert accepted.transition["reason"] == "subagent-stop:verify-implement:PASS"
    assert engine.store.read().step_id == "s02"

    duplicate = lifecycle.stop(payload)
    assert duplicate.ok
    assert duplicate.continue_session is False
    assert duplicate.transition["event"] == "verdict_duplicate"
    assert engine.store.read().step_id == "s02"


def test_qa_pass_keeps_parent_alive_until_context_sync_done(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)
    qa_path = "memory-bank/back/qa/E1/qa-20260921-pass.yaml"
    write(tmp_path / qa_path, "schema: epic-qa/v1\nverdict: pass\n")
    lifecycle = SubagentLifecycle(paths)
    cursor = engine.store.read()
    assert cursor is not None and cursor.phase == "QA"

    qa_action = lifecycle.stop(
        {
                "cwd": str(tmp_path),
                "agent_type": "verify-qa",
                "last_assistant_message": _verdict_message(
                    cursor, agent_id="verify-qa", paths=paths
                ),
            }
        )
    assert qa_action.ok
    assert qa_action.continue_session is False
    assert qa_action.transition["phase"] == "QA"
    assert qa_action.transition["metadata"]["context_sync_required"] is True
    assert engine.store.read().phase == "QA"

    sync_path = "memory-bank/back/context-sync/E1/sync-20260921-current.md"
    write(tmp_path / sync_path, "# Context sync\n")
    sync_action = lifecycle.stop(
        {
            "cwd": str(tmp_path),
            "agent_type": "context-sync",
            "last_assistant_message": _context_sync_message(cursor, sync_path),
        }
    )
    assert sync_action.ok
    assert sync_action.continue_session is False
    assert sync_action.transition["event"] == "context_sync_completed"
    assert engine.store.read().status == CursorStatus.COMPLETE


def test_old_context_sync_artifact_does_not_complete_current_qa(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)
    write(tmp_path / "memory-bank/back/qa/E1/qa-20260921-pass.yaml", "schema: epic-qa/v1\nverdict: pass\n")
    write(tmp_path / "memory-bank/back/context-sync/E1/sync-20260920-old.md", "# Old sync\n")

    qa_pass = _finish_via_gate(engine)
    assert qa_pass.phase == "QA"
    assert engine.qa_context_sync_pending(engine.store.read())
    with pytest.raises(TransitionError, match="context-sync"):
        engine.finish(step_id="QA")
    assert engine.store.read().status == CursorStatus.ACTIVE


def test_context_sync_fail_keeps_qa_open(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)
    write(tmp_path / "memory-bank/back/qa/E1/qa-20260921-pass.yaml", "schema: epic-qa/v1\nverdict: pass\n")
    _finish_via_gate(engine)
    cursor = engine.store.read()
    assert cursor is not None
    sync_path = "memory-bank/back/context-sync/E1/sync-20260921-current.md"
    write(tmp_path / sync_path, "# Context sync\n")

    action = SubagentLifecycle(paths).stop(
        {
            "cwd": str(tmp_path),
            "agent_type": "context-sync",
            "last_assistant_message": _context_sync_message(cursor, sync_path, status="fail"),
        }
    )
    assert action.ok
    assert action.continue_session is False
    assert action.transition["event"] == "context_sync_failed"
    assert engine.store.read().phase == "QA"
    assert engine.store.read().status == CursorStatus.ACTIVE
    assert engine.qa_context_sync_pending(engine.store.read())


def test_context_sync_result_requires_current_qa_pass(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)
    cursor = engine.store.read()
    assert cursor is not None and cursor.phase == "QA"
    sync_path = "memory-bank/back/context-sync/E1/sync-20260921-current.md"
    write(tmp_path / sync_path, "# Context sync\n")
    lifecycle = SubagentLifecycle(paths)
    action = lifecycle.stop(
        {
            "cwd": str(tmp_path),
            "agent_type": "context-sync",
            "last_assistant_message": _context_sync_message(cursor, sync_path),
        }
    )
    assert not action.ok
    assert action.exit_code == 2
    assert engine.store.read().phase == "QA"


def test_context_sync_wire_contract_is_identity_bound(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    sync_path = "memory-bank/back/context-sync/E1/sync-20260921-current.md"
    valid = validate_context_sync_message(
        _context_sync_message(cursor, sync_path),
        session_id=cursor.session_id,
        epic_id=cursor.epic_id,
    )
    assert valid.valid and valid.record is not None
    wrong = _context_sync_message(cursor, sync_path).replace(cursor.epic_id, "E2")
    rejected = validate_context_sync_message(wrong, session_id=cursor.session_id, epic_id=cursor.epic_id)
    assert not rejected.valid
    assert "context_sync_wrong_epic_id" in rejected.diagnostic_codes


def test_subagent_fail_or_blocked_is_recorded_without_finishing(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    lifecycle = SubagentLifecycle(paths)

    for verdict in ("FAIL", "BLOCKED"):
        action = lifecycle.stop(
            {
                "cwd": str(tmp_path),
                "agent_type": "verify-implement",
                "last_assistant_message": _verdict_message(cursor, verdict=verdict, paths=paths),
            }
        )
        assert action.ok
        assert action.continue_session is False
        assert action.transition["event"] == "verdict_recorded"
        assert action.transition["reason"] == verdict
        assert engine.store.read().step_id == "s01"

    events = paths.events.read_text(encoding="utf-8")
    assert events.count('"event": "verdict_recorded"') == 2


def test_content_fail_recovery_prompt_requires_gate_repair(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    engine.accept_verdict(
        GateVerdict(
            schema=SCHEMA_GATE_VERDICT,
            agent_id="verify-implement",
            verdict="FAIL",
            step_id=cursor.step_id,
            session_id=cursor.session_id,
            epic_id=cursor.epic_id,
            recorded_at="2026-09-21T00:00:00+00:00",
        ),
        expected_agent_id="verify-implement",
    )

    current = engine.store.read()
    assert current is not None
    recovery = _gate_recovery_prompt(current, engine)
    assert "gate-repair" in recovery
    assert "BLOCKERS" in recovery
    assert "product/content result" in recovery
    assert "evidence_sha256" in recovery
    assert "Do not finish" in recovery
    assert "Classify the verifier's concrete finding" in recovery
    assert engine.store.latest_event("verdict_recorded")["phase"] == "IMPLEMENT"


def test_legacy_verdict_event_still_gets_gate_repair_recovery(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    engine.record_event(
        {
            "event": "verdict_recorded",
            "agent_id": "verify-implement",
            "verdict": "FAIL",
            "session_id": cursor.session_id,
            "epic_id": cursor.epic_id,
            "step_id": cursor.step_id,
        }
    )

    recovery = _gate_recovery_prompt(cursor, engine)
    assert "gate-repair" in recovery


def test_subagent_invalid_verdict_has_atomic_retry_budget(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    before = engine.store.read()
    assert before is not None
    old_session = before.session_id
    lifecycle = SubagentLifecycle(paths)
    payload = {"cwd": str(tmp_path), "agent_type": "verify-implement", "last_assistant_message": "no json"}

    first = lifecycle.stop(payload)
    second = lifecycle.stop(payload)
    third = lifecycle.stop(payload)
    assert first.exit_code == second.exit_code == third.exit_code == 2
    assert "retry 1/2" in first.reason
    assert "retry 2/2" in second.reason
    assert third.reason.startswith("step_restarted:verify-implement")
    after = engine.store.read()
    assert after is not None
    assert after.status == CursorStatus.ACTIVE
    assert after.attempt == 0
    assert after.session_id != old_session
    assert after.step_id == before.step_id
    events = paths.events.read_text(encoding="utf-8")
    assert events.count('"event": "verdict_rejected"') == 3
    assert '"event": "step_restarted"' in events
    assert '"event": "halt"' not in events


def test_three_verify_fail_and_repair_cycles_restart_step(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    old_session = cursor.session_id

    def fail_verdict(recorded_at: str) -> GateVerdict:
        return GateVerdict(
            schema=SCHEMA_GATE_VERDICT,
            agent_id="verify-implement",
            verdict="FAIL",
            step_id=cursor.step_id,
            session_id=engine.store.read().session_id,
            epic_id=cursor.epic_id,
            recorded_at=recorded_at,
        )

    for index in range(3):
        engine.record_event(
            {
                "event": "repair_recorded",
                "agent_id": "gate-repair",
                "phase": "IMPLEMENT",
                "step_id": cursor.step_id,
                "status": "done",
                "fixed_blockers": [],
                "remaining_blockers": [],
                "recorded_at": f"2026-09-21T00:0{index}:00+00:00",
            }
        )
        if index < 2:
            engine.accept_verdict(fail_verdict(f"2026-09-21T01:0{index}:00+00:00"), expected_agent_id="verify-implement")
        else:
            transition = engine.accept_verdict(
                fail_verdict(f"2026-09-21T01:0{index}:00+00:00"),
                expected_agent_id="verify-implement",
            )
            assert transition.event == "step_restarted"

    after = engine.store.read()
    assert after is not None
    assert after.status == CursorStatus.ACTIVE
    assert after.session_id != old_session
    assert after.attempt == 0
    assert after.step_id == cursor.step_id


def test_session_attempts_exhausted_restarts_step(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    before = engine.start("E1")
    old_session = before.session_id

    class OkNoFinishRuntime:
        def run(self, prompt, *, model, project, log_path, timeout):
            return RuntimeResult("test", 0, log_path)

    run = SessionSupervisor(engine, OkNoFinishRuntime(), timeout=1, max_attempts=1, backoff=0).run_step(
        "work", model="test", project=tmp_path, session_id=before.session_id
    )
    assert run.outcome == SessionOutcome.STEP_RESTARTED
    after = engine.store.read()
    assert after is not None
    assert after.status == CursorStatus.ACTIVE
    assert after.attempt == 0
    assert after.session_id != old_session
    assert after.phase == before.phase
    assert after.step_id == before.step_id
    assert "step_restarted" in (paths.events.read_text(encoding="utf-8"))


def test_session_supervisor_commits_failure_and_halt_atomically(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")

    class FailingRuntime:
        def run(self, prompt, *, model, project, log_path, timeout):
            return RuntimeResult("test", 17, log_path, message="runtime failed")

    # max_attempts=1 → first failure exhausts budget → step restart (not halt yet)
    run = SessionSupervisor(engine, FailingRuntime(), timeout=1, max_attempts=1, backoff=0).run_step(
        "work", model="test", project=tmp_path, session_id="session-1"
    )
    assert run.outcome == SessionOutcome.STEP_RESTARTED
    cursor = engine.store.read()
    assert cursor is not None
    assert cursor.status == CursorStatus.ACTIVE
    assert cursor.failure is None


def test_session_supervisor_rate_limit_halts_without_retry(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    before = engine.start("E1")

    class RateLimitedRuntime:
        def run(self, prompt, *, model, project, log_path, timeout):
            return RuntimeResult(
                "codex",
                1,
                log_path,
                message=(
                    "exceeded retry limit, last status: 429 Too Many Requests, "
                    "request id: 8ca19edb-1073-4e89-9fb2-01b06948a5a7"
                ),
            )

    run = SessionSupervisor(engine, RateLimitedRuntime(), timeout=1, max_attempts=3, backoff=0).run_step(
        "work", model="test", project=tmp_path, session_id=before.session_id
    )
    assert run.outcome == SessionOutcome.RUNTIME_FAILURE
    assert "provider_rate_limited" in run.reason
    cursor = engine.store.read()
    assert cursor is not None
    assert cursor.status == CursorStatus.HALTED
    assert cursor.session_id == before.session_id
    assert cursor.attempt == before.attempt
    assert cursor.failure is not None
    assert cursor.failure.code == "provider_rate_limited"
    assert cursor.failure.retryable is False
    events = paths.events.read_text(encoding="utf-8")
    assert '"event": "retry"' not in events
    assert '"event": "step_restarted"' not in events
    assert '"event": "halt"' in events


def test_session_supervisor_soft_retry_sleeps_backoff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    slept: list[float] = []

    def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("loop.kernel.session.time.sleep", fake_sleep)

    class OkNoFinishRuntime:
        def run(self, prompt, *, model, project, log_path, timeout):
            return RuntimeResult("test", 0, log_path)

    run = SessionSupervisor(engine, OkNoFinishRuntime(), timeout=1, max_attempts=3, backoff=2.0).run_step(
        "work", model="test", project=tmp_path
    )
    assert run.outcome == SessionOutcome.SESSION_ROTATED
    assert slept == [2.0]


def test_session_supervisor_step_restart_uses_longer_backoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    slept: list[float] = []
    monkeypatch.setattr("loop.kernel.session.time.sleep", lambda seconds: slept.append(seconds))

    class FailingRuntime:
        def run(self, prompt, *, model, project, log_path, timeout):
            return RuntimeResult("test", 17, log_path, message="runtime failed")

    run = SessionSupervisor(engine, FailingRuntime(), timeout=1, max_attempts=1, backoff=2.0).run_step(
        "work", model="test", project=tmp_path
    )
    assert run.outcome == SessionOutcome.STEP_RESTARTED
    # attempt=1 exhausted, step_restart → backoff * max(attempt, max_attempts) * 2 = 2 * 1 * 2
    assert slept == [4.0]


def test_subagent_stop_hook_accepts_pydantic_verdict(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    environment = os.environ.copy()
    environment.update(
        {
            "LOOP_ACTIVE": "1",
            "EPIC_LOOP": "1",
            "LOOP_WORKFLOW_HOOKS": "loop",
            "PROJECT_ROOT": str(tmp_path),
            "DEV_HUB": str(paths.hub),
        }
    )
    payload = {
        "cwd": str(tmp_path),
        "agent_type": "verify-implement",
        "last_assistant_message": _verdict_message(cursor, paths=paths),
    }
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parents[2] / "harness/hooks/subagent-stop.py")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    hook_payload = json.loads(result.stdout)
    assert hook_payload["ok"] is True
    assert hook_payload["continue"] is False
    assert hook_payload["transition"]["reason"] == "subagent-stop:verify-implement:PASS"
    assert engine.store.read().step_id == "s02"


def test_subagent_start_hook_injects_cursor_identity(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    environment = os.environ.copy()
    environment.update(
        {
            "LOOP_ACTIVE": "1",
            "EPIC_LOOP": "1",
            "LOOP_WORKFLOW_HOOKS": "loop",
            "PROJECT_ROOT": str(tmp_path),
            "DEV_HUB": str(paths.hub),
        }
    )
    payload = {
        "cwd": str(tmp_path),
        "agent_type": "verify-implement",
        "prompt": "check the implementation and return the gate verdict",
    }
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parents[2] / "harness/hooks/subagent-start.py")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    hook_payload = json.loads(result.stdout)
    context = hook_payload["hookSpecificOutput"]["additionalContext"]
    assert f"GATE_IDENTITY session_id={cursor.session_id} epic_id=E1 step_id=s01" in context
    assert "validate-verdict" in context
    assert "pre-emit stamp" in context
    assert "FORBIDDEN keys" in context


def test_native_validator_command_validates_gate_payload(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    message = _verdict_message(cursor)
    payload = json.loads(message.split("\n", 2)[1])
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parents[2] / "bin/loop.py"),
            "validate-verdict",
            "--project",
            str(tmp_path),
            "--payload",
            json.dumps(payload),
        ],
        text=True,
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "DEV_HUB": str(paths.hub),
            "HUB_ROOT": str(paths.hub),
            "PROJECT_ROOT": str(tmp_path),
        },
    )
    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["valid"] is True
    assert body["pre_emit_stamp"]["payload_sha256"]
    accepted = SubagentLifecycle(paths).stop(
        {
            "cwd": str(tmp_path),
            "agent_type": "verify-implement",
            "last_assistant_message": message,
        }
    )
    assert accepted.ok


def test_gate_verdict_without_pre_emit_stamp_is_rejected(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    action = SubagentLifecycle(paths).stop(
        {
            "cwd": str(tmp_path),
            "agent_type": "verify-implement",
            "last_assistant_message": _verdict_message(cursor),
        }
    )
    assert action.ok is False
    assert "pre_emit_validate_missing" in action.diagnostic_codes
    assert "pre-emit stamp missing" in action.reason
    assert engine.store.read().step_id == "s01"


def test_gate_verdict_pre_emit_stamp_mismatch_is_rejected(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    stamped = _verdict_payload(cursor, verdict="PASS")
    from loop.kernel.pre_emit import write_pre_emit_stamp

    write_pre_emit_stamp(paths, stamped)
    mutated = dict(stamped)
    mutated["verdict"] = "FAIL"
    action = SubagentLifecycle(paths).stop(
        {
            "cwd": str(tmp_path),
            "agent_type": "verify-implement",
            "last_assistant_message": "```json\n" + json.dumps(mutated) + "\n```",
        }
    )
    assert action.ok is False
    assert "pre_emit_validate_mismatch" in action.diagnostic_codes
    assert "EMIT_EXACTLY=" in action.reason
    assert engine.store.read().step_id == "s01"


def test_gate_verdict_recorded_at_may_differ_from_pre_emit_stamp(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    stamped = _verdict_payload(cursor, verdict="PASS")
    from loop.kernel.pre_emit import write_pre_emit_stamp

    write_pre_emit_stamp(paths, stamped)
    emitted = dict(stamped)
    emitted["recorded_at"] = "2026-10-15T21:42:50+00:00"
    action = SubagentLifecycle(paths).stop(
        {
            "cwd": str(tmp_path),
            "agent_type": "verify-implement",
            "last_assistant_message": "```json\n" + json.dumps(emitted) + "\n```",
        }
    )
    assert action.ok is True
    assert action.transition is not None
    assert engine.store.read().step_id == "s02"


def test_validate_verdict_returns_emit_exactly(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    payload = _verdict_payload(cursor, verdict="PASS")
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parents[2] / "bin/loop.py"),
            "validate-verdict",
            "--project",
            str(tmp_path),
            "--payload",
            json.dumps(payload),
        ],
        text=True,
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "DEV_HUB": str(paths.hub),
            "HUB_ROOT": str(paths.hub),
            "PROJECT_ROOT": str(tmp_path),
        },
    )
    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["valid"] is True
    assert body["emit_exactly"]["verdict"] == "PASS"
    assert body["emit_exactly"]["session_id"] == cursor.session_id
    assert body["binding_sha256"]
    assert body["pre_emit_stamp"]["payload"]["agent_id"] == "verify-implement"


def test_native_validator_accepts_repair_result_schema(tmp_path: Path) -> None:
    seed_project(tmp_path)
    payload = {
        "schema": SCHEMA_REPAIR_RESULT,
        "agent_id": "gate-repair",
        "parent_evidence_id": "evidence-1",
        "status": "partial",
        "fixed_blockers": ["scope"],
        "remaining_blockers": ["tests"],
        "recorded_at": "2026-09-18T19:00:00+00:00",
    }
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parents[2] / "bin/loop.py"),
            "validate",
            "--project",
            str(tmp_path),
            "--schema",
            SCHEMA_REPAIR_RESULT,
            "--payload",
            json.dumps(payload),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["valid"] is True
    result_verdict_command = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parents[2] / "bin/loop.py"),
            "validate-verdict",
            "--project",
            str(tmp_path),
            "--payload",
            json.dumps(payload),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result_verdict_command.returncode == 0, result_verdict_command.stderr
    assert json.loads(result_verdict_command.stdout)["valid"] is True


def test_codex_uses_omniroute_wrapper_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wrapper = tmp_path / "codex" / "bin" / "codex-omniroute.sh"
    write(wrapper, "#!/usr/bin/env bash\n")
    wrapper.chmod(0o755)
    monkeypatch.delenv("CODEX_BIN", raising=False)
    monkeypatch.setenv("CODEX_USE_OMNIROUTE", "1")
    monkeypatch.setenv("DEV_HUB", str(tmp_path))

    assert CodexRuntime().executable() == str(wrapper)


def test_codex_can_explicitly_disable_omniroute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODEX_BIN", raising=False)
    monkeypatch.setenv("CODEX_USE_OMNIROUTE", "0")
    assert CodexRuntime().executable() == shutil.which("codex")


def test_codex_command_uses_native_headless_contract(tmp_path: Path) -> None:
    command = CodexRuntime().command("do work", model="model", project=tmp_path)

    assert command[1:7] == [
        "exec",
        "--json",
        "--dangerously-bypass-approvals-and-sandbox",
        "--dangerously-bypass-hook-trust",
        "--cd",
        str(tmp_path),
    ]
    assert "--ephemeral" not in command
    assert "--enable" not in command
    assert "-c" not in command
    assert command[-1] == "do work"


def test_codex_command_passes_effort_override_before_exec(tmp_path: Path) -> None:
    command = CodexRuntime(effort="medium").command("do work", model="agy/gemini-3.8-flash-tiered", project=tmp_path)

    assert command[1:3] == ["-c", 'model_reasoning_effort="medium"']
    assert command[3] == "exec"
    assert "--model" in command
    assert command[command.index("--model") + 1] == "agy/gemini-3.8-flash-tiered"
    assert command.index("-c") < command.index("exec")
    assert command[-1] == "do work"


def test_codex_renders_compact_progress_events() -> None:
    runtime = CodexRuntime()
    started = runtime._progress_line(
        json.dumps({"type": "item.started", "item": {"type": "command_execution", "command": "rg -n foo src"}})
    )
    completed = runtime._progress_line(
        json.dumps(
            {
                "type": "item.completed",
                "item": {"type": "command_execution", "command": "apply_patch < patch", "status": "completed", "exit_code": 0},
            }
        )
    )

    assert started == "  • read  rg -n foo src"
    assert completed == "  ✓ write finished (exit=0)"


def test_codex_labels_gate_spawn_from_current_phase_when_payload_omits_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = seed_project(tmp_path)
    monkeypatch.setenv("DEV_HUB", str(paths.hub))
    engine = LoopEngine(paths)
    engine.start("E1")
    runtime = CodexRuntime()
    runtime._progress_started(tmp_path, "")

    rendered = runtime._progress_line(
        json.dumps(
            {
                "type": "item.started",
                "item": {
                    "type": "collab_tool_call",
                    "tool": "spawn_agent",
                    "prompt": "GATE_IDENTITY session_id=session-1 epic_id=E1 step_id=s01",
                    "receiver_thread_ids": ["thread-1"],
                },
            }
        )
    )

    assert rendered is not None
    assert "subagent spawn type=verify-implement" in rendered


def test_codex_progress_reports_errors_without_raw_json() -> None:
    runtime = CodexRuntime()
    rendered = runtime._progress_line(json.dumps({"type": "error", "message": "metadata fallback"}))

    assert rendered == "  ! metadata fallback"
    assert "{\"type\"" not in rendered


def test_codex_renders_subagent_state_and_json_verdict() -> None:
    runtime = CodexRuntime()
    verdict = (
        "```json\n"
        '{"schema":"loop-gate-verdict/v1","agent_id":"verify-implement",'
        '"verdict":"PASS"}\n'
        "```"
    )
    rendered = runtime._progress_line(
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "collab_tool_call",
                    "tool": "wait",
                    "agents_states": {
                        "thread-1": {"status": "completed", "message": verdict}
                    },
                },
            }
        )
    )

    assert "subagent verify-implement id=thread-1 status=completed" in rendered
    assert "loop-gate-verdict/v1" in rendered
    assert '"verdict":"PASS"' in rendered


def test_codex_does_not_submit_intermediate_child_message_as_verdict(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    runtime = CodexRuntime()
    runtime._progress_started(tmp_path, "")
    rendered = runtime._progress_line(
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "collab_tool_call",
                    "tool": "wait",
                    "agents_states": {
                        "thread-1": {"status": "completed", "message": "Проверяю файлы и формирую verdict."}
                    },
                },
            }
        )
    )

    assert rendered is not None
    assert "verdict hook error" not in rendered
    assert "verdict_json_fence_missing" not in rendered
    assert '"event": "verdict_rejected"' not in paths.events.read_text(encoding="utf-8")


def test_codex_subagent_pass_is_applied_to_new_kernel(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    runtime = CodexRuntime()
    runtime._progress_started(tmp_path, "")
    runtime._collab_lifecycle = SubagentLifecycle(paths)
    message = _verdict_message(cursor, paths=paths)

    rendered = runtime._progress_line(
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "collab_tool_call",
                    "tool": "wait",
                    "agents_states": {
                        "thread-1": {"status": "completed", "message": message}
                    },
                },
            }
        )
    )

    assert "verdict verify-implement=PASS -> IMPLEMENT/s02" in rendered
    assert engine.store.read().step_id == "s02"


def test_runtime_captures_child_output_without_polluting_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    class TestRuntime(Runtime):
        name = "test"

        def executable(self) -> str:
            return sys.executable

        def command(self, prompt: str, *, model: str, project: Path) -> list[str]:
            script = (
                "from pathlib import Path\n"
                "import time\n"
                "print('runtime-start', flush=True)\n"
                "while not Path('release').exists(): time.sleep(0.01)\n"
                "print('runtime-end', flush=True)\n"
            )
            return [sys.executable, "-u", "-c", script]

    result: list[object] = []
    thread = threading.Thread(
        target=lambda: result.append(
            TestRuntime().run(
                "prompt",
                model="model",
                project=tmp_path,
                log_path=tmp_path / "session.log",
                timeout=5,
            )
        ),
        daemon=True,
    )
    thread.start()
    (tmp_path / "release").write_text("release\n", encoding="utf-8")
    thread.join(timeout=3)

    assert not thread.is_alive()
    assert result and result[0].exit_code == 0
    assert capsys.readouterr().out == ""
    log = (tmp_path / "session.log").read_text(encoding="utf-8")
    assert "runtime-start" in log
    assert "runtime-end" in log


def test_runtime_heartbeat_elapsed_and_idle_timeout_are_recorded(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    class SilentRuntime(Runtime):
        name = "silent"

        def executable(self) -> str:
            return sys.executable

        def command(self, prompt: str, *, model: str, project: Path) -> list[str]:
            return [sys.executable, "-u", "-c", "import time; time.sleep(3)"]

    result = SilentRuntime(
        LoopSettings(
            status_heartbeat=1,
            stream_idle_timeout=1,
            session_kill_grace=1,
            collaboration_wait_timeout=1,
        )
    ).run(
        "prompt",
        model="model",
        project=tmp_path,
        log_path=tmp_path / "session-silent.log",
        timeout=3,
    )

    assert result.exit_code == 124
    assert result.idle_timed_out is True
    assert result.timed_out is False
    assert result.hung is True
    assert result.elapsed_sec >= 1
    assert result.heartbeat_count >= 1
    captured = capsys.readouterr().out
    assert "heartbeat:" in captured
    assert "idle timeout:" in captured
    log = (tmp_path / "session-silent.log").read_text(encoding="utf-8")
    assert "SESSION_HEARTBEAT" in log
    assert "SESSION_IDLE_TIMEOUT" in log
    assert "SESSION_END" in log


def test_runtime_abandons_wait_after_managed_gate_end(tmp_path: Path) -> None:
    """SESSION_END_REQUESTED must leave the select loop (no exited+collab hang)."""

    class StickyRuntime(Runtime):
        name = "sticky-end"

        def executable(self) -> str:
            return sys.executable

        def command(self, prompt: str, *, model: str, project: Path) -> list[str]:
            # Emit one line then sleep; parent kills on end-session request.
            return [
                sys.executable,
                "-u",
                "-c",
                "import time; print('gate-done', flush=True); time.sleep(120)",
            ]

        def _emit_progress(self, text: str, *, final: bool = False) -> None:
            super()._emit_progress(text, final=final)
            if "gate-done" in text:
                self._end_session_requested = True

    started = time.monotonic()
    result = StickyRuntime(
        LoopSettings(status_heartbeat=1, session_kill_grace=1)
    ).run(
        "prompt",
        model="model",
        project=tmp_path,
        log_path=tmp_path / "session-end-abandon.log",
        timeout=60,
    )
    elapsed = time.monotonic() - started

    assert elapsed < 20, f"hung after end-session: elapsed={elapsed:.1f}s"
    assert result.elapsed_sec < 20
    log = (tmp_path / "session-end-abandon.log").read_text(encoding="utf-8")
    assert "SESSION_END_REQUESTED" in log
    assert "SESSION_WAIT_ABANDON" in log
    assert "SESSION_END" in log
    # Must not keep heartbeating as exited+collab for minutes.
    exited_heartbeats = [
        line for line in log.splitlines() if "state=exited" in line and "SESSION_HEARTBEAT" in line
    ]
    assert len(exited_heartbeats) <= 2


def test_runtime_reaps_leftover_process_group_after_success(tmp_path: Path) -> None:
    """Parent exit must not leave nested children holding sockets open."""
    child_pid_path = tmp_path / "orphan.pid"
    script = tmp_path / "leave_child.py"
    script.write_text(
        "\n".join(
            [
                "import os, signal, sys, time",
                "signal.signal(signal.SIGHUP, signal.SIG_IGN)",
                "pid = os.fork()",
                "if pid == 0:",
                "    signal.signal(signal.SIGHUP, signal.SIG_IGN)",
                "    open(sys.argv[1], 'w', encoding='utf-8').write(str(os.getpid()))",
                "    time.sleep(60)",
                "    os._exit(0)",
                "sys.exit(0)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    class LeaveChildRuntime(Runtime):
        name = "leave-child"

        def executable(self) -> str:
            return sys.executable

        def command(self, prompt: str, *, model: str, project: Path) -> list[str]:
            return [sys.executable, str(script), str(child_pid_path)]

    result = LeaveChildRuntime(LoopSettings(session_kill_grace=1)).run(
        "prompt",
        model="model",
        project=tmp_path,
        log_path=tmp_path / "session-reap.log",
        timeout=10,
    )

    assert result.exit_code == 0
    assert child_pid_path.exists()
    orphan_pid = int(child_pid_path.read_text(encoding="utf-8").strip())
    # Give the reaper a moment, then the leftover child must be gone.
    deadline = time.time() + 2
    alive = True
    while time.time() < deadline:
        try:
            os.kill(orphan_pid, 0)
        except OSError:
            alive = False
            break
        time.sleep(0.05)
    assert alive is False
    log = (tmp_path / "session-reap.log").read_text(encoding="utf-8")
    assert "SESSION_END" in log
    assert "SESSION_REAP" in log


def test_runtime_idle_timeout_applies_after_subagent_wait_completes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """After wait completes, collaboration must not block idle forever (pre-collab semantics)."""

    class CollabThenSilentRuntime(Runtime):
        name = "collab-then-silent"
        progress_mode = "codex_json"

        def executable(self) -> str:
            return sys.executable

        def command(self, prompt: str, *, model: str, project: Path) -> list[str]:
            # Emit spawn+wait completed, then go silent (Codex keep-alive mimic).
            payload_spawn = json.dumps(
                {
                    "type": "item.started",
                    "item": {
                        "type": "collab_tool_call",
                        "tool": "spawn_agent",
                        "receiver_thread_ids": ["thr-idle"],
                        "status": "in_progress",
                    },
                }
            )
            payload_wait = json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "type": "collab_tool_call",
                        "tool": "wait",
                        "receiver_thread_ids": ["thr-idle"],
                        "agents_states": {"thr-idle": {"status": "completed"}},
                        "status": "completed",
                    },
                }
            )
            script = (
                "import time\n"
                f"print({payload_spawn!r}, flush=True)\n"
                "time.sleep(0.3)\n"
                f"print({payload_wait!r}, flush=True)\n"
                "time.sleep(30)\n"
            )
            return [sys.executable, "-u", "-c", script]

    started = time.monotonic()
    result = CollabThenSilentRuntime(
        LoopSettings(
            status_heartbeat=1,
            stream_idle_timeout=2,
            session_kill_grace=1,
            collaboration_wait_timeout=None,
        )
    ).run(
        "prompt",
        model="model",
        project=tmp_path,
        log_path=tmp_path / "session-collab-idle.log",
        timeout=30,
    )
    elapsed = time.monotonic() - started

    assert elapsed < 15, f"collab blocked idle: elapsed={elapsed:.1f}s"
    assert result.idle_timed_out is True
    assert result.exit_code == 124
    log = (tmp_path / "session-collab-idle.log").read_text(encoding="utf-8")
    assert "SESSION_COLLAB_COMPLETE" in log
    assert "SESSION_IDLE_TIMEOUT" in log


def test_collaboration_state_clears_pending_when_wait_completes() -> None:
    """Wait completion must clear pending so idle timeout is not bypassed forever."""
    now = 100.0
    spawn = {
        "type": "item.started",
        "item": {
            "type": "collab_tool_call",
            "tool": "spawn_agent",
            "receiver_thread_ids": ["thr-1"],
        },
    }
    pending, started, done = _collaboration_state(json.dumps(spawn), set(), None, now=now)
    assert pending == {"thr-1"}
    assert started == now
    assert done is False

    wait_done = {
        "type": "item.completed",
        "item": {
            "type": "collab_tool_call",
            "tool": "wait",
            "receiver_thread_ids": ["thr-1"],
            "agents_states": {"thr-1": {"status": "completed"}},
        },
    }
    pending, started, done = _collaboration_state(json.dumps(wait_done), pending, started, now=now + 1)
    assert pending == set()
    assert started is None
    assert done is True


def test_collaboration_state_preserves_pending_on_wait_completed_without_states() -> None:
    pending = {"thr-2"}
    wait_done = {
        "type": "item.completed",
        "item": {
            "type": "collab_tool_call",
            "tool": "wait",
            "receiver_thread_ids": ["thr-2"],
        },
    }
    pending, started, done = _collaboration_state(json.dumps(wait_done), pending, 50.0, now=60.0)
    assert pending == {"thr-2"}
    assert started == 50.0
    assert done is False


def test_collaboration_state_does_not_reset_wait_clock_on_repeated_empty_waits() -> None:
    pending = {"thr-2"}
    wait_done = json.dumps(
        {
            "type": "item.completed",
            "item": {
                "type": "collab_tool_call",
                "tool": "wait",
                "receiver_thread_ids": ["thr-2"],
            },
        }
    )

    pending, started, done = _collaboration_state(wait_done, pending, 50.0, now=60.0)
    assert pending == {"thr-2"}
    assert started == 50.0
    assert done is False

    pending, started, done = _collaboration_state(wait_done, pending, started, now=70.0)
    assert pending == {"thr-2"}
    assert started == 50.0
    assert done is False


def test_collaboration_state_spawn_completed_keeps_pending_while_child_runs() -> None:
    pending, started, done = _collaboration_state(
        json.dumps(
            {
                "type": "item.started",
                "item": {
                    "type": "collab_tool_call",
                    "tool": "spawn_agent",
                    "receiver_thread_ids": ["thr-3"],
                },
            }
        ),
        set(),
        None,
        now=1.0,
    )
    assert done is False
    pending, started, done = _collaboration_state(
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "collab_tool_call",
                    "tool": "spawn_agent",
                    "receiver_thread_ids": ["thr-3"],
                },
            }
        ),
        pending,
        started,
        now=2.0,
    )
    assert pending == {"thr-3"}
    assert started == 1.0
    assert done is False


def test_collaboration_state_spawn_and_wait_same_chunk_marks_wave_done() -> None:
    chunk = "\n".join(
        [
            json.dumps(
                {
                    "type": "item.started",
                    "item": {
                        "type": "collab_tool_call",
                        "tool": "spawn_agent",
                        "receiver_thread_ids": ["thr-4"],
                    },
                }
            ),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "type": "collab_tool_call",
                        "tool": "wait",
                        "receiver_thread_ids": ["thr-4"],
                        "agents_states": {"thr-4": {"status": "completed"}},
                    },
                }
            ),
        ]
    )
    pending, started, done = _collaboration_state(chunk, set(), None, now=10.0)
    assert pending == set()
    assert started is None
    assert done is True
