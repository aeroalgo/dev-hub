"""Unit tests for roadmap cadence schema and SoT API (load/save/fail-closed)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from loop.roadmap_cadence import (
    advance_replan,
    bind_replan_epic,
    canon_cadence_path,
    execute_cadence_resync,
    filter_critical_gaps,
    is_critical_gap,
    load_cadence,
    mark_plan_stale,
    on_feature_done,
    on_replan_epic_done,
    on_non_feature_done,
    on_refactor_done,
    on_resync_done,
    record_refactor_noop,
    record_resync_evidence,
    reset_cadence_idle,
    run_cadence_resync,
    save_cadence,
    start_refactor_phase,
)
from loop.schemas.roadmap_cadence import (
    CADENCE_PHASES,
    SCHEMA_ROADMAP_CADENCE,
    ReplanEvidence,
    ReplanGap,
    ReplanOutcomeRecord,
    ReplanSkipRecord,
    ResyncEvidence,
    RoadmapCadenceState,
)


def test_cadence_schema_validation() -> None:
    # Default instantiation
    state = RoadmapCadenceState()
    assert state.schema_version == SCHEMA_ROADMAP_CADENCE
    assert state.phase == "idle"
    assert state.counter == 0
    assert state.every_n == 4
    assert state.review_window_n == 8
    assert state.pair_ids == []

    # Valid phases
    for ph in CADENCE_PHASES:
        s = RoadmapCadenceState(phase=ph)
        assert s.phase == ph

    # Valid custom values
    custom = RoadmapCadenceState(
        schema="roadmap-cadence/v1",
        phase="replan",
        counter=2,
        every_n=3,
        pair_ids=["T-HUB-001", "T-HUB-002"],
    )
    assert custom.phase == "replan"
    assert custom.counter == 2
    assert custom.every_n == 3
    assert custom.pair_ids == ["T-HUB-001", "T-HUB-002"]

    # Schema version mismatch
    with pytest.raises(ValidationError):
        RoadmapCadenceState(schema="roadmap-cadence/v2")

    # Unknown phase
    with pytest.raises(ValidationError):
        RoadmapCadenceState(phase="unknown_phase")

    # Negative counter
    with pytest.raises(ValidationError):
        RoadmapCadenceState(counter=-1)

    # Invalid every_n
    with pytest.raises(ValidationError):
        RoadmapCadenceState(every_n=0)

    # Extra forbid
    with pytest.raises(ValidationError):
        RoadmapCadenceState.model_validate({"extra_field": 123})


def test_cadence_load_save(tmp_path: Path) -> None:
    cadence_file = tmp_path / "memory-bank" / "back" / "roadmap" / "cadence.yaml"

    # Save from dict
    initial_data = {
        "schema": SCHEMA_ROADMAP_CADENCE,
        "phase": "idle",
        "counter": 1,
        "every_n": 2,
        "pair_ids": ["T-HUB-010"],
    }
    saved_path = save_cadence(initial_data, cwd=tmp_path)
    assert saved_path == cadence_file
    assert cadence_file.is_file()

    # Load from cwd
    loaded = load_cadence(cwd=tmp_path)
    assert isinstance(loaded, RoadmapCadenceState)
    assert loaded.phase == "idle"
    assert loaded.counter == 1
    assert loaded.pair_ids == ["T-HUB-010"]

    # Mutate and save RoadmapCadenceState instance
    loaded.phase = "replan"
    loaded.counter = 2
    loaded.pair_ids.append("T-HUB-011")
    save_cadence(loaded, path=cadence_file)

    # Reload from explicit path
    reloaded = load_cadence(path=cadence_file)
    assert reloaded.phase == "replan"
    assert reloaded.counter == 2
    assert reloaded.pair_ids == ["T-HUB-010", "T-HUB-011"]

    # Check canon_cadence_path helper
    assert canon_cadence_path(tmp_path) == cadence_file


def test_cadence_fail_closed_on_corrupt(tmp_path: Path) -> None:
    # Missing file
    non_existent = tmp_path / "missing_cadence.yaml"
    with pytest.raises(FileNotFoundError):
        load_cadence(path=non_existent)

    # Corrupt YAML syntax
    corrupt_syntax = tmp_path / "corrupt_syntax.yaml"
    corrupt_syntax.write_text(":: this is not yaml :: [[[", encoding="utf-8")
    with pytest.raises(ValueError):
        load_cadence(path=corrupt_syntax)

    # Non-dict YAML (e.g. list)
    non_dict = tmp_path / "non_dict.yaml"
    non_dict.write_text("- item1\n- item2\n", encoding="utf-8")
    with pytest.raises((ValueError, TypeError)):
        load_cadence(path=non_dict)

    # Invalid schema version in YAML
    bad_schema = tmp_path / "bad_schema.yaml"
    bad_schema.write_text("schema: invalid/v1\nphase: idle\ncounter: 0\nevery_n: 2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_cadence(path=bad_schema)

    # Unknown phase in YAML
    bad_phase = tmp_path / "bad_phase.yaml"
    bad_phase.write_text("schema: roadmap-cadence/v1\nphase: invalid_phase\ncounter: 0\nevery_n: 2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_cadence(path=bad_phase)

    # Bad counter in YAML
    bad_counter = tmp_path / "bad_counter.yaml"
    bad_counter.write_text("schema: roadmap-cadence/v1\nphase: idle\ncounter: -5\nevery_n: 2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_cadence(path=bad_counter)


def test_on_feature_done_triggers_replan_after_every_n(tmp_path: Path) -> None:
    save_cadence(RoadmapCadenceState(every_n=2), cwd=tmp_path)

    first = on_feature_done("T-HUB-001", cwd=tmp_path)
    assert first.counter == 1
    assert first.phase == "idle"
    assert first.pair_ids == ["T-HUB-001"]

    second = on_feature_done("T-HUB-002", cwd=tmp_path)
    assert second.counter == 2
    assert second.phase == "replan"
    assert second.pair_ids == ["T-HUB-001", "T-HUB-002"]
    assert load_cadence(cwd=tmp_path) == second


def test_default_cadence_uses_four_features_and_eight_item_review_window(tmp_path: Path) -> None:
    save_cadence(RoadmapCadenceState(), cwd=tmp_path)

    state = RoadmapCadenceState()
    for index in range(1, 9):
        state = on_feature_done(f"T-FEAT-{index}", cwd=tmp_path)
        if index < 4:
            assert state.phase == "idle"
        elif index == 4:
            assert state.phase == "replan"
            break

    assert state.every_n == 4
    assert state.review_window_n == 8
    assert state.counter == 4
    assert state.feature_history == [f"T-FEAT-{i}" for i in range(1, 5)]
    assert state.pair_ids == state.feature_history


def test_replan_is_one_aggregate_epic_then_refactor(tmp_path: Path) -> None:
    save_cadence(
        RoadmapCadenceState(
            phase="replan",
            counter=4,
            every_n=4,
            review_window_n=8,
            pair_ids=[f"T-FEAT-{i}" for i in range(1, 9)],
            feature_history=[f"T-FEAT-{i}" for i in range(1, 9)],
        ),
        cwd=tmp_path,
    )

    bound = bind_replan_epic(cwd=tmp_path, epic_id="T-REPLAN-001")
    assert bound.replan_epic_id == "T-REPLAN-001"
    assert bound.replan_started is True
    assert bound.phase == "replan"

    finished = on_replan_epic_done(cwd=tmp_path, epic_id="T-REPLAN-001")
    assert finished.phase == "refactor"
    assert list(finished.replan_outcomes) == ["T-REPLAN-001"]
    assert finished.feature_history == [f"T-FEAT-{i}" for i in range(1, 9)]


def test_replan_arm_loads_only_review_prompts(tmp_path: Path) -> None:
    from loop.epic_transition import _arm_pre_implement

    feature_ids = ["T-FEAT-1", "T-FEAT-2"]
    save_cadence(
        RoadmapCadenceState(
            phase="replan",
            pair_ids=feature_ids,
            feature_history=feature_ids,
        ),
        cwd=tmp_path,
    )
    for epic_id in feature_ids:
        base = tmp_path / "memory-bank" / "back" / "plan" / epic_id / "md"
        base.mkdir(parents=True, exist_ok=True)
        (base / "plan.md").write_text("# source plan\n", encoding="utf-8")
        (base / "prompt.md").write_text("## Epic\nOutcome\n", encoding="utf-8")

    armed = _arm_pre_implement(
        tmp_path,
        epic_id=feature_ids[-1],
        role="back",
        phase="REPLAN",
        target_rel=None,
    )
    assert armed["ok"] is True
    active = (tmp_path / "memory-bank" / "activeContext.md").read_text(encoding="utf-8")
    assert "prompt.md" in active
    assert active.count("memory-bank/back/plan/T-FEAT-1/md/prompt.md") >= 1
    assert active.count("memory-bank/back/plan/T-FEAT-2/md/prompt.md") >= 1
    assert "plan.md" not in active


def test_on_non_feature_done_does_not_change_cadence(tmp_path: Path) -> None:
    initial = RoadmapCadenceState(counter=1, pair_ids=["T-HUB-001"])
    save_cadence(initial, cwd=tmp_path)

    result = on_non_feature_done(cwd=tmp_path)

    assert result == initial
    assert load_cadence(cwd=tmp_path) == initial
def test_on_feature_done_transition_to_replan(tmp_path: Path) -> None:
    save_cadence(RoadmapCadenceState(phase="idle", counter=0, every_n=2, pair_ids=[]), cwd=tmp_path)

    # First feature done
    s1 = on_feature_done(tmp_path, "T-HUB-001")
    assert s1.counter == 1
    assert s1.phase == "idle"
    assert s1.pair_ids == ["T-HUB-001"]

    # Second feature done -> triggers phase=replan and pair_ids of length 2
    s2 = on_feature_done(tmp_path, "T-HUB-002")
    assert s2.counter == 2
    assert s2.phase == "replan"
    assert s2.pair_ids == ["T-HUB-001", "T-HUB-002"]

    loaded = load_cadence(cwd=tmp_path)
    assert loaded.phase == "replan"
    assert loaded.counter == 2
    assert loaded.pair_ids == ["T-HUB-001", "T-HUB-002"]

    # Calling while phase!=idle does not increment
    s3 = on_feature_done(tmp_path, "T-HUB-003")
    assert s3.phase == "replan"
    assert s3.counter == 2
    assert s3.pair_ids == ["T-HUB-001", "T-HUB-002"]


def test_on_non_feature_done_no_counter_increment(tmp_path: Path) -> None:
    initial = RoadmapCadenceState(phase="idle", counter=1, every_n=2, pair_ids=["T-HUB-001"])
    save_cadence(initial, cwd=tmp_path)

    res = on_non_feature_done(tmp_path, "T-HUB-REFACTOR-01")
    assert res.counter == 1
    assert res.phase == "idle"
    assert res.pair_ids == ["T-HUB-001"]

    loaded = load_cadence(cwd=tmp_path)
    assert loaded == initial


def test_cli_cadence_status(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from loop.context_loop import cadence_status, main

    # 1. Missing cadence -> returns ok=False, exit code 1
    code = main(["--cwd", str(tmp_path), "cadence-status"])
    assert code == 1
    captured = capsys.readouterr()
    import json
    data = json.loads(captured.out)
    assert data["ok"] is False
    assert data["status"] == "missing"

    # 2. Idle cadence -> returns ok=True, exit code 0
    save_cadence(RoadmapCadenceState(phase="idle", counter=1, every_n=2, pair_ids=["T-HUB-001"]), cwd=tmp_path)
    code = main(["--cwd", str(tmp_path), "cadence-status"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["ok"] is True
    assert data["phase"] == "idle"
    assert data["counter"] == 1
    assert data["every_n"] == 2
    assert data["pair_ids"] == ["T-HUB-001"]
    assert data["paused"] is False
    assert data["blocked"] is False
    assert data["status"] == "active"

    # 3. Active cadence block (replan) -> returns ok=True, paused=True, blocked=True
    save_cadence(RoadmapCadenceState(phase="replan", counter=2, every_n=2, pair_ids=["T-HUB-001", "T-HUB-002"]), cwd=tmp_path)
    code = main(["--cwd", str(tmp_path), "cadence-status", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["ok"] is True
    assert data["phase"] == "replan"
    assert data["counter"] == 2
    assert data["pair_ids"] == ["T-HUB-001", "T-HUB-002"]
    assert data["paused"] is True
    assert data["blocked"] is True
    assert data["status"] == "paused"
    assert "T-HUB-093" in data["message"]

    # 4. Direct helper call returns consistent dict
    res = cadence_status(tmp_path)
    assert res == data


def test_cadence_status_output_formatting(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from loop.context_loop import format_cadence_status, main, status

    # 1. Text format on active/idle
    save_cadence(RoadmapCadenceState(phase="idle", counter=1, every_n=2, pair_ids=["T-HUB-001"]), cwd=tmp_path)
    code = main(["--cwd", str(tmp_path), "cadence-status", "--format", "text"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Roadmap Cadence Status: ACTIVE" in captured.out
    assert "Phase:    idle" in captured.out
    assert "Counter:  1 / 2" in captured.out
    assert "Pair IDs: T-HUB-001" in captured.out

    # 2. Text format on paused/replan
    save_cadence(RoadmapCadenceState(phase="replan", counter=2, every_n=2, pair_ids=["T-HUB-001", "T-HUB-002"]), cwd=tmp_path)
    code = main(["--cwd", str(tmp_path), "cadence-status", "--format", "text"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Roadmap Cadence Status: PAUSED (cadence block active)" in captured.out
    assert "Phase:    replan" in captured.out
    assert "Counter:  2 / 2" in captured.out
    assert "Pair IDs: T-HUB-001, T-HUB-002" in captured.out
    assert "T-HUB-093 / T-HUB-094" in captured.out

    # 3. Direct format helper error handling
    err_text = format_cadence_status({"ok": False, "error": "file corrupted"})
    assert "Roadmap cadence status: ERROR (file corrupted)" in err_text

    # 4. Overall status() payload integration
    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "activeContext.md").write_text("## load_now\n\n## Handoff\n", encoding="utf-8")
    overall = status(tmp_path)
    assert "cadence" in overall
    assert overall["cadence"]["ok"] is True
    assert overall["cadence"]["phase"] == "replan"
    assert overall["cadence"]["paused"] is True


def test_advance_replan_records_outcome(tmp_path: Path) -> None:
    cadence_file = tmp_path / "memory-bank" / "back" / "roadmap" / "cadence.yaml"
    initial_state = RoadmapCadenceState(
        phase="replan",
        counter=2,
        every_n=2,
        pair_ids=["T-HUB-001", "T-HUB-002"],
    )
    save_cadence(initial_state, path=cadence_file)

    # 1. Skip with evidence on first epic
    ev1 = ReplanEvidence(
        reason="no critical gaps found",
        cosmetic_gaps=["doc typo in header"],
    )
    st1 = advance_replan(
        path=cadence_file,
        epic_id="T-HUB-001",
        outcome="skip",
        evidence=ev1,
    )
    assert st1.phase == "replan"
    assert "T-HUB-001" in st1.replan_outcomes
    assert st1.replan_outcomes["T-HUB-001"].outcome == "skip"
    assert st1.replan_outcomes["T-HUB-001"].reason == "no critical gaps found"

    # 2. Complete with critical gaps on second epic
    ev2 = ReplanEvidence(
        reason="resolved critical missing gate",
        critical_gaps=["CRITICAL: unhandled edge case"],
        cosmetic_gaps=["minor formatting"],
    )
    st2 = advance_replan(
        path=cadence_file,
        epic_id="T-HUB-002",
        outcome="complete",
        evidence=ev2,
    )
    assert st2.phase == "refactor"
    assert "T-HUB-002" in st2.replan_outcomes
    assert st2.replan_outcomes["T-HUB-002"].outcome == "complete"

    # Verify reload from disk
    reloaded = load_cadence(path=cadence_file)
    assert reloaded.phase == "refactor"
    assert len(reloaded.replan_outcomes) == 2


def test_advance_replan_transitions_to_refactor(tmp_path: Path) -> None:
    cadence_file = tmp_path / "memory-bank" / "back" / "roadmap" / "cadence.yaml"
    initial_state = RoadmapCadenceState(
        phase="replan",
        counter=2,
        every_n=2,
        pair_ids=["T-HUB-101", "T-HUB-102"],
    )
    save_cadence(initial_state, path=cadence_file)

    # Advance first: still in replan
    st1 = advance_replan(
        path=cadence_file,
        epic_id="T-HUB-101",
        outcome="skip",
        reason="no gaps",
    )
    assert st1.phase == "replan"

    # Advance second: transitions to refactor
    st2 = advance_replan(
        path=cadence_file,
        epic_id="T-HUB-102",
        outcome="skip",
        reason="no gaps",
    )
    assert st2.phase == "refactor"


def test_advance_replan_validation(tmp_path: Path) -> None:
    cadence_file = tmp_path / "memory-bank" / "back" / "roadmap" / "cadence.yaml"
    state = RoadmapCadenceState(
        phase="idle",
        counter=0,
        every_n=2,
        pair_ids=["T-HUB-001", "T-HUB-002"],
    )
    save_cadence(state, path=cadence_file)

    # Fail: cannot advance when phase is idle
    with pytest.raises(ValueError, match="current cadence phase is 'idle'"):
        advance_replan(path=cadence_file, epic_id="T-HUB-001", outcome="skip", reason="test")

    # Set phase to replan
    state.phase = "replan"
    save_cadence(state, path=cadence_file)

    # Fail: missing epic_id
    with pytest.raises(ValueError, match="epic_id is required"):
        advance_replan(path=cadence_file, epic_id="", outcome="skip", reason="test")

    # Fail: unknown epic_id not in pair_ids
    with pytest.raises(ValueError, match="not in cadence pair_ids"):
        advance_replan(path=cadence_file, epic_id="T-HUB-999", outcome="skip", reason="test")

    # Fail: invalid outcome
    with pytest.raises(ValueError, match="invalid replan outcome"):
        advance_replan(path=cadence_file, epic_id="T-HUB-001", outcome="unknown")

    # Fail: skip without evidence or reason
    with pytest.raises(ValueError, match="missing evidence for replan skip"):
        advance_replan(path=cadence_file, epic_id="T-HUB-001", outcome="skip")

    # Record outcome for T-HUB-001
    advance_replan(path=cadence_file, epic_id="T-HUB-001", outcome="skip", reason="test")

    # Fail: duplicate replan for epic with already recorded outcome
    with pytest.raises(ValueError, match="already has terminal replan outcome"):
        advance_replan(path=cadence_file, epic_id="T-HUB-001", outcome="skip", reason="duplicate")


def test_advance_replan_fail_closed_validation(tmp_path: Path) -> None:
    """Explicit fail-closed validation for advance_replan matching -k fail_closed."""
    test_advance_replan_validation(tmp_path)


def test_critical_only_gap_filter(tmp_path: Path) -> None:
    cadence_file = tmp_path / "memory-bank" / "back" / "roadmap" / "cadence.yaml"
    state = RoadmapCadenceState(
        phase="replan",
        counter=2,
        every_n=2,
        pair_ids=["T-HUB-001", "T-HUB-002"],
    )
    save_cadence(state, path=cadence_file)

    # Test helper functions
    assert is_critical_gap({"severity": "critical", "text": "breakage"}) is True
    assert is_critical_gap({"severity": "cosmetic", "text": "typo"}) is False
    assert is_critical_gap({"cosmetic": True, "text": "minor"}) is False
    assert is_critical_gap("cosmetic wording change") is False
    assert is_critical_gap("critical database deadlock") is True

    mixed_gaps = [
        {"severity": "cosmetic", "text": "cosmetic 1"},
        {"severity": "critical", "text": "critical 1"},
        "cosmetic comment typo",
        "CRITICAL security vuln",
    ]
    critical_only = filter_critical_gaps(mixed_gaps)
    assert len(critical_only) == 2

    # Attempting to complete replan with ONLY cosmetic gaps must fail
    cosmetic_ev = ReplanEvidence(
        cosmetic_gaps=["just a typo"],
        gaps=[{"severity": "cosmetic", "text": "style only"}],
    )
    with pytest.raises(ValueError, match="only cosmetic gaps provided"):
        advance_replan(
            path=cadence_file,
            epic_id="T-HUB-001",
            outcome="complete",
            evidence=cosmetic_ev,
        )

    # Skipping replan when only cosmetic gaps exist is allowed and records evidence
    skip_state = advance_replan(
        path=cadence_file,
        epic_id="T-HUB-001",
        outcome="skip",
        evidence=cosmetic_ev,
        reason="cosmetic only - no replan work created",
    )
    assert "T-HUB-001" in skip_state.replan_outcomes
    assert skip_state.replan_outcomes["T-HUB-001"].outcome == "skip"


def test_start_refactor_phase_blocked_in_replan(tmp_path: Path) -> None:
    # 1. Blocked in replan phase
    save_cadence(
        RoadmapCadenceState(
            phase="replan",
            counter=0,
            every_n=2,
            pair_ids=["T-FEAT-1", "T-FEAT-2"],
        ),
        cwd=tmp_path,
    )
    with pytest.raises(ValueError, match="cannot start refactor phase.*'replan'"):
        start_refactor_phase(tmp_path, "T-REF-1")

    # 2. Blocked in idle phase
    save_cadence(
        RoadmapCadenceState(
            phase="idle",
            counter=1,
            every_n=2,
            pair_ids=["T-FEAT-1"],
        ),
        cwd=tmp_path,
    )
    with pytest.raises(ValueError, match="cannot start refactor phase.*'idle'"):
        start_refactor_phase(tmp_path, epic_spec={"id": "T-REF-1"})

    # 3. Allowed in refactor phase
    save_cadence(
        RoadmapCadenceState(
            phase="refactor",
            counter=0,
            every_n=2,
            pair_ids=["T-FEAT-1", "T-FEAT-2"],
        ),
        cwd=tmp_path,
    )
    # Create valid queue.yaml
    queue_file = tmp_path / "memory-bank/back/roadmap/queue.yaml"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text("""version: roadmap-queue/v2
