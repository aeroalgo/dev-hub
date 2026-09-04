from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load_ctx():
    path = ROOT / "loop" / "context_loop.py"
    spec = importlib.util.spec_from_file_location("context_loop", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # ensure hooks importable
    hooks = str(ROOT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    spec.loader.exec_module(mod)
    return mod


def _write(cwd: Path, rel: str, body: str) -> None:
    p = cwd / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _seed_context(cwd: Path, *, next_line: str = "INTEG IMPLEMENT e16") -> None:
    _write(
        cwd,
        "memory-bank/integration/analyze/x/analyze-20260901-pass.yaml",
        "schema: epic-analyze/v1\nmetrics:\n  critical_count: 0\nstatus: complete\n",
    )
    _write(
        cwd,
        "memory-bank/integration/plan/decompose-x/e16-foo.yaml",
        "schema: epic-decompose/v1\nstep_id: e16\n",
    )
    _write(
        cwd,
        "memory-bank/integration/implement/implement-x/index.md",
        "| Step | Status |\n| e16 | pending |\n",
    )
    _write(
        cwd,
        "memory-bank/activeContext.md",
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: INTEG\n"
        "mode: IMPLEMENT\n"
        "epic_id: x\n"
        "step_id: e16\n"
        "---\n\n"
        "## load_now\n"
        "1. [e16-foo.yaml](integration/plan/decompose-x/e16-foo.yaml)\n"
        "2. [index.md](integration/implement/implement-x/index.md)\n\n"
        "## Handoff INTEG IMPLEMENT\n"
        f"- **Следующий:** `{next_line}`\n"
        "- **Gaps:** none.\n",
    )


def test_sync_cursor_skips_implement_when_analyze_pending(tmp_path: Path) -> None:
    hooks = str(ROOT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    loop_dir = str(ROOT / "loop")
    if loop_dir not in sys.path:
        sys.path.insert(0, loop_dir)
    from epic import sync_cursor_from_index, save_epic_state
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-T-HUB-099/index.yaml",
        "schema: epic-decompose-index/v1\n"
        "epic_id: T-HUB-099\n"
        "steps:\n"
        "  - step_id: s01\n"
        "    status: pending\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-T-HUB-099/s01-foo.yaml",
        "schema: epic-decompose/v1\nstep_id: s01\n",
    )
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n"
        "1. [s01-foo.yaml](back/plan/decompose-T-HUB-099/s01-foo.yaml)\n"
        "2. [index.yaml](back/plan/decompose-T-HUB-099/index.yaml)\n\n"
        "## Handoff BACK IMPLEMENT\n"
        "- **Следующий:** `BACK IMPLEMENT s01`\n",
    )
    save_epic_state(
        tmp_path,
        {
            "armed_epic": "T-HUB-099",
            "armed_decompose": "memory-bank/back/plan/decompose-T-HUB-099/index.yaml",
            "armed_step": "s01",
        },
    )
    res = sync_cursor_from_index(tmp_path)
    assert res["ok"] is True
    assert res["synced"] is True
    assert res["reason"] == "analyze_gate_rearm"
    assert res["armed_step"] == "ANALYZE"


def test_dag_fanout_arms_dependency_ready_node(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _write(tmp_path, "memory-bank/activeContext.md", "## load_now\n1. old\n")
    _write(
        tmp_path,
        "loop/dag/portal.yaml",
        "schema: loop-dag/v1\n"
        "pipeline_id: portal\n"
        "nodes:\n"
        "  - id: back\n"
        "    role_dir: back\n"
        "    decompose: memory-bank/back/plan/decompose-demo/index.md\n"
        "    depends_on: []\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/index.md",
        "| step_id | title | status |\n"
        "| :--- | :--- | :--- |\n"
        "| **s01** | [s01-one.yaml](s01-one.yaml) | pending |\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/s01-one.yaml",
        "schema: epic-decompose/v1\nstep_id: s01\n",
    )

    out = ctx.dag_fanout(tmp_path)

    assert out["ok"] is True
    assert out["armed"] is True
    assert out["node"] == "back"
    assert "decompose-demo" in (tmp_path / "memory-bank/activeContext.md").read_text()


def test_status_includes_permission_mode_from_project_env(
    tmp_path: Path, monkeypatch
) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    _write(tmp_path, ".claude/project.env", "EPIC_PERMISSION_MODE=bypassPermissions\n")
    monkeypatch.delenv("EPIC_PERMISSION_MODE", raising=False)

    configuration = ctx.status(tmp_path)["configuration"]

    assert configuration["effective"]["EPIC_PERMISSION_MODE"] == "bypassPermissions"
    assert configuration["sources"]["EPIC_PERMISSION_MODE"] == "project"
    assert "project.env" not in json.dumps(configuration)


def test_status_includes_finish_integrity_and_permission(tmp_path: Path, monkeypatch) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    _write(tmp_path, ".claude/project.env", "EPIC_PERMISSION_MODE=bypassPermissions\n")
    _write(
        tmp_path,
        "memory-bank/integration/plan/decompose-x/index.yaml",
        "schema: epic-decompose-index/v1\nplan_id: x\nsteps:\n"
        "- id: e16\n  file: e16-foo.yaml\n  status: pending\n",
    )
    _write(
        tmp_path,
        "memory-bank/integration/plan/decompose-x/index.md",
        "# Реестр\n",
    )
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        '{"armed_epic":"x","armed_decompose":"memory-bank/integration/plan/decompose-x/index.yaml","armed_step":"e16"}\n',
    )
    monkeypatch.delenv("EPIC_PERMISSION_MODE", raising=False)

    out = ctx.status(tmp_path)

    assert out["configuration"]["effective"]["EPIC_PERMISSION_MODE"] == "bypassPermissions"
    assert out["finish_integrity"] == {
        "ok": True,
        "errors": [],
        "diagnostic_codes": [],
        "armed_epic": "x",
        "armed_step": "e16",
    }


def test_status_exposes_dag_cursor_and_gate_state(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    _write(
        tmp_path,
        "loop/dag/portal.yaml",
        "schema: loop-dag/v1\npipeline_id: portal\nnodes: []\n",
    )

    out = ctx.status(tmp_path)

    assert out["ok"] is True
    assert "dag" in out
    assert "recovery" in out
    assert out["dag"]["pipeline_id"] == "portal"


def test_status_agent_policy_section(tmp_path: Path, monkeypatch) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    monkeypatch.setenv("EPIC_LOOP", "1")
    monkeypatch.setenv("PROJECT_AGENT_VERIFY_MODEL", "sonnet")
    monkeypatch.setenv("PROJECT_AGENT_REVIEWER_MODEL", "sonnet")

    policy = ctx.status(tmp_path)["agent_policy"]

    assert set(policy) == {
        "context",
        "workflow_policy",
        "registry_revision",
        "active",
        "inactive",
        "errors",
        "gates",
    }
    assert policy["context"] == "loop"
    assert policy["registry_revision"].startswith("sha256:")
    assert isinstance(policy["active"], list)
    assert isinstance(policy["inactive"], list)
    assert isinstance(policy["gates"], dict)


def test_status_agent_policy_active_loop_agents(tmp_path: Path, monkeypatch) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    for agent in ("explorer", "reviewer", "verify"):
        _write(tmp_path, f".claude/agents/{agent}.md", f"---\nname: {agent}\n---\nbody\n")
    monkeypatch.setenv("EPIC_LOOP", "1")
    monkeypatch.setenv("PROJECT_AGENT_EXPLORER_MODEL_LOOP", "1")
    monkeypatch.setenv("PROJECT_AGENT_VERIFY_MODEL", "sonnet")
    monkeypatch.setenv("PROJECT_AGENT_REVIEWER_MODEL", "sonnet")

    policy = ctx.status(tmp_path)["agent_policy"]

    assert policy["active"] == ["explorer", "reviewer", "verify"]
    assert not policy["inactive"]
    assert policy["gates"] == {
        "reviewer": {"required": False, "active": True, "done": False},
        "verify": {"required": False, "active": True, "done": False},
    }


def test_agent_policy_no_secrets(tmp_path: Path, monkeypatch) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    secret = "sk-test-secret-value"
    monkeypatch.setenv("EPIC_LOOP", "1")
    monkeypatch.setenv("PROJECT_AGENT_VERIFY_MODEL", secret)
    monkeypatch.setenv("PROJECT_AGENT_REVIEWER_MODEL", "sonnet")

    rendered = json.dumps(ctx.status(tmp_path)["agent_policy"])

    assert secret not in rendered
    assert "project.env" not in rendered
    assert "sk-" not in rendered


def test_agent_policy_invalid_agent_is_inactive(tmp_path: Path, monkeypatch) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    _write(
        tmp_path,
        ".claude/agents/broken.md",
        "---\nname: broken\noverlay:\n  managed: true\n  requires_model: true\n  default_loop: true\n---\nbody\n",
    )
    monkeypatch.setenv("EPIC_LOOP", "1")
    monkeypatch.delenv("PROJECT_AGENT_BROKEN_MODEL", raising=False)

    policy = ctx.status(tmp_path)["agent_policy"]

    assert "broken" not in policy["active"]
    assert {item["id"] for item in policy["inactive"]} == {"broken"}
    assert policy["inactive"][0]["reason"] == "model_missing"


def test_dag_generate_reads_gap_decompose_links(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _write(
        tmp_path,
        "memory-bank/integration/gap/portal/gap-20260804-api.md",
        "| BACK | decompose-demo |\n| FRONT | decompose-demo-front |\n",
    )

    out = ctx._cmd_dag_generate(tmp_path, "portal")
    dag = (tmp_path / out["path"]).read_text(encoding="utf-8")

    assert out["ok"] is True
    assert "decompose-demo" in dag
    assert "decompose-demo-front" in dag


def test_gaps_field_is_not_stop_marker(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    text = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert ctx.detect_stop_marker(text) is None


def test_uppercase_gaps_deferred_note_is_not_stop(tmp_path: Path) -> None:
    """Regression: agents wrote **GAPS:** for deferred sNN scope and halted the loop."""
    ctx = _load_ctx()
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n"
        "1. [s02.yaml](back/plan/decompose-x/s02.yaml)\n\n"
        "## Handoff\n"
        "- **Дальше:** BACK IMPLEMENT @s02\n"
        "- **GAPS:** docker cutover left for s12; engine confirm in s03\n"
        "- GAPS: also a bare deferred note\n",
    )
    text = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert ctx.detect_stop_marker(text) is None
    prompt = ctx.build_prompt(
        tmp_path,
        load_now=["memory-bank/activeContext.md"],
        shape_errors=[],
        delta_ok=False,
        delta_paths=[],
    )
    assert "GAPS: …" not in prompt
    assert "FORBIDDEN stop-маркер: `GAPS:`" in prompt
    assert "BLOCKED:" in prompt
    assert "NEED_HUMAN:" in prompt
    assert "Ты в автоцикле" not in prompt
    assert "Выполни один шаг" in prompt
    assert "## Команды" in prompt


def test_blocked_stop_marker(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n"
        "1. [e16-foo.yaml](integration/plan/decompose-x/e16-foo.yaml)\n\n"
        "## Handoff INTEG\n"
        "BLOCKED: needs human\n"
        "- **Следующий:** INTEG IMPLEMENT e16\n",
    )
    text = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    stop = ctx.detect_stop_marker(text)
    assert stop and stop.startswith("BLOCKED")


def test_prepare_builds_prompt_with_activecontext(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    out = ctx.prepare_session(tmp_path, model="gpt")
    assert out["ok"] is True
    assert out.get("load_now")
    assert out.get("degraded") is False
    prompt = Path(out["prompt_file"]).read_text(encoding="utf-8")
    assert "memory-bank/activeContext.md" in prompt
    assert "activeContext.md" in prompt
    assert "Context degraded" not in prompt
    assert "mb-finish implement" in prompt
    assert "## IMPLEMENT FINISH" not in prompt
    assert "## projection" in prompt
    assert "runner-derived" not in prompt
    assert "Выполни один шаг" in prompt
    assert "Ты в автоцикле" not in prompt
    assert "Context economy" not in prompt
    assert "step_context (JSON)" not in prompt
    assert "expected_artifact" not in prompt


def test_prepare_emits_runtime_claude_default(tmp_path: Path, monkeypatch) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    monkeypatch.delenv("EPIC_RUNTIME", raising=False)

    out = ctx.prepare_session(tmp_path)

    assert out["runtime"] == "claude"


def test_prepare_emits_runtime_dsh(tmp_path: Path, monkeypatch) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    monkeypatch.setenv("EPIC_RUNTIME", "dsh")

    out = ctx.prepare_session(tmp_path)

    assert out["runtime"] == "dsh"


def test_prepare_emits_dsh_profile(tmp_path: Path, monkeypatch) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    monkeypatch.setenv("EPIC_RUNTIME", "dsh")

    out = ctx.prepare_session(tmp_path)

    assert out["dsh_profile"].startswith("epic-")
    assert out["runtime_extras"] == {"dsh_profile": "epic-implement"}


def test_prepare_runtime_extras_via_adapter(tmp_path: Path, monkeypatch) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    monkeypatch.setenv("EPIC_RUNTIME", "dsh")

    out = ctx.prepare_session(tmp_path)

    assert out["runtime_extras"] == {"dsh_profile": "epic-implement"}


def test_prepare_runtime_extras_claude(tmp_path: Path, monkeypatch) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    monkeypatch.setenv("EPIC_RUNTIME", "claude")

    out = ctx.prepare_session(tmp_path)

    assert out["runtime_extras"] == {}


def test_argparse_choices_runtime_from_registry() -> None:
    from loop.runtime.registry import list_ids
    import argparse
    from loop.context_loop import main

    choices = list_ids()
    assert "claude" in choices
    assert "dsh" in choices


def test_context_loop_runtime_extras_generic_key(tmp_path: Path, monkeypatch) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)

    out = ctx.prepare_session(tmp_path, runtime="dsh")

    assert "runtime_extras" in out
    assert isinstance(out["runtime_extras"], dict)


def test_prepare_emits_dsh_workspace(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)

    out = ctx.prepare_session(tmp_path, runtime="dsh")

    assert out["dsh_workspace"] == str(tmp_path)


def test_prepare_cli_runtime_override(tmp_path: Path, monkeypatch, capsys) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    monkeypatch.setenv("EPIC_RUNTIME", "claude")

    rc = ctx.main(["--cwd", str(tmp_path), "prepare", "--runtime", "dsh"])
    out = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert out["runtime"] == "dsh"


def test_prepare_rebuilds_derived_projection(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    _write(
        tmp_path,
        "memory-bank/integration/plan/decompose-x/index.md",
        "| step_id | title | status |\n"
        "| :--- | :--- | :--- |\n"
        "| **e16** | [e16-foo.yaml](e16-foo.yaml) | pending |\n",
    )
    ctx.arm_session(tmp_path, "decompose-x")
    out = ctx.prepare_session(tmp_path)
    assert out["ok"] is True
    state = json.loads(
        (tmp_path / ".claude/runtime/epic/state.json").read_text(
            encoding="utf-8"
        )
    )
    projection = state["projection"]
    assert projection["source"] == "event-log+decompose-index"
    assert projection["phase"] == "INTEG IMPLEMENT"
    assert projection["next_step"] == "e16"
    assert state["phase"] == projection["phase"]


def test_delta_paths_exist_skips_explorer_in_prompt(tmp_path: Path) -> None:
    ctx = _load_ctx()
    code_a = "frontend/src/features/trends/useSetpoints.ts"
    code_b = "frontend/src/lib/api/setpoints.ts"
    _write(tmp_path, code_a, "export const a = 1\n")
    _write(tmp_path, code_b, "export const b = 1\n")
    _write(
        tmp_path,
        ".claude/agents/explorer.md",
        "---\nname: explorer\noverlay:\n  managed: true\n  mode: search\n"
        "  default_loop: true\n  requires_model: false\n---\nbody\n",
    )
    _write(
        tmp_path,
        ".claude/project.env",
        "PROJECT_AGENT_EXPLORER_MODEL=fable\n"
        "PROJECT_AGENT_EXPLORER_MODEL_LOOP=1\n",
    )
    _write(
        tmp_path,
        "memory-bank/integration/plan/decompose-x/e16-foo.yaml",
        "schema: epic-decompose/v1\nstep_id: e16\n"
        "files:\n"
        f"- {code_a}\n"
        f"- {code_b}\n",
    )
    _write(
        tmp_path,
        "memory-bank/integration/implement/implement-x/index.md",
        "| Step | Status |\n| e16 | pending |\n",
    )
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n"
        "1. [e16-foo.yaml](integration/plan/decompose-x/e16-foo.yaml)\n"
        "2. [index.md](integration/implement/implement-x/index.md)\n\n"
        "## Handoff INTEG IMPLEMENT\n"
        "- **Следующий:** `INTEG IMPLEMENT e16`\n",
    )
    out = ctx.prepare_session(tmp_path)
    assert out["ok"] is True
    assert out.get("delta_paths_exist") is True
    assert out.get("delta_scope") == "exist"
    assert code_a in (out.get("delta_paths") or [])
    prompt = Path(out["prompt_file"]).read_text(encoding="utf-8")
    assert "delta_paths_exist: yes" in prompt
    assert "SKIP `@explorer`" in prompt
    assert code_a in prompt


def test_explorer_off_prompt_does_not_require_agent(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _write(
        tmp_path,
        ".claude/agents/explorer.md",
        "---\nname: explorer\noverlay:\n  managed: true\n  mode: search\n"
        "  default_loop: true\n  requires_model: false\n---\nbody\n",
    )
    _write(
        tmp_path,
        ".claude/project.env",
        "PROJECT_AGENT_EXPLORER_MODEL=fable\n"
        "PROJECT_AGENT_EXPLORER_MODEL_LOOP=0\n",
    )
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n"
        "1. [e16-foo.yaml](integration/plan/decompose-x/e16-foo.yaml)\n\n"
        "## Handoff INTEG IMPLEMENT\n"
        "- **Следующий:** `INTEG IMPLEMENT e16`\n",
    )
    _write(
        tmp_path,
        "memory-bank/integration/plan/decompose-x/e16-foo.yaml",
        "schema: epic-decompose/v1\nstep_id: e16\n",
    )
    prompt = ctx.build_prompt(
        tmp_path,
        load_now=["memory-bank/activeContext.md"],
        shape_errors=[],
        delta_ok=False,
        delta_paths=[],
        projection={"phase": "BACK IMPLEMENT", "epic": "x", "next_step": "e16"},
    )
    assert "managed: off" in prompt
    assert "1× `@explorer`" not in prompt


def test_extract_shard_resolves_bare_unique_ts(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _write(
        tmp_path,
        "frontend/src/features/trends/useEventMarkers.ts",
        "export {}\n",
    )
    text = "ui:\n  components: '** `useEventMarkers.ts` + helpers'\n"
    paths = ctx.extract_shard_code_paths(tmp_path, text)
    assert any(p.endswith("useEventMarkers.ts") for p in paths)


def test_detect_delta_paths_scoped_when_missing_files(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _write(
        tmp_path,
        "memory-bank/integration/plan/decompose-x/e16-foo.yaml",
        "files:\n- frontend/src/missing-a.ts\n- frontend/src/missing-b.ts\n",
    )
    load_now = ["memory-bank/integration/plan/decompose-x/e16-foo.yaml"]
    scope, paths = ctx.detect_delta_paths(tmp_path, load_now)
    assert scope == "scoped"
    assert len(paths) == 2


def test_delta_paths_scoped_skips_explorer_for_hub_shard(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _write(
        tmp_path,
        ".claude/agents/explorer.md",
        "---\nname: explorer\noverlay:\n  managed: true\n  mode: search\n"
        "  default_loop: true\n  requires_model: false\n---\nbody\n",
    )
    _write(
        tmp_path,
        ".claude/project.env",
        "PROJECT_AGENT_EXPLORER_MODEL=fable\n"
        "PROJECT_AGENT_EXPLORER_MODEL_LOOP=1\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-T-HUB-007/index.yaml",
        "schema: epic-decompose-index/v1\n"
        "epic_id: T-HUB-007\n"
        "steps:\n"
        "  - step_id: s02\n"
        "    status: pending\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/analyze/T-HUB-007/analyze-20260901-pass.yaml",
        "schema: epic-analyze/v1\nepic_id: T-HUB-007\nmetrics:\n  critical_count: 0\nstatus: complete\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-T-HUB-007/s02-epic-implement-profile.yaml",
        "schema: epic-decompose/v1\n"
        "context:\n"
        "  consumes:\n"
        "    - dsh/scripts/sync-agent-md-to-presets.py\n"
        "  produces:\n"
        "    - dsh/profiles/epic-implement/package.json\n"
        "files:\n"
        "  - dsh/profiles/epic-implement/package.json\n"
        "  - dsh/profiles/epic-implement/cordis.patch.yml\n",
    )
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        "epic_id: T-HUB-007\n"
        "step_id: s02\n"
        "---\n\n"
        "## load_now\n"
        "1. [s02.yaml](back/plan/decompose-T-HUB-007/s02-epic-implement-profile.yaml)\n"
        "2. [index.yaml](back/plan/decompose-T-HUB-007/index.yaml)\n\n"
        "## Handoff BACK IMPLEMENT\n"
        "- **Следующий:** `BACK IMPLEMENT s02`\n",
    )
    out = ctx.prepare_session(tmp_path)
    assert out["ok"] is True
    assert out.get("delta_scope") == "scoped"
    assert out.get("delta_paths_scoped") is True
    prompt = Path(out["prompt_file"]).read_text(encoding="utf-8")
    assert "delta_paths_scoped: yes" in prompt
    assert "SKIP `@explorer`" in prompt
    assert "search_scope" in prompt
    assert "ALLOW" in prompt
    assert "1× `@explorer`" not in prompt


def test_prepare_degraded_when_load_now_empty(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _write(
        tmp_path,
        "memory-bank/integration/plan/x/md/decompose-index.md",
        "| Step | Status |\n| **e16** | pending |\n",
    )
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n\n## Handoff INTEG\n- **Следующий:** ???\n",
    )
    out = ctx.prepare_session(tmp_path, model="gpt")
    assert out["ok"] is True
    assert out.get("degraded") is True
    prompt = Path(out["prompt_file"]).read_text(encoding="utf-8")
    assert "Context degraded" in prompt
    assert "decompose-index.md" in prompt


def test_prepare_degraded_when_shape_broken(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n1. missing.yaml\n\n"
        "## Handoff one\n- a\n\n## Handoff two\n- b\n",
    )
    out = ctx.prepare_session(tmp_path)
    assert out["ok"] is True
    assert out.get("degraded") is True
    assert out.get("shape_errors")
    prompt = Path(out["prompt_file"]).read_text(encoding="utf-8")
    assert "Context degraded" in prompt


def test_prepare_clears_blocked_and_continues(tmp_path: Path, monkeypatch) -> None:
    # BLOCKED: left by a previous session must be stripped so the loop retries
    # rather than halting permanently with "LOOP COMPLETE (stop marker)".
    ctx = _load_ctx()
    monkeypatch.setenv("DEV_HUB", str(tmp_path / "hub"))
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("HUB_ROOT", raising=False)
    _seed_context(tmp_path)
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n"
        "1. memory-bank/back/plan/"
        "decompose-T-036-session-checkpoint-resume/"
        "s03-dirty-resume-extend.yaml\n\n"
        "## Handoff\nBLOCKED: verify_no_verdict\n",
    )
    out = ctx.prepare_session(tmp_path)
    # prepare should now succeed (ok=True) and the marker should be gone
    assert out.get("ok") is True
    ac = (tmp_path / "memory-bank" / "activeContext.md").read_text()
    assert "BLOCKED" not in ac


def test_prepare_recovers_projection_conflict_by_clearing_checkpoint(
    tmp_path: Path, monkeypatch
) -> None:
    """Stale committed checkpoint after AC rewrite must not halt prepare."""
    ctx = _load_ctx()
    monkeypatch.setenv("DEV_HUB", str(tmp_path / "hub"))
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("HUB_ROOT", raising=False)
    decompose = "memory-bank/back/plan/decompose-demo/index.yaml"
    _write(
        tmp_path,
        decompose,
        "schema: epic-decompose-index/v1\n"
        "plan_id: demo\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-one.yaml\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  title: one\n"
        "  status: pending\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/s01-one.yaml",
        "schema: epic-decompose/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: one\nnext_phase: BACK IMPLEMENT\nneeds_creative: \"no\"\n"
        "goal: x\ncontext: {}\ndelta: []\ndeletes: []\nout_of_scope: []\n"
        "skills: {}\ncheckpoints:\n- id: cp1\n  criterion: x\n  verify: echo\n"
        "tdd: []\n",
    )
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n"
        "1. [s01-one.yaml](back/plan/decompose-demo/s01-one.yaml)\n"
        "2. [index.yaml](back/plan/decompose-demo/index.yaml)\n\n"
        "## Handoff BACK IMPLEMENT — s01\n"
        "- **Эпик:** demo\n"
        "- **Текущий шаг:** s01\n",
    )
    from epic import (
        checkpoint_lifecycle,
        load_epic_state,
        save_epic_state,
        checkpoint_path,
    )

    st = load_epic_state(tmp_path)
    st["active"] = True
    st["status"] = "armed"
    st["armed_epic"] = "demo"
    st["armed_decompose"] = decompose
    st["armed_step"] = "s01"
    st["role"] = "BACK"
    st["session_id"] = "sess-projection-conflict"
    save_epic_state(tmp_path, st)
    checkpoint_lifecycle(
        tmp_path,
        checkpoint_id="sess:s01",
        session_id="sess-projection-conflict",
        runner_id="test",
        identity={"epic": "demo", "role": "BACK", "step": "s01", "action": "invoke"},
        step_id="s01",
        phase="BACK IMPLEMENT",
        phase_epoch="epoch-1",
        projection_hash="sha256:stale-projection",
        index_fingerprint="sha256:stale-index",
        context_fingerprint="stale-context",
        stage="committed",
        status="committed",
        next_action="advance",
        resume_policy="next_step",
    )
    assert checkpoint_path(tmp_path).is_file()

    out = ctx.prepare_session(tmp_path)
    assert out.get("ok") is True, out
    assert out.get("halt") is not True
    # prepare rewrites a fresh prepared checkpoint
    assert checkpoint_path(tmp_path).is_file()


def test_prepare_clears_stale_post_implement_checkpoint(
    tmp_path: Path, monkeypatch
) -> None:
    """QA committed same_step must not halt prepare when lifecycle is DONE."""
    ctx = _load_ctx()
    monkeypatch.setenv("DEV_HUB", str(tmp_path / "hub"))
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("HUB_ROOT", raising=False)
    epic = "T-HUB-015-dsh-board-arm-loop"
    decompose = f"memory-bank/back/plan/decompose-{epic}/index.yaml"
    _write(
        tmp_path,
        decompose,
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic}\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-one.yaml\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  title: one\n"
        "  status: completed\n",
    )
    _write(
        tmp_path,
        f"memory-bank/back/plan/decompose-{epic}/s01-one.yaml",
        "schema: epic-decompose/v1\nrole: back\nstep_id: s01\n",
    )
    _write(
        tmp_path,
        f"memory-bank/back/implement/implement-{epic}/s01-one.yaml",
        "schema: epic-implement/v1\nrole: back\nstep_id: s01\n"
        f"plan_id: {epic}\ntitle: s01 — one IMPLEMENT\nstatus: completed\n"
        f"decompose_ref: memory-bank/back/plan/decompose-{epic}/s01-one.yaml\n"
        "date: '2026-08-29'\n",
    )
    _write(
        tmp_path,
        f"memory-bank/back/audit/{epic}/audit-20260829-demo.yaml",
        "schema: epic-audit/v1\n",
    )
    _write(
        tmp_path,
        f"memory-bank/back/qa/{epic}/qa-20260829-board-arm-loop.yaml",
        "schema: epic-qa/v1\nverdict: pass\nissues: []\n",
    )
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n"
        f"1. [qa-20260829-board-arm-loop.yaml](back/qa/{epic}/qa-20260829-board-arm-loop.yaml)\n"
        f"2. [index.yaml](back/plan/decompose-{epic}/index.yaml)\n\n"
        f"## Handoff BACK QA — {epic}\n"
        f"- **Эпик:** {epic}.\n"
        "- **Режим/шаг:** `BACK QA`.\n",
    )
    from epic import (
        checkpoint_lifecycle,
        checkpoint_path,
        load_epic_state,
        save_epic_state,
    )

    st = load_epic_state(tmp_path)
    st["active"] = True
    st["status"] = "running"
    st["armed_epic"] = epic
    st["armed_decompose"] = decompose
    st["armed_step"] = "QA"
    st["role"] = "BACK"
    st["phase"] = "QA"
    save_epic_state(tmp_path, st)
    checkpoint_lifecycle(
        tmp_path,
        checkpoint_id="sess23:QA",
        session_id="sess23",
        identity={
            "action": "invoke",
            "epic": epic,
            "role": "BACK",
            "step": "QA",
        },
        step_id="QA",
        phase="QA",
        phase_epoch="1",
        stage="committed",
        status="committed",
        next_action="resume",
        resume_policy="same_step",
    )
    assert checkpoint_path(tmp_path).is_file()

    out = ctx.prepare_session(tmp_path, model="gpt")
    assert out.get("complete") is True, out
    assert out.get("stop") == "EPIC_DONE"


def test_check_after_commits_next_step_for_post_implement_phase(
    tmp_path: Path, monkeypatch
) -> None:
    ctx = _load_ctx()
    monkeypatch.setenv("DEV_HUB", str(tmp_path / "hub"))
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("HUB_ROOT", raising=False)
    epic = "demo"
    decompose = "memory-bank/back/plan/decompose-demo/index.yaml"
    _write(
        tmp_path,
        decompose,
        "schema: epic-decompose-index/v1\n"
        "plan_id: demo\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-one.yaml\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  title: one\n"
        "  status: completed\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/s01-one.yaml",
        "schema: epic-decompose/v1\nrole: back\nstep_id: s01\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/implement/implement-demo/s01-one.yaml",
        "schema: epic-implement/v1\nrole: back\nstep_id: s01\n"
        "plan_id: demo\ntitle: s01 — one IMPLEMENT\nstatus: completed\n"
        "decompose_ref: memory-bank/back/plan/decompose-demo/s01-one.yaml\n"
        "date: '2026-08-29'\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/audit/demo/audit-20260829-demo.yaml",
        "schema: epic-audit/v1\n",
    )
    _write(
        tmp_path,
        f"memory-bank/back/qa/{epic}/qa-20260829-demo.yaml",
        "schema: epic-qa/v1\nverdict: pass\nissues: []\n",
    )
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: QA\n"
        "epic_id: demo\n"
        "step_id: QA\n"
        "---\n\n"
        "## load_now\n"
        f"1. [qa-20260829-demo.yaml](back/qa/{epic}/qa-20260829-demo.yaml)\n"
        f"2. [index.yaml]({decompose})\n\n"
        "## Handoff BACK QA — demo\n"
        "- **Эпик:** demo.\n"
        "- **Режим/шаг:** `BACK QA` завершён, QA pass.\n"
        "- **Дальше:** выполнить `BACK REFLECT`.\n",
    )
    from epic import checkpoint_lifecycle, checkpoint_path, load_epic_state, save_epic_state

    st = load_epic_state(tmp_path)
    st["active"] = True
    st["status"] = "running"
    st["armed_epic"] = epic
    st["armed_decompose"] = decompose
    st["armed_step"] = "QA"
    st["role"] = "BACK"
    st["phase"] = "QA"
    save_epic_state(tmp_path, st)
    checkpoint_lifecycle(
        tmp_path,
        checkpoint_id="prepare-qa:QA",
        session_id="prepare-qa",
        identity={
            "action": "invoke",
            "epic": epic,
            "role": "BACK",
            "step": "QA",
        },
        step_id="QA",
        phase="QA",
        phase_epoch="1",
        stage="prepared",
        status="active",
        next_action="invoke",
        resume_policy="same_step",
        context_fingerprint="before-fp",
    )
    before_text = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: QA\n"
        "epic_id: demo\n"
        "step_id: QA\n"
        "---\n\n"
        "## load_now\n"
        f"1. [index.yaml]({decompose})\n\n"
        "## Handoff BACK QA — demo\n"
        "- **Режим/шаг:** `BACK QA` in progress.\n"
    )
    after = ctx.check_after(
        tmp_path,
        fingerprint_before=ctx.fingerprint_context(before_text),
    )
    assert after.get("ok") is True, after
    cp = json.loads(checkpoint_path(tmp_path).read_text(encoding="utf-8"))
    assert cp.get("resume_policy") == "next_step"
    assert cp.get("stage") == "committed"
    assert after.get("post_implement_phase") == "DONE"


