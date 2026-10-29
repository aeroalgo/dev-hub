from __future__ import annotations

from pathlib import Path

from loop.kernel.engine import LoopEngine
from loop.kernel.index import Step, implement_path
from loop.kernel.model import CursorStatus
from loop.kernel.store import LoopPaths
from loop.kernel.verdict import (
    ContextSyncResult,
    GateVerdict,
    SCHEMA_CONTEXT_SYNC_RESULT,
    SCHEMA_GATE_VERDICT,
)


EPIC_ID = "APP-LIFECYCLE"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def seed_decompose(root: Path) -> None:
    write(root / f"memory-bank/app/plan/{EPIC_ID}/md/plan.md", "# APP lifecycle plan\n")
    write(
        root / f"memory-bank/app/plan/{EPIC_ID}/yaml/decompose-index.yaml",
        f"""schema: epic-decompose-index/v1
plan_id: {EPIC_ID}
steps:
  - id: s01
    file: s01-contract.yaml
    title: contract and backend
    next_phase: APP IMPLEMENT
    status: pending
  - id: s02
    file: s02-ui-wire.yaml
    title: UI and wire
    next_phase: APP IMPLEMENT
    status: pending
""",
    )
    shard_template = """schema: epic-decompose/v1
role: app
step_id: {step_id}
plan_id: {epic}
title: {title}
next_phase: APP IMPLEMENT
needs_creative: {needs_creative}
goal: one mixed vertical slice
plan_contract:
  fr_ids: [FR-001]
  nouns: [method/path, UI journey, wire contract]
  layout_paths: [memory-bank/app/plan/{epic}/, memory-bank/app/implement/{epic}/]
  ac_quotes: [contract and UI are both live]
  plan_jumps: []
context:
  consumes: []
  produces: []
  plan_refs: []
  files:
    - loop/kernel/index.py
    - loop/tests/test_app_lifecycle.py
as_built: []
delta:
  - enable APP lifecycle
deletes: []
out_of_scope: []
skills:
  code_surface: test
  impl: []
checkpoints:
  - id: cp1
    criterion: mixed contract is covered
    verify: bin/pytest loop/tests/test_app_lifecycle.py -q
verify:
  - bin/pytest loop/tests/test_app_lifecycle.py -q
tdd:
  - red
  - green
"""
    write(
        root / f"memory-bank/app/plan/{EPIC_ID}/yaml/steps/s01-contract.yaml",
        shard_template.format(
            step_id="s01",
            epic=EPIC_ID,
            title="contract and backend",
            needs_creative="no",
        ),
    )
    write(
        root / f"memory-bank/app/plan/{EPIC_ID}/yaml/steps/s02-ui-wire.yaml",
        shard_template.format(
            step_id="s02",
            epic=EPIC_ID,
            title="UI and wire",
            needs_creative='"yes (CR-APP-1)"',
        ),
    )


def write_implement_artifact(root: Path, step_id: str) -> None:
    filename = {
        "s01": "s01-contract.yaml",
        "s02": "s02-ui-wire.yaml",
    }[step_id]
    step = Step(step_id=step_id, status="pending", title=step_id, shard=filename)
    path = implement_path(root, "app", EPIC_ID, step)
    write(
        path,
        f"""schema: epic-implement/v1
role: app
step_id: {step_id}
plan_id: {EPIC_ID}
status: in_progress
done:
  - APP contract evidence
files:
  - backend/contract.py
  - frontend/feature.ts
  - tests/test_wire.py
deletes: []
tests:
  - bin/pytest loop/tests/test_app_lifecycle.py -q
integration_check:
  - wire journey reaches the real contract
wire_complete:
  call_sites: [frontend/feature.ts -> backend/contract.py]
  enforce_path: backend/contract.py
  dual_path_rg: "rg -n 'legacy|mock' frontend/feature.ts backend/contract.py"
  instruction_rg: "rg -n 'APP|wire' memory-bank/app/"
  deny_old_proven: true
checkpoints:
  - id: cp1
    criterion: mixed contract is covered
    status: pending
""",
    )


def gate(engine: LoopEngine, agent_id: str, verdict: str, timestamp: str) -> None:
    cursor = engine.store.read()
    assert cursor is not None
    engine.accept_verdict(
        GateVerdict(
            schema=SCHEMA_GATE_VERDICT,
            agent_id=agent_id,
            verdict=verdict,
            step_id=cursor.step_id,
            session_id=cursor.session_id,
            epic_id=cursor.epic_id,
            recorded_at=timestamp,
        ),
        expected_agent_id=agent_id,
    )