role: back
queue:
  - id: T-FEAT-3
    epic_id: T-FEAT-3
    plan: T-FEAT-3/md/plan.md
    deps: []
    kind: feature
done: []
""")

    res = start_refactor_phase(tmp_path, "T-REF-1")
    assert res["ok"] is True
    assert res["kind"] == "refactor"
    assert res["id"] == "T-REF-1"


def test_refactor_noop_and_done_transition_resync(tmp_path: Path) -> None:
    # 1. record_refactor_noop transitions refactor -> resync without counter increment
    save_cadence(
        RoadmapCadenceState(
            phase="refactor",
            counter=0,
            every_n=2,
            pair_ids=["T-FEAT-1", "T-FEAT-2"],
        ),
        cwd=tmp_path,
    )
    res_noop = record_refactor_noop(
        tmp_path,
        reason="architecture clean, no refactoring required",
        evidence={"reason": "no structural gaps"},
    )
    assert res_noop.phase == "resync"
    assert res_noop.counter == 0
    saved = load_cadence(cwd=tmp_path)
    assert saved.phase == "resync"
    assert saved.counter == 0

    # record_refactor_noop fails closed if not in refactor phase
    with pytest.raises(ValueError, match="cannot record refactor noop.*'resync'"):
        record_refactor_noop(tmp_path, reason="another attempt")

    # 2. on_refactor_done transitions refactor -> resync without counter increment
    save_cadence(
        RoadmapCadenceState(
            phase="refactor",
            counter=0,
            every_n=2,
            pair_ids=["T-FEAT-1", "T-FEAT-2"],
        ),
        cwd=tmp_path,
    )
    res_done = on_refactor_done(tmp_path, epic_id="T-REF-1")
    assert res_done.phase == "resync"
    assert res_done.counter == 0
    saved_done = load_cadence(cwd=tmp_path)
    assert saved_done.phase == "resync"
    assert saved_done.counter == 0

    # on_refactor_done in idle phase does not change phase
    save_cadence(
        RoadmapCadenceState(
            phase="idle",
            counter=1,
            every_n=2,
            pair_ids=["T-FEAT-1"],
        ),
        cwd=tmp_path,
    )
    res_idle = on_refactor_done(tmp_path, epic_id="T-REF-AD-HOC")
    assert res_idle.phase == "idle"
    assert res_idle.counter == 1
def test_rules_cadence_instructions() -> None:
    """cp1: workflow-replan.mdc, workflow-plan-refactor.mdc, and mainrule.mdc contain cadence instructions, order and one-hop."""
    rules_root = Path(__file__).resolve().parents[2] / ".cursor" / "rules" / "back_developer"

    replan_mdc = (rules_root / "workflow-replan.mdc").read_text(encoding="utf-8")
    refactor_mdc = (rules_root / "workflow-plan-refactor.mdc").read_text(encoding="utf-8")
    mainrule_mdc = (rules_root / "mainrule.mdc").read_text(encoding="utf-8")

    # replan instructions: cadence.yaml, phase order, one-hop, forbid replan-of-replan, skip evidence, critical gaps
    assert "cadence.yaml" in replan_mdc
    assert "phase=replan" in replan_mdc
    assert "phase=refactor" in replan_mdc
    assert "one-hop" in replan_mdc.lower() or "one hop" in replan_mdc.lower()
    assert "replan-of-replan" in replan_mdc
    assert "skip" in replan_mdc.lower() and "evidence" in replan_mdc.lower()
    assert "critical" in replan_mdc.lower()

    # refactor instructions: after replan, start_refactor_phase / kind: refactor, noop evidence, resync transition
    assert "cadence.yaml" in refactor_mdc
    assert "phase=replan" in refactor_mdc
    assert "phase=refactor" in refactor_mdc
    assert "resync" in refactor_mdc
    assert "noop" in refactor_mdc.lower()

    # mainrule instructions: cadence block order
    assert "phase=replan" in mainrule_mdc
    assert "phase=refactor" in mainrule_mdc
    assert "phase=resync" in mainrule_mdc
    assert "one-hop" in mainrule_mdc.lower() or "one hop" in mainrule_mdc.lower()


def test_rules_anti_carry_policy() -> None:
    """cp2: Rules contain explicit anti-carry policy and forbid sliding windows."""
    rules_root = Path(__file__).resolve().parents[2] / ".cursor" / "rules" / "back_developer"

    replan_mdc = (rules_root / "workflow-replan.mdc").read_text(encoding="utf-8")
    refactor_mdc = (rules_root / "workflow-plan-refactor.mdc").read_text(encoding="utf-8")
    mainrule_mdc = (rules_root / "mainrule.mdc").read_text(encoding="utf-8")

    for text in (replan_mdc, refactor_mdc, mainrule_mdc):
        assert "anti-carry" in text.lower() or "anti carry" in text.lower() or "запрет переноса" in text.lower()
        assert "sliding window" in text.lower() or "скользящ" in text.lower()
        assert "FORBIDDEN" in text


def test_cadence_status_output_details(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """cp1: cadence-status CLI and helper provide detailed pair_ids progress and refactor phase info."""
    from loop.context_loop import cadence_status, format_cadence_status, main

    # 1. Detailed replan status with completed, skipped, and pending pair_ids
    state = RoadmapCadenceState(
        phase="replan",
        counter=2,
        every_n=2,
        pair_ids=["T-FEAT-1", "T-FEAT-2", "T-FEAT-3"],
        replan_outcomes={
            "T-FEAT-1": ReplanOutcomeRecord(epic_id="T-FEAT-1", outcome="complete"),
            "T-FEAT-2": ReplanOutcomeRecord(
                epic_id="T-FEAT-2",
                outcome="skip",
                reason="no critical architectural gaps found",
                evidence=ReplanEvidence(critical_gaps=[]),
            ),
        },
    )
    save_cadence(state, cwd=tmp_path)

    # Inspect cadence_status structured dict
    res = cadence_status(tmp_path)
    assert res["ok"] is True
    assert res["phase"] == "replan"
    assert res["pair_ids"] == ["T-FEAT-1", "T-FEAT-2", "T-FEAT-3"]
    assert "replan_outcomes" in res
    assert res["replan_outcomes"]["T-FEAT-1"]["outcome"] == "complete"
    assert res["replan_outcomes"]["T-FEAT-2"]["outcome"] == "skip"
    assert res["replan_outcomes"]["T-FEAT-2"]["reason"] == "no critical architectural gaps found"

    pair_details = res["pair_details"]
    assert len(pair_details) == 3
    assert pair_details[0]["epic_id"] == "T-FEAT-1"
    assert pair_details[0]["status"] == "complete"
    assert pair_details[1]["epic_id"] == "T-FEAT-2"
    assert pair_details[1]["status"] == "skip"
    assert pair_details[1]["reason"] == "no critical architectural gaps found"
    assert pair_details[2]["epic_id"] == "T-FEAT-3"
    assert pair_details[2]["status"] == "pending"

    # Text format rendering
    formatted = format_cadence_status(res)
    assert "Roadmap Cadence Status: PAUSED (cadence block active)" in formatted
    assert "Phase:    replan" in formatted
    assert "Pair Progress:" in formatted
    assert "- T-FEAT-1: COMPLETED" in formatted
    assert "- T-FEAT-2: SKIPPED (no critical architectural gaps found)" in formatted
    assert "- T-FEAT-3: PENDING" in formatted
    assert "Refactor: PENDING" in formatted

    # CLI invocation with text format
    code = main(["--cwd", str(tmp_path), "cadence-status", "--format", "text"])
    assert code == 0
    captured = capsys.readouterr()
    assert "- T-FEAT-1: COMPLETED" in captured.out
    assert "- T-FEAT-2: SKIPPED (no critical architectural gaps found)" in captured.out
    assert "- T-FEAT-3: PENDING" in captured.out

    # CLI invocation with JSON format
    code = main(["--cwd", str(tmp_path), "cadence-status", "--json"])
    assert code == 0
    captured_json = capsys.readouterr()
    import json
    data = json.loads(captured_json.out)
    assert data["ok"] is True
    assert data["replan_outcomes"]["T-FEAT-1"]["outcome"] == "complete"
    assert data["pair_details"][1]["reason"] == "no critical architectural gaps found"

    # 2. Refactor phase rendering
    save_cadence(
        RoadmapCadenceState(
            phase="refactor",
            counter=0,
            every_n=2,
            pair_ids=["T-FEAT-1", "T-FEAT-2"],
        ),
        cwd=tmp_path,
    )
    res_refactor = cadence_status(tmp_path)
    assert res_refactor["phase"] == "refactor"
    formatted_refactor = format_cadence_status(res_refactor)
    assert "Refactor: IN_PROGRESS" in formatted_refactor

    # 3. Resync phase rendering
    save_cadence(
        RoadmapCadenceState(
            phase="resync",
            counter=0,
            every_n=2,
            pair_ids=["T-FEAT-1", "T-FEAT-2"],
        ),
        cwd=tmp_path,
    )
    res_resync = cadence_status(tmp_path)
    assert res_resync["phase"] == "resync"
    formatted_resync = format_cadence_status(res_resync)
    assert "Refactor: COMPLETED / NOOP" in formatted_resync


def test_cadence_block_e2e_progression(tmp_path: Path) -> None:
    """cp2: End-to-end test verifying full cadence block execution cycle and TM invariants (TM-01, TM-02, TM-03)."""
    # -------------------------------------------------------------------------
    # Scenario A: Full cycle with feature completion -> replan pair -> refactor epic -> resync
    # -------------------------------------------------------------------------
    # 0. Initial idle state
    save_cadence(
        RoadmapCadenceState(phase="idle", counter=0, every_n=2, pair_ids=[]),
        cwd=tmp_path,
    )

    # 1. Complete feature 1 -> counter becomes 1, pair_ids=[T-FEAT-1], phase remains idle
    s1 = on_feature_done(tmp_path, epic_id="T-FEAT-1")
    assert s1.phase == "idle"
    assert s1.counter == 1
    assert s1.pair_ids == ["T-FEAT-1"]

    # 2. Complete a non-feature / chore (TM-03: non-feature does not increment counter)
    s_chore = on_non_feature_done(tmp_path, epic_id="T-CHORE-1")
    assert s_chore.phase == "idle"
    assert s_chore.counter == 1
    assert s_chore.pair_ids == ["T-FEAT-1"]

    # 3. Complete feature 2 -> triggers cadence block: counter=2, pair_ids=[T-FEAT-1, T-FEAT-2], phase=replan
    s2 = on_feature_done(tmp_path, epic_id="T-FEAT-2")
    assert s2.phase == "replan"
    assert s2.counter == 2
    assert s2.pair_ids == ["T-FEAT-1", "T-FEAT-2"]

    # TM-01: Refactor before replan done -> fail closed
    with pytest.raises(ValueError, match="cannot start refactor phase.*'replan'"):
        start_refactor_phase(tmp_path, "T-REF-1")
    with pytest.raises(ValueError, match="cannot record refactor noop.*'replan'"):
        record_refactor_noop(tmp_path, reason="premature noop")

    # Negative: Try advance replan for an unknown epic not in pair_ids
    with pytest.raises(ValueError, match="not in cadence pair_ids"):
        advance_replan(tmp_path, epic_id="T-UNKNOWN", outcome="complete")

    # Negative: Try skip without reason and evidence
    with pytest.raises((ValidationError, ValueError)):
        advance_replan(tmp_path, epic_id="T-FEAT-1", outcome="skip", reason="", evidence=None)

    # 4. Advance first epic in replan with complete
    s_rep1 = advance_replan(
        tmp_path,
        epic_id="T-FEAT-1",
        outcome="complete",
        evidence=ReplanEvidence(critical_gaps=[ReplanGap(gap_id="G1", description="Architecture refactor needed", severity="critical")]),
    )
    assert s_rep1.phase == "replan"
    assert "T-FEAT-1" in s_rep1.replan_outcomes
    assert s_rep1.replan_outcomes["T-FEAT-1"].outcome == "complete"

    # TM-01: Still in replan because T-FEAT-2 is not resolved yet -> refactor start must fail
    with pytest.raises(ValueError, match="cannot start refactor phase.*'replan'"):
        start_refactor_phase(tmp_path, "T-REF-1")

    # 5. Advance second epic in replan with skip (with valid reason & evidence)
    s_rep2 = advance_replan(
        tmp_path,
        epic_id="T-FEAT-2",
        outcome="skip",
        reason="no critical architectural gaps found in T-FEAT-2",
        evidence=ReplanEvidence(critical_gaps=[]),
    )
    # Both pair epics resolved -> state automatically transitions to refactor phase and resets counter to 0
    assert s_rep2.phase == "refactor"
    assert s_rep2.counter == 2  # Counter unchanged during replan/refactor
    assert "T-FEAT-2" in s_rep2.replan_outcomes
    assert s_rep2.replan_outcomes["T-FEAT-2"].outcome == "skip"

    # 6. Start refactor phase: upsert refactor epic into queue.yaml
    queue_file = tmp_path / "memory-bank/back/roadmap/queue.yaml"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text("""version: roadmap-queue/v2
