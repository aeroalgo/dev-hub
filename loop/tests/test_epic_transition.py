"""Contract tests for loop.epic_transition — resolve_next delegate + stub guards."""
from __future__ import annotations
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# test_resolve_next_delegates_to_resolver
# ---------------------------------------------------------------------------
def test_resolve_next_delegates_to_resolver(tmp_path):
    from loop.epic_transition import resolve_next  # noqa: PLC0415
    from loop.board_sync.epic_resolver import EpicNextAction  # noqa: PLC0415

    expected = EpicNextAction(
        epic_id="T-TEST-001",
        role="back",
        next_command="BACK IMPLEMENT",
        phase="IMPLEMENT",
    )

    with patch(
        "loop.epic_transition.resolve_epic_next_action",
        return_value=expected,
    ) as mock:
        result = resolve_next(tmp_path, "T-TEST-001", "back")

    mock.assert_called_once_with(tmp_path, "back", "T-TEST-001")
    assert result is expected


# ---------------------------------------------------------------------------
# test_arm_phase_decompose
# ---------------------------------------------------------------------------
def test_arm_phase_decompose(tmp_path):
    from loop.epic_transition import arm_phase  # noqa: PLC0415

    expected = {"ok": True, "armed_step": "s01", "active_context": "memory-bank/activeContext.md"}

    with patch(
        "epic.core.arm_active_context_from_decompose",
        return_value=expected,
    ) as mock:
        res = arm_phase(tmp_path, "T-TEST-001", "DECOMPOSE", "back", decompose_rel="memory-bank/back/plan/decompose-T-TEST-001")

    assert res["ok"] is True
    assert res["armed_step"] == "s01"
    assert res["handoff"] == "memory-bank/activeContext.md"
    assert res["role"] == "back"


# ---------------------------------------------------------------------------
# test_arm_phase_analyze
# ---------------------------------------------------------------------------
def test_arm_phase_analyze(tmp_path):
    from loop.epic_transition import arm_phase  # noqa: PLC0415

    expected = {"ok": True, "step_id": "ANALYZE", "active_context": "memory-bank/activeContext.md"}

    with patch(
        "epic.core.arm_pre_implement_context",
        return_value=expected,
    ) as mock:
        res = arm_phase(tmp_path, "T-TEST-001", "ANALYZE", "back")

    assert res["ok"] is True
    assert res["armed_step"] == "ANALYZE"
    assert res["handoff"] == "memory-bank/activeContext.md"


# ---------------------------------------------------------------------------
# test_arm_phase_implement
# ---------------------------------------------------------------------------
def test_arm_phase_implement(tmp_path):
    from loop.epic_transition import arm_phase  # noqa: PLC0415

    expected = {"ok": True, "step_id": "s01", "active_context": "memory-bank/activeContext.md"}

    with patch(
        "epic.core.arm_active_context_from_decompose",
        return_value=expected,
    ) as mock:
        res = arm_phase(tmp_path, "T-TEST-001", "IMPLEMENT", "back", decompose_rel="memory-bank/back/plan/decompose-T-TEST-001/index.yaml")

    assert res["ok"] is True
    assert res["armed_step"] == "s01"


# ---------------------------------------------------------------------------
# test_arm_phase_unknown_falls_back_to_arm_epic
# ---------------------------------------------------------------------------
def test_arm_phase_unknown_falls_back_to_arm_epic(tmp_path):
    from loop.epic_transition import arm_phase  # noqa: PLC0415

    expected = {"ok": True, "step_id": "UNKNOWN", "active_context": "memory-bank/activeContext.md"}

    with patch(
        "epic.core.arm_epic",
        return_value=expected,
    ) as mock:
        res = arm_phase(tmp_path, "T-TEST-001", "UNKNOWN_PHASE", "back")

    mock.assert_called_once()
    assert res["ok"] is True


# ---------------------------------------------------------------------------
# test_arm_phase_deprecation_warn_from_legacy
# ---------------------------------------------------------------------------
def test_arm_phase_deprecation_warn_from_legacy(tmp_path):
    import sys
    hooks_path = str(ROOT / ".claude" / "hooks")
    if hooks_path not in sys.path:
        sys.path.insert(0, hooks_path)
    from epic.core import arm_active_context_from_decompose  # noqa: PLC0415

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        # Call with invalid args so it fails fast after issuing warning
        arm_active_context_from_decompose(tmp_path, None)

    assert len(caught) >= 1
    assert any(issubclass(w.category, DeprecationWarning) and "arm_active_context_from_decompose" in str(w.message) for w in caught)