def test_arm_clears_stale_checkpoint(tmp_path: Path, monkeypatch) -> None:
    ctx = _load_ctx()
    monkeypatch.setenv("DEV_HUB", str(tmp_path / "hub"))
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("HUB_ROOT", raising=False)
    decompose = "memory-bank/back/plan/decompose-demo/index.yaml"
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/index.md",
        "| step_id | title | next_phase | status |\n"
        "| :--- | :--- | :--- | :--- |\n"
        "| **s01** | one · [yaml](s01-one.yaml) | BACK IMPLEMENT | pending |\n",
    )
    _write(
        tmp_path,
        decompose,
        "schema: epic-decompose-index/v1\n"
        "plan_id: demo\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-one.yaml\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  title: one\n"
        "  status: pending\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/s01-one.yaml",
        "schema: epic-decompose/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: one\nnext_phase: BACK IMPLEMENT\nneeds_creative: \"no\"\n"
        "goal: x\ncontext: {}\ndelta: []\ndeletes: []\nout_of_scope: []\n"
        "skills: {}\ncheckpoints:\n- id: cp1\n  criterion: x\n  verify: echo\n"
        "tdd: []\n",
    )
    from epic import checkpoint_lifecycle, checkpoint_path, load_epic_state, save_epic_state

    st = load_epic_state(tmp_path)
    st["active"] = True
    st["armed_epic"] = "demo"
    st["armed_step"] = "s01"
    save_epic_state(tmp_path, st)
    checkpoint_lifecycle(
        tmp_path,
        checkpoint_id="old:s01",
        session_id="old",
        runner_id="test",
        identity={"epic": "demo", "role": "BACK", "step": "s01"},
        step_id="s01",
        phase="BACK IMPLEMENT",
        phase_epoch="e",
        projection_hash="sha256:old",
        context_fingerprint="oldfp",
        stage="committed",
        status="committed",
        next_action="advance",
        resume_policy="next_step",
    )
    assert checkpoint_path(tmp_path).is_file()
    out = ctx.arm_session(tmp_path, decompose)
    assert out.get("ok") is True, out
    assert not checkpoint_path(tmp_path).exists()