role: back
queue:
  - id: T-FEAT-3
    epic_id: T-FEAT-3
    plan: T-FEAT-3/md/plan.md
    deps: []
    kind: feature
done: []
""")
    res_start_ref = start_refactor_phase(tmp_path, epic_spec={"id": "T-REF-1", "epic_id": "T-REF-1", "kind": "refactor"})
    assert res_start_ref["ok"] is True
    assert res_start_ref["id"] == "T-REF-1"
    assert res_start_ref["kind"] == "refactor"

    # TM-03: Non-feature / refactor completion does NOT increment feature counter
    s_ref_done = on_refactor_done(tmp_path, epic_id="T-REF-1")
    assert s_ref_done.phase == "resync"
    assert s_ref_done.counter == 2  # TM-03: Refactor does not increment feature counter

    # -------------------------------------------------------------------------
    # Scenario B: Both pair epics skipped -> noop refactor allowed (TM-02)
    # -------------------------------------------------------------------------
    tmp_b = tmp_path / "b"
    tmp_b.mkdir(parents=True, exist_ok=True)
    save_cadence(
        RoadmapCadenceState(phase="idle", counter=0, every_n=2, pair_ids=[]),
        cwd=tmp_b,
    )
    on_feature_done(tmp_b, epic_id="T-FEAT-A")
    s_b2 = on_feature_done(tmp_b, epic_id="T-FEAT-B")
    assert s_b2.phase == "replan"
    assert s_b2.pair_ids == ["T-FEAT-A", "T-FEAT-B"]

    # Skip first epic
    advance_replan(
        tmp_b,
        epic_id="T-FEAT-A",
        outcome="skip",
        reason="no gaps in epic A",
        evidence={"critical_gaps": []},
    )
    # Skip second epic -> transitions to refactor
    s_b_ref = advance_replan(
        tmp_b,
        epic_id="T-FEAT-B",
        outcome="skip",
        reason="no gaps in epic B",
        evidence={"critical_gaps": []},
    )
    assert s_b_ref.phase == "refactor"
    assert s_b_ref.counter == 2

    # TM-02: Both skipped -> record_refactor_noop allowed without inserting refactor epic
    s_b_noop = record_refactor_noop(
        tmp_b,
        reason="all epics skipped during replan; codebase clean",
        evidence={"reason": "noop"},
    )
    assert s_b_noop.phase == "resync"
    assert s_b_noop.counter == 2

    # TM-03: Counter remains 0 after noop refactor
    saved_b = load_cadence(cwd=tmp_b)
    assert saved_b.phase == "resync"
    assert saved_b.counter == 2


def test_resync_evidence(tmp_path: Path) -> None:
    # 1. ResyncEvidence schema defaults and custom initialization
    ev_default = ResyncEvidence()
    assert ev_default.high_count == 0
    assert ev_default.resync_action == ""
    assert ev_default.stale_epics == []
    assert ev_default.timestamp is None

    ev_custom = ResyncEvidence(
        high_count=2,
        resync_action="stale_plan_marked",
        stale_epics=["T-HUB-095", "T-HUB-096"],
        timestamp="2026-09-13T12:00:00Z",
        details={"reason": "queue reconcile high drift"},
    )
    assert ev_custom.high_count == 2
    assert ev_custom.resync_action == "stale_plan_marked"
    assert ev_custom.stale_epics == ["T-HUB-095", "T-HUB-096"]
    assert ev_custom.timestamp == "2026-09-13T12:00:00Z"
    assert ev_custom.details["reason"] == "queue reconcile high drift"

    # 2. record_resync_evidence fails closed if phase is not 'resync'
    save_cadence(
        RoadmapCadenceState(
            phase="idle",
            counter=0,
            every_n=2,
        ),
        cwd=tmp_path,
    )
    with pytest.raises(ValueError, match="cannot record resync evidence.*'idle'"):
        record_resync_evidence(tmp_path, high_count=0)

    # 3. record_resync_evidence succeeds in 'resync' phase
    save_cadence(
        RoadmapCadenceState(
            phase="resync",
            counter=0,
            every_n=2,
            pair_ids=["T-FEAT-1", "T-FEAT-2"],
        ),
        cwd=tmp_path,
    )
    recorded_state = record_resync_evidence(
        tmp_path,
        high_count=1,
        resync_action="stale_plan_marked",
        stale_epics=["T-FEAT-3"],
    )
    assert recorded_state.phase == "resync"
    assert recorded_state.resync_evidence is not None
    assert recorded_state.resync_evidence.high_count == 1
    assert recorded_state.resync_evidence.resync_action == "stale_plan_marked"
    assert recorded_state.resync_evidence.stale_epics == ["T-FEAT-3"]
    assert recorded_state.resync_evidence.timestamp is not None

    # Reload from disk and verify persistence
    reloaded = load_cadence(cwd=tmp_path)
    assert reloaded.resync_evidence is not None
    assert reloaded.resync_evidence.high_count == 1
    assert reloaded.resync_evidence.stale_epics == ["T-FEAT-3"]

    # 4. record_resync_evidence with structured ResyncEvidence object
    new_ev = ResyncEvidence(
        high_count=0,
        resync_action="clean_pass",
        stale_epics=[],
        timestamp="2026-09-13T13:00:00Z",
    )
    recorded_state2 = record_resync_evidence(tmp_path, evidence=new_ev)
    assert recorded_state2.resync_evidence.high_count == 0
    assert recorded_state2.resync_evidence.resync_action == "clean_pass"

    # 5. run_cadence_resync orchestration
    # Setup queue file and empty bundle
    q_dir = tmp_path / "memory-bank" / "back" / "roadmap"
    q_dir.mkdir(parents=True, exist_ok=True)
    (q_dir / "queue.yaml").write_text(
        "version: roadmap-queue/v2\nrole: back\nqueue: []\ndone: []\n",
        encoding="utf-8",
    )
    res_state, res_report = run_cadence_resync(tmp_path)
    assert res_state.phase == "resync"
    assert res_state.resync_summary is not None
    assert res_state.resync_evidence is not None
    assert res_state.resync_evidence.resync_action == "reconciled"

    # Verify fail-closed for run_cadence_resync when phase is idle
    save_cadence(RoadmapCadenceState(phase="idle"), cwd=tmp_path)
    with pytest.raises(ValueError, match="cannot run cadence resync.*'idle'"):
        run_cadence_resync(tmp_path)


def test_mark_plan_stale(tmp_path: Path) -> None:
    # 1. Setup sample plan directory and files
    plan_dir = tmp_path / "memory-bank" / "back" / "plan" / "T-TEST-095" / "md"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / "plan.md"
    prompt_file = plan_dir / "prompt.md"

    initial_prompt_content = "# Prompt for T-TEST-095\n\n§Epic: Core immutable requirement prompt text.\n"
    prompt_file.write_text(initial_prompt_content, encoding="utf-8")

    initial_plan_content = """# [T-TEST-095 | downstream-epic] PLAN

