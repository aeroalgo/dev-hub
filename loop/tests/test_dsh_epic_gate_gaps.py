from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / ".claude" / "hooks" / "subagent-stop.py"
STOP_GATE = ROOT / ".claude" / "hooks" / "stop-gate.py"
HOOKS = ROOT / ".claude" / "hooks"
TS_HANDLER = ROOT / "dsh" / "plugins" / "epic-gate" / "src" / "subagent-stop.ts"
TS_START_HANDLER = ROOT / "dsh" / "plugins" / "epic-gate" / "src" / "subagent-start.ts"
TS_PRETOOL_HANDLER = ROOT / "dsh" / "plugins" / "epic-gate" / "src" / "pre-tool-use.ts"
DSH_README = ROOT / "dsh" / "README.md"
EPIC_GATE_README = ROOT / "dsh" / "plugins" / "epic-gate" / "README.md"
EPIC_PROFILES = sorted((ROOT / "dsh" / "profiles").glob("epic-*/cordis.patch.yml"))


def _ts_payload(event: dict[str, object]) -> dict[str, object]:
    source = json.dumps(event, ensure_ascii=False)
    script = f"""
import {{ enrichSubagentStopPayload }} from {json.dumps('./dsh/plugins/epic-gate/src/subagent-stop.ts')};
const event = JSON.parse({json.dumps(source)});
console.log(JSON.stringify(enrichSubagentStopPayload({{ get: () => undefined }}, event)));
"""
    result = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _pretool_smoke(tmp_path: Path, tool_name: str, prompt: str) -> dict[str, object]:
    source = json.dumps(prompt, ensure_ascii=False)
    script = f"""
import {{ preToolUse }} from './src/pre-tool-use.ts';
const decision = await preToolUse({{
  name: {json.dumps(tool_name)},
  arguments: {{ subagent_type: 'verify', prompt: JSON.parse({json.dumps(source)}) }},
  agent: {{ session: {{ header: {{ id: 'pretool-child', cwd: {json.dumps(str(ROOT))} }} }} }},
}});
console.log(JSON.stringify(decision));
"""
    env = os.environ.copy()
    env.update({
        "EPIC_LOOP": "1",
        "PROJECT_WORKFLOW_HOOKS": "loop",
        "PROJECT_ROOT": str(ROOT),
        "PYTHON": sys.executable,
        "DSH_SPAWN_VALIDATE": str(ROOT / ".claude" / "hooks" / "spawn_validate.py"),
        "PYTHONPATH": str(HOOKS),
    })
    result = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=ROOT / "dsh" / "plugins" / "epic-gate",
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return json.loads(result.stdout)


