from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from loop.kernel.engine import LoopEngine, TransitionError
from loop.kernel.lifecycle import SubagentLifecycle
from loop.kernel.model import CursorStatus, RuntimeResult
from loop.kernel.runtime import CodexRuntime, Runtime
from loop.kernel.session import SessionOutcome, SessionSupervisor
from loop.kernel.store import CursorStore, LoopPaths
from loop.kernel.verdict import BoundaryIdentity, SCHEMA_GATE_VERDICT, SCHEMA_REPAIR_RESULT, validate_boundary, validate_message


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def seed_project(root: Path) -> LoopPaths:
    write(root / "memory-bank/back/plan/E1/yaml/decompose-index.yaml", """
schema: epic-decompose-index/v1
epic_id: E1
steps:
  - id: s01
    file: s01-one.yaml
    status: pending
  - id: s02
    file: s02-two.yaml
    status: pending
""")
    write(root / "memory-bank/back/plan/E1/yaml/s01-one.yaml", "step_id: s01\n")
    write(root / "memory-bank/back/plan/E1/yaml/s02-two.yaml", "step_id: s02\n")
    return LoopPaths(project=root, hub=root / "hub")


def test_cursor_is_the_only_runtime_state_and_finish_advances_index(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)

    cursor = engine.start("E1")
    assert cursor.phase == "IMPLEMENT"
    assert cursor.step_id == "s01"
    assert paths.cursor.is_file()
    assert not (paths.runtime / "state.json").exists()
    assert not (paths.runtime / "checkpoint.json").exists()
    assert not (paths.runtime / "last-session.json").exists()

    transition = engine.finish(step_id="s01")
    assert transition.phase == "IMPLEMENT"
    assert transition.step_id == "s02"
    index = (tmp_path / "memory-bank/back/plan/E1/yaml/decompose-index.yaml").read_text()
    assert "id: s01" in index and "status: completed" in index


