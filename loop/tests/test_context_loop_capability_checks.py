"""Integration tests for check-after capability checks discovery, execution, and evidence persistence."""

import json
from pathlib import Path
import pytest

from loop.context_loop import check_after
from loop.stack_profiles.evidence import get_evidence_relative_path, read_capability_evidence
from loop.stack_profiles.execution import CapabilityCheckSpec, compute_declaration_fingerprint
from loop.stack_profiles.schemas import CapabilityName


def _setup_monorepo_project(root: Path, role: str = "back", epic_id: str = "T-HUB-076", step_id: str = "s04") -> None:
    """Create a 3-target workspace (python, rust, javascript) with dev-hub.project.yaml and decompose shards."""
    # 1. Dev-hub project manifest
    (root / "services" / "py_api").mkdir(parents=True)
    (root / "services" / "py_api" / "pyproject.toml").write_text("[project]\nname='py_api'\n", encoding="utf-8")

    (root / "services" / "rs_core").mkdir(parents=True)
    (root / "services" / "rs_core" / "Cargo.toml").write_text('[package]\nname="rs_core"\nversion="0.1.0"\n', encoding="utf-8")

    (root / "services" / "web_app").mkdir(parents=True)
    (root / "services" / "web_app" / "package.json").write_text('{"name":"web_app","scripts":{"lint":"true","build":"true"}}\n', encoding="utf-8")
    (root / "services" / "web_app" / "package-lock.json").write_text('{"name":"web_app","lockfileVersion":3}\n', encoding="utf-8")

    manifest = (
        "schema: dev-hub-project/v1\n"
        "default_target: py_api\n"
        "targets:\n"
        "  py_api:\n"
        "    root: services/py_api\n"
        "    profile: python\n"
        "  rs_core:\n"
        "    root: services/rs_core\n"
        "    profile: rust\n"
        "  web_app:\n"
        "    root: services/web_app\n"
        "    profile: javascript\n"
    )
    (root / "dev-hub.project.yaml").write_text(manifest, encoding="utf-8")

    # 2. Epic decompose index
    decomp_index_rel = f"memory-bank/{role}/plan/{epic_id}/yaml/decompose-index.yaml"
    (root / decomp_index_rel).parent.mkdir(parents=True, exist_ok=True)
    (root / decomp_index_rel).write_text(
        f"schema: epic-decompose-index/v1\n"
        f"plan_id: {epic_id}\n"
        f"steps:\n"
        f"  - id: {step_id}\n"
        f"    file: {step_id}-test.yaml\n"
        f"    title: Step {step_id}\n"
        f"    status: pending\n",
        encoding="utf-8",
    )