def test_coerce_verify_demotes_pass_when_checkpoints_pending(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DEV_HUB", str(tmp_path / "hub"))
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("HUB_ROOT", raising=False)
    from epic import load_epic_state, save_epic_state
    from epic.core import coerce_verify_verdict

    decompose = "memory-bank/back/plan/decompose-demo/index.yaml"
    _write(
        tmp_path,
        decompose,
        "schema: epic-decompose-index/v1\nplan_id: demo\nsteps:\n"
        "- id: s01\n  file: s01-one.yaml\n  next_phase: BACK IMPLEMENT\n"
        "  title: one\n  status: pending\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/implement/implement-demo/s01-one.yaml",
        "schema: epic-implement/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: one\nstatus: in_progress\ndate: '2026-08-22'\n"
        "done: []\nfiles: []\ntests: []\nintegration_check: []\n"
        "gaps:\n  status: blocked\n  items: [parity incomplete]\n"
        "checkpoints:\n"
        "- id: cp1\n  criterion: parity pass\n  status: pending\n"
        "- id: cp2\n  criterion: other\n  status: done\n",
    )
    st = load_epic_state(tmp_path)
    st["active"] = True
    st["armed_epic"] = "demo"
    st["armed_decompose"] = decompose
    st["armed_step"] = "s01"
    st["role"] = "BACK"
    save_epic_state(tmp_path, st)

    effective, blockers = coerce_verify_verdict(tmp_path, "PASS")
    assert effective == "FAIL"
    assert any("checkpoints not done" in b for b in blockers)
    assert any("gaps" in b for b in blockers)


def test_incomplete_step_fix_blocks_forbids_blocked_spin() -> None:
    ctx = _load_ctx()
    block = "\n".join(ctx._incomplete_step_fix_blocks(Path("/nonexistent")))
    assert block == ""
    source = (ROOT / "loop" / "context_loop.py").read_text(encoding="utf-8")
    assert "FORBIDDEN: `BLOCKED:`" in source
    assert "_incomplete_step_fix_blocks" in source
    assert 'if extra_phase_kind in {"implement", "generic"}:' in source


def test_check_after_finish_integrity_wire() -> None:
    source = (ROOT / "loop" / "context_loop.py").read_text(encoding="utf-8")

    assert "validate_finish_integrity" in source
    assert '"diagnostic_codes": finish_integrity["diagnostic_codes"]' in source


def test_prepare_syncs_cursor_from_index_yaml_sot(tmp_path: Path) -> None:
    """AC/armed_step lag behind index.yaml — prepare rewrites from yaml SoT."""
    ctx = _load_ctx()
    decompose = "memory-bank/back/plan/decompose-demo/index.yaml"
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/index.md",
        "| step_id | title | next_phase | status |\n"
        "| :--- | :--- | :--- | :--- |\n"
        "| **s01** | one · [yaml](s01-one.yaml) | BACK IMPLEMENT | completed |\n"
        "| **s02** | two · [yaml](s02-two.yaml) | BACK IMPLEMENT | pending |\n",
    )
    _write(
        tmp_path,
        decompose,
        "schema: epic-decompose-index/v1\n"
        "plan_id: demo\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-one.yaml\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  title: one\n"
        "  status: completed\n"
        "- id: s02\n"
        "  file: s02-two.yaml\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  title: two\n"
        "  status: pending\n",
    )
    _write(tmp_path, "memory-bank/back/plan/decompose-demo/s01-one.yaml", "step_id: s01\n")
    _write(tmp_path, "memory-bank/back/plan/decompose-demo/s02-two.yaml", "step_id: s02\n")
    _write(
        tmp_path,
        "memory-bank/back/implement/implement-demo/s01-one.yaml",
        "schema: epic-implement/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: one\nstatus: completed\ndate: '2026-08-16'\n"
        "done: [x]\nfiles: [a.py]\ntests: ['timeout 300s .venv/bin/pytest -q']\n"
        "integration_check: [ok]\n"
        "checkpoints:\n- id: cp1\n  criterion: x\n  status: done\n",
    )
    # Stale cursors: AC + armed still on s01, checkpoint on s01
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n"
        "1. [s01-one.yaml](back/plan/decompose-demo/s01-one.yaml)\n"
        "2. [index.yaml](back/plan/decompose-demo/index.yaml)\n\n"
        "## Handoff\n- stuck on s01\n",
    )
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        json.dumps(
            {
                "armed_decompose": decompose,
                "armed_step": "s01",
                "armed_epic": "demo",
                "status": "armed",
                "active": True,
                "role": "BACK",
            }
        )
        + "\n",
    )
    _write(
        tmp_path,
        ".claude/runtime/epic/checkpoint.json",
        json.dumps(
            {
                "schema": "loop-checkpoint/v1",
                "checkpoint_id": "stale",
                "checkpoint_seq": 1,
                "session_id": "stale",
                "runner_id": "",
                "identity": {
                    "epic": "demo",
                    "role": "BACK",
                    "step": "s01",
                    "action": "invoke",
                },
                "step_id": "s01",
                "phase": "BACK IMPLEMENT",
                "phase_epoch": "x",
                "projection_hash": "sha256:old",
                "stage": "prepared",
                "status": "active",
                "next_action": "invoke",
                "resume_policy": "same_step",
                "updated_at": "2026-08-16T00:00:00Z",
            }
        )
        + "\n",
    )

    prep = ctx.prepare_session(tmp_path)

    assert prep.get("ok") is True
    sync = prep.get("cursor_sync") or {}
    assert sync.get("synced") is True
    assert sync.get("step_id") == "s02"
    assert prep.get("armed_step") == "s02"
    ac = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert "s02-two.yaml" in ac
    assert "s01-one.yaml" not in ac.split("## Handoff")[0]


