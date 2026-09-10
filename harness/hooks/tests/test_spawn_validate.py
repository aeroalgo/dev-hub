from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from spawn_validate import validate_spawn_input  # noqa: E402


def _agent(root: Path, filename: str, frontmatter: str) -> None:
    agents = root / ".claude" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / filename).write_text(
        f"---\n{frontmatter}\n---\nbody\n", encoding="utf-8"
    )


def _verify_setup(tmp_path: Path) -> None:
    _agent(
        tmp_path,
        "verify.md",
        "name: verify\noverlay:\n  managed: true\n  mode: gate\n  default_loop: true\n  requires_model: true\n  verdict: pass-fail",
    )
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_VERIFY_MODEL=sonnet\n", encoding="utf-8"
    )


def _verify_prompt(
    allow_read: str | None = None,
    *,
    with_steps: bool = True,
    cwd: Path | None = None,
) -> str:
    """Minimal verify spawn prompt. When with_steps, seed impl+decompose under cwd."""
    lines = ["ALLOW READ"]
    if with_steps and cwd is not None:
        impl = "memory-bank/back/implement/T-spawn/s01-demo.yaml"
        dec = "memory-bank/back/plan/T-spawn/yaml/steps/s01-demo.yaml"
        for rel, body in (
            (impl, "schema: epic-implement/v1\nstep_id: s01\nstatus: in_progress\n"),
            (dec, "schema: epic-decompose/v1\nstep_id: s01\n"),
        ):
            path = cwd / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.is_file():
                path.write_text(body, encoding="utf-8")
            lines.append(rel)
    if allow_read:
        lines.append(allow_read)
    elif not with_steps:
        lines.append("foo.py")
    return "\n".join(lines) + "\n"


def test_missing_contract_sections_are_denied(tmp_path: Path, monkeypatch) -> None:
    _verify_setup(tmp_path)
    monkeypatch.setenv("EPIC_LOOP", "1")

    tool_input = {"subagent_type": "verify", "prompt": "spawn"}
    deny_reasons, _notes = validate_spawn_input(tool_input, {}, tmp_path)

    assert any("prompt_incomplete" in reason for reason in deny_reasons)


def test_allow_read_directory_is_denied(tmp_path: Path, monkeypatch) -> None:
    _verify_setup(tmp_path)
    monkeypatch.setenv("EPIC_LOOP", "1")

    tool_input = {
        "subagent_type": "verify",
        "prompt": _verify_prompt("memory-bank/", cwd=tmp_path),
    }
    deny_reasons, _notes = validate_spawn_input(tool_input, {}, tmp_path)

    assert any("ALLOW READ" in reason and "каталог" in reason for reason in deny_reasons)


def test_managed_in_flight_is_denied(tmp_path: Path, monkeypatch) -> None:
    _verify_setup(tmp_path)
    monkeypatch.setenv("EPIC_LOOP", "1")

    state = {
        "in_flight": [
            {"agent": "explorer", "model": "fable", "managed": True}
        ]
    }
    tool_input = {
        "subagent_type": "verify",
        "prompt": _verify_prompt(cwd=tmp_path),
    }
    deny_reasons, _notes = validate_spawn_input(tool_input, state, tmp_path)

    assert any("managed_in_flight" in reason for reason in deny_reasons)


def test_well_formed_prompt_without_in_flight_is_allowed(
    tmp_path: Path, monkeypatch
) -> None:
    _verify_setup(tmp_path)
    monkeypatch.setenv("EPIC_LOOP", "1")

    tool_input = {
        "subagent_type": "verify",
        "prompt": _verify_prompt(cwd=tmp_path),
    }
    deny_reasons, _notes = validate_spawn_input(tool_input, {}, tmp_path)

    assert deny_reasons == []


def test_verify_implement_requires_decompose_step(
    tmp_path: Path, monkeypatch
) -> None:
    _verify_setup(tmp_path)
    monkeypatch.setenv("EPIC_LOOP", "1")
    impl = "memory-bank/back/implement/T-spawn/s01-demo.yaml"
    path = tmp_path / impl
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("status: in_progress\n", encoding="utf-8")

    tool_input = {
        "subagent_type": "verify-implement",
        "prompt": f"ALLOW READ\n{impl}\nfoo.py\n",
    }
    deny_reasons, _notes = validate_spawn_input(tool_input, {}, tmp_path)

    assert any("decompose_step_not_in_allow" in reason for reason in deny_reasons)


def test_verify_implement_allow_without_ac_sections(
    tmp_path: Path, monkeypatch
) -> None:
    _agent(
        tmp_path,
        "verify-implement.md",
        "name: verify-implement\noverlay:\n  managed: true\n  mode: gate\n  default_loop: true\n  requires_model: true\n  verdict: pass-fail",
    )
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_VERIFY_MODEL=sonnet\n", encoding="utf-8"
    )
    monkeypatch.setenv("EPIC_LOOP", "1")

    tool_input = {
        "subagent_type": "verify-implement",
        "prompt": _verify_prompt(cwd=tmp_path),
    }
    deny_reasons, _notes = validate_spawn_input(tool_input, {}, tmp_path)

    assert deny_reasons == []
    assert "AC+" not in tool_input["prompt"]