# ---------------------------------------------------------------------------
# promote_if_ready
# ---------------------------------------------------------------------------
def _seed_decompose_index(tmp_path: Path, epic: str, *, analyze_yaml: str | None = None) -> str:
    decomp = f"memory-bank/back/plan/decompose-{epic}"
    (tmp_path / decomp).mkdir(parents=True, exist_ok=True)
    (tmp_path / f"{decomp}/index.yaml").write_text(
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic}\n"
        "steps:\n"
        "- id: s01\n  file: s01-step.yaml\n  status: pending\n  next_phase: BACK IMPLEMENT\n",
        encoding="utf-8",
    )
    (tmp_path / f"{decomp}/s01-step.yaml").write_text(
        "schema: epic-decompose/v1\nstep_id: s01\nneeds_creative: 'no'\n",
        encoding="utf-8",
    )
    if analyze_yaml is not None:
        analyze_dir = tmp_path / f"memory-bank/back/analyze/{epic}"
        analyze_dir.mkdir(parents=True, exist_ok=True)
        (analyze_dir / "analyze-20260831-pass.yaml").write_text(analyze_yaml, encoding="utf-8")
    return decomp


def test_promote_if_ready_analyze_gate_required(tmp_path, monkeypatch):
    from epic.core import load_epic_state, save_epic_state  # noqa: PLC0415
    from loop.epic_transition import promote_if_ready  # noqa: PLC0415

    epic = "T-TEST-001"
    decomp = _seed_decompose_index(tmp_path, epic)
    st = {
        "armed_epic": epic,
        "armed_decompose": f"{decomp}/index.yaml",
        "armed_step": "DECOMPOSE",
        "role": "BACK",
    }
    save_epic_state(tmp_path, st)

    with patch("loop.epic_transition.arm_phase") as mock_arm:
        mock_arm.return_value = {"ok": True, "armed_step": "ANALYZE"}
        res = promote_if_ready(tmp_path, epic, "back")

    assert res is not None
    assert res["armed_step"] == "ANALYZE"
    assert res["reason"] == "analyze_gate"
    mock_arm.assert_called_once()
    assert mock_arm.call_args[0][2] == "ANALYZE"


def test_promote_if_ready_no_gate_goes_implement(tmp_path):
    from epic.core import save_epic_state  # noqa: PLC0415
    from loop.epic_transition import promote_if_ready  # noqa: PLC0415

    epic = "T-TEST-002"
    decomp = _seed_decompose_index(
        tmp_path,
        epic,
        analyze_yaml="schema: epic-analyze/v1\nmetrics:\n  critical_count: 0\n",
    )
    save_epic_state(
        tmp_path,
        {
            "armed_epic": epic,
            "armed_decompose": f"{decomp}/index.yaml",
            "armed_step": "DECOMPOSE",
            "role": "BACK",
        },
    )

    with patch("loop.epic_transition.arm_phase") as mock_arm:
        mock_arm.return_value = {"ok": True, "armed_step": "s01"}
        res = promote_if_ready(tmp_path, epic, "back")

    assert res is not None
    assert res["armed_step"] == "s01"
    assert res["reason"] == "implement_promote"
    mock_arm.assert_called_once()
    assert mock_arm.call_args[0][2] == "IMPLEMENT"


