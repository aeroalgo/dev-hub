from __future__ import annotations

from pathlib import Path

import yaml

from loop.board_sync.scan_gates import GateWorkItem, scan_gates
from loop.board_sync.workspaces import WorkspaceRef


def _project(tmp_path: Path, epic: str = "T-DEMO") -> tuple[Path, WorkspaceRef]:
    project = tmp_path / "project"
    (project / "memory-bank/back/plan").mkdir(parents=True)
    return project, WorkspaceRef(project, "demo")


def _index(project: Path, epic: str, statuses: list[str]) -> Path:
    path = project / f"memory-bank/back/plan/decompose-{epic}/index.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "schema": "epic-decompose-index/v1",
                "plan_id": epic,
                "steps": [
                    {"id": f"s{i:02d}", "title": "step", "status": status}
                    for i, status in enumerate(statuses, 1)
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _queue(project: Path, epic: str) -> None:
    (project / "memory-bank/back/plan/roadmap-epics.queue.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "roadmap-queue/v1",
                "role": "back",
                "roadmap": "memory-bank/back/plan/roadmap-epics.md",
                "queue": [{"id": epic, "plan": f"plan-{epic}.md", "deps": []}],
            }
        ),
        encoding="utf-8",
    )


def test_gate_analyze(tmp_path: Path) -> None:
    project, workspace = _project(tmp_path)
    _index(project, "T-DEMO", ["pending"])
    gates = scan_gates([workspace], [])

    assert any(
        gate.epic_id == "T-DEMO" and gate.gate_phase == "ANALYZE"
        for gate in gates
    )


def test_post_implement_lifecycle(monkeypatch, tmp_path: Path) -> None:
    project, workspace = _project(tmp_path)
    _index(project, "T-DEMO", ["completed"])
    calls: list[tuple[Path, str, str]] = []

    def reducer(cwd: Path, role: str, epic: str) -> dict[str, str]:
        calls.append((cwd, role, epic))
        return {"phase": "AUDIT", "reason_code": "audit_required"}

    monkeypatch.setattr("loop.board_sync.scan_gates.reduce_epic_lifecycle", reducer)
    gates = scan_gates([workspace], [])

    assert [(gate.epic_id, gate.gate_phase) for gate in gates] == [("T-DEMO", "AUDIT")]
    assert calls == [(project, "back", "T-DEMO")]


def test_done_emits_archive_all_signal(monkeypatch, tmp_path: Path) -> None:
    project, workspace = _project(tmp_path)
    _index(project, "T-DEMO", ["done"])
    monkeypatch.setattr(
        "loop.board_sync.scan_gates.reduce_epic_lifecycle",
        lambda *_: {"phase": "DONE", "reason_code": "reflection_completed"},
    )

    gates = scan_gates([workspace], [])

    assert [(gate.epic_id, gate.gate_phase, gate.archive_all) for gate in gates] == [
        ("T-DEMO", "DONE", True)
    ]


def test_qa_failed_uses_bugfix(monkeypatch, tmp_path: Path) -> None:
    project, workspace = _project(tmp_path)
    _index(project, "T-DEMO", ["done"])
    monkeypatch.setattr(
        "loop.board_sync.scan_gates.reduce_epic_lifecycle",
        lambda *_: {"phase": "QA", "reason_code": "qa_failed"},
    )

    gates = scan_gates([workspace], [])

    assert [(gate.epic_id, gate.gate_phase) for gate in gates] == [("T-DEMO", "BUGFIX")]


def test_no_gate_when_steps_active(monkeypatch, tmp_path: Path) -> None:
    project, workspace = _project(tmp_path)
    _index(project, "T-DEMO", ["pending"])
    monkeypatch.setattr(
        "loop.board_sync.scan_gates.reduce_epic_lifecycle",
        lambda *_: (_ for _ in ()).throw(AssertionError("reducer must not run")),
    )

    gates = scan_gates([workspace], [])

    assert not any(gate.epic_id == "T-DEMO" and gate.gate_phase in {"AUDIT", "QA", "BUGFIX", "REFLECT"} for gate in gates)


def test_exactly_one_gate_qa(monkeypatch, tmp_path: Path) -> None:
    project, workspace = _project(tmp_path)
    _index(project, "T-DEMO", ["completed", "done"])
    monkeypatch.setattr(
        "loop.board_sync.scan_gates.reduce_epic_lifecycle",
        lambda *_: {"phase": "QA", "reason_code": "qa_required"},
    )

    gates = scan_gates([workspace], [])

    assert sum(gate.epic_id == "T-DEMO" and gate.gate_phase == "QA" for gate in gates) == 1
    assert all(isinstance(gate, GateWorkItem) for gate in gates)


def test_roadmap_invalid_queue_diagnostic(monkeypatch, tmp_path: Path) -> None:
    project, workspace = _project(tmp_path)
    monkeypatch.setattr(
        "loop.board_sync.scan_gates.reduce_epic_lifecycle",
        lambda *_: {"phase": "ROADMAP", "reason_code": "roadmap_required"},
    )
    monkeypatch.setattr(
        "roadmap_queue.select_next_epic",
        lambda *_: {"ok": False, "error": "queue_yaml_missing"},
    )

    gates = scan_gates([workspace], [])

    assert gates == []
    assert gates.errors == [f"{project}: roadmap selection failed: queue_yaml_missing"]


def test_roadmap_valid_selection_is_side_effect_free(monkeypatch, tmp_path: Path) -> None:
    _, workspace = _project(tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(
        "roadmap_queue.select_next_epic",
        lambda *_: {"ok": True, "entry": {"epic": "T-NEXT"}},
    )
    monkeypatch.setattr("roadmap_queue.arm_roadmap_entry", lambda *_: calls.append("arm"))

    gates = scan_gates([workspace], [])

    assert [(gate.gate_phase, gate.reason_code) for gate in gates] == [("ROADMAP", "T-NEXT")]
    assert gates.errors == []
    assert calls == []
