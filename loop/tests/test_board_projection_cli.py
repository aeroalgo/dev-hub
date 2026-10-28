from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any
import pytest
import yaml

from loop.board_projection.mapping import (
    BoardEpicMap,
    EpicMapEntry,
    load_board_epic_map,
    save_board_epic_map,
)
from loop.board_projection.protocol import BoardProjectionAdapter, EpicRef
from loop.kernel.cli import main
from loop.kernel.engine import LoopEngine
from loop.kernel.model import CursorStatus
from loop.kernel.session import SessionOutcome, SessionRun
from loop.kernel.store import CursorStore, LoopPaths
from loop.kernel.verdict import GateVerdict, SCHEMA_GATE_VERDICT


class MockAdapter(BoardProjectionAdapter):
    def __init__(self, provider: str = "plane") -> None:
        self._provider = provider
        self.created: list[EpicRef] = []
        self.moved: list[tuple[str, str]] = []

    @property
    def provider_name(self) -> str:
        return self._provider

    def ensure_card(self, epic: EpicRef) -> str:
        self.created.append(epic)
        return f"ext-{epic.epic_id}"

    def move_card(self, external_id: str, phase: str) -> None:
        self.moved.append((external_id, phase))


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _seed_project(root: Path, epic_id: str = "E1") -> LoopPaths:
    _write(root / f"memory-bank/back/plan/{epic_id}/yaml/decompose-index.yaml", f"""
schema: epic-decompose-index/v1
epic_id: {epic_id}
steps:
  - id: s01
    file: s01-one.yaml
    status: pending
  - id: s02
    file: s02-two.yaml
    status: pending
""")
    _write(root / f"memory-bank/back/plan/{epic_id}/yaml/s01-one.yaml", "step_id: s01\n")
    _write(root / f"memory-bank/back/plan/{epic_id}/yaml/s02-two.yaml", "step_id: s02\n")

    impl_yaml = f"""schema: epic-implement/v1
role: back
step_id: s01
plan_id: {epic_id}
status: in_progress
done:
  - seeded evidence
files: []
deletes: []
tests: []
integration_check: []
checkpoints:
  - id: cp1
    criterion: seeded
    status: in_progress
"""
    _write(root / f"memory-bank/back/implement/{epic_id}/s01-one.yaml", impl_yaml)
    _write(root / f"memory-bank/back/implement/{epic_id}/s02-two.yaml", impl_yaml.replace("s01", "s02"))
    _write(
        root / f"memory-bank/back/analyze/{epic_id}/analyze-20260921-pass.yaml",
        "schema: epic-analyze/v1\nstatus: complete\nmetrics:\n  critical_count: 0\n",
    )
    return LoopPaths.for_project(root)


def _write_projection_config(root: Path, provider: str = "plane") -> None:
    cfg = {
        "schema": "loop-board-projection/v1",
        "provider": provider,
        "role_allowlist": ["back"],
        "phase_alias": {
            "QUEUED": "backlog",
            "PLAN": "design",
            "IMPLEMENT": "build",
            "QA": "verify",
            "DONE": "done",
            "HALT": "blocked",
        },
        "providers": {
            "bitrix24": {
                "webhook_url": "https://bx.example.com/rest/1/webhook",
                "group_id": 42,
                "responsible_id": 1,
                "stage_map": {"backlog": "1", "design": "2", "build": "3", "verify": "4", "done": "5", "blocked": "6"},
            },
            "plane": {
                "base_url": "https://plane.example.com",
                "api_key": "plane-key-123",
                "workspace_slug": "ws-demo",
                "project_id": "proj-999",
                "state_map": {"backlog": "s-1", "design": "s-2", "build": "s-3", "verify": "s-4", "done": "s-5", "blocked": "s-6"},
            },
        },
    }
    _write(root / ".loop" / "board-projection.yaml", yaml.safe_dump(cfg))