def test_lifecycle_has_one_transition_path(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    engine.finish(step_id="s01")
    engine.finish(step_id="s02")
    assert engine.store.read().phase == "AUDIT"

    write(tmp_path / "memory-bank/back/audit/E1/audit.yaml", "schema: audit\nverdict: pass\n")
    engine.finish(step_id="AUDIT")
    assert engine.store.read().phase == "QA"

    write(tmp_path / "memory-bank/back/qa/E1/qa.yaml", "schema: qa\nverdict: fail\n")
    engine.finish(step_id="QA")
    assert engine.store.read().phase == "BUGFIX"

    write(tmp_path / "memory-bank/back/bugfix/E1/fix.yaml", "schema: bugfix\nstatus: completed\n")
    engine.finish(step_id="BUGFIX")
    assert engine.store.read().phase == "QA"

    write(tmp_path / "memory-bank/back/qa/E1/qa.yaml", "schema: qa\nverdict: pass\n")
    engine.finish(step_id="QA")
    assert engine.store.read().status == CursorStatus.COMPLETE


def test_retry_is_bounded_by_one_counter(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    first = engine.retry("runtime_exit_1")
    second = engine.retry("runtime_exit_2")
    assert first.attempt == 1
    assert second.attempt == 2
    payload = json.loads(paths.cursor.read_text(encoding="utf-8"))
    assert set(payload) == {
        "schema",
        "revision",
        "epic_id",
        "role",
        "phase",
        "step_id",
        "phase_epoch",
        "status",
        "attempt",
        "session_id",
        "failure",
        "updated_at",
    }


def test_session_supervisor_commits_failure_and_halt_atomically(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")

    class FailingRuntime:
        def run(self, prompt, *, model, project, log_path, timeout):
            return RuntimeResult("test", 17, log_path, message="runtime failed")

    run = SessionSupervisor(engine, FailingRuntime(), timeout=1, max_attempts=1, backoff=0).run_step(
        "work", model="test", project=tmp_path, session_id="session-1"
    )

    assert run.outcome == SessionOutcome.RUNTIME_FAILURE
    assert run.transition is not None
    cursor = engine.store.read()
    assert cursor is not None
    assert cursor.status == CursorStatus.HALTED
    assert cursor.failure is not None
    assert cursor.failure.category == "session"
    assert cursor.failure.code == "retry_exhausted"
    assert cursor.failure.details["exit_code"] == 17


def test_phase_finish_requires_evidence_and_halt_is_terminal(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    engine.finish(step_id="s01")
    engine.finish(step_id="s02")

    with pytest.raises(TransitionError, match="audit artifact"):
        engine.finish(step_id="AUDIT")

    halted = engine.halt("manual stop")
    assert halted.status == CursorStatus.HALTED
    with pytest.raises(TransitionError, match="halted"):
        engine.finish(step_id="AUDIT")


def test_cursor_transaction_recovers_after_projection_write_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    original = CursorStore._write_cursor_unlocked
    failed = False

    def fail_once(store: CursorStore, cursor) -> None:
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("simulated cursor projection failure")
        original(store, cursor)

    monkeypatch.setattr(CursorStore, "_write_cursor_unlocked", fail_once)
    with pytest.raises(OSError, match="simulated cursor"):
        engine.start("E1")

    monkeypatch.setattr(CursorStore, "_write_cursor_unlocked", original)
    recovered = engine.store.read()
    assert recovered is not None
    assert recovered.epic_id == "E1"
    assert recovered.step_id == "s01"
    records = paths.events.read_text(encoding="utf-8").splitlines()
    assert sum('"record_type": "commit"' in line for line in records) == 1
    assert engine.store.read().revision == recovered.revision


def test_journal_recovers_an_incomplete_trailing_record(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    with paths.events.open("ab") as handle:
        handle.write(b'{"schema":"loop-journal/v1"')

    recovered = engine.store.read()
    assert recovered is not None
    engine.record_event({"event": "after_partial_journal"})
    records = [json.loads(line) for line in paths.events.read_text(encoding="utf-8").splitlines()]
    assert records[-1]["event"] == "after_partial_journal"


def test_legacy_cursor_schema_is_not_used_as_runtime_state(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    paths.runtime.mkdir(parents=True, exist_ok=True)
    paths.cursor.write_text(json.dumps({"schema": "loop-cursor/v1", "epic_id": "E1"}), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported cursor schema"):
        LoopEngine(paths).status()


def test_legacy_cursor_failure_field_is_not_used_as_runtime_state(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    paths.runtime.mkdir(parents=True, exist_ok=True)
    paths.cursor.write_text(json.dumps({"schema": "loop-state/v2", "last_error": "old failure"}), encoding="utf-8")

    with pytest.raises(ValueError, match="legacy cursor field last_error"):
        LoopEngine(paths).status()


def test_finish_recovers_index_and_context_from_prepared_transaction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    original = CursorStore._write_cursor_unlocked

    def fail_projection(_store: CursorStore, _cursor) -> None:
        raise OSError("simulated finish projection failure")

    monkeypatch.setattr(CursorStore, "_write_cursor_unlocked", fail_projection)
    with pytest.raises(OSError, match="simulated finish"):
        engine.finish(step_id="s01")

    monkeypatch.setattr(CursorStore, "_write_cursor_unlocked", original)
    recovered = engine.store.read()
    assert recovered is not None
    assert recovered.step_id == "s02"
    index = (tmp_path / "memory-bank/back/plan/E1/yaml/decompose-index.yaml").read_text(encoding="utf-8")
    assert "status: completed" in index
    assert "step_id: s02" in paths.active_context.read_text(encoding="utf-8")


def _verdict_message(cursor, *, agent_id: str = "verify-implement", verdict: str = "PASS") -> str:
    payload = {
        "schema": SCHEMA_GATE_VERDICT,
        "agent_id": agent_id,
        "verdict": verdict,
        "step_id": cursor.step_id,
        "session_id": cursor.session_id,
        "epic_id": cursor.epic_id,
        "recorded_at": "2026-09-18T19:00:00+00:00",
    }
    return "```json\n" + json.dumps(payload) + "\n```"


def test_gate_verdict_is_strict_and_identity_bound(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    identity = BoundaryIdentity(cursor.session_id, cursor.epic_id, cursor.step_id, "verify-implement")

    valid = validate_message(_verdict_message(cursor), identity=identity)
    assert valid.valid and valid.record is not None
    assert valid.record.agent_id == "verify-implement"

    wrong_step = _verdict_message(cursor).replace('"step_id": "s01"', '"step_id": "s02"')
    rejected = validate_message(wrong_step, identity=identity)
    assert not rejected.valid
    assert "verdict_wrong_step_id" in rejected.diagnostic_codes

    extra = json.loads(_verdict_message(cursor).split("\n", 2)[1])
    extra["reason"] = "human text is not part of the wire contract"
    rejected_extra = validate_boundary(SCHEMA_GATE_VERDICT, extra, identity=identity)
    assert not rejected_extra.valid
    assert any(code.startswith("schema_") for code in rejected_extra.diagnostic_codes)


def test_subagent_pass_finishes_once_and_duplicate_is_idempotent(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    lifecycle = SubagentLifecycle(paths)
    payload = {
        "cwd": str(tmp_path),
        "agent_type": "verify-implement",
        "last_assistant_message": _verdict_message(cursor),
    }

    accepted = lifecycle.stop(payload)
    assert accepted.ok
    assert accepted.transition["reason"] == "subagent-stop:verify-implement:PASS"
    assert engine.store.read().step_id == "s02"

    duplicate = lifecycle.stop(payload)
    assert duplicate.ok
    assert duplicate.transition["event"] == "verdict_duplicate"
    assert engine.store.read().step_id == "s02"


def test_subagent_fail_or_blocked_is_recorded_without_finishing(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    lifecycle = SubagentLifecycle(paths)

    for verdict in ("FAIL", "BLOCKED"):
        action = lifecycle.stop(
            {
                "cwd": str(tmp_path),
                "agent_type": "verify-implement",
                "last_assistant_message": _verdict_message(cursor, verdict=verdict),
            }
        )
        assert action.ok
        assert action.transition["event"] == "verdict_recorded"
        assert action.transition["reason"] == verdict
        assert engine.store.read().step_id == "s01"

    events = paths.events.read_text(encoding="utf-8")
    assert events.count('"event": "verdict_recorded"') == 2


def test_subagent_invalid_verdict_has_atomic_retry_budget(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    lifecycle = SubagentLifecycle(paths)
    payload = {"cwd": str(tmp_path), "agent_type": "verify-implement", "last_assistant_message": "no json"}

    first = lifecycle.stop(payload)
    second = lifecycle.stop(payload)
    third = lifecycle.stop(payload)
    assert first.exit_code == second.exit_code == third.exit_code == 2
    assert "retry 1/2" in first.reason
    assert "retry 2/2" in second.reason
    assert third.reason == "schema_retry_exhausted:verify-implement"
    assert engine.store.read().status == CursorStatus.HALTED
    events = paths.events.read_text(encoding="utf-8")
    assert events.count('"event": "verdict_rejected"') == 3
    assert '"event": "halt"' in events


def test_subagent_stop_hook_accepts_pydantic_verdict(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    environment = os.environ.copy()
    environment.update(
        {
            "LOOP_ACTIVE": "1",
            "EPIC_LOOP": "1",
            "LOOP_WORKFLOW_HOOKS": "loop",
            "PROJECT_ROOT": str(tmp_path),
            "DEV_HUB": str(paths.hub),
        }
    )
    payload = {
        "cwd": str(tmp_path),
        "agent_type": "verify-implement",
        "last_assistant_message": _verdict_message(cursor),
    }
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parents[2] / "harness/hooks/subagent-stop.py")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    hook_payload = json.loads(result.stdout)
    assert hook_payload["ok"] is True
    assert hook_payload["transition"]["reason"] == "subagent-stop:verify-implement:PASS"
    assert engine.store.read().step_id == "s02"


def test_subagent_start_hook_injects_cursor_identity(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    environment = os.environ.copy()
    environment.update(
        {
            "LOOP_ACTIVE": "1",
            "EPIC_LOOP": "1",
            "LOOP_WORKFLOW_HOOKS": "loop",
            "PROJECT_ROOT": str(tmp_path),
            "DEV_HUB": str(paths.hub),
        }
    )
    payload = {
        "cwd": str(tmp_path),
        "agent_type": "verify-implement",
        "prompt": "check the implementation and return the gate verdict",
    }
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parents[2] / "harness/hooks/subagent-start.py")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    hook_payload = json.loads(result.stdout)
    context = hook_payload["hookSpecificOutput"]["additionalContext"]
    assert f"GATE_IDENTITY session_id={cursor.session_id} epic_id=E1 step_id=s01" in context
    assert "validate-verdict" in context


def test_native_validator_command_validates_gate_payload(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    message = _verdict_message(cursor)
    payload = json.loads(message.split("\n", 2)[1])
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parents[2] / "bin/loop.py"),
            "validate-verdict",
            "--project",
            str(tmp_path),
            "--payload",
            json.dumps(payload),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["valid"] is True


def test_native_validator_accepts_repair_result_schema(tmp_path: Path) -> None:
    seed_project(tmp_path)
    payload = {
        "schema": SCHEMA_REPAIR_RESULT,
        "agent_id": "gate-repair",
        "parent_evidence_id": "evidence-1",
        "status": "partial",
        "fixed_blockers": ["scope"],
        "remaining_blockers": ["tests"],
        "recorded_at": "2026-09-18T19:00:00+00:00",
    }
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parents[2] / "bin/loop.py"),
            "validate",
            "--project",
            str(tmp_path),
            "--schema",
            SCHEMA_REPAIR_RESULT,
            "--payload",
            json.dumps(payload),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["valid"] is True


def test_codex_uses_omniroute_wrapper_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wrapper = tmp_path / "codex" / "bin" / "codex-omniroute.sh"
    write(wrapper, "#!/usr/bin/env bash\n")
    wrapper.chmod(0o755)
    monkeypatch.delenv("CODEX_BIN", raising=False)
    monkeypatch.setenv("CODEX_USE_OMNIROUTE", "1")
    monkeypatch.setenv("DEV_HUB", str(tmp_path))

    assert CodexRuntime().executable() == str(wrapper)


def test_codex_can_explicitly_disable_omniroute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODEX_BIN", raising=False)
    monkeypatch.setenv("CODEX_USE_OMNIROUTE", "0")
    assert CodexRuntime().executable() == shutil.which("codex")


def test_runtime_streams_output_before_child_exits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class TestRuntime(Runtime):
        name = "test"

        def executable(self) -> str:
            return sys.executable

        def command(self, prompt: str, *, model: str, project: Path) -> list[str]:
            script = (
                "from pathlib import Path\n"
                "import time\n"
                "print('runtime-start', flush=True)\n"
                "while not Path('release').exists(): time.sleep(0.01)\n"
                "print('runtime-end', flush=True)\n"
            )
            return [sys.executable, "-u", "-c", script]

    class Capture:
        def __init__(self) -> None:
            self.parts: list[str] = []
            self.started = threading.Event()

        def write(self, value: str) -> int:
            self.parts.append(value)
            if "runtime-start" in value:
                self.started.set()
            return len(value)

        def flush(self) -> None:
            return None

    capture = Capture()
    monkeypatch.setattr(sys, "stdout", capture)
    result: list[object] = []
    thread = threading.Thread(
        target=lambda: result.append(
            TestRuntime().run(
                "prompt",
                model="model",
                project=tmp_path,
                log_path=tmp_path / "session.log",
                timeout=5,
            )
        ),
        daemon=True,
    )
    thread.start()
    streamed = capture.started.wait(timeout=1)
    (tmp_path / "release").write_text("release\n", encoding="utf-8")
    thread.join(timeout=3)

    assert streamed
    assert not thread.is_alive()
    assert result and result[0].exit_code == 0
    log = (tmp_path / "session.log").read_text(encoding="utf-8")
    assert "runtime-start" in log
    assert "runtime-end" in log