def test_promote_if_ready_implement_done_goes_audit(tmp_path):
    from epic.core import save_epic_state  # noqa: PLC0415
    from loop.epic_transition import promote_if_ready  # noqa: PLC0415

    epic = "T-TEST-004"
    decomp = _seed_decompose_index(
        tmp_path,
        epic,
        analyze_yaml="schema: epic-analyze/v1\nmetrics:\n  critical_count: 0\n",
    )
    idx = tmp_path / decomp / "index.yaml"
    idx.write_text(
        idx.read_text(encoding="utf-8").replace("status: pending", "status: completed"),
        encoding="utf-8",
    )
    save_epic_state(
        tmp_path,
        {
            "armed_epic": epic,
            "armed_decompose": f"{decomp}/index.yaml",
            "armed_step": "s01",
            "role": "BACK",
        },
    )

    with patch("loop.epic_transition.arm_phase") as mock_arm:
        mock_arm.return_value = {"ok": True, "armed_step": "AUDIT", "phase": "AUDIT"}
        res = promote_if_ready(tmp_path, epic, "back")

    assert res is not None
    assert res.get("reason") == "audit_promote"
    assert res.get("armed_step") == "AUDIT"
    mock_arm.assert_called_once()
    assert mock_arm.call_args[0][2] == "AUDIT"


def test_promote_if_ready_incomplete_index_returns_none(tmp_path):
    from epic.core import save_epic_state  # noqa: PLC0415
    from loop.epic_transition import promote_if_ready  # noqa: PLC0415

    epic = "T-TEST-003"
    save_epic_state(
        tmp_path,
        {
            "armed_epic": epic,
            "armed_step": "DECOMPOSE",
            "role": "BACK",
        },
    )
    assert promote_if_ready(tmp_path, epic, "back") is None


def test_promote_if_ready_analyze_finish_goes_implement(tmp_path):
    from epic.core import save_epic_state  # noqa: PLC0415
    from loop.epic_transition import promote_if_ready  # noqa: PLC0415

    epic = "T-TEST-004"
    decomp = _seed_decompose_index(
        tmp_path,
        epic,
        analyze_yaml="schema: epic-analyze/v1\nmetrics:\n  critical_count: 0\n",
    )
    save_epic_state(
        tmp_path,
        {
            "armed_epic": epic,
            "armed_decompose": f"{decomp}/index.yaml",
            "armed_step": "ANALYZE",
            "role": "BACK",
        },
    )

    with patch("loop.epic_transition.arm_phase") as mock_arm:
        mock_arm.return_value = {"ok": True, "armed_step": "s01"}
        res = promote_if_ready(tmp_path, epic, "back")

    assert res is not None
    assert res["promoted_from"] == "ANALYZE"
    assert res["reason"] == "implement_promote"
    mock_arm.assert_called_once()
    assert mock_arm.call_args[0][2] == "IMPLEMENT"


# ---------------------------------------------------------------------------
# test_legacy_warn_emits_deprecation
# ---------------------------------------------------------------------------
def test_legacy_warn_emits_deprecation():
    from loop.epic_transition import _legacy_warn  # noqa: PLC0415

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _legacy_warn("old_caller_fn")

    assert len(caught) == 1
    assert issubclass(caught[0].category, DeprecationWarning)
    assert "old_caller_fn" in str(caught[0].message)


# ---------------------------------------------------------------------------
# Phase Registry tests (s06)
# ---------------------------------------------------------------------------
def test_load_phase_registry_returns_all_phases():
    from loop.epic_transition import load_phase_registry  # noqa: PLC0415

    reg = load_phase_registry(pack_id="dev-hub-software", cwd=ROOT)
    assert isinstance(reg, dict)
    assert "phases" in reg
    assert len(reg["phases"]) >= 10
    assert "IMPLEMENT" in reg["phases"]
    assert "REFLECT" not in reg["terminal_phases"]
    assert "DONE" in reg["terminal_phases"]


def test_get_phase_config_unknown_fails_closed():
    from loop.epic_transition import get_phase_config  # noqa: PLC0415

    cfg = get_phase_config("IMPLEMENT")
    assert cfg["arm_template"] == "implement"
    assert get_phase_config("BACK IMPLEMENT")["arm_template"] == "implement"
    assert get_phase_config("front qa")["arm_template"] == get_phase_config("QA")["arm_template"]

    with pytest.raises(ValueError, match="unknown phase 'BOGUS'"):
        get_phase_config("BOGUS")


def test_get_verify_agent_implement():
    from loop.epic_transition import get_verify_agent  # noqa: PLC0415

    assert get_verify_agent("IMPLEMENT") == "verify-implement"


def test_get_verify_agent_qa():
    from loop.epic_transition import get_verify_agent  # noqa: PLC0415

    assert get_verify_agent("QA") == "verify-qa"