def test_check_after_executes_only_current_armed_step_capability_checks(tmp_path: Path, monkeypatch):
    """cp1: check-after discovers only the current armed step declarations and executes each in declaration order."""
    from harness.hooks.epic import save_epic_state, load_epic_state
    import loop.context_loop as ctx_mod

    role = "back"
    epic_id = "T-HUB-076"
    step_id = "s04"
    _setup_monorepo_project(tmp_path, role=role, epic_id=epic_id, step_id=step_id)

    # Shard s04 declares 3 capability checks across the 3 targets
    shard_s04 = (
        "schema: epic-decompose/v1\n"
        "role: back\n"
        f"step_id: {step_id}\n"
        f"plan_id: {epic_id}\n"
        "title: check after test\n"
        "next_phase: BACK IMPLEMENT\n"
        "needs_creative: 'no'\n"
        "goal: test\n"
        "context: {}\n"
        "delta: []\n"
        "deletes: []\n"
        "out_of_scope: []\n"
        "skills: {}\n"
        "checkpoints: []\n"
        "tdd: []\n"
        "capability_checks:\n"
        "  - capability: lint\n"
        "    target: py_api\n"
        "  - capability: format.check\n"
        "    target: rs_core\n"
        "  - capability: lint\n"
        "    target: web_app\n"
    )
    s04_path = tmp_path / f"memory-bank/{role}/plan/{epic_id}/yaml/steps/{step_id}-test.yaml"
    s04_path.parent.mkdir(parents=True, exist_ok=True)
    s04_path.write_text(shard_s04, encoding="utf-8")

    # Shard s05 declares a different check (must not be executed)
    shard_s05 = (
        "schema: epic-decompose/v1\n"
        "role: back\n"
        "step_id: s05\n"
        f"plan_id: {epic_id}\n"
        "title: s05\n"
        "next_phase: BACK IMPLEMENT\n"
        "needs_creative: 'no'\n"
        "goal: test\n"
        "context: {}\n"
        "delta: []\n"
        "deletes: []\n"
        "out_of_scope: []\n"
        "skills: {}\n"
        "checkpoints: []\n"
        "tdd: []\n"
        "capability_checks:\n"
        "  - capability: build\n"
        "    target: web_app\n"
    )
    s05_path = tmp_path / f"memory-bank/{role}/plan/{epic_id}/yaml/steps/s05-test.yaml"
    s05_path.write_text(shard_s05, encoding="utf-8")

    # ActiveContext
    ac_text = (
        "---\n"
        "schema: loop-handoff/v1\n"
        f"role: {role.upper()}\n"
        "mode: IMPLEMENT\n"
        f"epic_id: {epic_id}\n"
        f"step_id: {step_id}\n"
        "---\n\n"
        "## load_now\n"
        f"1. [{step_id}-test.yaml]({role}/plan/{epic_id}/yaml/steps/{step_id}-test.yaml)\n\n"
        f"## Handoff BACK IMPLEMENT\n"
        f"- **Следующий:** `BACK IMPLEMENT {step_id}`\n"
    )
    (tmp_path / "memory-bank" / "activeContext.md").write_text(ac_text, encoding="utf-8")

    st = load_epic_state(tmp_path)
    st["active"] = True
    st["armed_epic"] = epic_id
    st["armed_step"] = step_id
    st["role"] = role.upper()
    st["armed_decompose"] = f"memory-bank/{role}/plan/{epic_id}/yaml/decompose-index.yaml"
    save_epic_state(tmp_path, st)

    executed_calls = []

    def _mock_execute(project_root, check):
        executed_calls.append((check.target, check.capability.value if hasattr(check.capability, 'value') else check.capability))
        from loop.stack_profiles.execution import CapabilityExecutionResult
        return CapabilityExecutionResult(
            ok=True,
            target=check.target,
            profile="python" if check.target == "py_api" else ("rust" if check.target == "rs_core" else "javascript"),
            capability=check.capability.value if hasattr(check.capability, 'value') else check.capability,
            cwd=str(project_root / f"services/{check.target}"),
            argv=["mock-cmd"],
            timeout_seconds=300,
            status="succeeded",
            exit_code=0,
            duration_ms=50,
        )

    monkeypatch.setattr(ctx_mod, "execute_capability", _mock_execute)

    res = check_after(tmp_path)
    assert res.get("ok") is True
    assert res.get("halt") is not True

    # Check that all 3 declared checks in s04 were executed in exact order
    assert executed_calls == [
        ("py_api", "lint"),
        ("rs_core", "format.check"),
        ("web_app", "lint"),
    ]


def test_check_after_persists_each_successful_capability_evidence_before_continue(tmp_path: Path, monkeypatch):
    """cp2: Every successful declared check writes matching role/epic/step evidence before the green continuation."""
    from harness.hooks.epic import save_epic_state, load_epic_state
    import loop.context_loop as ctx_mod

    role = "back"
    epic_id = "T-HUB-076"
    step_id = "s04"
    _setup_monorepo_project(tmp_path, role=role, epic_id=epic_id, step_id=step_id)

    shard_s04 = (
        "schema: epic-decompose/v1\n"
        "role: back\n"
        f"step_id: {step_id}\n"
        f"plan_id: {epic_id}\n"
        "title: check after test\n"
        "next_phase: BACK IMPLEMENT\n"
        "needs_creative: 'no'\n"
        "goal: test\n"
        "context: {}\n"
        "delta: []\n"
        "deletes: []\n"
        "out_of_scope: []\n"
        "skills: {}\n"
        "checkpoints: []\n"
        "tdd: []\n"
        "capability_checks:\n"
        "  - capability: lint\n"
        "    target: py_api\n"
        "  - capability: format.check\n"
        "    target: rs_core\n"
    )
    s04_path = tmp_path / f"memory-bank/{role}/plan/{epic_id}/yaml/steps/{step_id}-test.yaml"
    s04_path.parent.mkdir(parents=True, exist_ok=True)
    s04_path.write_text(shard_s04, encoding="utf-8")

    ac_text = (
        "---\n"
        "schema: loop-handoff/v1\n"
        f"role: {role.upper()}\n"
        "mode: IMPLEMENT\n"
        f"epic_id: {epic_id}\n"
        f"step_id: {step_id}\n"
        "---\n\n"
        "## load_now\n"
        f"1. [{step_id}-test.yaml]({role}/plan/{epic_id}/yaml/steps/{step_id}-test.yaml)\n\n"
        f"## Handoff BACK IMPLEMENT\n"
        f"- **Следующий:** `BACK IMPLEMENT {step_id}`\n"
    )
    (tmp_path / "memory-bank" / "activeContext.md").write_text(ac_text, encoding="utf-8")

    st = load_epic_state(tmp_path)
    st["active"] = True
    st["armed_epic"] = epic_id
    st["armed_step"] = step_id
    st["role"] = role.upper()
    st["armed_decompose"] = f"memory-bank/{role}/plan/{epic_id}/yaml/decompose-index.yaml"
    save_epic_state(tmp_path, st)

    def _mock_execute(project_root, check):
        from loop.stack_profiles.execution import CapabilityExecutionResult
        return CapabilityExecutionResult(
            ok=True,
            target=check.target,
            profile="python" if check.target == "py_api" else "rust",
            capability=check.capability.value if hasattr(check.capability, 'value') else check.capability,
            cwd=str(project_root / f"services/{check.target}"),
            argv=["mock-cmd"],
            timeout_seconds=300,
            status="succeeded",
            exit_code=0,
            duration_ms=75,
        )

    monkeypatch.setattr(ctx_mod, "execute_capability", _mock_execute)

    res = check_after(tmp_path)
    assert res.get("ok") is True
    assert res.get("halt") is not True

    # Check evidence on disk
    check1 = CapabilityCheckSpec(target="py_api", capability=CapabilityName.LINT)
    ev1 = read_capability_evidence(tmp_path, role=role, epic_id=epic_id, step_id=step_id, declaration=check1)
    assert ev1 is not None
    assert ev1.status == "succeeded"
    assert ev1.exit_code == 0

    check2 = CapabilityCheckSpec(target="rs_core", capability=CapabilityName.FORMAT_CHECK)
    ev2 = read_capability_evidence(tmp_path, role=role, epic_id=epic_id, step_id=step_id, declaration=check2)
    assert ev2 is not None
    assert ev2.status == "succeeded"