def test_cli_no_direct_vendor_imports():
    """Verify that loop/kernel/cli.py does not import vendor modules directly (AC-7, TM-009)."""
    cli_path = Path("loop/kernel/cli.py")
    tree = ast.parse(cli_path.read_text(encoding="utf-8"))
    forbidden_modules = {
        "loop.board_projection.adapters.bitrix24",
        "loop.board_projection.adapters.plane",
        "bitrix24",
        "plane",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for forbidden in forbidden_modules:
                    assert forbidden not in alias.name, f"Forbidden direct vendor import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for forbidden in forbidden_modules:
                assert forbidden not in mod, f"Forbidden direct vendor from-import: {mod}"


def test_cli_finish_halt_wire(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """finish and halt trigger project_after_transition without breaking on error (FR-004, AC-7, TM-009)."""
    paths = _seed_project(tmp_path, epic_id="E1")
    engine = LoopEngine(paths)
    engine.start("E1")

    cursor = engine.store.read()
    assert cursor is not None
    assert cursor.phase == "IMPLEMENT"
    assert cursor.step_id == "s01"

    # Bypass gate check for CLI finish command test
    monkeypatch.setattr(LoopEngine, "_require_gate_pass", lambda *args, **kwargs: None)

    calls = []

    def mock_project_after_transition(**kwargs: Any):
        calls.append(kwargs)
        if kwargs.get("phase") == "HALT":
            raise RuntimeError("simulated projection network error during halt")

    monkeypatch.setattr("loop.kernel.cli.project_after_transition", mock_project_after_transition)

    # 1. Test finish command wires projection
    rc = main(["finish", "--project", str(tmp_path), "--step", "s01", "--json"])
    assert rc == 0
    assert len(calls) == 1
    call = calls[0]
    assert call["epic_id"] == "E1"
    assert call["role"] == "back"
    # Transition moved to next step s02 in IMPLEMENT
    assert call["phase"] == "IMPLEMENT"

    # 2. Test halt command wires projection and soft-fails gracefully even if projection raises
    rc_halt = main(["halt", "--project", str(tmp_path), "--reason", "blocked on external dep", "--json"])
    assert rc_halt == 0
    assert len(calls) == 2
    halt_call = calls[1]
    assert halt_call["epic_id"] == "E1"
    assert halt_call["phase"] == "HALT"

    # Verify cursor state was successfully updated to HALTED despite projection error
    cur_halted = engine.store.read()
    assert cur_halted is not None
    assert cur_halted.status == CursorStatus.HALTED


def test_cli_start_projects_initial_phase(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Starting an epic after PLAN mirrors DECOMPOSE (the design column)."""
    _write(tmp_path / "memory-bank/back/plan/E2/md/plan.md", "# plan\n")
    calls: list[dict[str, Any]] = []

    def capture(**kwargs: Any):
        calls.append(kwargs)

    monkeypatch.setattr("loop.kernel.cli.project_after_transition", capture)

    rc = main(["start", "--project", str(tmp_path), "--epic", "E2", "--json"])

    assert rc == 0
    assert calls[0]["phase"] == "DECOMPOSE"
    assert calls[0]["role"] == "back"


def test_cli_run_projects_auto_committed_transition(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The normal run path mirrors transitions committed by SessionSupervisor."""
    _seed_project(tmp_path, epic_id="E1")
    monkeypatch.setattr(LoopEngine, "_require_gate_pass", lambda *args, **kwargs: None)
    monkeypatch.setattr("loop.kernel.cli.activate_loop_process", lambda **kwargs: None)

    calls: list[dict[str, Any]] = []

    def capture(**kwargs: Any):
        calls.append(kwargs)

    monkeypatch.setattr("loop.kernel.cli.project_after_transition", capture)
    monkeypatch.setattr("loop.kernel.cli.runtime_for", lambda *args, **kwargs: object())

    class FakeSupervisor:
        def __init__(self, engine, runtime, **kwargs: Any):
            self.engine = engine

        def run_step(self, prompt: str, *, model: str, project, session_id: str | None = None):
            transition = self.engine.finish(step_id="s01")
            return SessionRun(SessionOutcome.COMMITTED, None, transition, "done", 0)

    monkeypatch.setattr("loop.kernel.cli.SessionSupervisor", FakeSupervisor)

    rc = main(
        [
            "run",
            "--project",
            str(tmp_path),
            "--epic",
            "E1",
            "--model",
            "test-model",
            "--max-steps",
            "1",
            "--json",
        ]
    )

    assert rc == 0
    assert [call["phase"] for call in calls] == ["IMPLEMENT", "IMPLEMENT"]


def test_cli_board_sync_uses_plan_phase_without_cursor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Manual catch-up after PLAN starts the card in design, not backlog."""
    _write(tmp_path / "memory-bank/back/plan/E2/md/plan.md", "# plan\n")
    _write_projection_config(tmp_path, provider="plane")
    fake_adapter = MockAdapter(provider="plane")
    monkeypatch.setattr("loop.board_projection.service.get_adapter", lambda cfg: fake_adapter)

    rc = main(["board-sync", "--project", str(tmp_path), "--epic", "E2", "--json"])

    assert rc == 0
    assert len(fake_adapter.created) == 1
    assert fake_adapter.created[0].phase == "PLAN"


def test_cli_finish_without_config_no_http(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    """finish without config succeeds with explicit disabled status and zero HTTP (AC-5, SC-002, TM-001)."""
    paths = _seed_project(tmp_path, epic_id="E1")
    engine = LoopEngine(paths)
    engine.start("E1")

    # Bypass gate check for CLI finish test
    monkeypatch.setattr(LoopEngine, "_require_gate_pass", lambda *args, **kwargs: None)

    # Ensure no config file exists
    cfg_file = tmp_path / ".loop" / "board-projection.yaml"
    assert not cfg_file.exists()

    # Track if any adapter or http call was attempted
    import httpx
    monkeypatch.setattr(httpx, "Client", lambda *args, **kwargs: pytest.fail("HTTP call attempted when config missing!"))

    rc = main(["finish", "--project", str(tmp_path), "--step", "s01", "--json"])
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["projection_status"] == "disabled"
    assert payload["projection_disabled_reason"] == "missing_config"


def test_cli_halt_without_config_exposes_disabled_reason(tmp_path: Path, capsys: pytest.CaptureFixture):
    """halt without config exposes explicit disabled reason in output."""
    paths = _seed_project(tmp_path, epic_id="E1")
    engine = LoopEngine(paths)
    engine.start("E1")

    rc = main(["halt", "--project", str(tmp_path), "--reason", "blocked", "--json"])
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["projection_status"] == "disabled"
    assert payload["projection_disabled_reason"] == "missing_config" 


def test_cli_board_sync(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """board-sync subcommand performs projection catch-up and clears sync_error (FR-012, TM-008)."""
    paths = _seed_project(tmp_path, epic_id="E1")
    engine = LoopEngine(paths)
    engine.start("E1")

    _write_projection_config(tmp_path, provider="plane")
    map_path = tmp_path / ".loop" / "board-epic-map.yaml"

    # Seed map with existing error
    initial_map = BoardEpicMap(
        provider="plane",
        epics={
            "E1": EpicMapEntry(
                external_id="ext-E1",
                last_phase="PLAN",
                sync_error="Network timeout: Connection refused",
            )
        },
    )
    save_board_epic_map(initial_map, map_path)

    fake_adapter = MockAdapter(provider="plane")

    monkeypatch.setattr("loop.board_projection.service.get_adapter", lambda cfg: fake_adapter)

    # Run board-sync with explicit --epic
    rc = main(["board-sync", "--project", str(tmp_path), "--epic", "E1", "--json"])
    assert rc == 0

    # Verify fake_adapter moved card
    assert len(fake_adapter.moved) == 1
    assert fake_adapter.moved[0][0] == "ext-E1"

    # Verify sync_error was cleared in the sidecar mapping
    reloaded_map = load_board_epic_map(map_path)
    entry = reloaded_map.epics.get("E1")
    assert entry is not None
    assert entry.sync_error is None
