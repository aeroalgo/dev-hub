import pytest
from pathlib import Path

from loop.incidents.schema import IncidentRecord
from loop.incidents.tier1_prompt import (
    build_tier1_prompt,
    format_scope_block,
    load_runbook,
)


def test_prompt_contains_runbook_text(tmp_path: Path):
    runbooks_dir = tmp_path / "runbooks"
    runbooks_dir.mkdir()
    rb_file = runbooks_dir / "active_context_shape_invalid.md"
    rb_file.write_text("Fix activeContext shape by re-generating valid header.", encoding="utf-8")

    incident = IncidentRecord(
        incident_id="inc-12345",
        opened_at="2026-08-30T12:00:00Z",
        project_root="/app",
        epic_id="T-HUB-018",
        step_id="s01",
        phase="BACK IMPLEMENT",
        session_id="sess-abc",
        source="test",
        diagnostic_codes=["active_context_shape_invalid"],
        fingerprint="fp123",
    )

    prompt = build_tier1_prompt(
        incident=incident,
        epic_dir=tmp_path,
        scope_allowlist=["memory-bank/activeContext.md"],
        runbooks_dir=runbooks_dir,
    )

    assert "Fix activeContext shape by re-generating valid header." in prompt
    assert "active_context_shape_invalid" in prompt


def test_missing_runbook_no_exception(tmp_path: Path):
    runbooks_dir = tmp_path / "runbooks"
    runbooks_dir.mkdir()

    content = load_runbook("non_existent_code", runbooks_dir=runbooks_dir)
    assert content == "No runbook for non_existent_code"

    incident = IncidentRecord(
        incident_id="inc-12345",
        opened_at="2026-08-30T12:00:00Z",
        project_root="/app",
        epic_id="T-HUB-018",
        step_id="s01",
        phase="BACK IMPLEMENT",
        session_id="sess-abc",
        source="test",
        diagnostic_codes=["unknown_code"],
        fingerprint="fp123",
    )

    prompt = build_tier1_prompt(
        incident=incident,
        epic_dir=tmp_path,
        scope_allowlist=["memory-bank/activeContext.md"],
        runbooks_dir=runbooks_dir,
    )
    assert "No runbook for unknown_code" in prompt


def test_prompt_contains_all_allowed_paths():
    allowlist = ["memory-bank/activeContext.md", "loop/incidents/schema.py"]
    formatted = format_scope_block(allowlist)

    assert "memory-bank/activeContext.md" in formatted
    assert "loop/incidents/schema.py" in formatted
    assert "FORBIDDEN" in formatted


def test_prompt_contains_forbidden_block(tmp_path: Path):
    incident = IncidentRecord(
        incident_id="inc-12345",
        opened_at="2026-08-30T12:00:00Z",
        project_root="/app",
        epic_id="T-HUB-018",
        step_id="s01",
        phase="BACK IMPLEMENT",
        session_id="sess-abc",
        source="test",
        diagnostic_codes=["active_context_shape_invalid"],
        fingerprint="fp123",
    )

    prompt = build_tier1_prompt(
        incident=incident,
        epic_dir=tmp_path,
        scope_allowlist=["memory-bank/activeContext.md"],
        runbooks_dir=tmp_path,
    )
    assert "FORBIDDEN" in prompt
    assert "Forbidden writes" in prompt or "FORBIDDEN" in prompt


def test_prompt_stable_same_input(tmp_path: Path):
    incident = IncidentRecord(
        incident_id="inc-12345",
        opened_at="2026-08-30T12:00:00Z",
        project_root="/app",
        epic_id="T-HUB-018",
        step_id="s01",
        phase="BACK IMPLEMENT",
        session_id="sess-abc",
        source="test",
        diagnostic_codes=["active_context_shape_invalid"],
        fingerprint="fp123",
    )

    p1 = build_tier1_prompt(
        incident=incident,
        epic_dir=tmp_path,
        scope_allowlist=["memory-bank/activeContext.md", "loop/test.py"],
        runbooks_dir=tmp_path,
    )

    p2 = build_tier1_prompt(
        incident=incident,
        epic_dir=tmp_path,
        scope_allowlist=["loop/test.py", "memory-bank/activeContext.md"],
        runbooks_dir=tmp_path,
    )

    assert p1 == p2


def test_prompt_no_secrets_in_output(tmp_path: Path):
    incident = IncidentRecord(
        incident_id="inc-12345",
        opened_at="2026-08-30T12:00:00Z",
        project_root="/app",
        epic_id="T-HUB-018",
        step_id="s01",
        phase="BACK IMPLEMENT",
        session_id="sess-abc",
        source="test",
        diagnostic_codes=["active_context_shape_invalid"],
        fingerprint="fp123",
        metadata={"secret_key": "SUPERSECRETVALUE"},
    )

    prompt = build_tier1_prompt(
        incident=incident,
        epic_dir=tmp_path,
        scope_allowlist=["memory-bank/activeContext.md"],
        runbooks_dir=tmp_path,
    )

    assert "SUPERSECRETVALUE" not in prompt
