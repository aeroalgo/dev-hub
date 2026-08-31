from pathlib import Path
import pytest
from loop.dag import _arm_dag_next, dag_advance_epic
from loop.board_sync.epic_resolver import EpicNextAction


def test_dag_arm_dag_next_calls_resolve_and_arm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    resolved_action = EpicNextAction(
        epic_id="T-HUB-029",
        role="back",
        next_command="implement",
        phase="IMPLEMENT",
    )
    called_resolve = {}
    called_arm = {}

    def mock_resolve_next(cwd: Path | str, epic_id: str, role: str) -> EpicNextAction:
        called_resolve["cwd"] = cwd
        called_resolve["epic_id"] = epic_id
        called_resolve["role"] = role
        return resolved_action

    def mock_arm_phase(cwd: Path | str, epic_id: str, phase: str, role: str, **kwargs) -> dict:
        called_arm["cwd"] = cwd
        called_arm["epic_id"] = epic_id
        called_arm["phase"] = phase
        called_arm["role"] = role
        called_arm["kwargs"] = kwargs
        return {"ok": True, "armed_epic": epic_id, "phase": phase}

    import loop.epic_transition as et
    monkeypatch.setattr(et, "resolve_next", mock_resolve_next)
    monkeypatch.setattr(et, "arm_phase", mock_arm_phase)

    res = _arm_dag_next(tmp_path, "T-HUB-029", "back")

    assert called_resolve == {"cwd": tmp_path, "epic_id": "T-HUB-029", "role": "back"}
    assert called_arm["cwd"] == tmp_path
    assert called_arm["epic_id"] == "T-HUB-029"
    assert called_arm["phase"] == "IMPLEMENT"
    assert called_arm["role"] == "back"
    assert res == {"ok": True, "armed_epic": "T-HUB-029", "phase": "IMPLEMENT"}


def test_dag_arm_dag_next_analyze_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    resolved_action = EpicNextAction(
        epic_id="T-HUB-029",
        role="back",
        next_command="analyze",
        phase="ANALYZE",
    )
    called_arm = {}

    def mock_resolve_next(cwd: Path | str, epic_id: str, role: str) -> EpicNextAction:
        return resolved_action

    def mock_arm_phase(cwd: Path | str, epic_id: str, phase: str, role: str, **kwargs) -> dict:
        called_arm["phase"] = phase
        return {"ok": True, "armed_epic": epic_id, "phase": phase}

    import loop.epic_transition as et
    monkeypatch.setattr(et, "resolve_next", mock_resolve_next)
    monkeypatch.setattr(et, "arm_phase", mock_arm_phase)

    res = _arm_dag_next(tmp_path, "T-HUB-029", "back")

    assert called_arm["phase"] == "ANALYZE"
    assert res.get("ok") is True


def test_dag_arm_dag_next_fail_closed_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    resolved_action = EpicNextAction(
        epic_id="T-HUB-029",
        role="back",
        next_command="unknown_command",
        phase="INVALID_PHASE",
    )

    def mock_resolve_next(cwd: Path | str, epic_id: str, role: str) -> EpicNextAction:
        return resolved_action

    import loop.epic_transition as et
    monkeypatch.setattr(et, "resolve_next", mock_resolve_next)

    with pytest.raises(ValueError, match="unknown phase"):
        _arm_dag_next(tmp_path, "T-HUB-029", "back")


def test_dag_advance_epic_wrapper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    called = {}

    def mock_arm_dag_next(cwd: Path | str, epic_id: str, role: str) -> dict:
        called["args"] = (cwd, epic_id, role)
        return {"ok": True}

    import loop.dag as dag_mod
    monkeypatch.setattr(dag_mod, "_arm_dag_next", mock_arm_dag_next)

    res = dag_advance_epic(tmp_path, "T-HUB-029", "back")
    assert called["args"] == (tmp_path, "T-HUB-029", "back")
    assert res == {"ok": True}
