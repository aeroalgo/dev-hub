from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_operational_docs_describe_production_semantics() -> None:
    readme = _read("loop/README.md")
    workflow = _read("loop/WORKFLOW.md")
    instruction = _read(".claude/instructions/epic-loop.md")

    for text in (readme, workflow, instruction):
        assert "loop-dag/v2" in text
        assert "sequential" in text.lower()
        assert "checkpoint" in text.lower()
        assert "resume" in text.lower()
        assert "source of truth" in text.lower()
        assert "EPIC_SESSION_TIMEOUT_SEC" in text
        assert ".claude/project.env" in text
        assert ".claude/project.env.example" not in text

    assert "GAP_FANOUT" in readme
    assert "manual" in readme.lower()
    assert "state.json" in instruction
    assert "durable cursor" in instruction.lower()


def test_operational_docs_expose_bounded_contract() -> None:
    project_env = _read(".claude/project.env")
    instruction = _read(".claude/instructions/epic-loop.md")
    workflow = _read("loop/WORKFLOW.md")

    keys = (
        "EPIC_SESSION_TIMEOUT_SEC",
        "EPIC_SESSION_KILL_GRACE_SEC",
        "EPIC_TRANSIENT_RETRY_MAX",
        "EPIC_DEGRADED_MAX",
        "EPIC_STATUS_HEARTBEAT_SEC",
        "EPIC_PERMISSION_MODE",
    )
    for key in keys:
        assert key in project_env
        assert key in instruction

    assert "bounded" in workflow.lower()
    assert "secret" in instruction.lower()
    assert "one checkout" in instruction.lower()
    assert "no parallel" in instruction.lower()


def test_operational_docs_define_rollout_and_rollback() -> None:
    readme = _read("loop/README.md")
    workflow = _read("loop/WORKFLOW.md")
    instruction = _read(".claude/instructions/epic-loop.md")
    gap_template = _read(".cursor/templates/integration-gap.md")
    contract = _read(".cursor/templates/integration-contract.md")

    combined = "\n".join((readme, workflow, instruction, gap_template, contract)).lower()
    for term in ("phase a", "phase b", "phase c", "phase d", "phase e"):
        assert term in combined
    for term in ("rollback", "resume_from_step", "t-034", "v1", "dependency"):
        assert term in combined

    assert "finish" in workflow.lower()
    assert "verify" in workflow.lower()
    assert "mark-index-status" in workflow
    assert "checkpoint/index" in instruction.lower()