def test_check_after_halts_on_stale_or_foreign_evidence(tmp_path: Path, monkeypatch):
    """cp4: Stale or foreign evidence does not satisfy check-after; executions must match current armed step."""
    from harness.hooks.epic import save_epic_state, load_epic_state
    import loop.context_loop as ctx_mod

    role = "back"
    epic_id = "T-HUB-076"
    step_id = "s04"
    _setup_monorepo_project(tmp_path, role=role, epic_id=epic_id, step_id=step_id)

    # Shard s04 with lint check
    shard_s04 = (
        "schema: epic-decompose/v1\n"
        "role: back\n"
        f"step_id: {step_id}\n"
        f"plan_id: {epic_id}\n"
        "title: check after test\n"
        "next_phase: BACK IMPLEMENT\n"
        "needs_creative: 'no'\n"
        "goal: test\n"
        "context: {}\n"
        "delta: []\n"
        "deletes: []\n"
        "out_of_scope: []\n"
        "skills: {}\n"
        "checkpoints: []\n"
        "tdd: []\n"
        "capability_checks:\n"
        "  - capability: lint\n"
        "    target: py_api\n"
    )
    s04_path = tmp_path / f"memory-bank/{role}/plan/{epic_id}/yaml/steps/{step_id}-test.yaml"
    s04_path.parent.mkdir(parents=True, exist_ok=True)
    s04_path.write_text(shard_s04, encoding="utf-8")

    ac_text = (
        "---\n"
        "schema: loop-handoff/v1\n"
        f"role: {role.upper()}\n"
        "mode: IMPLEMENT\n"
        f"epic_id: {epic_id}\n"
        f"step_id: {step_id}\n"
        "---\n\n"
        "## load_now\n"
        f"1. [{step_id}-test.yaml]({role}/plan/{epic_id}/yaml/steps/{step_id}-test.yaml)\n\n"
        f"## Handoff BACK IMPLEMENT\n"
        f"- **Следующий:** `BACK IMPLEMENT {step_id}`\n"
    )
    (tmp_path / "memory-bank" / "activeContext.md").write_text(ac_text, encoding="utf-8")

    st = load_epic_state(tmp_path)
    st["active"] = True
    st["armed_epic"] = epic_id
    st["armed_step"] = step_id
    st["role"] = role.upper()
    st["armed_decompose"] = f"memory-bank/{role}/plan/{epic_id}/yaml/decompose-index.yaml"
    save_epic_state(tmp_path, st)

    # Let execute_capability return failed status
    def _mock_execute_fail(project_root, check):
        from loop.stack_profiles.execution import CapabilityExecutionResult
        from loop.stack_profiles.schemas import Diagnostic
        return CapabilityExecutionResult(
            ok=False,
            target=check.target,
            profile="python",
            capability="lint",
            cwd=str(project_root / "services/py_api"),
            argv=["ruff", "check"],
            timeout_seconds=300,
            status="failed",
            exit_code=1,
            duration_ms=100,
            diagnostics=[Diagnostic(code="command_failed", message="Ruff lint found 2 errors")],
        )

    monkeypatch.setattr(ctx_mod, "execute_capability", _mock_execute_fail)

    res = check_after(tmp_path)
    assert res.get("ok") is False
    assert res.get("halt") is True
    assert "command_failed" in res.get("diagnostic_codes", []) or res.get("diagnostic_code") == "command_failed"