def test_app_role_runs_decompose_implement_creative_qa_bugfix_and_done(tmp_path: Path) -> None:
    seed_decompose(tmp_path)
    tree_paths = [
        tmp_path / f"memory-bank/app/plan/{EPIC_ID}/yaml/decompose-index.yaml",
        tmp_path / f"memory-bank/app/plan/{EPIC_ID}/yaml/steps/s01-contract.yaml",
        tmp_path / f"memory-bank/app/plan/{EPIC_ID}/yaml/steps/s02-ui-wire.yaml",
    ]
    tree_contents = {path: path.read_text(encoding="utf-8") for path in tree_paths}
    for path in tree_paths:
        path.unlink()
    engine = LoopEngine(LoopPaths(project=tmp_path, hub=tmp_path / "hub"))

    cursor = engine.start(EPIC_ID, role="app")
    assert (cursor.role, cursor.phase, cursor.step_id) == ("app", "DECOMPOSE", "DECOMPOSE")
    for path, content in tree_contents.items():
        write(path, content)

    gate(engine, "verify-decompose", "PASS", "2026-10-29T12:00:01+00:00")
    cursor = engine.store.read()
    assert cursor is not None
    assert (cursor.phase, cursor.step_id) == ("IMPLEMENT", "s01")

    write_implement_artifact(tmp_path, "s01")
    gate(engine, "verify-implement", "PASS", "2026-10-29T12:00:03+00:00")
    cursor = engine.store.read()
    assert cursor is not None
    assert (cursor.phase, cursor.step_id) == ("CREATIVE", "s02")

    write(
        tmp_path / f"memory-bank/app/creative/{EPIC_ID}/creative-s02.md",
        "# APP UI decision\n\nThe contract journey is visible and wired.\n",
    )
    shard_path = tmp_path / f"memory-bank/app/plan/{EPIC_ID}/yaml/steps/s02-ui-wire.yaml"
    shard_path.write_text(
        shard_path.read_text(encoding="utf-8").replace(
            'needs_creative: "yes (CR-APP-1)"',
            'needs_creative: "yes (CR-APP-1) — **closed**"',
        ),
        encoding="utf-8",
    )
    transition = engine.finish(step_id="s02")
    assert (transition.phase, transition.step_id) == ("IMPLEMENT", "s02")

    write_implement_artifact(tmp_path, "s02")
    gate(engine, "verify-implement", "PASS", "2026-10-29T12:00:04+00:00")
    cursor = engine.store.read()
    assert cursor is not None
    assert (cursor.phase, cursor.step_id) == ("QA", "QA")

    write(
        tmp_path / f"memory-bank/app/qa/{EPIC_ID}/qa-20261029-fail.yaml",
        "schema: app-qa/v1\nverdict: fail\nmode: diff_aware\n",
    )
    write(
        tmp_path / f"memory-bank/app/bugfix/{EPIC_ID}/bugfix-queue.yaml",
        """schema: epic-bugfix-queue/v1
items:
  - id: APP-BUG-1
    status: open
verification:
  status: pending
""",
    )
    gate(engine, "verify-qa", "FAIL", "2026-10-29T12:00:05+00:00")
    cursor = engine.store.read()
    assert cursor is not None
    assert (cursor.phase, cursor.step_id) == ("BUGFIX", "BUGFIX")

    write(
        tmp_path / f"memory-bank/app/bugfix/{EPIC_ID}/bugfix-20261029-fix.md",
        "# APP bugfix\n\nRoot cause fixed across contract and UI wire.\n",
    )
    write(
        tmp_path / f"memory-bank/app/bugfix/{EPIC_ID}/bugfix-queue.yaml",
        """schema: epic-bugfix-queue/v1
items:
  - id: APP-BUG-1
    status: closed
    evidence: targeted mixed regression
verification:
  status: pass
  command: bin/pytest loop/tests/test_app_lifecycle.py -q
  last_run_at: '2026-10-29T12:00:06+00:00'
  evidence: targeted mixed regression
""",
    )
    gate(engine, "verify-bugfix", "PASS", "2026-10-29T12:00:07+00:00")
    cursor = engine.store.read()
    assert cursor is not None
    assert (cursor.phase, cursor.step_id) == ("QA", "QA")

    write(
        tmp_path / f"memory-bank/app/qa/{EPIC_ID}/qa-20261029-pass.yaml",
        """schema: app-qa/v1
verdict: pass
mode: regression
charter:
  surfaces_required: [backend, frontend_build, browser, live_smoke, wire_journey]
lanes:
  - id: backend
    status: pass
  - id: frontend_build
    status: pass
  - id: browser
    status: pass
  - id: live_smoke
    status: pass
  - id: wire_journey
    status: pass
""",
    )
    gate(engine, "verify-qa", "PASS", "2026-10-29T12:00:08+00:00")
    cursor = engine.store.read()
    assert cursor is not None
    assert (cursor.phase, cursor.step_id, cursor.status) == ("QA", "QA", CursorStatus.ACTIVE)

    sync_path = tmp_path / f"memory-bank/app/context-sync/{EPIC_ID}/sync-20261029-app.md"
    write(sync_path, "# APP context sync\n")
    transition = engine.complete_context_sync(
        ContextSyncResult(
            schema=SCHEMA_CONTEXT_SYNC_RESULT,
            agent_id="context-sync",
            epic_id=EPIC_ID,
            status="done",
            sync_path=str(sync_path),
            session_id=cursor.session_id,
            recorded_at="2026-10-29T12:00:09+00:00",
        )
    )
    assert (transition.phase, transition.step_id, transition.status) == ("DONE", "DONE", CursorStatus.COMPLETE)
