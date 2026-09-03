import json
import pytest
from pathlib import Path
import sys

# Ensure .claude/hooks and loop are in sys.path
root_dir = Path(__file__).resolve().parents[2]
hooks_dir = root_dir / ".claude" / "hooks"
for p in (str(hooks_dir), str(root_dir)):
    if p not in sys.path:
        sys.path.insert(0, p)

from epic import (
    load_epic_state,
    save_epic_state,
    validate_checkpoint,
    mark_index_step_status,
    finalize_step,
    repair_index_mirror,
    project_handoff_from_reducer,
    _state_diagnostics,
)
from loop.schemas.state import EpicState, DriftCounters
from loop.schemas.board import BoardCardMetadata
from _lib import extract_verdict


def test_us001_corrupt_state_json(tmp_path: Path):
    state_dir = tmp_path / ".claude" / "runtime" / "epic"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "state.json"
    state_file.write_text("{corrupt json", encoding="utf-8")

    diag = _state_diagnostics(tmp_path)
    assert "state_schema_invalid" in diag

    state = load_epic_state(tmp_path)
    assert state.get("status") == "idle" or state.get("active") is False


def test_us002_invalid_cp_field():
    cp_dict = {
        "id": "cp1",
        "criterion": "test criterion",
        "status": "invalid_status_value"
    }
    err = validate_checkpoint(cp_dict)
    assert err is not None


def test_us003_invalid_board_card():
    invalid_data = {
        "card_kind": "step",
        "project_root": "/tmp",
        "workspace_id": "ws1",
        "role": "back",
        "sync_generation": "invalid_int_value"
    }
    with pytest.raises(Exception):
        BoardCardMetadata.model_validate(invalid_data)


def test_us004_save_epic_state_version(tmp_path: Path):
    state = EpicState(epic_id="T-HUB-022").model_dump()
    save_epic_state(tmp_path, state)

    state_file = tmp_path / ".claude" / "runtime" / "epic" / "state.json"
    content = json.loads(state_file.read_text(encoding="utf-8"))
    assert content.get("state_schema_version") == "loop-state/v2"


def test_us005_stale_handoff_reflect(tmp_path: Path):
    epic = "T-HUB-022"
    decompose = f"memory-bank/back/plan/decompose-{epic}/index.yaml"
    decompose_file = tmp_path / decompose
    decompose_file.parent.mkdir(parents=True, exist_ok=True)
    decompose_file.write_text(
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic}\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-one.yaml\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  title: one\n"
        "  status: completed\n",
        encoding="utf-8"
    )
    qa_file = tmp_path / f"memory-bank/back/qa/{epic}/qa-20260830-demo.yaml"
    qa_file.parent.mkdir(parents=True, exist_ok=True)
    qa_file.write_text(
        "schema: epic-qa/v1\nverdict: pass\nissues: []\n",
        encoding="utf-8"
    )
    active_ctx = tmp_path / "memory-bank" / "activeContext.md"
    active_ctx.parent.mkdir(parents=True, exist_ok=True)
    active_ctx.write_text(
        "## load_now\n"
        f"1. [index.yaml](back/plan/decompose-{epic}/index.yaml)\n\n"
        f"## Handoff BACK BUGFIX — {epic}\n"
        "- **Режим/шаг:** `BACK BUGFIX`.\n",
        encoding="utf-8"
    )

    out = project_handoff_from_reducer(tmp_path)
    assert out.get("ok") is True
    assert out.get("projected") is True
    assert out.get("phase") == "DONE"


def test_us006_sidecar_pass_transcript_fail(tmp_path: Path):
    from loop.gate_verdict_store import write_gate_verdict

    write_gate_verdict(
        tmp_path,
        "verify",
        "PASS",
        step_id="s01",
        session_id="sess-1",
        epic_id="T-HUB-022",
        recorded_at="2026-08-31T00:00:00Z",
    )

    verdict = extract_verdict("VERDICT: FAIL", cwd=str(tmp_path), agent_id="verify")
    assert verdict == "PASS"


def test_us007_strict_legacy_ac_blocked(tmp_path: Path):
    # Invalid step_id format triggers error/blocked response
    res = finalize_step(cwd=tmp_path, decompose="memory-bank/back/plan/decompose-T-HUB-022/index.yaml", step_id="invalid_step")
    assert res.get("ok") is False or "bad step_id" in str(res)


def test_us008_repair_index_mirror_drift(tmp_path: Path):
    state = EpicState(epic_id="T-HUB-022", drift_counters=DriftCounters(index_mirror_repair=0)).model_dump()
    save_epic_state(tmp_path, state)

    repair_index_mirror(tmp_path, decompose="memory-bank/back/plan/decompose-T-HUB-022/index.yaml")

    loaded_state = load_epic_state(tmp_path)
    assert loaded_state.get("drift_counters", {}).get("index_mirror_repair", 0) >= 1


def test_us009_mark_index_step_status(tmp_path: Path):
    index_path = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-HUB-022" / "index.yaml"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("steps:\n  - id: s01\n    status: pending\n", encoding="utf-8")
    index_md = index_path.with_name("index.md")
    index_md.write_text("# Index\n- [ ] s01\n", encoding="utf-8")

    mark_index_step_status(tmp_path, "memory-bank/back/plan/decompose-T-HUB-022/index.yaml", "s01", "completed")

    assert "completed" in index_path.read_text(encoding="utf-8")
    assert "completed" in index_md.read_text(encoding="utf-8")
