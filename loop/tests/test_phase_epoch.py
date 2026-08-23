from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"


def _load_epic_lib():
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    spec = importlib.util.spec_from_file_location("epic_lib_epoch", HOOKS / "epic_lib.py")
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


def test_phase_epoch_changes_for_relevant_phase_source(tmp_path: Path) -> None:
    epic_lib = _load_epic_lib()
    _seed(tmp_path)
    first = epic_lib.rebuild_epic_projection(tmp_path)["projection"]

    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n"
        "- `memory-bank/back/plan/decompose-T-035-loop-state-prod-hardening/index.md`\n\n"
        "## Handoff BACK QA\n"
        "- **Следующий:** `BACK QA @s08`\n",
    )
    second = epic_lib.rebuild_epic_projection(tmp_path)["projection"]

    assert second["phase"] == "BACK IMPLEMENT"
    assert second["phase_epoch"] == first["phase_epoch"]


def test_phase_epoch_changes_for_event_diagnostic(tmp_path: Path) -> None:
    epic_lib = _load_epic_lib()
    _seed(tmp_path)
    first = epic_lib.rebuild_epic_projection(tmp_path)["projection"]
    _write(
        tmp_path,
        "memory-bank/back/events/T-035-loop-state-prod-hardening/events.jsonl",
        "{malformed\n",
    )
    second = epic_lib.rebuild_epic_projection(tmp_path)["projection"]

    assert second["diagnostic_codes"] == ["invalid_json", "state_rebuilt"]
    assert second["phase_epoch"] != first["phase_epoch"]
    assert second["projection_generation"] == first["projection_generation"] + 1
