from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "harness" / "hooks"
sys.path.insert(0, str(HOOKS))
sys.path.insert(0, str(ROOT))

from touch_ledger import (  # noqa: E402
    ensure_touch_ledger_identity,
    load_touch_ledger,
    record_touch,
    reset_touch_ledger,
    touched_paths,
    touch_ledger_path,
)
from _lib import bash_discard_dirty_deny_reason  # noqa: E402


def test_record_touch_and_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    monkeypatch.setenv("DEV_HUB", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    (project / "a.py").write_text("x\n", encoding="utf-8")

    reset_touch_ledger(project, epic_id="T-HUB-091-x", step_id="s02")
    record_touch(project, "a.py", operation="edit", epic_id="T-HUB-091-x", step_id="s02")
    record_touch(project, "a.py", operation="edit", epic_id="T-HUB-091-x", step_id="s02")
    record_touch(project, "b.py", operation="write", epic_id="T-HUB-091-x", step_id="s02")

    assert touched_paths(project) == ["a.py", "b.py"]
    data = load_touch_ledger(project)
    assert data["epic_id"] == "T-HUB-091-x"
    assert data["step_id"] == "s02"
    assert touch_ledger_path(project).is_file()


def test_identity_change_resets_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    monkeypatch.setenv("DEV_HUB", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    record_touch(project, "old.py", epic_id="T-HUB-080", step_id="s01")
    assert touched_paths(project) == ["old.py"]

    ensure_touch_ledger_identity(project, epic_id="T-HUB-091", step_id="s02")
    assert touched_paths(project) == []
    data = load_touch_ledger(project)
    assert data["epic_id"] == "T-HUB-091"
    assert data["step_id"] == "s02"


def test_phase_run_id_does_not_wipe_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    monkeypatch.setenv("DEV_HUB", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    reset_touch_ledger(project, epic_id="T-HUB-091", step_id="s03", phase_run_id="run-a")
    record_touch(
        project,
        "harness/hooks/subagent-stop.py",
        epic_id="T-HUB-091",
        step_id="s03",
        phase_run_id="run-a",
    )
    ensure_touch_ledger_identity(
        project,
        epic_id="T-HUB-091",
        step_id="s03",
        phase_run_id="run-b",
    )
    assert touched_paths(project) == ["harness/hooks/subagent-stop.py"]
    data = load_touch_ledger(project)
    assert data["phase_run_id"] == "run-b"


def test_agent_posttool_records_apply_patch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    monkeypatch.setenv("DEV_HUB", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    target = project / "harness" / "hooks" / "x.py"
    target.parent.mkdir(parents=True)
    target.write_text("print(1)\n", encoding="utf-8")

    from epic_paths import epic_dir

    epic = epic_dir(project)
    (epic / "state.json").write_text(
        json.dumps(
            {
                "armed_epic": "T-HUB-091-test",
                "armed_step": "s03",
                "phase_run_id": "abc",
            }
        ),
        encoding="utf-8",
    )

    import subprocess

    post = ROOT / "harness" / "hooks" / "agent-posttool.py"
    payload = {
        "tool_name": "apply_patch",
        "cwd": str(project),
        "session_id": "sess-1",
        "tool_input": {
            "path": str(target),
            "patch": "*** Begin Patch\n*** Update File: harness/hooks/x.py\n@@\n-print(1)\n+print(2)\n*** End Patch\n",
        },
    }
    proc = subprocess.run(
        [sys.executable, str(post)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(project),
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    paths = touched_paths(project)
    assert any(p.endswith("harness/hooks/x.py") for p in paths), paths


def test_bash_discard_dirty_deny_reason() -> None:
    assert bash_discard_dirty_deny_reason("git status") is None
    assert bash_discard_dirty_deny_reason("git restore --staged foo.py") is None
    assert bash_discard_dirty_deny_reason("git log -1") is None

    denied = [
        "git checkout -- harness/hooks/epic/core.py",
        "git checkout HEAD -- loop/gate_identity.py",
        "/bin/bash -lc 'git checkout -- a.py b.py'",
        "git restore loop/x.py",
        "git reset --hard",
        "git clean -fd",
        "echo hi && git restore --worktree foo.py",
    ]
    for cmd in denied:
        reason = bash_discard_dirty_deny_reason(cmd)
        assert reason and "git_discard_dirty_forbidden" in reason, cmd


def test_should_promote_foreign_dirty_fail_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    monkeypatch.setenv("DEV_HUB", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    reset_touch_ledger(project, epic_id="T-HUB-091", step_id="s04")

    from touch_ledger import should_promote_foreign_dirty_fail

    report = """
```json
{"schema":"loop-gate-verdict/v1","agent_id":"verify-implement","verdict":"FAIL","step_id":"s04","session_id":"x","epic_id":"T-HUB-091","recorded_at":"2026-09-10T00:00:00Z"}
```
AC+: PASS
VERIFY: PASS
STEP: PASS
BLOCKERS:
- `diff_outside_allow` — `git status` содержит изменения вне scope/ALLOW, включая harness/hooks/subagent-start.py
"""
    ok, notes = should_promote_foreign_dirty_fail(project, report)
    assert ok is True
    assert any("empty_touch_ledger" in n or "foreign_dirty_ignored" in n for n in notes)


def test_empty_ledger_promotes_scope_isolation_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    monkeypatch.setenv("DEV_HUB", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    reset_touch_ledger(project, epic_id="T-HUB-091", step_id="s03")

    from touch_ledger import should_promote_foreign_dirty_fail

    report = """
```json
{"schema":"loop-gate-verdict/v1","agent_id":"verify-implement","verdict":"FAIL","step_id":"s03","session_id":"x","epic_id":"T-HUB-091","recorded_at":"2026-09-10T00:00:00Z"}
```
AC+:
- PASS — Claude injection ok
AC−:
- FAIL — `subagent-stop.py` modifies Codex transport, outside S03 scope.
§0.11:
- FAIL — scope isolation violated by Codex changes.
VERIFY: PASS — 5 passed
BLOCKERS: `codex_transport_scope_violation` — restore deferred Codex behavior
"""
    ok, notes = should_promote_foreign_dirty_fail(project, report)
    assert ok is True, notes
    assert any("empty_touch_ledger" in n for n in notes)


def test_empty_ledger_does_not_promote_verify_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    monkeypatch.setenv("DEV_HUB", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    reset_touch_ledger(project, epic_id="T-HUB-091", step_id="s03")

    from touch_ledger import should_promote_foreign_dirty_fail

    report = """
AC+: PASS
AC−: FAIL — Codex transport outside scope
VERIFY: FAIL — 1 failed
BLOCKERS:
- codex_transport_scope_violation | harness/hooks/subagent-stop.py | restore
"""
    ok, notes = should_promote_foreign_dirty_fail(project, report)
    assert ok is False
    assert any("verify_fail" in n for n in notes)


def test_should_not_promote_when_other_blockers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    monkeypatch.setenv("DEV_HUB", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    reset_touch_ledger(project, epic_id="T-HUB-091", step_id="s04")

    from touch_ledger import should_promote_foreign_dirty_fail

    report = """
BLOCKERS:
- diff_outside_allow | harness/x.py | ignore
- silent_exception_drop | harness/hooks/_lib.py | remove bare except
"""
    ok, notes = should_promote_foreign_dirty_fail(project, report)
    assert ok is False
    assert any("other_blockers" in n for n in notes)


def test_empty_ledger_does_not_promote_pass_mentioning_transport_bind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PASS reports about transport_bind work must not look like scope FAILs."""
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    monkeypatch.setenv("DEV_HUB", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    reset_touch_ledger(project, epic_id="T-HUB-091", step_id="s05")

    from touch_ledger import should_promote_foreign_dirty_fail

    report = """
```json
{"schema":"loop-gate-verdict/v1","agent_id":"verify-implement","verdict":"PASS","step_id":"s05","session_id":"x","epic_id":"T-HUB-091","recorded_at":"2026-09-10T00:00:00Z"}
```
AC+:
- A3: PASS — `bind_fence(..., policy="transport_bind")`.
AC−:
- N3: PASS — `scope-check` успешен, `oos_ledger_paths=[]`.
VERIFY: PASS — 5 passed.
BLOCKERS: нет.
"""
    ok, notes = should_promote_foreign_dirty_fail(project, report)
    assert ok is False, notes


def test_repair_denies_foreign_dirty_blocker() -> None:
    from _lib import repair_blocker_violations

    prompt = """
BLOCKERS:
- diff_outside_allow | loop/x.py | ensure scoped

ALLOW WRITE:
- loop/x.py

VERIFY:
- bin/pytest -q
"""
    viol = repair_blocker_violations(prompt)
    assert any("foreign_dirty_not_repairable" in v for v in viol)


def test_agent_posttool_records_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    monkeypatch.setenv("DEV_HUB", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    target = project / "loop" / "x.py"
    target.parent.mkdir(parents=True)
    target.write_text("print(1)\n", encoding="utf-8")

    # Seed epic state identity for record_touch fallback
    from epic_paths import epic_dir

    epic = epic_dir(project)
    (epic / "state.json").write_text(
        json.dumps(
            {
                "armed_epic": "T-HUB-091-test",
                "armed_step": "s02",
                "phase_run_id": "abc",
            }
        ),
        encoding="utf-8",
    )

    import subprocess

    post = ROOT / "harness" / "hooks" / "agent-posttool.py"
    payload = {
        "tool_name": "Write",
        "cwd": str(project),
        "session_id": "sess-1",
        "tool_input": {
            "file_path": str(target),
            "content": "print(2)\n",
        },
    }
    proc = subprocess.run(
        [sys.executable, str(post)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(project),
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    paths = touched_paths(project)
    assert any(p.endswith("loop/x.py") for p in paths), paths
