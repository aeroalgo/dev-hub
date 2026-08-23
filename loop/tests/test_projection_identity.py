from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"


def _load_epic_lib():
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    path = HOOKS / "epic_lib.py"
    spec = importlib.util.spec_from_file_location("epic_lib_projection", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write(cwd: Path, rel: str, body: str) -> None:
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _seed(cwd: Path, *, phase: str = "BACK IMPLEMENT", status: str = "pending") -> None:
    _write(
        cwd,
        "memory-bank/back/plan/decompose-T-035-loop-state-prod-hardening/index.md",
        "| step_id | title | status |\n"
        "| :--- | :--- | :--- |\n"
        f"| **s08** | [s08-projection-phase-epoch.yaml](s08-projection-phase-epoch.yaml) | {status} |\n",
    )
    _write(
        cwd,
        "memory-bank/back/plan/decompose-T-035-loop-state-prod-hardening/s08-projection-phase-epoch.yaml",
        "schema: epic-decompose/v1\nstep_id: s08\n",
    )
    _write(
        cwd,
        "memory-bank/activeContext.md",
        "## load_now\n"
        "- `memory-bank/back/plan/decompose-T-035-loop-state-prod-hardening/index.md`\n\n"
        "## Handoff BACK IMPLEMENT\n"
        f"- **Следующий:** `{phase} @s08`\n",
    )


def test_stable_projection_hash_and_phase_epoch(tmp_path: Path) -> None:
    epic_lib = _load_epic_lib()
    _seed(tmp_path)

    first = epic_lib.rebuild_epic_projection(tmp_path)
    second = epic_lib.rebuild_epic_projection(tmp_path)

    assert first["projection"]["projection_hash"].startswith("sha256:")
    assert first["projection"]["projection_hash"] == second["projection"]["projection_hash"]
    assert first["projection"]["phase_epoch"] == second["projection"]["phase_epoch"]
    assert first["projection"]["projection_generation"] == second["projection"]["projection_generation"]


def test_projection_hash_changes_for_phase_and_index_revision(tmp_path: Path) -> None:
    epic_lib = _load_epic_lib()
    _seed(tmp_path)
    initial = epic_lib.rebuild_epic_projection(tmp_path)["projection"]

    _seed(tmp_path, phase="BACK QA", status="active")
    changed = epic_lib.rebuild_epic_projection(tmp_path)["projection"]

    assert changed["projection_hash"] != initial["projection_hash"]
    assert changed["phase_epoch"] != initial["phase_epoch"]
    assert changed["projection_generation"] > initial["projection_generation"]


def test_projection_snapshot_contains_gate_and_event_evidence(tmp_path: Path) -> None:
    epic_lib = _load_epic_lib()
    _seed(tmp_path)

    projection = epic_lib.rebuild_epic_projection(tmp_path)["projection"]

    assert projection["schema_version"] == "loop-projection/v2"
    assert projection["pipeline_id"] is None
    assert projection["epic_id"] == "T-035-loop-state-prod-hardening"
    assert projection["role"] == "BACK"
    assert projection["next_step"] == "s08"
    assert projection["next_step_status"] == "pending"
    assert projection["event_digest"].startswith("sha256:")
    assert projection["last_event_seq"] is None
    assert projection["gates"] == {
        "mode": "implement",
        "need_verify": True,
        "need_reviewer": False,
    }
    assert projection["diagnostic_codes"] == ["state_rebuilt"]


def test_diagnostic_event_changes_projection_identity(tmp_path: Path) -> None:
    epic_lib = _load_epic_lib()
    _seed(tmp_path)
    initial = epic_lib.rebuild_epic_projection(tmp_path)["projection"]
    _write(
        tmp_path,
        "memory-bank/back/events/T-035-loop-state-prod-hardening/events.jsonl",
        "{malformed\n",
    )

    changed = epic_lib.rebuild_epic_projection(tmp_path)["projection"]

    assert changed["projection_hash"] != initial["projection_hash"]
    assert changed["phase_epoch"] != initial["phase_epoch"]
    assert changed["diagnostic_codes"]