def test_get_verify_agent_analyze_optional():
    from loop.epic_transition import get_verify_agent, get_phase_config  # noqa: PLC0415

    assert get_verify_agent("ANALYZE") == "analyze-verify"
    cfg = get_phase_config("ANALYZE")
    assert cfg.get("verify_optional_env") == "PROJECT_LOOP_ANALYZE_VERIFY"


def test_get_verify_agent_unknown_fails_closed():
    from loop.epic_transition import get_verify_agent  # noqa: PLC0415

    with pytest.raises(ValueError, match="unknown phase 'INVALID'"):
        get_verify_agent("INVALID")


def test_agent_registry_aliases():
    from agent_registry import AGENT_ALIASES, resolve_agent_alias  # noqa: PLC0415

    assert AGENT_ALIASES.get("verify") == "verify-implement"
    assert AGENT_ALIASES.get("reviewer") == "verify-qa"
    assert resolve_agent_alias("verify") == "verify-implement"
    assert resolve_agent_alias("reviewer") == "verify-qa"
    assert resolve_agent_alias("verify-implement") == "verify-implement"


def test_get_dsh_preset_implement():
    from loop.epic_transition import get_dsh_preset  # noqa: PLC0415

    assert get_dsh_preset("IMPLEMENT") == "implement"
    assert get_dsh_preset("DECOMPOSE") == "decompose"
    assert get_dsh_preset("ANALYZE") == "analyze"
    assert get_dsh_preset("BUGFIX") == "bugfix"
    assert get_dsh_preset("QA") == "qa"
    assert get_dsh_preset("PLAN") is None
    assert get_dsh_preset("CLARIFY") is None
    import pytest

    with pytest.raises(ValueError, match="unknown phase"):
        get_dsh_preset("REFLECT")


def test_arm_phase_dsh_injects_preset(tmp_path, monkeypatch):
    from loop.epic_transition import arm_phase  # noqa: PLC0415

    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    schema_dir = tmp_path / "loop" / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    custom_yaml = {
        "schema": "phase-registry/v1",
        "phases": {
            "IMPLEMENT": {"verify_agent": "verify-implement", "dsh_preset": "implement"},
        },
    }
    (schema_dir / "phase_registry.yaml").write_text(yaml.dump(custom_yaml), encoding="utf-8")

    def mock_arm_epic(cwd, epic_id, **kwargs):
        return {"ok": True, "armed_epic": epic_id, "kwargs": kwargs}

    monkeypatch.setattr("epic.core.arm_epic", mock_arm_epic)
    monkeypatch.setenv("EPIC_RUNTIME", "dsh")

    res = arm_phase(tmp_path, "T-TEST-001", "IMPLEMENT", "back")
    assert res.get("ok") is True
    assert res.get("kwargs", {}).get("dsh_preset") == "implement"


def test_arm_phase_dsh_missing_preset_fails_closed(tmp_path, monkeypatch):
    from loop.epic_transition import arm_phase  # noqa: PLC0415

    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    schema_dir = tmp_path / "loop" / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    custom_yaml = {
        "schema": "phase-registry/v1",
        "phases": {
            "PLAN": {"verify_agent": None, "dsh_preset": None},
        },
    }
    (schema_dir / "phase_registry.yaml").write_text(yaml.dump(custom_yaml), encoding="utf-8")

    monkeypatch.setenv("EPIC_RUNTIME", "dsh")

    with pytest.raises(ValueError, match="no DSH preset for phase 'PLAN'"):
        arm_phase(tmp_path, "T-TEST-001", "PLAN", "back")


def test_registry_roles_covers_all():
    from loop.epic_transition import load_phase_registry  # noqa: PLC0415

    reg = load_phase_registry(pack_id="dev-hub-software", cwd=ROOT)
    assert reg.get("roles") == ["back", "front", "integration"]


