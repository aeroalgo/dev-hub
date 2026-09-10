"""Late remirror after promote must not demote last_verify against the next step."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "harness" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from harness.hooks.epic.core import (  # noqa: E402
    default_state,
    load_epic_state,
    mirror_verify_verdict,
    save_epic_state,
)


def test_mirror_stale_verify_step_does_not_demote_after_promote(tmp_path: Path) -> None:
    st = default_state()
    st.update(
        {
            "active": True,
            "armed_epic": "T-HUB-STALE",
            "armed_step": "s02",
            "armed_role": "BACK",
            "armed_decompose": "memory-bank/back/plan/decompose-T-HUB-STALE/index.yaml",
            "session_id": "sess-stale",
            "last_verify_verdict": "PASS",
            "last_verify_evidence": {
                "schema": "loop-verifier-receipt/v1",
                "session_id": "sess-stale",
                "epic_id": "T-HUB-STALE",
                "role": "BACK",
                "step": "s01",
                "verifier_identity": "verify-implement",
                "verdict": "PASS",
                "authority": "autonomous",
            },
            "last_finish_tool": {
                "name": "mb-finish implement",
                "step_id": "s01",
                "phase_run_id": "run-1",
            },
        }
    )
    save_epic_state(tmp_path, st)

    plan = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-HUB-STALE"
    plan.mkdir(parents=True)
    (plan / "index.yaml").write_text(
        "schema: epic-decompose-index/v1\n"
        "epic_id: T-HUB-STALE\n"
        "steps:\n"
        "  - id: s01\n"
        "    file: s01.yaml\n"
        "    status: completed\n"
        "  - id: s02\n"
        "    file: s02.yaml\n"
        "    status: pending\n",
        encoding="utf-8",
    )

    mirror_verify_verdict(
        tmp_path,
        "PASS",
        evidence={
            "schema": "loop-verifier-receipt/v1",
            "session_id": "sess-stale",
            "epic_id": "T-HUB-STALE",
            "role": "BACK",
            "step": "s01",
            "verifier_identity": "verify-implement",
            "verdict": "PASS",
            "authority": "manual",
        },
        session_id="sess-stale",
        agent_id="verify-implement",
    )

    after = load_epic_state(tmp_path)
    assert after.get("last_verify_verdict") == "PASS"
    assert after.get("gate_diagnostic") == "stale_verify_step"
    assert not (after.get("last_verify_evidence") or {}).get("demoted_from_pass")
