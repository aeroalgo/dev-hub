"""Tests for Step s05: Kind I — README gate_verdict + prompts «no fence = FAIL» runtime-true (FR-010, FR-012)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import pytest

from loop.schemas.boundary_registry import (
    BOUNDARY_REGISTRY,
    SCHEMA_LOOP_GATE_VERDICT,
    SCHEMA_LOOP_REPAIR_RESULT,
    SCHEMA_LOOP_SUNSET_INVENTORY,
)
from loop.schemas.gate_verdict import GateVerdictRecord
from loop.schemas.repair_result import RepairResultRecord
from loop.schemas.sunset_inventory import SunsetReport

ROOT = Path(__file__).resolve().parents[2]
README_PATH = ROOT / "loop" / "schemas" / "README.md"
AGENT_PROMPTS_DIR = ROOT / "harness" / "agents"
SUBAGENT_STOP_SCRIPT = ROOT / ".claude" / "hooks" / "subagent-stop.py"


def test_readme_not_skip_after_purge():
    """s06 TDD: Ensure README contains no SKIP or obsolete verdict.py references."""
    test_readme_gate_verdict_not_skip_or_verdict_py()


def test_readme_gate_verdict_not_skip_or_verdict_py():
    """FR-012 / cp1: README current SoT is GateVerdictRecord PASS/FAIL/BLOCKED in gate_verdict.py.

    Leftover verdict.py or SKIP as current SoT in schemas table equals 0.
    """
    assert README_PATH.is_file(), f"Missing README at {README_PATH}"
    readme_text = README_PATH.read_text(encoding="utf-8")

    # GateVerdictRecord and gate_verdict.py must be present
    assert "GateVerdictRecord" in readme_text
    assert "gate_verdict.py" in readme_text
    assert "PASS/FAIL/BLOCKED" in readme_text

    # Obsolete verdict.py (exact whole word or path) and SKIP references in schema table/SoT must be absent
    assert not re.search(r"(?<!gate_)verdict\.py", readme_text), "Found obsolete verdict.py reference in README"
    assert "LoopGateVerdict" not in readme_text
    assert "SKIP" not in readme_text

    # RepairResultRecord and SunsetReport must also be accurately documented in README registry
    assert "RepairResultRecord" in readme_text
    assert "repair_result.py" in readme_text
    assert "SunsetReport" in readme_text
    assert "sunset_inventory.py" in readme_text


def test_prompts_require_fence_and_runtime_agrees(tmp_path: Path):
    """FR-010 / cp2 / cp3: Prompts still require JSON fence and runtime rejects no-fence."""
    verify_impl_path = AGENT_PROMPTS_DIR / "verify-implement.md"
    verify_qa_path = AGENT_PROMPTS_DIR / "verify-qa.md"
    gate_repair_path = AGENT_PROMPTS_DIR / "gate-repair.md"

    for prompt_file in (verify_impl_path, verify_qa_path, gate_repair_path):
        assert prompt_file.is_file(), f"Missing prompt file {prompt_file}"
        text = prompt_file.read_text(encoding="utf-8")
        # Must require JSON fence / schema
        assert "```json" in text or "JSON fence" in text
        assert "schema" in text

    # Set up isolated epic runtime directory so test execution does not pollute root epic state
    (tmp_path / ".claude" / "runtime" / "epic").mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["HUB_ROOT"] = str(tmp_path)

    session_id = "test-kind-i-living-nofence"
    tool_use_id = "call-kind-i-living-nofence"
    payload = {
        "agent_type": "verify-implement",
        "session_id": session_id,
        "tool_use_id": tool_use_id,
        "cwd": str(tmp_path),
        "verdict": "PASS",
        "last_assistant_message": "Here is my evaluation. VERDICT: PASS\nAll tests pass.",
        "stop_hook_active": False,
    }

    proc = subprocess.run(
        [sys.executable, str(SUBAGENT_STOP_SCRIPT)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(tmp_path),
        env=env,
        check=False,
    )

    # Must fail schema validation because there is no fenced JSON
    assert proc.returncode == 2
    assert "schema validation failed" in proc.stderr
    state_file = tmp_path / ".claude" / "runtime" / "spawn-gate" / f"{session_id}.json"
    if state_file.exists():
        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert state.get("verify_verdict") != "PASS"
        assert state.get("verify_done") is not True


def test_kind_i_no_payload_sot_or_extra_ignore():
    """FR-010 / FR-012 / cp4: Kind I does not teach payload data.verdict as SoT or extra=ignore collab."""
    # Check that in instructions/docs/prompts we don't claim data.verdict is SoT over fence
    search_dirs = [
        ROOT / "harness" / "agents",
        ROOT / "loop" / "schemas",
        ROOT / ".claude" / "instructions",
    ]

    for sdir in search_dirs:
        if not sdir.exists():
            continue
        for f in sdir.glob("**/*"):
            if f.is_file() and f.suffix in (".md", ".txt"):
                txt = f.read_text(encoding="utf-8")
                # Positive check: no instructions stating data.verdict overrides fence or extra=ignore on gate
                assert "payload verdict is SoT" not in txt
                assert "data.verdict is SoT" not in txt
                assert "extra=ignore" not in txt or "forbid" in txt