def _run_hook(tmp_path: Path, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / ".claude" / "hooks")
    env["EPIC_LOOP"] = "1"
    env["PROJECT_WORKFLOW_HOOKS"] = "loop"
    return subprocess.run(
        [sys.executable, str(HOOK)],
        cwd=tmp_path,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _run_stop_gate(tmp_path: Path, *, session_id: str = "dsh-stop", self_limit: str = "2") -> dict[str, object]:
    env = os.environ.copy()
    env.pop("DEV_HUB", None)
    env.pop("HUB_ROOT", None)
    env.update(
        {
            "CLAUDE_PROJECT_DIR": str(tmp_path),
            "DSH_HOOKS_BRIDGE": "1",
            "EPIC_LOOP": "1",
            "PROJECT_ROOT": str(tmp_path),
            "PROJECT_WORKFLOW_HOOKS": "loop",
            "PYTHONPATH": str(HOOKS),
            "DSH_SELF_LIMIT_MAX": self_limit,
        }
    )
    result = subprocess.run(
        [sys.executable, str(STOP_GATE)],
        cwd=tmp_path,
        input=json.dumps(
            {
                "session_id": session_id,
                "cwd": str(tmp_path),
                "last_assistant_message": "FINISH: stop",
                "stop_hook_active": False,
            }
        ),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout) if result.stdout.strip() else {}


def _prepare_stop_gate(tmp_path: Path) -> None:
    active_context = tmp_path / "memory-bank" / "activeContext.md"
    active_context.parent.mkdir(parents=True, exist_ok=True)
    active_context.write_text(
        "## load_now\n- `memory-bank/back/plan/decompose-s06/index.yaml`\n\n"
        "## Handoff BACK IMPLEMENT — in progress\n- next\n",
        encoding="utf-8",
    )
    hooks = tmp_path / ".claude" / "agents"
    hooks.mkdir(parents=True, exist_ok=True)
    for name, mode, verdict in (
        ("verify", "gate", "pass-fail"),
        ("reviewer", "gate", "pass-blocked-fail"),
        ("explorer", "search", "none"),
    ):
        (hooks / f"{name}.md").write_text(
            f"---\\nname: {name}\\noverlay:\\n  managed: true\\n  mode: {mode}\\n"
            f"  requires_model: false\\n  default_loop: true\\n  default_chat: false\\n"
            f"  verdict: {verdict}\\n---\\n",
            encoding="utf-8",
        )

    import_path = HOOKS / "epic.py"
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    import epic

    state = epic.default_state()
    state.update(
        {
            "active": True,
            "status": "running",
            "phase": "IMPLEMENT",
            "pending_fingerprint_before": epic.fingerprint_context(active_context.read_text()),
            "armed_step": "s06",
            "armed_decompose": "memory-bank/back/plan/decompose-s06/s06.yaml",
        }
    )
    epic.save_epic_state(tmp_path, state)


def test_all_epic_profiles_mount_gate_after_hooks_bridge() -> None:
    assert len(EPIC_PROFILES) == 8
    for profile in EPIC_PROFILES:
        text = profile.read_text(encoding="utf-8")
        assert text.index("id: cc-hooks-bridge") < text.index("id: epic-gate"), profile


def test_epic_gate_readme_closes_or_defers_every_parity_gap() -> None:
    text = EPIC_GATE_README.read_text(encoding="utf-8")
    assert text.count("| closed |") + text.count("| deferred |") >= 4
    assert "owner" in text.lower()
    for gap in ("A", "B", "C", "D"):
        assert f"Gap {gap}" in text


def test_dsh_readme_closes_t_hub_008_gap_rows() -> None:
    text = DSH_README.read_text(encoding="utf-8")
    section = text.split("## Hooks bridge", 1)[1].split("## Version pinning", 1)[0]
    assert section.count("T-HUB-008") >= 4
    assert "| open |" not in section.lower()
    assert "closed" in section.lower()


def test_native_pretool_denies_incomplete_verify_spawn_with_stable_reason(tmp_path: Path) -> None:
    decision = _pretool_smoke(tmp_path, "Agent", "incomplete verify payload")

    assert decision["kind"] == "deny"
    assert "prompt_incomplete" in decision["reason"]


def test_native_pretool_allows_non_spawn_tools(tmp_path: Path) -> None:
    decision = _pretool_smoke(tmp_path, "Bash", "incomplete verify payload")

    assert decision == {"kind": "allow"}


def test_verdict_extraction_pass_and_fail() -> None:
    passed = _ts_payload({"lastAssistantMessage": [{"type": "text", "text": "VERDICT: PASS"}]})
    failed = _ts_payload({"lastAssistantMessage": [{"type": "text", "text": "VERDICT: FAIL"}]})

    assert passed["verdict"] == "PASS"
    assert failed["verdict"] == "FAIL"
    assert passed["last_assistant_message"] == "VERDICT: PASS"


def test_verdict_extraction_uses_last_line_and_returns_empty_without_verdict() -> None:
    corrected = _ts_payload(
        {"lastAssistantMessage": [{"type": "text", "text": "draft\nVERDICT: PASS\nVERDICT: FAIL"}]}
    )
    missing = _ts_payload({"lastAssistantMessage": [{"type": "text", "text": "still working"}]})

    assert corrected["verdict"] == "FAIL"
    assert "verdict" not in missing


def test_subagent_stop_verdict_round_trip_records_enriched_verdict(tmp_path: Path) -> None:
    payload = _ts_payload(
        {
            "id": "child-round-trip",
            "session_id": "child-round-trip",
            "agent_type": "verify",
            "cwd": str(tmp_path),
            "lastAssistantMessage": [{"type": "text", "text": "VERDICT: PASS\nAC+: ok"}],
        }
    )
    result = _run_hook(tmp_path, payload)

    assert result.returncode == 0, result.stderr
    state = json.loads(
        (tmp_path / ".claude" / "runtime" / "spawn-gate" / "child-round-trip.json").read_text(
            encoding="utf-8"
        )
    )
    assert state["verify_verdict"] == "PASS"


def test_subagent_stop_accepts_verdict_without_assistant_message(tmp_path: Path) -> None:
    result = _run_hook(
        tmp_path,
        {
            "session_id": "child-direct-verdict",
            "agent_type": "verify",
            "cwd": str(tmp_path),
            "verdict": "FAIL",
            "stop_hook_active": False,
        },
    )

    assert result.returncode == 0, result.stderr
    state = json.loads(
        (tmp_path / ".claude" / "runtime" / "spawn-gate" / "child-direct-verdict.json").read_text(
            encoding="utf-8"
        )
    )
    assert state["verify_verdict"] == "FAIL"


def test_subagent_stop_without_verdict_does_not_crash_for_generic_dsh_event(tmp_path: Path) -> None:
    result = _run_hook(
        tmp_path,
        {
            "session_id": "child-no-verdict",
            "agent_type": "general-purpose",
            "cwd": str(tmp_path),
            "stop_hook_active": False,
        },
    )

    assert result.returncode == 0, result.stderr


def _session_start_smoke(source: str) -> dict[str, object]:
    script = f"""
import {{ applySessionStart }} from './src/index.ts';
const listeners = new Map();
const injected = [];
applySessionStart({{ on(name, handler) {{ listeners.set(name, handler); }} }}, () => ({{
  additionalContext: 'first-turn context',
  sessionTitle: 'epic:context',
}}));
listeners.get('agent/session-start')({{
  agent: {{ inject(message) {{ injected.push(message); }} }},
  source: {json.dumps(source)},
}});
console.log(JSON.stringify({{ injected }}));
"""
    result = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=ROOT / "dsh" / "plugins" / "epic-gate",
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _subagent_start_smoke(agent_type: str) -> dict[str, object]:
    script = f"""
import {{ applySubagentStart }} from './src/subagent-start.ts';
const listeners = new Map();
const injected = [];
const agent = {{ id: 'child-1', session: {{ header: {{ id: 'child-1', cwd: process.cwd() }} }}, inject(message) {{ injected.push(message); }} }};
applySubagentStart({{ on(name, handler) {{ listeners.set(name, handler); }}, logger: {{ warn() {{}} }} }}, {{ python: process.env.PYTHON ?? 'python3' }});
listeners.get('subagent/start')({{ id: 'child-1', agent_type: {json.dumps(agent_type)}, agent }});
await new Promise((resolve) => setTimeout(resolve, 500));
console.log(JSON.stringify({{ injected }}));
"""
    env = os.environ.copy()
    env.update({
        "EPIC_LOOP": "1",
        "PROJECT_WORKFLOW_HOOKS": "loop",
        "PROJECT_ROOT": str(ROOT),
        "PYTHONPATH": str(HOOKS),
    })
    result = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=ROOT / "dsh" / "plugins" / "epic-gate",
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return json.loads(result.stdout)


def test_native_subagent_start_maps_each_supported_contract() -> None:
    for agent_type in ("verify", "reviewer", "explorer"):
        payload = _subagent_start_smoke(agent_type)
        assert len(payload["injected"]) == 1
        text = payload["injected"][0]["content"][0]["text"]
        assert f"agent_type={agent_type} preset=preset.{agent_type}" in text
        assert f"CONTRACT {agent_type}:" in text


def test_native_subagent_start_fails_closed_for_unknown_type() -> None:
    payload = _subagent_start_smoke("general-purpose")
    assert payload["injected"] == []


def test_native_subagent_start_uses_product_root_for_hook_bridge() -> None:
    script = """
import { nativeSubagentStartPayload } from './src/subagent-start.ts';
const agent = { id: 'child-1', session: { header: { cwd: '/wrong/hub' } } };
console.log(JSON.stringify(nativeSubagentStartPayload({ id: 'child-1', cwd: '/wrong/hub' }, agent, 'verify')));
"""
    env = os.environ.copy()
    env["PROJECT_ROOT"] = "/product/root"
    result = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=ROOT / "dsh" / "plugins" / "epic-gate",
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    assert json.loads(result.stdout)["cwd"] == "/product/root"


def test_resolve_project_root_handles_valid_missing_and_conflicting() -> None:
    script = """
import { resolveProjectRoot } from './src/subagent-start.ts';
const validEpic = resolveProjectRoot({ EPIC_PROJECT_ROOT: '/epic/root', PROJECT_ROOT: '/epic/root' });
const validProj = resolveProjectRoot({ PROJECT_ROOT: '/proj/root' });
const validClaude = resolveProjectRoot({ CLAUDE_PROJECT_DIR: '/claude/root' });
let conflictErr = '';
try {
  resolveProjectRoot({ EPIC_PROJECT_ROOT: '/epic/root', PROJECT_ROOT: '/proj/root' });
} catch (e) {
  conflictErr = String(e);
}
console.log(JSON.stringify({ validEpic, validProj, validClaude, conflictErr }));
"""
    result = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=ROOT / "dsh" / "plugins" / "epic-gate",
        capture_output=True,
        text=True,
        check=True,
    )
    res = json.loads(result.stdout)
    assert res["validEpic"] == "/epic/root"
    assert res["validProj"] == "/proj/root"
    assert res["validClaude"] == "/claude/root"
    assert "conflicting EPIC_PROJECT_ROOT" in res["conflictErr"]


def test_dsh_stop_finish_blocking(tmp_path: Path) -> None:
    _prepare_stop_gate(tmp_path)

    blocked = _run_stop_gate(tmp_path)

    assert blocked["decision"] == "block"


def test_session_start_injects_context_at_dsh_first_turn_boundary() -> None:
    payload = _session_start_smoke("startup")

    assert len(payload["injected"]) == 1
    assert payload["injected"][0]["content"] == [
        {"type": "text", "text": "first-turn context"}
    ]
    assert payload["injected"][0]["source"]["plugin"] == "epic-gate"


def test_session_start_bridge_handles_dsh_resume_without_resetting_context() -> None:
    payload = _session_start_smoke("resume")

    assert len(payload["injected"]) == 1
    assert payload["injected"][0]["content"][0]["text"] == "first-turn context"


def test_session_start_bridge_uses_injected_context_not_initial_user_message() -> None:
    payload = _session_start_smoke("startup")
    message = payload["injected"][0]

    assert "initialUserMessage" not in message
    assert "sessionTitle" not in message
    assert message["source"]["summary"] == "epic:context"
