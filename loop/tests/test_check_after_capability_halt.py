"""Negative tests for check-after capability check HALT matrices."""

from pathlib import Path
import pytest

from loop.context_loop import check_after
from loop.stack_profiles.execution import CapabilityExecutionResult
from loop.stack_profiles.schemas import Diagnostic


def _setup_halt_workspace(root: Path, shard_yaml: str, role: str = "back", epic_id: str = "T-HUB-076", step_id: str = "s04") -> None:
    (root / "services" / "worker").mkdir(parents=True)
    (root / "services" / "worker" / "pyproject.toml").write_text("[project]\nname='worker'\n", encoding="utf-8")

    manifest = (
        "schema: dev-hub-project/v1\n"
        "default_target: worker\n"
        "targets:\n"
        "  worker:\n"
        "    root: services/worker\n"
        "    profile: python\n"
    )
    (root / "dev-hub.project.yaml").write_text(manifest, encoding="utf-8")

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

    s_path = root / f"memory-bank/{role}/plan/{epic_id}/yaml/steps/{step_id}-test.yaml"
    s_path.parent.mkdir(parents=True, exist_ok=True)
    s_path.write_text(shard_yaml, encoding="utf-8")

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
    (root / "memory-bank" / "activeContext.md").write_text(ac_text, encoding="utf-8")

    from harness.hooks.epic import save_epic_state, load_epic_state
    st = load_epic_state(root)
    st["active"] = True
    st["armed_epic"] = epic_id
    st["armed_step"] = step_id
    st["role"] = role.upper()
    st["armed_decompose"] = f"memory-bank/{role}/plan/{epic_id}/yaml/decompose-index.yaml"
    save_epic_state(root, st)


def test_check_after_halts_on_missing_target_without_spawning(tmp_path: Path, monkeypatch):
    """cp3: Missing declaration target halts before subprocess execution."""
    import loop.context_loop as ctx_mod

    # Shard with invalid check (target omitted / invalid)
    shard_invalid = (
        "schema: epic-decompose/v1\n"
        "role: back\n"
        "step_id: s04\n"
        "plan_id: T-HUB-076\n"
        "title: invalid target\n"
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
        "    target: ''\n"
    )

    _setup_halt_workspace(tmp_path, shard_invalid)

    def _fail_execute(*args, **kwargs):
        raise AssertionError("execute_capability must not be called when declaration target is invalid")

    monkeypatch.setattr(ctx_mod, "execute_capability", _fail_execute)

    res = check_after(tmp_path)
    assert res.get("ok") is False
    assert res.get("halt") is True


@pytest.mark.parametrize("status,diag_code", [
    ("resolution_failed", "target_unknown"),
    ("spawn_failed", "spawn_failed"),
    ("timed_out", "process_timed_out"),
    ("failed", "command_failed"),
])
def test_check_after_halts_on_resolution_spawn_timeout_and_nonzero(tmp_path: Path, monkeypatch, status, diag_code):
    """cp3: Resolution, spawn, timeout and nonzero command failures HALT with diagnostic without fallback."""
    import loop.context_loop as ctx_mod

    shard_valid = (
        "schema: epic-decompose/v1\n"
        "role: back\n"
        "step_id: s04\n"
        "plan_id: T-HUB-076\n"
        "title: test check\n"
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
        "    target: worker\n"
    )
    _setup_halt_workspace(tmp_path, shard_valid)

    def _mock_execute_status(project_root, check):
        return CapabilityExecutionResult(
            ok=False,
            target=check.target,
            profile="python",
            capability="lint",
            cwd=str(project_root / "services/worker"),
            argv=["mock"],
            timeout_seconds=300,
            status=status,
            exit_code=1 if status == "failed" else None,
            duration_ms=50,
            diagnostics=[Diagnostic(code=diag_code, message=f"Diagnostic error: {diag_code}")],
        )

    monkeypatch.setattr(ctx_mod, "execute_capability", _mock_execute_status)

    res = check_after(tmp_path)
    assert res.get("ok") is False
    assert res.get("halt") is True
    diag_codes = res.get("diagnostic_codes") or []
    if res.get("diagnostic_code"):
        diag_codes.append(res["diagnostic_code"])
    assert diag_code in diag_codes or status in res.get("reason", "")