def test_check_after_fingerprint_stall_retries_then_halts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EPIC_DEGRADED_MAX", "2")
    ctx = _load_ctx()
    _seed_context(tmp_path)
    prep = ctx.prepare_session(tmp_path)
    assert prep["ok"]
    after1 = ctx.check_after(tmp_path, fingerprint_before=prep["fingerprint"])
    assert after1.get("ok") is True
    assert after1.get("halt") is not True
    assert after1.get("retry_fingerprint_stall") is True
    assert after1.get("fingerprint_stall_count") == 1
    assert "fingerprint" in (after1.get("reason") or "").lower()

    after2 = ctx.check_after(tmp_path, fingerprint_before=prep["fingerprint"])
    assert after2.get("halt") is True
    assert after2.get("ok") is False
    stop = after2.get("stop") or after2.get("reason") or ""
    assert stop.startswith("NEED_HUMAN:")
    assert after2.get("fingerprint_stall_count") == 2


def test_check_after_repairs_fingerprint_stall_via_evidence(tmp_path: Path) -> None:
    """Agent finished step (files+cps) but forgot Handoff → auto finalize + advance."""
    ctx = _load_ctx()
    hooks = str(ROOT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)

    decompose = "memory-bank/back/plan/decompose-demo/index.yaml"
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/index.md",
        "| step_id | title | next_phase | status |\n"
        "| :--- | :--- | :--- | :--- |\n"
        "| **s01** | one · [yaml](s01-one.yaml) | BACK IMPLEMENT | pending |\n"
        "| **s02** | two · [yaml](s02-two.yaml) | BACK IMPLEMENT | pending |\n",
    )
    _write(
        tmp_path,
        decompose,
        "schema: epic-decompose-index/v1\n"
        "plan_id: demo\n"
        "status_canon: index.yaml\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-one.yaml\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  title: one\n"
        "  status: pending\n"
        "- id: s02\n"
        "  file: s02-two.yaml\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  title: two\n"
        "  status: pending\n",
    )
    _write(tmp_path, "memory-bank/back/plan/decompose-demo/s01-one.yaml", "step_id: s01\n")
    _write(tmp_path, "memory-bank/back/plan/decompose-demo/s02-two.yaml", "step_id: s02\n")
    _write(tmp_path, "core/demo_mod.py", "X = 1\n")
    _write(
        tmp_path,
        "memory-bank/back/implement/implement-demo/s01-one.yaml",
        "schema: epic-implement/v1\n"
        "role: back\n"
        "step_id: s01\n"
        "plan_id: demo\n"
        "title: one\n"
        "status: in_progress\n"
        "date: '2026-08-16'\n"
        "done:\n- shipped\n"
        "files:\n- core/demo_mod.py\n"
        "tests:\n- 'timeout 300s .venv/bin/pytest -q'\n"
        "integration_check:\n- ok\n"
        "checkpoints:\n"
        "- id: cp1\n"
        "  criterion: x\n"
        "  status: done\n"
        "  done_at: '2026-08-16T00:00:00Z'\n",
    )
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n"
        "1. [s01-one.yaml](back/plan/decompose-demo/s01-one.yaml)\n"
        "2. [index.yaml](back/plan/decompose-demo/index.yaml)\n\n"
        "## Handoff\n- **Режим/шаг:** BACK IMPLEMENT `s01`\n",
    )
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        json.dumps(
            {
                "armed_decompose": decompose,
                "armed_step": "s01",
                "armed_epic": "demo",
                "status": "running",
                "active": True,
            }
        )
        + "\n",
    )

    fp_before = ctx.fingerprint_context(
        (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    )
    after = ctx.check_after(tmp_path, fingerprint_before=fp_before)

    assert after.get("ok") is True
    assert after.get("halt") is not True
    repair = after.get("fingerprint_repair") or {}
    assert repair.get("repaired") is True
    assert repair.get("mode") == "finalize_evidence"
    ac = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert "s02-two.yaml" in ac
    idx = (tmp_path / decompose).read_text(encoding="utf-8")
    assert "id: s01" in idx and "status: completed" in idx


def test_check_after_repairs_fingerprint_when_index_already_completed(
    tmp_path: Path,
) -> None:
    ctx = _load_ctx()
    decompose = "memory-bank/back/plan/decompose-demo/index.yaml"
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/index.md",
        "| step_id | title | next_phase | status |\n"
        "| :--- | :--- | :--- | :--- |\n"
        "| **s01** | one · [yaml](s01-one.yaml) | BACK IMPLEMENT | completed |\n"
        "| **s02** | two · [yaml](s02-two.yaml) | BACK IMPLEMENT | pending |\n",
    )
    _write(
        tmp_path,
        decompose,
        "schema: epic-decompose-index/v1\n"
        "plan_id: demo\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-one.yaml\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  title: one\n"
        "  status: completed\n"
        "- id: s02\n"
        "  file: s02-two.yaml\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  title: two\n"
        "  status: pending\n",
    )
    _write(tmp_path, "memory-bank/back/plan/decompose-demo/s01-one.yaml", "step_id: s01\n")
    _write(tmp_path, "memory-bank/back/plan/decompose-demo/s02-two.yaml", "step_id: s02\n")
    _write(
        tmp_path,
        "memory-bank/back/implement/implement-demo/s01-one.yaml",
        "schema: epic-implement/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: one\nstatus: completed\ndate: '2026-08-16'\n"
        "done: [x]\nfiles: [a.py]\ntests: ['timeout 300s .venv/bin/pytest -q']\n"
        "integration_check: [ok]\n"
        "checkpoints:\n- id: cp1\n  criterion: x\n  status: done\n",
    )
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n"
        "1. [s01-one.yaml](back/plan/decompose-demo/s01-one.yaml)\n"
        "2. [index.yaml](back/plan/decompose-demo/index.yaml)\n\n"
        "## Handoff\n- stale on s01\n",
    )
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        json.dumps(
            {
                "armed_decompose": decompose,
                "armed_step": "s01",
                "armed_epic": "demo",
                "status": "running",
                "active": True,
            }
        )
        + "\n",
    )

    fp_before = ctx.fingerprint_context(
        (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    )
    after = ctx.check_after(tmp_path, fingerprint_before=fp_before)

    assert after.get("ok") is True
    repair = after.get("fingerprint_repair") or {}
    assert repair.get("mode") == "rearm_completed_step"
    assert "s02-two.yaml" in (tmp_path / "memory-bank/activeContext.md").read_text()


def test_check_after_continues_when_handoff_advanced(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    prep = ctx.prepare_session(tmp_path)
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: INTEG\n"
        "mode: IMPLEMENT\n"
        "epic_id: x\n"
        "step_id: e17\n"
        "---\n\n"
        "## load_now\n"
        "1. [e17.yaml](integration/plan/decompose-x/e17.yaml)\n"
        "2. [index.md](integration/implement/implement-x/index.md)\n\n"
        "## Handoff INTEG IMPLEMENT e16 done\n"
        "- **Следующий:** `INTEG IMPLEMENT e17`\n",
    )
    _write(tmp_path, "memory-bank/integration/plan/decompose-x/e17.yaml", "step_id: e17\n")
    after = ctx.check_after(tmp_path, fingerprint_before=prep["fingerprint"])
    assert after["ok"] is True
    assert after.get("complete") is False


def test_check_after_shape_broken_does_not_halt(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    prep = ctx.prepare_session(tmp_path)
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n1. a\n\n## Handoff A\n- x\n\n## Handoff B\n- y\n",
    )
    after = ctx.check_after(tmp_path, fingerprint_before=prep["fingerprint"])
    assert after["ok"] is True or after.get("degraded") is True
    assert after.get("halt") is not True or after.get("degraded") is True


def test_check_after_epic_done(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    # Full post-implement evidence required for EPIC_DONE
    _write(
        tmp_path,
        "memory-bank/integration/qa/x/qa-20260802-x.yaml",
        "schema: epic-qa/v1\nverdict: pass\nissues: []\n",
    )
    _write(
        tmp_path,
        "memory-bank/integration/reflection/reflection-x.md",
        "# Reflection x\nepic: x\n",
    )
    prep = ctx.prepare_session(tmp_path)
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n"
        "1. [index.md](integration/plan/decompose-x/index.md)\n"
        "2. [qa-20260802-x.yaml](integration/qa/x/qa-20260802-x.yaml)\n\n"
        "## Handoff INTEG\n"
        "EPIC_DONE\n"
        "- **Следующий:** ARCHIVE вручную\n",
    )
    # arm epic id "x" via state
    st = ctx.load_epic_state(tmp_path)
    st["armed_epic"] = "x"
    st["armed_decompose"] = "memory-bank/integration/plan/decompose-x/index.md"
    ctx.save_epic_state(tmp_path, st)
    _write(
        tmp_path,
        "memory-bank/integration/plan/decompose-x/index.md",
        "| step_id | title | status |\n| :--- | :--- | :--- |\n"
        "| **e16** | [e16-foo.yaml](e16-foo.yaml) | completed |\n",
    )
    after = ctx.check_after(tmp_path, fingerprint_before=prep["fingerprint"])
    assert after.get("complete") is True
    assert after.get("stop") == "EPIC_DONE"


def test_epic_done_accepts_backticks_and_list_forms() -> None:
    """Agents often write `- `EPIC_DONE``; stop-hook must still halt the loop."""
    ctx = _load_ctx()
    cases = [
        "EPIC_DONE",
        "- EPIC_DONE",
        "* EPIC_DONE",
        "**EPIC_DONE**",
        "- **EPIC_DONE**",
        "`EPIC_DONE`",
        "- `EPIC_DONE`",
        "* `EPIC_DONE`",
        "- **`EPIC_DONE`**",
        "- **Стоп:** `EPIC_DONE`.",
        "- **Стоп:** EPIC_DONE",
        "**Стоп:** `EPIC_DONE`",
        "- **Stop:** `EPIC_DONE`.",
    ]
    for marker in cases:
        text = f"## load_now\n1. x\n\n## Handoff\n{marker}\n- next: none\n"
        assert ctx.detect_stop_marker(text) == "EPIC_DONE", marker


def test_degraded_prompt_skips_other_epics_after_epic_done(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-other/index.md",
        "| step_id | title | status |\n| :--- | :--- | :--- |\n"
        "| **s01** | [s01.yaml](s01.yaml) | pending |\n",
    )
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n\n## Handoff BACK REFLECT\n"
        "- **Стоп:** `EPIC_DONE`.\n"
        "- await VAN / next T-xxx\n",
    )
    prompt = ctx.build_prompt(tmp_path, load_now=[], shape_errors=[])
    assert "decompose-other" not in prompt
    assert "epic finished" not in prompt
    assert "premature EPIC_DONE" in prompt


