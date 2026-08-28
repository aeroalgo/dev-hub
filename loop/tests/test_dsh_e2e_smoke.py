from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FAKE_DSH = ROOT / "loop" / "tests" / "fixtures" / "fake_dsh.sh"
COMPLETED_LOG = ROOT / "loop" / "tests" / "fixtures" / "dsh_session_completed.jsonl"


def _load_context_loop():
    hooks = str(ROOT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    path = ROOT / "loop" / "context_loop.py"
    spec = importlib.util.spec_from_file_location("context_loop_dsh_smoke", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _seed_context(cwd: Path) -> None:
    shard = cwd / "memory-bank" / "integration" / "plan" / "decompose-x" / "e16-foo.yaml"
    shard.parent.mkdir(parents=True)
    shard.write_text("schema: epic-decompose/v1\nstep_id: e16\n", encoding="utf-8")
    index = cwd / "memory-bank" / "integration" / "implement" / "implement-x" / "index.md"
    index.parent.mkdir(parents=True)
    index.write_text("| Step | Status |\n| e16 | pending |\n", encoding="utf-8")
    active = cwd / "memory-bank" / "activeContext.md"
    active.parent.mkdir(parents=True, exist_ok=True)
    active.write_text(
        "## load_now\n"
        "1. [e16-foo.yaml](integration/plan/decompose-x/e16-foo.yaml)\n"
        "2. [index.md](integration/implement/implement-x/index.md)\n\n"
        "## Handoff INTEG IMPLEMENT\n"
        "- **Следующий:** `INTEG IMPLEMENT e16`\n"
        "- **Gaps:** none.\n",
        encoding="utf-8",
    )


def test_dsh_e2e_smoke_prepare_runtime_dsh(tmp_path: Path, monkeypatch) -> None:
    context_loop = _load_context_loop()
    _seed_context(tmp_path)
    monkeypatch.setenv("EPIC_RUNTIME", "dsh")

    result = context_loop.prepare_session(tmp_path)

    assert result["runtime"] == "dsh"
    assert result["dsh_profile"].startswith("epic-")


def test_dsh_e2e_smoke_record_abort_completed(tmp_path: Path) -> None:
    context_loop = _load_context_loop()
    log = tmp_path / "dsh-session.jsonl"
    log.write_text(COMPLETED_LOG.read_text(encoding="utf-8"), encoding="utf-8")

    result = context_loop.record_abort(tmp_path, log_path=log, exit_code=0, runtime="dsh")

    assert result["ok"] is True
    assert result["outcome"] == "clean"


def test_dsh_e2e_smoke_claude_default_no_fake_dsh_called(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("claude path", encoding="utf-8")
    fake_claude = tmp_path / "fake-claude"
    fake_claude.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    fake_claude.chmod(fake_claude.stat().st_mode | stat.S_IXUSR)
    record = tmp_path / "fake-dsh.txt"
    env = os.environ.copy()
    env.update(
        {
            "PROJECT_ROOT": str(tmp_path),
            "STATE_DIR": str(tmp_path),
            "CLAUDE_BIN": str(fake_claude),
            "EPIC_RUNTIME_RESOLVED": "claude",
            "DSH_BIN": str(FAKE_DSH),
            "FAKE_DSH_RECORD_FILE": str(record),
            "EPIC_SESSION_TIMEOUT_SEC": "10",
            "EPIC_SESSION_KILL_GRACE_SEC": "1",
        }
    )

    subprocess.run(
        [
            "bash",
            "-c",
            f"source loop/loop.sh >/dev/null 2>&1 || true; run_agent_session 1 {prompt!s}",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert not record.exists()