def test_arm_phase_front_decompose(tmp_path, monkeypatch):
    from loop.epic_transition import arm_phase  # noqa: PLC0415

    def mock_arm_pre(cwd, epic_id, role, phase, target_rel=None, decompose_rel=None):
        active_ctx = tmp_path / "memory-bank" / "activeContext.md"
        active_ctx.parent.mkdir(parents=True, exist_ok=True)
        role_prefix = "FRONT" if role == "front" else "INTEG" if role == "integration" else "BACK"
        active_ctx.write_text(f"## Handoff\n- Mode: {role_prefix} {phase}\n", encoding="utf-8")
        return {"ok": True, "active_context": str(active_ctx), "role": role}

    monkeypatch.setattr("epic.core.arm_pre_implement_context", mock_arm_pre)

    res = arm_phase(tmp_path, "T-FRONT-001", "DECOMPOSE", "front", target_rel="memory-bank/front/plan/plan-T-FRONT-001.md")
    assert res.get("ok") is True
    assert res.get("role") == "front"
    active_content = Path(res["handoff"]).read_text(encoding="utf-8")
    assert "FRONT DECOMPOSE" in active_content


def test_arm_phase_integ_implement(tmp_path, monkeypatch):
    from loop.epic_transition import arm_phase  # noqa: PLC0415

    def mock_arm_epic(cwd, epic_id, role="back", **kwargs):
        active_ctx = tmp_path / "memory-bank" / "activeContext.md"
        active_ctx.parent.mkdir(parents=True, exist_ok=True)
        role_prefix = "INTEG" if role == "integration" else "FRONT" if role == "front" else "BACK"
        active_ctx.write_text(f"## Handoff\n- Mode: {role_prefix} IMPLEMENT\n", encoding="utf-8")
        return {"ok": True, "active_context": str(active_ctx), "role": role}

    monkeypatch.setattr("epic.core.arm_epic", mock_arm_epic)

    res = arm_phase(tmp_path, "T-INTEG-001", "IMPLEMENT", "integration")
    assert res.get("ok") is True
    assert res.get("role") == "integration"
    active_content = Path(res["handoff"]).read_text(encoding="utf-8")
    assert "INTEG IMPLEMENT" in active_content


def test_promote_if_ready_front_analyze_gate(tmp_path, monkeypatch):
    from loop.epic_transition import promote_if_ready  # noqa: PLC0415

    monkeypatch.setattr("epic.core.load_epic_state", lambda cwd: {"armed_step": "DECOMPOSE", "armed_epic": "T-FRONT-002", "role": "front"})
    monkeypatch.setattr("roadmap_queue.find_decompose_index", lambda cwd, role, eid: tmp_path / "index.yaml")
    (tmp_path / "index.yaml").write_text("schema: epic-decompose-index/v1\nsteps: []\n", encoding="utf-8")
    monkeypatch.setattr("roadmap_queue.load_steps_for_index", lambda cwd, idx_p: {"ok": True, "steps": [{"step_id": "s01", "status": "pending"}]})
    monkeypatch.setattr("analyze_gate.analyze_required_before_implement", lambda cwd, role, eid, steps, index_path=None: {"required": True})

    def mock_arm_phase(cwd, epic_id, phase, role, **kwargs):
        return {"ok": True, "armed_phase": phase, "role": role, "promoted_from": "DECOMPOSE"}

    monkeypatch.setattr("loop.epic_transition.arm_phase", mock_arm_phase)

    res = promote_if_ready(tmp_path, "T-FRONT-002", "front")
    assert res is not None
    assert res.get("armed_phase") == "ANALYZE"
    assert res.get("role") == "front"


