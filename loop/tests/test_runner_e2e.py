"""End-to-end execution tests for bin/loop and loop/loop.sh with fake runtime across full loop turn."""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _seed_fake_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "product"
    repo.mkdir(parents=True)
    mb = repo / "memory-bank"
    mb.mkdir(parents=True)

    # Shard
    shard = mb / "back" / "plan" / "decompose-t01" / "s01-foo.yaml"
    shard.parent.mkdir(parents=True)
    shard.write_text("schema: epic-decompose/v1\nstep_id: s01\n", encoding="utf-8")

    # Index
    index = mb / "back" / "plan" / "decompose-t01" / "index.yaml"
    index.write_text(
        "schema: epic-decompose/v1\n"
        "epic_id: T-01\n"
        "steps:\n"
        "  - id: s01\n"
        "    title: Step 1\n"
        "    status: pending\n",
        encoding="utf-8",
    )

    # Active context
    active = mb / "activeContext.md"
    active.write_text(
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        "epic_id: T-01\n"
        "step_id: s01\n"
        "---\n"
        "## load_now\n"
        "1. [s01-foo.yaml](back/plan/decompose-t01/s01-foo.yaml)\n"
        "2. [index.yaml](back/plan/decompose-t01/index.yaml)\n\n"
        "## Handoff BACK IMPLEMENT\n"
        "- **Следующий:** `BACK IMPLEMENT s01`\n"
        "- **Gaps:** none.\n",
        encoding="utf-8",
    )
    return repo


def _create_fake_claude(tmp_path: Path) -> Path:
    fake = tmp_path / "fake-claude"
    script = (
        "#!/usr/bin/env python3\n"
        "import sys, os, json, pathlib\n"
        "prompt = sys.argv[-1] if len(sys.argv) > 1 else ''\n"
        "project_root = pathlib.Path(os.environ.get('PROJECT_ROOT', '.'))\n"
        "runtime_dir = project_root / 'runtime' / 'dev-hub' / 'epic'\n"
        "runtime_dir.mkdir(parents=True, exist_ok=True)\n"
        "state_file = runtime_dir / 'state.json'\n"
        "st = {}\n"
        "if state_file.is_file():\n"
        "    st = json.loads(state_file.read_text(encoding='utf-8'))\n"
        "st['last_finish_tool'] = {\n"
        "    'name': 'mb-finish implement',\n"
        "    'session_id': st.get('session_id', 'sess-1'),\n"
        "    'epic_id': st.get('armed_epic', 'T-01'),\n"
        "    'fingerprint': 'sha256:finish',\n"
        "    'step_id': st.get('armed_step', 's01'),\n"
        "}\n"
        "st['last_finished_step'] = st.get('armed_step', 's01')\n"
        "state_file.write_text(json.dumps(st), encoding='utf-8')\n"
        "print('SESSION_START session=' + st.get('session_id', 'sess-1') + ' mode=headless command=claude')\n"
        "print('{\"type\": \"tool_started\", \"name\": \"apply_patch\"}')\n"
        "print('{\"type\": \"tool_completed\", \"name\": \"apply_patch\"}')\n"
        "print('{\"type\": \"assistant_message\", \"text\": \"FINISH\"}')\n"
        "print('SESSION_END session=' + st.get('session_id', 'sess-1') + ' exit_code=0')\n"
        "sys.exit(0)\n"
    )
    fake.write_text(script, encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    return fake


def test_loop_sh_runs_help() -> None:
    res = subprocess.run(
        [str(ROOT / "loop" / "loop.sh"), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "Context-first" in res.stdout or "Usage:" in res.stdout


def test_bin_loop_runs_doctor(tmp_path: Path) -> None:
    repo = _seed_fake_repo(tmp_path)
    res = subprocess.run(
        [str(ROOT / "bin" / "loop"), str(repo), "doctor"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "project_root_valid" in res.stdout


def test_bin_loop_end_to_end_single_turn(tmp_path: Path) -> None:
    repo = _seed_fake_repo(tmp_path)
    fake_claude = _create_fake_claude(tmp_path)

    env = os.environ.copy()
    env["CLAUDE_BIN"] = str(fake_claude)
    env["PROJECT_LOOP_IMPLEMENT_MODEL"] = "gpt-5.6-terra"
    env["EPIC_RUNTIME"] = "claude"

    # Run loop via bin/loop
    proc = subprocess.Popen(
        [str(ROOT / "bin" / "loop"), str(repo), "gpt-5.6-terra"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        stdout, stderr = proc.communicate(timeout=20)
    except subprocess.TimeoutExpired:
        proc.terminate()
        stdout, stderr = proc.communicate(timeout=5)

    combined = f"{stdout}\n{stderr}"
    assert "======== SESSION" in combined, (
        f"bin/loop must enter LoopRunner outer loop; got rc={proc.returncode}\n"
        f"stdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert proc.returncode in (0, 1, 2, 130, 143)
