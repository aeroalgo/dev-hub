"""Regression: resume_policy=next_step must allow step transition.

When a session finishes with resume_policy=next_step, the next prepare
will have a different step in identity. This must not produce
checkpoint_identity_conflict.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
EPIC_LIB_PATH = HOOKS / "epic_lib.py"


def _load_epic_lib():
    hooks = str(HOOKS)
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    spec = importlib.util.spec_from_file_location("epic_lib_cp", EPIC_LIB_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_checkpoint(
    tmp_path: Path, resume_policy: str, stage: str, step: str = "s01"
) -> None:
    cp_dir = tmp_path / ".claude" / "runtime" / "epic"
    cp_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = {
        "schema": "loop-checkpoint/v1",
        "checkpoint_seq": 1,
        "checkpoint_id": f"prepare-abc:{step}",
        "session_id": "prepare-abc",
        "runner_id": None,
        "identity": {
            "action": "invoke",
            "epic": "T-039-loop-audit-remediation",
            "pipeline": "integ-demo",
            "role": "BACK",
            "step": step,
        },
        "step_id": step,
        "phase": "BACK IMPLEMENT",
        "phase_epoch": 1,
        "projection_hash": "h1",
        "stage": stage,
        "status": "committed",
        "next_action": "advance",
        "resume_policy": resume_policy,
        "context_fingerprint": None,
        "index_fingerprint": None,
        "retry_count": 0,
        "degraded_count": 0,
        "reason": None,
        "metadata": None,
        "created_at": "2026-08-07T00:00:00Z",
        "updated_at": "2026-08-07T00:00:00Z",
    }
    cp_json = cp_dir / "checkpoint.json"
    cp_json.write_text(json.dumps(checkpoint), encoding="utf-8")
    (cp_dir / "checkpoint.lock").write_text("", encoding="utf-8")


def test_next_step_committed_allows_step_mismatch(tmp_path: Path) -> None:
    """s01 next_step → prepare s02 must advance (no identity conflict)."""
    lib = _load_epic_lib()
    _write_checkpoint(tmp_path, "next_step", "committed", "s01")

    result = lib.resolve_checkpoint_resume(
        tmp_path,
        identity={
            "pipeline": "integ-demo",
            "epic": "T-039-loop-audit-remediation",
            "role": "BACK",
            "step": "s02",
        },
    )

    assert result.get("ok") is True, f"got: {result}"
    assert result.get("decision") == "advance"
    assert result.get("code") is None


def test_next_step_committed_rejects_other_field_mismatch(
    tmp_path: Path,
) -> None:
    """next_step allows only step; epic mismatch still conflicts."""
    lib = _load_epic_lib()
    _write_checkpoint(tmp_path, "next_step", "committed", "s01")

    result = lib.resolve_checkpoint_resume(
        tmp_path,
        identity={
            "pipeline": "integ-demo",
            "epic": "T-999-other",
            "role": "BACK",
            "step": "s02",
        },
    )

    assert result.get("ok") is False
    assert result.get("code") == "checkpoint_identity_conflict"


def test_next_step_committed_allows_absent_role_in_checkpoint(
    tmp_path: Path,
) -> None:
    """Stored identity without role must not halt when expected has role."""
    lib = _load_epic_lib()
    _write_checkpoint(tmp_path, "next_step", "committed", "DECOMPOSE")
    cp_path = tmp_path / ".claude" / "runtime" / "epic" / "checkpoint.json"
    record = json.loads(cp_path.read_text(encoding="utf-8"))
    record["identity"].pop("role", None)
    record["step_id"] = "DECOMPOSE"
    cp_path.write_text(json.dumps(record), encoding="utf-8")

    result = lib.resolve_checkpoint_resume(
        tmp_path,
        identity={
            "pipeline": "integ-demo",
            "epic": "T-039-loop-audit-remediation",
            "role": "BACK",
            "step": "s01",
        },
    )

    assert result.get("ok") is True, f"got: {result}"
    assert result.get("decision") == "advance"
    assert result.get("code") is None


def test_non_next_step_still_conflicts_on_step_mismatch(
    tmp_path: Path,
) -> None:
    """Without next_step, step mismatch must still halt."""
    lib = _load_epic_lib()
    _write_checkpoint(tmp_path, "same_step", "committed", "s01")

    result = lib.resolve_checkpoint_resume(
        tmp_path,
        identity={
            "pipeline": "integ-demo",
            "epic": "T-039-loop-audit-remediation",
            "role": "BACK",
            "step": "s02",
        },
    )

    assert result.get("ok") is False
    assert result.get("code") == "checkpoint_identity_conflict"


def test_next_step_committed_allows_qa_to_done(tmp_path: Path) -> None:
    """QA next_step → prepare DONE must advance (post-implement transition)."""
    lib = _load_epic_lib()
    cp_dir = tmp_path / ".claude" / "runtime" / "epic"
    cp_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = {
        "schema": "loop-checkpoint/v1",
        "checkpoint_seq": 2,
        "checkpoint_id": "sess23:QA",
        "session_id": "sess23",
        "identity": {
            "action": "invoke",
            "epic": "T-HUB-015-dsh-board-arm-loop",
            "role": "BACK",
            "step": "QA",
        },
        "step_id": "QA",
        "phase": "QA",
        "phase_epoch": "1",
        "stage": "committed",
        "status": "committed",
        "next_action": "advance",
        "resume_policy": "next_step",
        "retry_count": 0,
        "degraded_count": 0,
        "reason": None,
        "metadata": None,
        "updated_at": "2026-08-29T12:25:14Z",
    }
    (cp_dir / "checkpoint.json").write_text(json.dumps(checkpoint), encoding="utf-8")

    result = lib.resolve_checkpoint_resume(
        tmp_path,
        identity={
            "epic": "T-HUB-015-dsh-board-arm-loop",
            "role": "BACK",
            "step": "DONE",
        },
    )

    assert result.get("ok") is True, f"got: {result}"
    assert result.get("decision") == "advance"
    assert result.get("code") is None
