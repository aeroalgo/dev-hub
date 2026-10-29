from __future__ import annotations

from pathlib import Path

import pytest

from loop.kernel.creative import (
    effective_runner_phase,
    needs_creative_open,
)
from loop.kernel.engine import LoopEngine, TransitionError
from loop.kernel.store import LoopPaths
from loop.kernel.verdict import GateVerdict, SCHEMA_GATE_VERDICT
from loop.tests.test_kernel import write


def _full_step_yaml(
    *,
    epic_id: str,
    step_id: str = "s01",
    needs_creative: str = 'yes (CR-ELIB-1)',
    next_phase: str = "BACK IMPLEMENT",
) -> str:
    return f"""
schema: epic-decompose/v1
role: back
step_id: {step_id}
plan_id: {epic_id}
title: {step_id}
next_phase: {next_phase}
needs_creative: "{needs_creative}"
goal: outcome
plan_contract: {{}}
context: {{}}
as_built: []
delta: []
deletes: []
out_of_scope: []
skills: {{}}
checkpoints: []
verify: []
tdd: []
"""


def _seed_analyze_ready(tmp_path: Path, epic_id: str, *, needs_creative: str) -> LoopPaths:
    write(tmp_path / f"memory-bank/back/plan/{epic_id}/md/plan.md", f"# Plan: {epic_id}\n")
    write(
        tmp_path / f"memory-bank/back/plan/{epic_id}/yaml/decompose-index.yaml",
        f"""
schema: epic-decompose-index/v1
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
        tmp_path / f"memory-bank/back/plan/{epic_id}/yaml/steps/s01.yaml",
        _full_step_yaml(epic_id=epic_id, needs_creative=needs_creative),
    )
    write(
        tmp_path / f"memory-bank/back/analyze/{epic_id}/analyze-20260921-pass.yaml",
        "schema: epic-analyze/v1\nstatus: complete\nmetrics:\n  critical_count: 0\n",
    )
    return LoopPaths(project=tmp_path, hub=tmp_path / "hub")


def _finish_analyze(engine: LoopEngine) -> None:
    cursor = engine.store.read()
    assert cursor is not None
    engine.accept_verdict(
        GateVerdict(
            schema=SCHEMA_GATE_VERDICT,
            agent_id="analyze-verify",
            verdict="PASS",
            step_id=cursor.step_id,
            session_id=cursor.session_id,
            epic_id=cursor.epic_id,
            recorded_at="2026-09-18T19:00:00+00:00",
        ),
        expected_agent_id="analyze-verify",
    )


def test_needs_creative_open_forces_creative() -> None:
    assert needs_creative_open("yes (CR-ELIB-1)")
    assert effective_runner_phase(
        role="BACK",
        next_phase="BACK IMPLEMENT",
        needs_creative="yes (CR-ELIB-1)",
    ) == "CREATIVE"


def test_return_to_implement_when_needs_creative_closed() -> None:
    assert not needs_creative_open("yes (CR-ELIB-1) — closed")
    assert effective_runner_phase(
        role="BACK",
        next_phase="BACK IMPLEMENT",
        needs_creative="yes (CR-ELIB-1) — closed",
    ) == "IMPLEMENT"


def test_closed_needs_creative_overrides_stale_creative_next_phase() -> None:
    assert (
        effective_runner_phase(
            role="BACK",
            next_phase="BACK CREATIVE",
            needs_creative="yes (CR-ELIB-1) ✅",
        )
        == "IMPLEMENT"
    )
    assert (
        effective_runner_phase(
            role="BACK",
            next_phase="BACK CREATIVE",
            needs_creative="yes (CR-ELIB-1) — **closed**",
        )
        == "IMPLEMENT"
    )


def test_missing_needs_creative_keeps_explicit_creative_next_phase() -> None:
    assert (
        effective_runner_phase(
            role="BACK",
            next_phase="BACK CREATIVE",
            needs_creative=None,
        )
        == "CREATIVE"
    )


def test_analyze_hands_off_to_creative_when_gate_open(tmp_path: Path) -> None:
    paths = _seed_analyze_ready(tmp_path, "E-CR", needs_creative="yes (CR-ELIB-1)")
    engine = LoopEngine(paths)

    cursor = engine.start("E-CR")
    assert cursor.phase == "CREATIVE"
    assert cursor.step_id == "s01"


def test_creative_finish_requires_artifact_and_closed_gate(tmp_path: Path) -> None:
    paths = _seed_analyze_ready(tmp_path, "E-CR2", needs_creative="yes (CR-ELIB-1)")
    engine = LoopEngine(paths)
    engine.start("E-CR2")

    with pytest.raises(TransitionError, match="creative_gate_still_open"):
        engine.finish(step_id="s01")

    write(
        tmp_path / "memory-bank/back/creative/E-CR2/creative-token-contract.md",
        "# Creative\nepic: E-CR2\n",
    )
    with pytest.raises(TransitionError, match="creative_gate_still_open"):
        engine.finish(step_id="s01")

    write(
        tmp_path / "memory-bank/back/plan/E-CR2/yaml/steps/s01.yaml",
        _full_step_yaml(
            epic_id="E-CR2",
            needs_creative="yes (CR-ELIB-1) — **closed**",
        ),
    )
    transition = engine.finish(step_id="s01")
    assert transition.phase == "IMPLEMENT"
    assert transition.step_id == "s01"

    index = (tmp_path / "memory-bank/back/plan/E-CR2/yaml/decompose-index.yaml").read_text(
        encoding="utf-8"
    )
    assert "status: pending" in index
    assert "status: completed" not in index


def test_creative_finish_rejects_missing_artifact(tmp_path: Path) -> None:
    paths = _seed_analyze_ready(
        tmp_path,
        "E-CR3",
        needs_creative="yes (CR-ELIB-1) — **closed**",
    )
    engine = LoopEngine(paths)
    # closed gate alone still must not skip CREATIVE if next_phase says CREATIVE... 
    # but with closed needs_creative, start goes to IMPLEMENT. Force rewind.
    cursor = engine.start("E-CR3")
    assert cursor.phase == "IMPLEMENT"
    transition = engine.rewind("CREATIVE")
    assert transition.phase == "CREATIVE"
    assert transition.step_id == "s01"

    with pytest.raises(TransitionError, match="creative_artifact_missing"):
        engine.finish(step_id="s01")


def test_analyze_verdict_routes_to_creative(tmp_path: Path) -> None:
    paths = _seed_analyze_ready(tmp_path, "E-CR4", needs_creative="yes (CR-T-F01-token-contract)")
    # remove analyze so start lands on DECOMPOSE (analyze gate folded into DECOMPOSE)
    analyze = tmp_path / "memory-bank/back/analyze/E-CR4/analyze-20260921-pass.yaml"
    analyze.unlink()
    analyze.parent.rmdir()

    engine = LoopEngine(paths)
    cursor = engine.start("E-CR4")
    assert cursor.phase == "DECOMPOSE"

    write(
        tmp_path / "memory-bank/back/analyze/E-CR4/analyze-20260921-pass.yaml",
        "schema: epic-analyze/v1\nstatus: complete\nmetrics:\n  critical_count: 0\n",
    )
    # verify-decompose validates the tree, then analyze-verify atomically promotes to CREATIVE.
    cursor = engine.store.read()
    assert cursor is not None
    engine.accept_verdict(
        GateVerdict(
            schema=SCHEMA_GATE_VERDICT,
            agent_id="verify-decompose",
            verdict="PASS",
            step_id=cursor.step_id,
            session_id=cursor.session_id,
            epic_id=cursor.epic_id,
            recorded_at="2026-09-18T18:59:00+00:00",
        ),
        expected_agent_id="verify-decompose",
    )
    _finish_analyze(engine)
    after = engine.store.read()
    assert after is not None
    assert after.phase == "CREATIVE"
    assert after.step_id == "s01"