def test_load_phase_registry_invalid_yaml_raises(tmp_path):
    from loop.epic_transition import load_phase_registry  # noqa: PLC0415

    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    schema_dir = tmp_path / "loop" / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)

    bad_file = schema_dir / "phase_registry.yaml"
    bad_file.write_text("phases: [this is not a dict structure", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid YAML"):
        load_phase_registry(pack_id="dev-hub-software", cwd=tmp_path)

    bad_file.write_text("wrong_key: 123", encoding="utf-8")

    with pytest.raises(ValueError, match="missing 'phases' key"):
        load_phase_registry(pack_id="dev-hub-software", cwd=tmp_path)


def test_arm_pre_implement_decompose_sets_armed_decompose(tmp_path: Path) -> None:
    from epic.core import arm_pre_implement_context, load_epic_state  # noqa: PLC0415

    plan = tmp_path / "memory-bank" / "back" / "plan" / "plan-T-030-demo.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("# plan\n", encoding="utf-8")
    res = arm_pre_implement_context(
        tmp_path,
        epic_id="T-030-demo",
        role="back",
        phase="DECOMPOSE",
        target_rel="memory-bank/back/plan/plan-T-030-demo.md",
    )
    assert res.get("ok") is True
    st = load_epic_state(tmp_path)
    assert st.get("armed_decompose") is None
    assert st.get("armed_step") == "DECOMPOSE"
    assert st.get("armed_epic") == "T-030-demo"
    ac = (tmp_path / "memory-bank" / "activeContext.md").read_text(encoding="utf-8")
    assert "workflow-decompose.mdc" in ac
    assert "sNN-<slug>.yaml" in ac
    assert "decompose-T-030-demo/index.yaml" in ac


def test_arm_pre_implement_short_queue_id_uses_plan_stem(tmp_path: Path) -> None:
    from epic.core import arm_pre_implement_context, load_epic_state  # noqa: PLC0415

    plan = (
        tmp_path
        / "memory-bank"
        / "back"
        / "plan"
        / "plan-T-HUB-023-hooks-llm-fallbacks.md"
    )
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("# plan\n", encoding="utf-8")
    res = arm_pre_implement_context(
        tmp_path,
        epic_id="T-HUB-023",
        role="back",
        phase="DECOMPOSE",
        target_rel="memory-bank/back/plan/plan-T-HUB-023-hooks-llm-fallbacks.md",
    )
    assert res.get("ok") is True
    assert res.get("epic_id") == "T-HUB-023-hooks-llm-fallbacks"
    st = load_epic_state(tmp_path)
    assert st.get("armed_epic") == "T-HUB-023-hooks-llm-fallbacks"
    ac = (tmp_path / "memory-bank" / "activeContext.md").read_text(encoding="utf-8")
    assert "decompose-T-HUB-023-hooks-llm-fallbacks/index.yaml" in ac
    assert "epic_id: T-HUB-023-hooks-llm-fallbacks" in ac
    assert "NOT short queue id" in ac


def test_arm_pre_implement_decompose_with_index_sets_armed_decompose(tmp_path: Path) -> None:
    from epic.core import arm_pre_implement_context, load_epic_state  # noqa: PLC0415

    plan = tmp_path / "memory-bank" / "back" / "plan" / "plan-T-030-demo.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("# plan\n", encoding="utf-8")
    idx = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-030-demo" / "index.yaml"
    idx.parent.mkdir(parents=True, exist_ok=True)
    idx.write_text(
        "schema: epic-decompose-index/v1\nplan_id: T-030-demo\nsteps: []\n",
        encoding="utf-8",
    )
    res = arm_pre_implement_context(
        tmp_path,
        epic_id="T-030-demo",
        role="back",
        phase="DECOMPOSE",
        target_rel="memory-bank/back/plan/plan-T-030-demo.md",
    )
    assert res.get("ok") is True
    st = load_epic_state(tmp_path)
    assert st.get("armed_decompose") == (
        "memory-bank/back/plan/decompose-T-030-demo/index.yaml"
    )


def test_arm_phase_anti_loop_forbidden_when_same_step(tmp_path: Path) -> None:
    """TM-009 / cp2: arm_phase with next_step == last_finished_step returns loop_* diagnostic fail-closed."""
    from loop.epic_transition import arm_phase
    from harness.hooks.epic.core import save_epic_state

    # Setup epic state with last_finished_step = s01
    save_epic_state(
        tmp_path,
        {
            "active": True,
            "armed_epic": "T-TEST-001",
            "armed_role": "BACK",
            "armed_step": "s01",
            "last_finished_step": "s01",
            "last_finished_epic": "T-TEST-001",
            "armed_decompose": "memory-bank/back/plan/decompose-T-TEST-001/index.yaml",
        },
    )

    mb_dir = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-TEST-001"
    mb_dir.mkdir(parents=True, exist_ok=True)
    index_yaml = mb_dir / "index.yaml"
    index_yaml.write_text(
        "schema: epic-decompose-index/v1\n"
        "plan_id: T-TEST-001\n"
        "role: back\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-env.yaml\n"
        "  status: pending\n"
        "  next_phase: BACK IMPLEMENT\n",
        encoding="utf-8",
    )
    (mb_dir / "s01-env.yaml").write_text(
        "schema: epic-decompose/v1\nstep_id: s01\nneeds_creative: 'no'\n",
        encoding="utf-8",
    )

    res = arm_phase(
        tmp_path,
        "T-TEST-001",
        "IMPLEMENT",
        "back",
        decompose_rel="memory-bank/back/plan/decompose-T-TEST-001/index.yaml",
    )

    assert res.get("ok") is False
    assert res.get("diagnostic_code") == "step_loop_forbidden"
    assert "step_loop_forbidden" in (res.get("diagnostic_codes") or [])
    assert res.get("last_finished_step") == "s01"
    assert res.get("armed_step") == "s01"


def test_arm_phase_allows_same_phase_on_different_epic(tmp_path: Path) -> None:
    """Cross-epic DECOMPOSE after another epic finished DECOMPOSE must not step_loop_forbidden."""
    from loop.epic_transition import arm_phase
    from harness.hooks.epic.core import load_epic_state, save_epic_state

    save_epic_state(
        tmp_path,
        {
            "active": True,
            "armed_epic": "T-HUB-047-prev",
            "armed_role": "BACK",
            "armed_step": "ANALYZE",
            "last_finished_step": "DECOMPOSE",
            "last_finished_epic": "T-HUB-047-prev",
            "armed_after_finish": "ANALYZE",
        },
    )

    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_rel = "memory-bank/back/plan/plan-T-HUB-059-next.md"
    (tmp_path / plan_rel).write_text("# plan\n", encoding="utf-8")

    res = arm_phase(
        tmp_path,
        "T-HUB-059-next",
        "DECOMPOSE",
        "back",
        target_rel=plan_rel,
    )

    assert res.get("ok") is True
    assert res.get("diagnostic_code") is None
    assert str(res.get("armed_step") or "").upper() == "DECOMPOSE"
    assert res.get("epic_id") == "T-HUB-059-next"

    st = load_epic_state(tmp_path)
    assert st.get("armed_epic") == "T-HUB-059-next"
    assert st.get("armed_step") == "DECOMPOSE"
    assert st.get("last_finished_step") is None
    assert st.get("last_finished_epic") is None


def test_arm_phase_allows_same_phase_on_different_epic_legacy_without_finished_epic(
    tmp_path: Path,
) -> None:
    """Legacy state: only last_finished_step + armed_epic — still allow other epic."""
    from loop.epic_transition import arm_phase
    from harness.hooks.epic.core import load_epic_state, save_epic_state

    save_epic_state(
        tmp_path,
        {
            "active": True,
            "armed_epic": "T-HUB-047-prev",
            "armed_role": "BACK",
            "armed_step": "ANALYZE",
            "last_finished_step": "DECOMPOSE",
        },
    )
    plan_rel = "memory-bank/back/plan/plan-T-HUB-059-next.md"
    (tmp_path / plan_rel).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / plan_rel).write_text("# plan\n", encoding="utf-8")

    res = arm_phase(
        tmp_path,
        "T-HUB-059-next",
        "DECOMPOSE",
        "back",
        target_rel=plan_rel,
    )
    assert res.get("ok") is True
    st = load_epic_state(tmp_path)
    assert st.get("armed_epic") == "T-HUB-059-next"
    assert st.get("last_finished_step") is None


def test_write_last_finish_tool_records_last_finished_epic(tmp_path: Path) -> None:
    from harness.hooks.epic.core import load_epic_state, save_epic_state, write_last_finish_tool

    save_epic_state(
        tmp_path,
        {
            "active": True,
            "armed_epic": "T-HUB-047-prev",
            "armed_step": "DECOMPOSE",
        },
    )
    assert write_last_finish_tool(
        tmp_path,
        "mb-finish decompose",
        finished_step="DECOMPOSE",
        armed_after_finish="ANALYZE",
    )
    st = load_epic_state(tmp_path)
    assert st.get("last_finished_step") == "DECOMPOSE"
    assert st.get("last_finished_epic") == "T-HUB-047-prev"
    assert st.get("armed_after_finish") == "ANALYZE"