def test_check_after_epic_done_with_backticks(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    prep = ctx.prepare_session(tmp_path)
    _write(
        tmp_path,
        "memory-bank/integration/qa/x/qa-20260802-x.yaml",
        "schema: epic-qa/v1\nverdict: pass\nissues: []\n",
    )
    _write(
        tmp_path,
        "memory-bank/integration/reflection/reflection-x.md",
        "# Reflection x\nepic: x\n",
    )
    _write(
        tmp_path,
        "memory-bank/integration/plan/decompose-x/index.md",
        "| step_id | title | status |\n| :--- | :--- | :--- |\n"
        "| **e16** | [e16-foo.yaml](e16-foo.yaml) | completed |\n",
    )
    st = ctx.load_epic_state(tmp_path)
    st["armed_epic"] = "x"
    st["armed_decompose"] = "memory-bank/integration/plan/decompose-x/index.md"
    ctx.save_epic_state(tmp_path, st)
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n"
        "1. [index.md](integration/plan/decompose-x/index.md)\n\n"
        "## Handoff BACK QA\n"
        "- verdict: pass\n"
        "- `EPIC_DONE`\n",
    )
    after = ctx.check_after(tmp_path, fingerprint_before=prep["fingerprint"])
    assert after.get("complete") is True
    assert after.get("stop") == "EPIC_DONE"


def test_epic_done_rejected_without_qa_pass(tmp_path: Path) -> None:
    """HARD: EPIC_DONE without QA pass must not complete the loop."""
    ctx = _load_ctx()
    _seed_decompose_epic(tmp_path)
    _write(
        tmp_path,
        "memory-bank/integration/plan/decompose-demo/index.md",
        "| step_id | title | status |\n"
        "| :--- | :--- | :--- |\n"
        "| **e01** | [e01-one.yaml](e01-one.yaml) | completed |\n"
        "| **e02** | [e02-two.yaml](e02-two.yaml) | done |\n",
    )
    _write(
        tmp_path,
        "memory-bank/integration/audit/demo/audit-20260807-demo.yaml",
        "schema: epic-audit/v1\n",
    )
    ctx.arm_session(tmp_path, "decompose-demo")
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n1. [index.md](integration/plan/decompose-demo/index.md)\n\n"
        "## Handoff\nEPIC_DONE\n",
    )
    after = ctx.check_after(tmp_path, fingerprint_before="deadbeef")
    assert after.get("complete") is not True
    assert after.get("stop") != "EPIC_DONE"
    assert (
        after.get("rewrote_premature_epic_done")
        or after.get("reject_epic_done")
        or after.get("phase") == "QA"
    )
    gate = __import__("epic", fromlist=["epic_complete_allowed"]).epic_complete_allowed(
        tmp_path
    )
    # after rewrite, still not DONE
    assert gate.get("allowed") is False
    assert gate.get("phase") == "QA"