**Дата:** 2026-09-13  
**Режим:** BACK PLAN  
**Уровень:** L2–L3  
**Статус:** active  
**Prompt:** [md/prompt.md](prompt.md)  
**Deps:** none  

---

## Epic cut (нарезка)

| ID | Axis |
|----|------|
| T-TEST-095 | core |

## Prompt

§Epic: Core immutable requirement prompt text in plan.
"""
    plan_file.write_text(initial_plan_content, encoding="utf-8")

    # 2. Call mark_plan_stale with explicit path
    updated_path = mark_plan_stale(
        plan_file,
        reason="HIGH drift in downstream queue",
        cwd=tmp_path,
    )
    assert updated_path == plan_file
    updated_text = plan_file.read_text(encoding="utf-8")

    # Verify status is stale with reason
    assert "**Статус:** stale (resync: HIGH drift in downstream queue)" in updated_text
    assert "> **STALE (cadence resync):** HIGH drift in downstream queue" in updated_text

    # Verify prompt section and §Epic are completely intact and unmutated
    assert "## Prompt" in updated_text
    assert "§Epic: Core immutable requirement prompt text in plan." in updated_text
    assert prompt_file.read_text(encoding="utf-8") == initial_prompt_content

    # 3. Call mark_plan_stale by epic_id lookup
    plan_dir2 = tmp_path / "memory-bank" / "back" / "plan" / "T-HUB-096-resync-sample" / "md"
    plan_dir2.mkdir(parents=True, exist_ok=True)
    plan_file2 = plan_dir2 / "plan.md"
    plan_file2.write_text(
        "# [T-HUB-096 | resync-sample] PLAN\n\n**Статус:** active\n\n§Epic: Immutable.\n",
        encoding="utf-8",
    )
    updated_path2 = mark_plan_stale(
        epic_id="T-HUB-096",
        reason="downstream refactor invalidated layout",
        cwd=tmp_path,
    )
    assert updated_path2 == plan_file2
    content2 = plan_file2.read_text(encoding="utf-8")
    assert "**Статус:** stale (resync: downstream refactor invalidated layout)" in content2
    assert "§Epic: Immutable." in content2

    # 4. Fail-closed on missing plan
    with pytest.raises(FileNotFoundError):
        mark_plan_stale(epic_id="T-NONEXISTENT", cwd=tmp_path)

def test_advance_blocked_resync(tmp_path: Path) -> None:
    """cp1: roadmap_advance is blocked when phase=resync and high_count > 0 without resync_evidence."""
    from loop.roadmap_queue import roadmap_advance
    from loop.schemas.roadmap_cadence import RoadmapCadenceState, ResyncEvidence

    # Setup cadence in resync without resync_evidence
    save_cadence(
        RoadmapCadenceState(
            phase="resync",
            counter=0,
            every_n=2,
            pair_ids=["T-FEAT-1", "T-FEAT-2"],
            resync_evidence=None,
        ),
        cwd=tmp_path,
    )

    queue_yaml = "\n".join([
        "version: roadmap-queue/v2",
        "role: back",
        "queue:",
        "  - id: T-FEAT-3",
        "    epic_id: T-FEAT-3",
        "    plan: T-FEAT-3/md/plan.md",
        "    deps: []",
        "    kind: feature",
        "done:",
        "  - id: T-FEAT-1",
        "    epic_id: T-FEAT-1",
        "    plan: T-FEAT-1/md/plan.md",
        "    kind: feature",
        "  - id: T-FEAT-2",
        "    epic_id: T-FEAT-2",
        "    plan: T-FEAT-2/md/plan.md",
        "    kind: feature",
        "",
    ])
    qpath = tmp_path / "memory-bank/back/roadmap/queue.yaml"
    qpath.parent.mkdir(parents=True, exist_ok=True)
    qpath.write_text(queue_yaml, encoding="utf-8")

    plan3 = tmp_path / "memory-bank/back/plan/T-FEAT-3/md/plan.md"
    plan3.parent.mkdir(parents=True, exist_ok=True)
    plan3.write_text("# feat 3\n", encoding="utf-8")

    act = tmp_path / "memory-bank/activeContext.md"
    act.parent.mkdir(parents=True, exist_ok=True)
    act.write_text("## load_now\n- initial\n\n## Handoff\n", encoding="utf-8")

    # 1. Blocked when resync_evidence is None
    out = roadmap_advance(tmp_path)
    assert out["ok"] is False
    assert out["armed"] is False
    assert out["cadence_blocked"] is True
    assert out["phase"] == "resync"
    assert out.get("next_epic") == "T-FEAT-3"
    assert "T-FEAT-3" not in act.read_text(encoding="utf-8")

    # 2. Blocked when raw HIGH drift exists with drift_detected and no resync
    save_cadence(
        RoadmapCadenceState(
            phase="resync",
            counter=0,
            every_n=2,
            pair_ids=["T-FEAT-1", "T-FEAT-2"],
            resync_evidence=ResyncEvidence(
                high_count=2,
                resync_action="drift_detected",
                stale_epics=["T-FEAT-3"],
            ),
        ),
        cwd=tmp_path,
    )
    out_drift = roadmap_advance(tmp_path)
    assert out_drift["ok"] is False
    assert out_drift["armed"] is False
    assert out_drift["cadence_blocked"] is True
    assert out_drift["phase"] == "resync"

    # 3. Denies refactor epic while phase=resync
    q_refactor = "\n".join([
        "version: roadmap-queue/v2",
        "role: back",
        "queue:",
        "  - id: T-REF-1",
        "    epic_id: T-REF-1",
        "    plan: T-REF-1/md/plan.md",
        "    deps: []",
        "    kind: refactor",
        "done:",
        "  - id: T-FEAT-1",
        "    epic_id: T-FEAT-1",
        "    plan: T-FEAT-1/md/plan.md",
        "    kind: feature",
        "",
    ])
    qpath.write_text(q_refactor, encoding="utf-8")
    plan_ref = tmp_path / "memory-bank/back/plan/T-REF-1/md/plan.md"
    plan_ref.parent.mkdir(parents=True, exist_ok=True)
    plan_ref.write_text("# refactor 1\n", encoding="utf-8")
    record_resync_evidence(tmp_path, high_count=0)
    out_ref = roadmap_advance(tmp_path)
    assert out_ref["ok"] is False
    assert out_ref["error"] == "refactor_in_resync_denied"

def test_advance_succeeds_when_no_high_or_resynced(tmp_path: Path) -> None:
    """cp2: roadmap_advance succeeds when high_count == 0 or resync_evidence is present."""
    from loop.roadmap_queue import roadmap_advance
    from loop.schemas.roadmap_cadence import RoadmapCadenceState

    # Setup queue and plan
    queue_yaml = "\n".join([
        "version: roadmap-queue/v2",
        "role: back",
        "queue:",
        "  - id: T-FEAT-3",
        "    epic_id: T-FEAT-3",
        "    plan: T-FEAT-3/md/plan.md",
        "    deps: []",
        "    kind: feature",
        "done:",
        "  - id: T-FEAT-1",
        "    epic_id: T-FEAT-1",
        "    plan: T-FEAT-1/md/plan.md",
        "    kind: feature",
        "  - id: T-FEAT-2",
        "    epic_id: T-FEAT-2",
        "    plan: T-FEAT-2/md/plan.md",
        "    kind: feature",
        "",
    ])
    qpath = tmp_path / "memory-bank/back/roadmap/queue.yaml"
    qpath.parent.mkdir(parents=True, exist_ok=True)
    qpath.write_text(queue_yaml, encoding="utf-8")

    plan3 = tmp_path / "memory-bank/back/plan/T-FEAT-3/md/plan.md"
    plan3.parent.mkdir(parents=True, exist_ok=True)
    plan3.write_text("# feat 3\n", encoding="utf-8")

    act = tmp_path / "memory-bank/activeContext.md"
    act.parent.mkdir(parents=True, exist_ok=True)
    act.write_text("## load_now\n- initial\n\n## Handoff\n", encoding="utf-8")

    # 1. Advance succeeds when high_count == 0 in resync
    save_cadence(
        RoadmapCadenceState(
            phase="resync",
            counter=0,
            every_n=2,
            pair_ids=["T-FEAT-1", "T-FEAT-2"],
        ),
        cwd=tmp_path,
    )
    record_resync_evidence(tmp_path, high_count=0, resync_action="reconciled")

    out = roadmap_advance(tmp_path)
    assert out["ok"] is True
    assert out["armed"] is True
    assert out["epic"] == "T-FEAT-3"
    assert "T-FEAT-3" in act.read_text(encoding="utf-8")

    # 2. Advance succeeds when high_count > 0 was resynced
    tmp_path2 = tmp_path / "case2"
    qpath2 = tmp_path2 / "memory-bank/back/roadmap/queue.yaml"
    qpath2.parent.mkdir(parents=True, exist_ok=True)
    qpath2.write_text(queue_yaml, encoding="utf-8")
    plan3_2 = tmp_path2 / "memory-bank/back/plan/T-FEAT-3/md/plan.md"
    plan3_2.parent.mkdir(parents=True, exist_ok=True)
    plan3_2.write_text("# feat 3\n", encoding="utf-8")
    act2 = tmp_path2 / "memory-bank/activeContext.md"
    act2.parent.mkdir(parents=True, exist_ok=True)
    act2.write_text("## load_now\n- initial\n\n## Handoff\n", encoding="utf-8")

    save_cadence(
        RoadmapCadenceState(
            phase="resync",
            counter=0,
            every_n=2,
            pair_ids=["T-FEAT-1", "T-FEAT-2"],
        ),
        cwd=tmp_path2,
    )
    record_resync_evidence(
        tmp_path2,
        high_count=2,
        resync_action="reconciled",
        stale_epics=["T-FEAT-3"],
    )
    out2 = roadmap_advance(tmp_path2)
    assert out2["ok"] is True
    assert out2["armed"] is True
    assert out2["epic"] == "T-FEAT-3"

    # 3. Advance succeeds when cadence phase is idle
    tmp_path3 = tmp_path / "case3"
    qpath3 = tmp_path3 / "memory-bank/back/roadmap/queue.yaml"
    qpath3.parent.mkdir(parents=True, exist_ok=True)
    qpath3.write_text(queue_yaml, encoding="utf-8")
    plan3_3 = tmp_path3 / "memory-bank/back/plan/T-FEAT-3/md/plan.md"
    plan3_3.parent.mkdir(parents=True, exist_ok=True)
    plan3_3.write_text("# feat 3\n", encoding="utf-8")
    act3 = tmp_path3 / "memory-bank/activeContext.md"
    act3.parent.mkdir(parents=True, exist_ok=True)
    act3.write_text("## load_now\n- initial\n\n## Handoff\n", encoding="utf-8")

    save_cadence(
        RoadmapCadenceState(
            phase="idle",
            counter=0,
            every_n=2,
            pair_ids=[],
        ),
        cwd=tmp_path3,
    )
    out_idle = roadmap_advance(tmp_path3)
    assert out_idle["ok"] is True
    assert out_idle["armed"] is True
    assert out_idle["epic"] == "T-FEAT-3"


def test_reset_cadence_idle(tmp_path: Path) -> None:
    """cp1: on_resync_done / reset_cadence_idle resets cadence state to idle and completed_feature_count to 0."""
    cadence_file = tmp_path / "memory-bank" / "back" / "roadmap" / "cadence.yaml"

    # Initial state in resync phase with non-zero counter and pair_ids
    initial = RoadmapCadenceState(
        phase="resync",
        counter=2,
        every_n=2,
        pair_ids=["T-FEAT-1", "T-FEAT-2"],
    )
    save_cadence(initial, cwd=tmp_path)

    # 1. on_resync_done resets phase to idle and counter to 0
    res1 = on_resync_done(tmp_path)
    assert res1.phase == "idle"
    assert res1.counter == 0
    assert res1.completed_feature_count == 0
    assert res1.pair_ids == []

    # Check persisted file
    loaded = load_cadence(cwd=tmp_path)
    assert loaded.phase == "idle"
    assert loaded.counter == 0
    assert loaded.completed_feature_count == 0
    assert loaded.pair_ids == []

    # 2. reset_cadence_idle alias behaves identically with explicit path
    loaded.phase = "refactor"
    loaded.counter = 2
    loaded.pair_ids = ["T-FEAT-3", "T-FEAT-4"]
    save_cadence(loaded, path=cadence_file)

    res2 = reset_cadence_idle(path=cadence_file)
    assert res2.phase == "idle"
    assert res2.counter == 0
    assert res2.completed_feature_count == 0
    assert res2.pair_ids == []

    reloaded = load_cadence(path=cadence_file)
    assert reloaded.phase == "idle"
    assert reloaded.counter == 0
    assert reloaded.completed_feature_count == 0
    assert reloaded.pair_ids == []


def test_reset_cadence_idle_unblocks_feature_advance(tmp_path: Path) -> None:
    """cp2: resetting cadence to idle unblocks subsequent roadmap_advance call for next feature."""
    from loop.roadmap_queue import mark_queue_epic_done, roadmap_advance

    queue_yaml = "\n".join([
        "version: roadmap-queue/v2",
        "role: back",
        "queue:",
        "  - id: T-FEAT-3",
        "    epic_id: T-FEAT-3",
        "    plan: T-FEAT-3/md/plan.md",
        "    deps: []",
        "    kind: feature",
        "done:",
        "  - id: T-FEAT-1",
        "    epic_id: T-FEAT-1",
        "    plan: T-FEAT-1/md/plan.md",
        "    kind: feature",
        "  - id: T-FEAT-2",
        "    epic_id: T-FEAT-2",
        "    plan: T-FEAT-2/md/plan.md",
        "    kind: feature",
        "",
    ])
    qpath = tmp_path / "memory-bank" / "back" / "roadmap" / "queue.yaml"
    qpath.parent.mkdir(parents=True, exist_ok=True)
    qpath.write_text(queue_yaml, encoding="utf-8")

    plan3 = tmp_path / "memory-bank" / "back" / "plan" / "T-FEAT-3" / "md" / "plan.md"
    plan3.parent.mkdir(parents=True, exist_ok=True)
    plan3.write_text("# feat 3\n", encoding="utf-8")

    act = tmp_path / "memory-bank" / "activeContext.md"
    act.parent.mkdir(parents=True, exist_ok=True)
    act.write_text("## load_now\n- initial\n\n## Handoff\n", encoding="utf-8")

    # Cadence is in resync without evidence (blocked)
    save_cadence(
        RoadmapCadenceState(
            phase="resync",
            counter=2,
            every_n=2,
            pair_ids=["T-FEAT-1", "T-FEAT-2"],
        ),
        cwd=tmp_path,
    )

    # Advance is blocked in resync
    out_blocked = roadmap_advance(tmp_path)
    assert out_blocked["ok"] is False
    assert out_blocked["cadence_blocked"] is True

    # Perform on_resync_done
    reset_state = on_resync_done(tmp_path)
    assert reset_state.phase == "idle"
    assert reset_state.counter == 0

    # Advance is now unblocked and arms T-FEAT-3
    out_armed = roadmap_advance(tmp_path)
    assert out_armed["ok"] is True
    assert out_armed["armed"] is True
    assert out_armed["epic"] == "T-FEAT-3"
    assert "T-FEAT-3" in act.read_text(encoding="utf-8")

    # Also test mark_epic_done with kind: resync
    cadence_state = load_cadence(cwd=tmp_path)
    cadence_state.phase = "resync"
    cadence_state.counter = 2
    save_cadence(cadence_state, cwd=tmp_path)

    # Add resync epic to queue and mark it done
    queue_with_resync = "\n".join([
        "version: roadmap-queue/v2",
        "role: back",
        "queue:",
        "  - id: T-RESYNC-1",
        "    epic_id: T-RESYNC-1",
        "    plan: T-RESYNC-1/md/plan.md",
        "    deps: []",
        "    kind: resync",
        "done: []",
        "",
    ])
    qpath.write_text(queue_with_resync, encoding="utf-8")
    plan_res = tmp_path / "memory-bank" / "back" / "plan" / "T-RESYNC-1" / "md" / "plan.md"
    plan_res.parent.mkdir(parents=True, exist_ok=True)
    plan_res.write_text("# resync 1\n", encoding="utf-8")

    done_res = mark_queue_epic_done(tmp_path, "T-RESYNC-1")
    assert done_res["ok"] is True
    assert done_res["cadence"]["phase"] == "idle"
    assert done_res["cadence"]["counter"] == 0

def test_full_cadence_lifecycle_e2e(tmp_path: Path) -> None:
    """Kind I / E2E: 2 features -> replan -> refactor -> resync (HIGH) -> block -> resync -> reset idle -> next feature."""
    from loop.roadmap_queue import mark_queue_epic_done, roadmap_advance

    # Initialize cadence SoT
    save_cadence(RoadmapCadenceState(every_n=2), cwd=tmp_path)

    queue_yaml = "\n".join([
        "version: roadmap-queue/v2",
        "role: back",
        "queue:",
        "  - id: T-FEAT-1",
        "    epic_id: T-FEAT-1",
        "    plan: T-FEAT-1/md/plan.md",
        "    deps: []",
        "    kind: feature",
        "  - id: T-FEAT-2",
        "    epic_id: T-FEAT-2",
        "    plan: T-FEAT-2/md/plan.md",
        "    deps: []",
        "    kind: feature",
        "  - id: T-FEAT-3",
        "    epic_id: T-FEAT-3",
        "    plan: T-FEAT-3/md/plan.md",
        "    deps: []",
        "    kind: feature",
        "done: []",
        "",
    ])
    qpath = tmp_path / "memory-bank" / "back" / "roadmap" / "queue.yaml"
    qpath.parent.mkdir(parents=True, exist_ok=True)
    qpath.write_text(queue_yaml, encoding="utf-8")

    for feat in ["T-FEAT-1", "T-FEAT-2", "T-FEAT-3"]:
        plan_f = tmp_path / "memory-bank" / "back" / "plan" / feat / "md" / "plan.md"
        plan_f.parent.mkdir(parents=True, exist_ok=True)
        plan_f.write_text(f"# {feat}\n", encoding="utf-8")

    act = tmp_path / "memory-bank" / "activeContext.md"
    act.parent.mkdir(parents=True, exist_ok=True)
    act.write_text("## load_now\n- initial\n\n## Handoff\n", encoding="utf-8")

    # 1. Feature 1 complete -> cadence counter 1, phase idle
    res1 = mark_queue_epic_done(tmp_path, "T-FEAT-1")
    assert res1["ok"] is True
    assert res1["cadence"]["phase"] == "idle"
    assert res1["cadence"]["counter"] == 1

    # 2. Feature 2 complete -> triggers replan phase (counter 2)
    res2 = mark_queue_epic_done(tmp_path, "T-FEAT-2")
    assert res2["ok"] is True
    assert res2["cadence"]["phase"] == "replan"
    assert res2["cadence"]["counter"] == 2
    assert res2["cadence"]["pair_ids"] == ["T-FEAT-1", "T-FEAT-2"]

    # In replan phase with pending pair IDs, roadmap_advance arms REPLAN for pair epics
    adv_replan1 = roadmap_advance(tmp_path)
    assert adv_replan1["ok"] is True
    assert adv_replan1["armed"] is True
    assert adv_replan1["phase"] == "REPLAN"
    assert adv_replan1["epic"] == "T-FEAT-1"

    # 3. Advance replan for both epics -> transitions to refactor
    st_replan1 = advance_replan(
        tmp_path,
        epic_id="T-FEAT-1",
        outcome="skip",
        reason="no architectural gaps in T-FEAT-1",
        evidence=ReplanEvidence(critical_gaps=[]),
    )
    assert st_replan1.phase == "replan"

    st_replan2 = advance_replan(
        tmp_path,
        epic_id="T-FEAT-2",
        outcome="skip",
        reason="no architectural gaps in T-FEAT-2",
        evidence=ReplanEvidence(critical_gaps=[]),
    )
    assert st_replan2.phase == "refactor"

    # In refactor phase, roadmap_advance blocks next feature advance
    adv_blocked_refactor = roadmap_advance(tmp_path)
    assert adv_blocked_refactor["ok"] is False
    assert adv_blocked_refactor["cadence_blocked"] is True

    # 4. Refactor done (noop) -> transitions to resync
    st_refactor = record_refactor_noop(tmp_path, reason="both epics skipped replan")
    assert st_refactor.phase == "resync"

    # 5. Resync records HIGH drift
    st_resync_high = record_resync_evidence(
        tmp_path,
        high_count=2,
        resync_action="drift_detected",
    )
    assert st_resync_high.phase == "resync"
    assert st_resync_high.resync_evidence is not None
    assert st_resync_high.resync_evidence.high_count == 2

    # 6. Feature advance is strictly blocked on raw HIGH drift
    adv_blocked_high = roadmap_advance(tmp_path)
    assert adv_blocked_high["ok"] is False
    assert adv_blocked_high["cadence_blocked"] is True
    assert adv_blocked_high["stop"] == "CADENCE_BLOCKED"
    assert adv_blocked_high["high_count"] == 2

    # 7. Resync action performed -> record resync evidence with 0 high
    st_resync_cleared = record_resync_evidence(
        tmp_path,
        high_count=0,
        resync_action="reconciled",
    )
    assert st_resync_cleared.phase == "resync"
    assert st_resync_cleared.resync_evidence.high_count == 0

    # 8. Reset cadence idle (or on_resync_done)
    st_idle = reset_cadence_idle(tmp_path)
    assert st_idle.phase == "idle"
    assert st_idle.counter == 0
    assert st_idle.pair_ids == []

    # 9. Next feature advance succeeds and arms T-FEAT-3
    adv_armed = roadmap_advance(tmp_path)
    assert adv_armed["ok"] is True
    assert adv_armed["armed"] is True
    assert adv_armed["epic"] == "T-FEAT-3"
    assert "T-FEAT-3" in act.read_text(encoding="utf-8")
