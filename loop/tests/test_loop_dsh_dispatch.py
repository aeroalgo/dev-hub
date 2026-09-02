from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOOP_SH = ROOT / "loop" / "loop.sh"
FAKE_DSH = ROOT / "loop" / "tests" / "fixtures" / "fake_dsh.sh"


def _run_loop(tmp_path: Path, *, runtime: str = "dsh", dsh_bin: str | None = None) -> subprocess.CompletedProcess[str]:
    product = tmp_path / "product"
    (product / "memory-bank").mkdir(parents=True)
    (product / "memory-bank" / "activeContext.md").write_text(
        "## load_now\n1. [activeContext.md](activeContext.md)\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update(
        {
            "PROJECT_ROOT": str(product),
            "EPIC_RUNTIME_RESOLVED": runtime,
            "EPIC_DSH_PROFILE": "epic-implement",
            "DSH_BIN": dsh_bin or str(FAKE_DSH),
            "FAKE_DSH_RECORD_FILE": str(tmp_path / "fake-dsh.txt"),
        }
    )
    return subprocess.run(
        ["bash", "-c", "source loop/loop.sh"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_fake_dsh_records_argv_and_prompt(tmp_path: Path) -> None:
    record = tmp_path / "record.txt"
    result = subprocess.run(
        [str(FAKE_DSH), "--profile", "epic-implement", "hello"],
        env={**os.environ, "FAKE_DSH_RECORD_FILE": str(record)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--profile epic-implement hello" in record.read_text(encoding="utf-8")


def _run_dsh_function(
    tmp_path: Path,
    *,
    dsh_bin: str | None = None,
    path: str | None = None,
    resolver_path: Path | None = None,
    path_prefix: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("hello from prompt", encoding="utf-8")
    record = tmp_path / "fake-dsh.txt"
    env = os.environ.copy()
    env.update(
        {
            "PROJECT_ROOT": str(tmp_path),
            "STATE_DIR": str(tmp_path),
            "SESSION_WRAPPER": str(ROOT / ".claude/hooks/session_resilience.py"),
            "EPIC_SESSION_TIMEOUT_SEC": "10",
            "EPIC_SESSION_KILL_GRACE_SEC": "1",
            "EPIC_RUNTIME_RESOLVED": "dsh",
            "EPIC_DSH_PROFILE": "epic-implement",
            "DSH_BIN": dsh_bin or str(FAKE_DSH),
            "FAKE_DSH_RECORD_FILE": str(record),
        }
    )
    if path is not None:
        env["HUB_ROOT"] = str(tmp_path)
        dsh_dir = tmp_path / "dsh" / "bin"
        dsh_dir.mkdir(parents=True)
        resolver = dsh_dir / "which-dsh.sh"
        resolver.write_text(path, encoding="utf-8")
        resolver.chmod(0o755)
    if resolver_path is not None:
        env["DSH_RESOLVER"] = str(resolver_path)
    if path_prefix is not None:
        env["PATH"] = f"{path_prefix}:{env['PATH']}"
    result = subprocess.run(
        ["bash", "-c", f"source loop/loop.sh >/dev/null 2>&1 || true; run_agent_session 1 {shlex.quote(str(prompt))}"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result, record


def test_run_agent_session_dispatches_dsh(tmp_path: Path) -> None:
    result, record = _run_dsh_function(tmp_path)
    assert result.returncode == 0
    recorded = record.read_text(encoding="utf-8")
    assert "--profile epic-implement" in recorded
    assert "hello from prompt" in recorded


def test_run_agent_session_dispatches_global_dsh_resolver(tmp_path: Path) -> None:
    resolver = tmp_path / "global-resolver.sh"
    resolver.write_text(f"#!/usr/bin/env bash\nprintf '%s\\n' {shlex.quote(str(FAKE_DSH))}\n", encoding="utf-8")
    resolver.chmod(0o755)
    result, record = _run_dsh_function(tmp_path, resolver_path=resolver, dsh_bin="/nonexistent")
    assert result.returncode == 0
    recorded = record.read_text(encoding="utf-8")
    assert "--profile epic-implement" in recorded
    assert "hello from prompt" in recorded


def test_run_agent_session_dispatches_npx_resolver_as_argv(tmp_path: Path) -> None:
    resolver = tmp_path / "npx-resolver.sh"
    resolver.write_text(
        "#!/usr/bin/env bash\nprintf '%s\\n' npx -y @deepseek-ai/dsh\n",
        encoding="utf-8",
    )
    resolver.chmod(0o755)
    npx = tmp_path / "npx"
    npx.write_text(
        f"#!/usr/bin/env bash\nexec {shlex.quote(str(FAKE_DSH))} \"$@\"\n",
        encoding="utf-8",
    )
    npx.chmod(0o755)
    result, record = _run_dsh_function(
        tmp_path,
        resolver_path=resolver,
        dsh_bin="/nonexistent",
        path_prefix=tmp_path,
    )
    assert result.returncode == 0
    recorded = record.read_text(encoding="utf-8")
    assert "argv: -y @deepseek-ai/dsh --profile epic-implement --no-open hello from prompt" in recorded


def test_run_agent_session_defaults_to_claude(tmp_path: Path) -> None:
    script = LOOP_SH.read_text(encoding="utf-8")
    assert 'local runtime_id="${EPIC_RUNTIME_RESOLVED:-claude}"' in script
    assert "EPIC_DSH_PROFILE" not in script


def test_loop_dsh_dispatch_no_epic_dsh_profile_env(tmp_path: Path) -> None:
    script = LOOP_SH.read_text(encoding="utf-8")
    assert "EPIC_DSH_PROFILE" not in script


def test_run_dsh_session_fails_closed_on_missing_dsh(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("hello", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "PROJECT_ROOT": str(tmp_path),
            "STATE_DIR": str(tmp_path),
            "SESSION_WRAPPER": str(ROOT / ".claude/hooks/session_resilience.py"),
            "EPIC_SESSION_TIMEOUT_SEC": "10",
            "EPIC_SESSION_KILL_GRACE_SEC": "1",
            "EPIC_RUNTIME_RESOLVED": "dsh",
            "DSH_BIN": "/nonexistent",
            "DSH_RESOLVER": str(tmp_path / "missing-resolver.sh"),
        }
    )
    result = subprocess.run(
        ["bash", "-c", f"source loop/loop.sh >/dev/null 2>&1 || true; run_dsh_session 1 {shlex.quote(str(prompt))}"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "dsh binary not found" in result.stderr