def test_alias_is_normalized_by_spawn_validation(tmp_path: Path, monkeypatch) -> None:
    _agent(
        tmp_path,
        "explorer.md",
        "name: explorer\noverlay:\n  managed: true\n  mode: search\n  default_loop: true\n  requires_model: true",
    )
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_EXPLORER_MODEL=fable\n", encoding="utf-8"
    )
    monkeypatch.setenv("EPIC_LOOP", "1")

    tool_input = {"subagent_type": "explore", "prompt": "spawn"}
    deny_reasons, _notes = validate_spawn_input(tool_input, {}, tmp_path)

    assert deny_reasons == []
    assert tool_input["subagent_type"] == "explorer"


def test_cli_round_trip_denies_incomplete_spawn() -> None:
    payload = {
        "tool_name": "Agent",
        "tool_input": {"subagent_type": "verify-implement", "prompt": "spawn"},
        "session_id": "s03-round-trip",
        "cwd": str(ROOT),
    }
    env = {**dict(__import__("os").environ), "EPIC_LOOP": "1", "PYTHONPATH": str(HOOKS)}
    completed = subprocess.run(
        [sys.executable, str(HOOKS / "spawn_validate.py")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    result = json.loads(completed.stdout)
    assert any("prompt_incomplete" in reason for reason in result["deny_reasons"])


def _repair_setup(tmp_path: Path) -> None:
    _agent(
        tmp_path,
        "gate-repair.md",
        "name: gate-repair\noverlay:\n  managed: true\n  mode: repair\n  default_loop: true\n  requires_model: true\n  verdict: none",
    )
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_GATE_REPAIR_MODEL=sonnet\n", encoding="utf-8"
    )


def _repair_prompt() -> str:
    return (
        "BLOCKERS\n"
        "- diagnostic_code_mismatch | loop/mb_finish/finish_implement.py | "
        "align diagnostic code with gate identity SoT\n"
        "ALLOW WRITE\n"
        "loop/mb_finish/finish_implement.py\n"
        "VERIFY\n"
        "timeout 300s .venv/bin/pytest harness/hooks/tests/test_mb_finish_implement.py -q\n"
    )


def test_gate_repair_missing_sections_denied(tmp_path: Path, monkeypatch) -> None:
    _repair_setup(tmp_path)
    monkeypatch.setenv("EPIC_LOOP", "1")

    tool_input = {"subagent_type": "gate-repair", "prompt": "spawn"}
    deny_reasons, _notes = validate_spawn_input(tool_input, {}, tmp_path)

    assert any("prompt_incomplete" in reason for reason in deny_reasons)


def test_gate_repair_well_formed_prompt_allowed(tmp_path: Path, monkeypatch) -> None:
    _repair_setup(tmp_path)
    monkeypatch.setenv("EPIC_LOOP", "1")

    tool_input = {"subagent_type": "gate-repair", "prompt": _repair_prompt()}
    deny_reasons, _notes = validate_spawn_input(tool_input, {}, tmp_path)

    assert deny_reasons == []


def test_gate_repair_vague_blockers_denied(tmp_path: Path, monkeypatch) -> None:
    _repair_setup(tmp_path)
    monkeypatch.setenv("EPIC_LOOP", "1")

    prompt = (
        "BLOCKERS\n- missing_symbol\nALLOW WRITE\n"
        "path/to/file_a.py\n"
        "VERIFY\n"
        "bin/pytest path/to/test_c.py -q\n"
    )
    tool_input = {"subagent_type": "gate-repair", "prompt": prompt}
    deny_reasons, _notes = validate_spawn_input(tool_input, {}, tmp_path)

    assert any("prompt_incomplete:blocker_row" in reason for reason in deny_reasons)


def test_gate_repair_blocker_path_must_be_in_allow_write(
    tmp_path: Path, monkeypatch
) -> None:
    _repair_setup(tmp_path)
    monkeypatch.setenv("EPIC_LOOP", "1")

    prompt = (
        "BLOCKERS\n"
        "- missing_symbol | path/to/other.py | add symbol X\n"
        "ALLOW WRITE\n"
        "path/to/file_a.py\n"
        "VERIFY\n"
        "bin/pytest path/to/test_c.py -q\n"
    )
    tool_input = {"subagent_type": "gate-repair", "prompt": prompt}
    deny_reasons, _notes = validate_spawn_input(tool_input, {}, tmp_path)

    assert any("prompt_incomplete:blocker_row" in reason for reason in deny_reasons)


def test_gate_repair_after_qa_requires_full_suite(tmp_path: Path, monkeypatch) -> None:
    _repair_setup(tmp_path)
    monkeypatch.setenv("EPIC_LOOP", "1")

    prompt = _repair_prompt() + "\nPhase: BACK QA\n"
    tool_input = {"subagent_type": "gate-repair", "prompt": prompt}
    deny_reasons, _notes = validate_spawn_input(tool_input, {}, tmp_path)

    assert any("qa_repair_verify_incomplete" in reason for reason in deny_reasons)


def test_gate_repair_after_qa_accepts_full_suite(tmp_path: Path, monkeypatch) -> None:
    _repair_setup(tmp_path)
    monkeypatch.setenv("EPIC_LOOP", "1")

    prompt = (
        _repair_prompt().replace(
            "timeout 300s .venv/bin/pytest harness/hooks/tests/test_mb_finish_implement.py -q",
            "bin/pytest -q --tb=line\n"
            "timeout 300s .venv/bin/pytest harness/hooks/tests/test_mb_finish_implement.py -q",
        )
        + "\nPhase: BACK QA\n"
    )
    tool_input = {"subagent_type": "gate-repair", "prompt": prompt}
    deny_reasons, _notes = validate_spawn_input(tool_input, {}, tmp_path)

    assert deny_reasons == []


def _decompose_setup(tmp_path: Path) -> None:
    _agent(
        tmp_path,
        "verify-decompose.md",
        "name: verify-decompose\noverlay:\n  managed: true\n  mode: gate\n  default_loop: true\n  requires_model: true\n  verdict: pass-fail",
    )
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_VERIFY_DECOMPOSE_MODEL=haiku\n", encoding="utf-8"
    )