def _seed_decompose_epic(cwd: Path) -> None:
    _write(
        cwd,
        "memory-bank/integration/plan/decompose-demo/e01-one.yaml",
        "schema: epic-decompose/v1\nstep_id: e01\ntitle: one\n",
    )
    _write(
        cwd,
        "memory-bank/integration/plan/decompose-demo/e02-two.yaml",
        "schema: epic-decompose/v1\nstep_id: e02\ntitle: two\n",
    )
    _write(
        cwd,
        "memory-bank/integration/implement/implement-demo/index.md",
        "# Implement hub\n",
    )
    _write(
        cwd,
        "memory-bank/integration/implement/implement-demo/e01.yaml",
        "schema: epic-implement/v1\nrole: integ\nstep_id: e01\nplan_id: demo\n"
        "title: e01 — one IMPLEMENT\nstatus: completed\n"
        "implement_index: memory-bank/integration/implement/implement-demo/index.md\n"
        "date: '2026-08-10'\n",
    )
    _write(
        cwd,
        "memory-bank/integration/plan/decompose-demo/index.yaml",
        "schema: epic-decompose-index/v1\nplan_id: demo\nsteps:\n"
        "- id: e01\n  file: e01-one.yaml\n  status: completed\n"
        "- id: e02\n  file: e02-two.yaml\n  status: pending\n",
    )
    _write(
        cwd,
        "memory-bank/integration/plan/decompose-demo/index.md",
        "# Demo\n"
        "**Implement index:** [implement-demo/index.md](../../implement/implement-demo/index.md)\n\n"
        "| step_id | title | status |\n"
        "| :--- | :--- | :--- |\n"
        "| **e01** | [e01-one.yaml](e01-one.yaml) · INTEG IMPLEMENT | completed |\n"
        "| **e02** | [e02-two.yaml](e02-two.yaml) · INTEG IMPLEMENT | pending |\n",
    )
    _write(
        cwd,
        "memory-bank/activeContext.md",
        "## load_now\n1. other\n\n## Handoff OTHER\n"
        "BLOCKED: from another epic\n",
    )


def _write_e02_implement_completed(cwd: Path) -> None:
    _write(
        cwd,
        "memory-bank/integration/implement/implement-demo/e02.yaml",
        "schema: epic-implement/v1\nrole: integ\nstep_id: e02\nplan_id: demo\n"
        "title: e02 — two IMPLEMENT\nstatus: completed\n"
        "implement_index: memory-bank/integration/implement/implement-demo/index.md\n"
        "date: '2026-08-10'\n",
    )


def _mark_all_decompose_steps_done(cwd: Path) -> None:
    _write(
        cwd,
        "memory-bank/integration/plan/decompose-demo/index.yaml",
        "schema: epic-decompose-index/v1\nplan_id: demo\nsteps:\n"
        "- id: e01\n  file: e01-one.yaml\n  status: completed\n"
        "- id: e02\n  file: e02-two.yaml\n  status: done\n",
    )


