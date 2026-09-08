from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "harness" / "hooks" / "context-scope-pretool.py"


def _run_hook(workspace: Path, payload: dict[str, object]) -> dict[str, object]:
    env = os.environ.copy()
    env.update({"EPIC_LOOP": "1", "PROJECT_ROOT": str(workspace)})
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def _workspace(tmp_path: Path) -> Path:
    active = tmp_path / "memory-bank" / "activeContext.md"
    shard = tmp_path / "memory-bank" / "back" / "plan" / "E-1" / "yaml" / "steps" / "s01-step.yaml"
    shard.parent.mkdir(parents=True)
    active.parent.mkdir(parents=True, exist_ok=True)
    shard.write_text(
        """schema: epic-decompose/v1
role: back
step_id: s01
plan_id: E-1
title: step
goal: goal
delta: [app/main.py]
plan_contract:
  plan_jumps: [memory-bank/back/plan/E-1/md/plan.md:10-20]
files: [harness/hooks/tests/test_scope.py]
checkpoints: [{id: cp1, criterion: done, verify: 'bin/pytest x -q'}]
""",
        encoding="utf-8",
    )
    active.write_text(
        """---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: E-1
step_id: s01
---

## load_now
1. [memory-bank/back/plan/E-1/yaml/steps/s01-step.yaml](memory-bank/back/plan/E-1/yaml/steps/s01-step.yaml)
2. [memory-bank/back/plan/E-1/yaml/decompose-index.yaml](memory-bank/back/plan/E-1/yaml/decompose-index.yaml)

## Handoff BACK IMPLEMENT — s01
""",
        encoding="utf-8",
    )
    return tmp_path


def test_context_scope_pretool_denies_whole_plan(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    result = _run_hook(
        workspace,
        {
            "tool_name": "Read",
            "tool_input": {"file_path": "memory-bank/back/plan/E-1/md/plan.md"},
            "cwd": str(workspace),
        },
    )
    output = result["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert "Whole plan read denied" in output["permissionDecisionReason"]


def test_context_scope_pretool_allows_current_shard(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    result = _run_hook(
        workspace,
        {
            "tool_name": "Read",
            "tool_input": {
                "file_path": "memory-bank/back/plan/E-1/yaml/steps/s01-step.yaml"
            },
            "cwd": str(workspace),
        },
    )
    assert result == {}