def _decompose_prompt(*, plan_excerpt: bool = True, extra_allow: str = "") -> str:
    excerpt = (
        "## PLAN EXCERPT\n"
        "FR-001 registry schema; FR-002 pack row; fail-closed resolve.\n"
        if plan_excerpt
        else ""
    )
    return (
        "## ALLOW READ\n"
        "- memory-bank/back/plan/T-HUB-048/md/plan.md\n"
        "- memory-bank/back/plan/T-HUB-048/md/decompose-index.md\n"
        "- memory-bank/back/plan/T-HUB-048/yaml/decompose-index.yaml\n"
        "- memory-bank/back/plan/T-HUB-048/yaml/steps/s01-a.yaml\n"
        "- memory-bank/back/plan/T-HUB-048/yaml/steps/s03-b.yaml\n"
        "- memory-bank/back/plan/T-HUB-048/yaml/steps/s06-c.yaml\n"
        f"{extra_allow}"
        f"{excerpt}"
        "## Requirements coverage\n"
        "FR-001..010 covered by s01-s08; also mentions "
        "memory-bank/back/plan/T-HUB-048/yaml/steps/s07-x.yaml and "
        "memory-bank/back/plan/T-HUB-048/yaml/steps/s08-y.yaml\n"
        "## Stages coverage\n"
        "PackResolve / Failure matrix mapped.\n"
        "## Outcome map\n"
        "fail-closed / domain-agnostic outcomes mapped.\n"
        "## Replacement cleanup\n"
        "Kind I / Kind C in-epic deletes.\n"
    )


def test_verify_decompose_allow_read_ignores_later_section_paths(
    tmp_path: Path, monkeypatch
) -> None:
    """Regression: coverage/excerpt paths must not inflate ALLOW READ count."""
    import _lib as lib

    _decompose_setup(tmp_path)
    monkeypatch.setenv("EPIC_LOOP", "1")

    prompt = _decompose_prompt()
    files = lib.allow_read_files(prompt)
    assert len(files) == 6
    assert lib.allow_read_violations(prompt) == []

    tool_input = {"subagent_type": "verify-decompose", "prompt": prompt}
    deny_reasons, _notes = validate_spawn_input(tool_input, {}, tmp_path)
    assert deny_reasons == []


def test_verify_decompose_missing_plan_excerpt_denied(
    tmp_path: Path, monkeypatch
) -> None:
    _decompose_setup(tmp_path)
    monkeypatch.setenv("EPIC_LOOP", "1")

    tool_input = {
        "subagent_type": "verify-decompose",
        "prompt": _decompose_prompt(plan_excerpt=False),
    }
    deny_reasons, _notes = validate_spawn_input(tool_input, {}, tmp_path)
    assert any(
        "prompt_incomplete" in reason and "PLAN EXCERPT" in reason
        for reason in deny_reasons
    )


def test_verify_decompose_allow_read_over_limit_still_denied(
    tmp_path: Path, monkeypatch
) -> None:
    _decompose_setup(tmp_path)
    monkeypatch.setenv("EPIC_LOOP", "1")

    extra = "".join(
        f"- memory-bank/back/plan/T-HUB-048/yaml/steps/s{i:02d}-extra.yaml\n"
        for i in range(7, 13)
    )
    tool_input = {
        "subagent_type": "verify-decompose",
        "prompt": _decompose_prompt(extra_allow=extra),
    }
    deny_reasons, _notes = validate_spawn_input(tool_input, {}, tmp_path)
    assert any("ALLOW READ" in reason and "> 10" in reason for reason in deny_reasons)