def test_arm_overwrites_blocked_foreign_context(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_decompose_epic(tmp_path)
    out = ctx.arm_session(tmp_path, "decompose-demo")
    assert out["ok"] is True
    assert out.get("complete") is not True
    assert out["step_id"] == "e02"
    assert out["epic_id"] == "demo"
    assert "e02-two.yaml" in (out.get("work_shard") or "")
    text = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert "BLOCKED" not in text
    assert "e02" in text
    assert "decompose-demo" in text
    assert ctx.detect_stop_marker(text) is None
    prep = ctx.prepare_session(tmp_path, model="gpt")
    assert prep["ok"] is True
    assert any("e02-two.yaml" in p for p in prep["load_now"])


def test_arm_epic_done_when_all_completed(tmp_path: Path) -> None:
    """All implement done → arm to QA (not EPIC_DONE yet)."""
    ctx = _load_ctx()
    _seed_decompose_epic(tmp_path)
    _write(
        tmp_path,
        "memory-bank/integration/audit/demo/audit-20260807-demo.yaml",
        "schema: epic-audit/v1\n",
    )
    _write(
        tmp_path,
        "memory-bank/integration/plan/decompose-demo/index.md",
        "| step_id | title | status |\n"
        "| :--- | :--- | :--- |\n"
        "| **e01** | [e01-one.yaml](e01-one.yaml) | completed |\n"
        "| **e02** | [e02-two.yaml](e02-two.yaml) | done |\n",
    )
    _mark_all_decompose_steps_done(tmp_path)
    out = ctx.arm_session(tmp_path, "decompose-demo")
    assert out["ok"] is True
    assert out.get("complete") is not True
    assert out.get("phase") == "QA"
    text = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert ctx.detect_stop_marker(text) is None
    assert "Handoff INTEG QA" in text or "## Handoff INTEG QA" in text


def test_audit_phase_without_audit_artifact(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_decompose_epic(tmp_path)
    _write(
        tmp_path,
        "memory-bank/integration/plan/decompose-demo/index.md",
        "| step_id | title | status |\n"
        "| :--- | :--- | :--- |\n"
        "| **e01** | [e01-one.yaml](e01-one.yaml) | completed |\n"
        "| **e02** | [e02-two.yaml](e02-two.yaml) | done |\n",
    )
    _mark_all_decompose_steps_done(tmp_path)
    _write_e02_implement_completed(tmp_path)

    out = ctx.arm_session(tmp_path, "decompose-demo")

    assert out["ok"] is True
    assert out["phase"] == "AUDIT"
    assert out.get("complete") is not True
    text = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert ctx.detect_stop_marker(text) is None
    assert "Handoff INTEG AUDIT" in text
    projection = ctx.rebuild_epic_projection(tmp_path)["projection"]
    assert "audit" in (projection.get("expected_artifact") or "")
    prep = ctx.prepare_session(tmp_path, model="gpt")
    assert prep.get("complete") is not True
    assert prep["ok"] is True


def test_rebuild_projection_role_from_armed_decompose_not_stale_state(
    tmp_path: Path,
) -> None:
    ctx = _load_ctx()
    _seed_decompose_epic(tmp_path)
    _write(
        tmp_path,
        "memory-bank/integration/audit/demo/audit-20260807-demo.yaml",
        "schema: epic-audit/v1\n",
    )
    _write(
        tmp_path,
        "memory-bank/integration/plan/decompose-demo/index.md",
        "| step_id | title | status |\n"
        "| :--- | :--- | :--- |\n"
        "| **e01** | [e01-one.yaml](e01-one.yaml) | completed |\n"
        "| **e02** | [e02-two.yaml](e02-two.yaml) | done |\n",
    )
    _mark_all_decompose_steps_done(tmp_path)
    out = ctx.arm_session(tmp_path, "decompose-demo")
    assert out["ok"] is True
    assert out.get("role") in {"INTEG", "integration"}

    from epic import load_epic_state, save_epic_state

    st = load_epic_state(tmp_path)
    st["role"] = "FRONT"
    save_epic_state(tmp_path, st)

    projection = ctx.rebuild_epic_projection(tmp_path)["projection"]
    assert projection["role"] == "INTEG"
    assert projection["phase"] == "QA"
    assert "integration/qa/" in (projection.get("expected_artifact") or "")


def test_audit_to_qa_transition(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_decompose_epic(tmp_path)
    _write(
        tmp_path,
        "memory-bank/integration/plan/decompose-demo/index.md",
        "| step_id | title | status |\n"
        "| :--- | :--- | :--- |\n"
        "| **e01** | [e01-one.yaml](e01-one.yaml) | completed |\n"
        "| **e02** | [e02-two.yaml](e02-two.yaml) | done |\n",
    )
    _mark_all_decompose_steps_done(tmp_path)

    out_without_audit = ctx.arm_session(tmp_path, "decompose-demo")
    assert out_without_audit["phase"] == "AUDIT"

    _write(
        tmp_path,
        "memory-bank/integration/audit/demo/audit-20260807-demo.yaml",
        "schema: epic-audit/v1\n",
    )
    out_with_audit = ctx.arm_session(tmp_path, "decompose-demo")

    assert out_with_audit["phase"] == "QA"


def test_arm_done_when_qa_pass_exists(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_decompose_epic(tmp_path)
    _write(
        tmp_path,
        "memory-bank/integration/plan/decompose-demo/index.md",
        "| step_id | title | status |\n"
        "| :--- | :--- | :--- |\n"
        "| **e01** | [e01-one.yaml](e01-one.yaml) | completed |\n"
        "| **e02** | [e02-two.yaml](e02-two.yaml) | done |\n",
    )
    _write(
        tmp_path,
        "memory-bank/integration/qa/demo/qa-20260802-demo.yaml",
        "schema: epic-qa/v1\nverdict: pass\nissues: []\n",
    )
    _mark_all_decompose_steps_done(tmp_path)
    out = ctx.arm_session(tmp_path, "decompose-demo")
    assert out["ok"] is True
    assert out.get("complete") is True
    assert out.get("stop") == "EPIC_DONE"
    assert out.get("phase") == "DONE"
    text = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert "EPIC_DONE" in text


def test_arm_epic_done_after_qa_pass(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_decompose_epic(tmp_path)
    _write(
        tmp_path,
        "memory-bank/integration/plan/decompose-demo/index.md",
        "| step_id | title | status |\n"
        "| :--- | :--- | :--- |\n"
        "| **e01** | [e01-one.yaml](e01-one.yaml) | completed |\n"
        "| **e02** | [e02-two.yaml](e02-two.yaml) | done |\n",
    )
    _write(
        tmp_path,
        "memory-bank/integration/qa/demo/qa-20260802-demo.yaml",
        "schema: epic-qa/v1\nverdict: pass\nissues: []\n",
    )
    _write(
        tmp_path,
        "memory-bank/integration/reflection/reflection-demo.md",
        "# Reflection demo\nepic: demo\n",
    )
    _mark_all_decompose_steps_done(tmp_path)
    out = ctx.arm_session(tmp_path, "decompose-demo")
    assert out["ok"] is True
    assert out.get("complete") is True
    assert out.get("stop") == "EPIC_DONE"
    text = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert "EPIC_DONE" in text


def test_check_after_rewrites_premature_epic_done(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_decompose_epic(tmp_path)
    _write(
        tmp_path,
        "memory-bank/integration/audit/demo/audit-20260807-demo.yaml",
        "schema: epic-audit/v1\n",
    )
    _write(
        tmp_path,
        "memory-bank/integration/plan/decompose-demo/index.md",
        "| step_id | title | status |\n"
        "| :--- | :--- | :--- |\n"
        "| **e01** | [e01-one.yaml](e01-one.yaml) | completed |\n"
        "| **e02** | [e02-two.yaml](e02-two.yaml) | done |\n",
    )
    _mark_all_decompose_steps_done(tmp_path)
    # arm once to set armed_decompose in state, then force premature EPIC_DONE
    ctx.arm_session(tmp_path, "decompose-demo")
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n1. x\n\n## Handoff\nEPIC_DONE\n",
    )
    after = ctx.check_after(tmp_path, fingerprint_before="deadbeef")
    assert after.get("complete") is not True
    assert after.get("rewrote_premature_epic_done") is True
    assert after.get("phase") == "QA"
    text = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert ctx.detect_stop_marker(text) is None
    assert "QA" in text


def test_check_after_rewrites_premature_epic_done_to_audit(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_decompose_epic(tmp_path)
    _write(
        tmp_path,
        "memory-bank/integration/plan/decompose-demo/index.md",
        "| step_id | title | status |\n"
        "| :--- | :--- | :--- |\n"
        "| **e01** | [e01-one.yaml](e01-one.yaml) | completed |\n"
        "| **e02** | [e02-two.yaml](e02-two.yaml) | done |\n",
    )
    _mark_all_decompose_steps_done(tmp_path)
    _write_e02_implement_completed(tmp_path)
    ctx.arm_session(tmp_path, "decompose-demo")
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n1. x\n\n## Handoff\nEPIC_DONE\n",
    )
    after = ctx.check_after(tmp_path, fingerprint_before="deadbeef")
    assert after.get("complete") is not True
    assert after.get("rewrote_premature_epic_done") is True
    assert after.get("phase") == "AUDIT"
    text = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert ctx.detect_stop_marker(text) is None
    assert "AUDIT" in text
    prep = ctx.prepare_session(tmp_path, model="gpt")
    assert prep.get("complete") is not True
    assert prep["ok"] is True


def test_prepare_stale_complete_status_without_artifacts_does_not_finish(
    tmp_path: Path,
) -> None:
    ctx = _load_ctx()
    _seed_decompose_epic(tmp_path)
    _write(
        tmp_path,
        "memory-bank/integration/plan/decompose-demo/index.md",
        "| step_id | title | status |\n"
        "| :--- | :--- | :--- |\n"
        "| **e01** | [e01-one.yaml](e01-one.yaml) | completed |\n"
        "| **e02** | [e02-two.yaml](e02-two.yaml) | done |\n",
    )
    _mark_all_decompose_steps_done(tmp_path)
    _write_e02_implement_completed(tmp_path)
    ctx.arm_session(tmp_path, "decompose-demo")
    from epic import load_epic_state, save_epic_state

    st = load_epic_state(tmp_path)
    st["status"] = "complete"
    st["active"] = False
    save_epic_state(tmp_path, st)
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n1. [index.md](integration/plan/decompose-demo/index.md)\n\n"
        "## Handoff INTEG\nEPIC_DONE\n",
    )
    prep = ctx.prepare_session(tmp_path, model="gpt")
    assert prep.get("complete") is not True
    assert prep.get("stop") != "EPIC_DONE"
    text = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert ctx.detect_stop_marker(text) is None
    assert "AUDIT" in text


def test_degraded_prompt_epic_finished_only_after_qa_pass(
    tmp_path: Path,
) -> None:
    ctx = _load_ctx()
    _seed_decompose_epic(tmp_path)
    _write(
        tmp_path,
        "memory-bank/integration/plan/decompose-demo/index.md",
        "| step_id | title | status |\n"
        "| :--- | :--- | :--- |\n"
        "| **e01** | [e01-one.yaml](e01-one.yaml) | completed |\n"
        "| **e02** | [e02-two.yaml](e02-two.yaml) | done |\n",
    )
    _write(
        tmp_path,
        "memory-bank/integration/qa/demo/qa-20260802-demo.yaml",
        "schema: epic-qa/v1\nverdict: pass\nissues: []\n",
    )
    _write(
        tmp_path,
        "memory-bank/integration/reflection/reflection-demo.md",
        "# Reflection demo\nepic: demo\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-other/index.md",
        "| step_id | title | status |\n| :--- | :--- | :--- |\n"
        "| **s01** | [s01.yaml](s01.yaml) | pending |\n",
    )
    _mark_all_decompose_steps_done(tmp_path)
    out = ctx.arm_session(tmp_path, "decompose-demo")
    assert out.get("stop") == "EPIC_DONE"
    prompt = ctx.build_prompt(tmp_path, load_now=[], shape_errors=[])
    assert "decompose-other" not in prompt


def test_qa_and_audit_work_blocks_render_properly() -> None:
    ctx = _load_ctx()
    qa_block = ctx._qa_work_block("back", "demo-epic")
    assert "## QA canon (HARD)" in qa_block
    assert "back_developer" in qa_block
    assert "demo-epic" in qa_block

    audit_block = ctx._audit_work_block("back", "demo-epic")
    assert "## AUDIT canon (HARD)" in audit_block
    assert "back_developer" in audit_block
    assert "demo-epic" in audit_block


def test_bugfix_reopens_qa_after_prior_pass(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    _write(
        tmp_path,
        "memory-bank/integration/qa/demo/qa-20260802-demo.yaml",
        "schema: epic-qa/v1\nverdict: pass\nissues: []\n",
    )
    phase, qa, reflection = __import__(
        "epic", fromlist=["post_implement_phase"]
    ).post_implement_phase(tmp_path, "integration", "demo")
    assert phase == "DONE"
    assert qa is not None
    assert reflection is None

    _write(
        tmp_path,
        "memory-bank/integration/bugfix/demo/bugfix-20260803-fix.md",
        "# Fix\n",
    )

    phase, qa, reflection = __import__(
        "epic", fromlist=["post_implement_phase"]
    ).post_implement_phase(tmp_path, "integration", "demo")

    assert phase == "QA"
    assert qa is None
    assert reflection is None
    event_path = (
        tmp_path
        / "memory-bank/integration/events/demo/events.jsonl"
    )
    events = [
        json.loads(line)
        for line in event_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [event["kind"] for event in events] == [
        "qa_pass",
        "bugfix_done",
    ]
    assert events[0]["artifact"].endswith("qa-20260802-demo.yaml")


def test_event_log_is_idempotent_and_archives_old_events(tmp_path: Path) -> None:
    _load_ctx()
    _seed_context(tmp_path)
    event_lib = __import__("epic.core", fromlist=["_append_event"])
    artifact = tmp_path / "memory-bank/integration/qa/demo/qa.yaml"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("verdict: pass\n", encoding="utf-8")
    for index in range(40):
        item = tmp_path / f"memory-bank/integration/qa/demo/qa-{index}.yaml"
        item.write_text("verdict: pass\n", encoding="utf-8")
        event_lib._append_event(
            tmp_path, "integration", "demo", "qa_pass", item
        )
    event_lib._append_event(
        tmp_path, "integration", "demo", "qa_pass", artifact
    )
    event_lib._append_event(
        tmp_path, "integration", "demo", "qa_pass", artifact
    )
    event_path = (
        tmp_path
        / "memory-bank/integration/events/demo/events.jsonl"
    )
    assert len(event_path.read_text(encoding="utf-8").splitlines()) == 20
    archives = list(event_path.parent.glob("archive-*.jsonl"))
    assert len(archives) == 1
    assert archives[0].name == "archive-rollover.jsonl"


def test_record_abort_persists_transient_resume_marker(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        '{"status":"running", "armed_step":"e16"}\n',
    )
    log = tmp_path / "session.log"
    log.write_text(
        '{"type":"result","terminal_reason":"api_error","result":"API Error: terminated"}\n',
        encoding="utf-8",
    )

    out = ctx.record_abort(tmp_path, log_path=log, exit_code=1)

    assert out["retryable"] is True
    marker = (tmp_path / ".claude/runtime/epic/last-session.json")
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload["status"] == "aborted"
    assert payload["abort_kind"] == "transient"
    assert payload["reason"] == "API Error: terminated"
    assert payload["step_id"] == "e16"
    assert payload["resume_from"] == "e16"


def test_prepare_session_includes_aborted_resume_block(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        '{"status":"running", "armed_step":"e16"}\n',
    )
    _write(
        tmp_path,
        ".claude/runtime/epic/last-session.json",
        '{"status":"aborted","reason":"API Error: terminated","abort_kind":"transient",'
        '"resume_from":"e16"}\n',
    )

    out = ctx.prepare_session(tmp_path, model="gpt")
    prompt = Path(out["prompt_file"]).read_text(encoding="utf-8")

    assert "## resume_dirty (HARD)" in prompt
    assert "prev_session: aborted — API Error: terminated" in prompt
    assert "continue_from_checkpoint: e16" in prompt


def test_prepare_binds_runner_session_id(tmp_path: Path, monkeypatch) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        '{"status":"running", "armed_step":"e16", "session_id": null}\n',
    )
    monkeypatch.setenv("EPIC_RUNNER_SESSION_ID", "runner-loop-abc")

    out = ctx.prepare_session(tmp_path, model="gpt")
    assert out["ok"] is True
    assert out["checkpoint"] == "runner-loop-abc"
    from epic import load_epic_state

    st = load_epic_state(tmp_path)
    assert st["session_id"] == "runner-loop-abc"


def test_prepare_session_ignores_completed_resume_marker(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        '{"status":"running", "armed_step":"e16"}\n',
    )
    _write(
        tmp_path,
        ".claude/runtime/epic/last-session.json",
        '{"status":"completed","resume_from":"e16"}\n',
    )

    out = ctx.prepare_session(tmp_path, model="gpt")
    prompt = Path(out["prompt_file"]).read_text(encoding="utf-8")

    assert "## resume_dirty (HARD)" not in prompt


def test_record_abort_unknown_nonzero_is_fatal(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        '{"status":"running", "armed_step":"e16"}\n',
    )
    log = tmp_path / "session.log"
    log.write_text("ordinary process failure\n", encoding="utf-8")

    out = ctx.record_abort(tmp_path, log_path=log, exit_code=2)

    assert out["retryable"] is False
    assert out["abort_kind"] == "fatal"
    assert out["halted"] is True
    state = json.loads(
        (tmp_path / ".claude/runtime/epic/state.json").read_text(encoding="utf-8")
    )
    assert state["status"] == "halted"


def test_build_prompt_accepts_resume_lines(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)

    prompt = ctx.build_prompt(
        tmp_path,
        load_now=["memory-bank/integration/plan/decompose-x/e16-foo.yaml"],
        delta_ok=True,
        delta_paths=[],
        resume_lines=["## resume_dirty (HARD)", "prev_session: aborted"],
    )

    assert "## resume_dirty (HARD)" in prompt
    assert "prev_session: aborted" in prompt


def test_build_prompt_projection_schema(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)

    prompt = ctx.build_prompt(
        tmp_path,
        load_now=["memory-bank/integration/plan/decompose-x/e16-foo.yaml"],
        delta_ok=True,
        delta_paths=[],
        projection={
            "phase": "BACK IMPLEMENT",
            "epic": "T-039-loop-audit-remediation",
            "next_step": "s03",
            "expected_artifact": "decompose step s03 artifact",
            "projection_hash": "hash-039",
            "phase_epoch": 7,
        },
    )

    for field in (
        "phase",
        "epic",
        "step",
    ):
        assert f"{field}:" in prompt
    assert "- step: `s03`" in prompt
    assert "expected_artifact:" not in prompt
    assert "projection_hash:" not in prompt
    assert "phase_epoch:" not in prompt
    assert "hash-039" not in prompt


def test_prompt_projection_fills_step_from_armed_step(tmp_path: Path) -> None:
    ctx = _load_ctx()
    from epic.core import save_epic_state

    save_epic_state(
        tmp_path,
        {
            "armed_epic": "T-050-partner-rules-alembic-port",
            "armed_step": "s04",
            "role": "BACK",
        },
    )
    merged = ctx._prompt_projection(
        {"armed_epic": "T-050-partner-rules-alembic-port", "armed_step": "s04", "role": "BACK"},
        {
            "phase": "BACK IMPLEMENT",
            "epic": "T-050-partner-rules-alembic-port",
            "projection": {
                "phase": "BACK IMPLEMENT",
                "epic": "T-050-partner-rules-alembic-port",
            },
        },
    )
    assert merged["step"] == "s04"
    assert merged["next_step"] == "s04"

    prompt = ctx.build_prompt(
        tmp_path,
        load_now=["memory-bank/activeContext.md"],
        projection=merged,
    )
    assert "- step: `s04`" in prompt



def test_record_abort_clean_marks_session_completed(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    log = tmp_path / "session.log"
    log.write_text("clean session output\n", encoding="utf-8")

    out = ctx.record_abort(tmp_path, log_path=log, exit_code=0)

    assert out["ok"] is True
    payload = json.loads(
        (tmp_path / ".claude/runtime/epic/last-session.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"] == "completed"
    assert payload["reason"] is None

def test_record_abort_process_interrupt_is_fatal(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    log = tmp_path / "session.log"
    log.write_text("", encoding="utf-8")

    out = ctx.record_abort(tmp_path, log_path=log, exit_code=130)

    assert out["retryable"] is False
    assert out["abort_kind"] == "fatal"
    assert out["halted"] is True



def test_record_abort_exposes_outcome_and_resume_contract(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        '{"status":"running", "armed_step":"s03"}\n',
    )
    log = tmp_path / "session.log"
    log.write_text("malformed stream-json result\n", encoding="utf-8")

    out = ctx.record_abort(tmp_path, log_path=log, exit_code=1)
    payload = json.loads(
        (tmp_path / ".claude/runtime/epic/last-session.json").read_text(
            encoding="utf-8"
        )
    )

    assert out["outcome"] == "malformed_result"
    assert out["retryable"] is False
    assert payload["outcome"] == "malformed_result"
    assert payload["resume_from"] == "s03"
    assert payload["status"] == "aborted"


def test_record_abort_timeout_is_transient(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    log = tmp_path / "session.log"
    log.write_text("", encoding="utf-8")

    out = ctx.record_abort(tmp_path, log_path=log, exit_code=124)

    assert out["retryable"] is True
    assert out["abort_kind"] == "transient"
    assert out["halted"] is False


def test_loop_shell_skips_check_after_on_retry_cap() -> None:
    script = (ROOT / "loop" / "loop.sh").read_text(encoding="utf-8")
    assert "resume_outer=0" in script
    assert "resume_outer=1" in script
    assert 'if [[ "$resume_outer" -eq 1 ]]; then' in script
    assert "continue" in script


def test_loop_shell_reprepares_on_transient_retry() -> None:
    """Transient retry must call prepare again so armed_step matches index.yaml SoT."""
    script = (ROOT / "loop" / "loop.sh").read_text(encoding="utf-8")
    assert "_reprepare_for_transient_retry" in script
    transient_block = script.split("TRANSIENT API abort — retry after", 1)[1].split(
        "if [[ \"$retryable\" == \"1\" ]]; then", 1
    )[0]
    assert "_reprepare_for_transient_retry" in transient_block
    assert "armed_step resynced" in script


def test_record_abort_resyncs_armed_step_on_retryable_abort(tmp_path: Path) -> None:
    """Retryable abort syncs armed_step from index before resume marker."""
    ctx = _load_ctx()
    decompose = "memory-bank/back/plan/decompose-demo/index.yaml"
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/index.md",
        "| step_id | title | next_phase | status |\n"
        "| :--- | :--- | :--- | :--- |\n"
        "| **s01** | one · [yaml](s01-one.yaml) | BACK IMPLEMENT | completed |\n"
        "| **s02** | two · [yaml](s02-two.yaml) | BACK IMPLEMENT | pending |\n",
    )
    _write(
        tmp_path,
        decompose,
        "schema: epic-decompose-index/v1\n"
        "plan_id: demo\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-one.yaml\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  title: one\n"
        "  status: completed\n"
        "- id: s02\n"
        "  file: s02-two.yaml\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  title: two\n"
        "  status: pending\n",
    )
    _write(tmp_path, "memory-bank/back/plan/decompose-demo/s01-one.yaml", "step_id: s01\n")
    _write(tmp_path, "memory-bank/back/plan/decompose-demo/s02-two.yaml", "step_id: s02\n")
    _write(
        tmp_path,
        "memory-bank/back/implement/implement-demo/s01-one.yaml",
        "schema: epic-implement/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: one\nstatus: completed\ndate: '2026-08-16'\n"
        "done: [x]\nfiles: [a.py]\ntests: ['timeout 300s .venv/bin/pytest -q']\n"
        "integration_check: [ok]\n"
        "checkpoints:\n- id: cp1\n  criterion: x\n  status: done\n",
    )
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n"
        "1. [s01-one.yaml](back/plan/decompose-demo/s01-one.yaml)\n"
        "2. [index.yaml](back/plan/decompose-demo/index.yaml)\n\n"
        "## Handoff\n- stuck on s01\n",
    )
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        json.dumps(
            {
                "armed_decompose": decompose,
                "armed_step": "s01",
                "armed_epic": "demo",
                "status": "running",
                "active": True,
                "role": "BACK",
            }
        )
        + "\n",
    )
    log = tmp_path / "session.log"
    log.write_text(
        "SESSION_START session=1 mode=headless command=claude\n"
        '{"type":"stream_event","event":{"type":"message_start"}}\n'
        '{"type":"stream_event","event":{"type":"message_stop"}}\n'
        "SESSION_END session=1 exit_code=0 elapsed=12.0s\n",
        encoding="utf-8",
    )

    out = ctx.record_abort(tmp_path, log_path=log, exit_code=0)

    assert out["retryable"] is True
    sync = out.get("cursor_sync") or {}
    assert sync.get("synced") is True
    assert sync.get("step_id") == "s02"
    st = json.loads(
        (tmp_path / ".claude/runtime/epic/state.json").read_text(encoding="utf-8")
    )
    assert st.get("armed_step") == "s02"
    marker = json.loads(
        (tmp_path / ".claude/runtime/epic/last-session.json").read_text(encoding="utf-8")
    )
    assert marker.get("step_id") == "s02"
    assert marker.get("resume_from") == "s02"


def test_prepare_keeps_analyze_when_gate_pending(tmp_path: Path, monkeypatch) -> None:
    ctx = _load_ctx()
    monkeypatch.setenv("DEV_HUB", str(tmp_path / "hub"))
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("HUB_ROOT", raising=False)
    epic = "T-HUB-027-back-plan-gstack-adapt"
    _write(tmp_path, f"memory-bank/back/plan/plan-{epic}.md", "# plan\n")
    decomp = f"memory-bank/back/plan/decompose-{epic}"
    _write(
        tmp_path,
        f"{decomp}/index.yaml",
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic}\n"
        "steps:\n"
        "- id: s01\n  file: s01-clarify-product-probe.yaml\n  status: pending\n",
    )
    _write(
        tmp_path,
        f"{decomp}/index.md",
        "| step_id | status |\n| s01 | pending |\n",
    )
    _write(
        tmp_path,
        f"{decomp}/s01-clarify-product-probe.yaml",
        "schema: epic-decompose/v1\nstep_id: s01\n",
    )
    arm = ctx.arm_epic(tmp_path, epic, role="back")
    assert arm.get("ok") is True
    assert arm.get("phase") == "ANALYZE"
    prep = ctx.prepare_session(tmp_path, model="test-model")
    assert prep.get("ok") is True, prep
    text = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert "ANALYZE" in text
    assert "s01-clarify-product-probe.yaml" not in text
    assert prep.get("loop_phase") == "ANALYZE"
    assert "ANALYZE" in str(prep.get("phase") or "")


def test_prepare_promotes_analyze_to_implement_when_gate_passes(
    tmp_path: Path, monkeypatch
) -> None:
    ctx = _load_ctx()
    monkeypatch.setenv("DEV_HUB", str(tmp_path / "hub"))
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("HUB_ROOT", raising=False)
    epic = "T-050-partner-rules-alembic-port"
    _write(tmp_path, f"memory-bank/back/plan/plan-{epic}.md", "# plan\n")
    decomp = f"memory-bank/back/plan/decompose-{epic}"
    _write(
        tmp_path,
        f"{decomp}/index.yaml",
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic}\n"
        "steps:\n"
        "- id: s01\n  file: s01-env.yaml\n  status: pending\n  next_phase: BACK IMPLEMENT\n",
    )
    _write(
        tmp_path,
        f"{decomp}/index.md",
        "| step_id | status |\n| s01 | pending |\n",
    )
    _write(
        tmp_path,
        f"{decomp}/s01-env.yaml",
        "schema: epic-decompose/v1\nstep_id: s01\nneeds_creative: 'no'\n",
    )
    _write(
        tmp_path,
        f"memory-bank/back/analyze/{epic}/analyze-20260831-pass.yaml",
        "schema: epic-analyze/v1\nmetrics:\n  critical_count: 0\n",
    )
    from epic.core import save_epic_state

    save_epic_state(
        tmp_path,
        {
            "armed_epic": epic,
            "armed_decompose": f"{decomp}/index.yaml",
            "armed_step": "ANALYZE",
            "role": "BACK",
            "active": True,
            "status": "running",
        },
    )
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "---\nschema: loop-handoff/v1\nrole: BACK\nmode: IMPLEMENT\n"
        f"epic_id: {epic}\nstep_id: s01\n---\n\n## load_now\n",
    )
    prep = ctx.prepare_session(tmp_path, model="test-model")
    assert prep.get("ok") is True, prep
    assert prep.get("loop_phase") == "IMPLEMENT" or "s01" in str(
        prep.get("phase") or prep.get("loop_phase") or ""
    )
    text = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert "s01-env.yaml" in text
    assert prep.get("loop_phase") != "ANALYZE"


def test_build_prompt_decompose_includes_canon_checklist(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    prompt = ctx.build_prompt(
        tmp_path,
        load_now=["memory-bank/back/plan/plan-T-HUB-030-harness-runtime-wire.md"],
        projection={
            "phase": "BACK DECOMPOSE",
            "epic": "T-HUB-030",
            "role": "back",
            "step": "DECOMPOSE",
        },
    )
    assert "index.md" in prompt
    assert "sNN-<slug>.yaml" in prompt
    assert "mb-finish decompose" in prompt


def test_build_prompt_audit_includes_canon_checklist(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed_context(tmp_path)
    prompt = ctx.build_prompt(
        tmp_path,
        load_now=["memory-bank/activeContext.md"],
        projection={
            "phase": "BACK AUDIT",
            "epic": "T-HUB-049",
            "role": "back",
            "step": "AUDIT",
        },
    )
    assert "AUDIT canon" in prompt
    assert "Triple Assess" in prompt
    assert "mb-finish audit" in prompt
    assert "FORBIDDEN: pytest" in prompt
    assert "это чинится в сессии: FAIL → fix → re-verify" not in prompt
