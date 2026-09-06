"""TM-009: MCP mb_load parity and zero-duplication tests."""

import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from loop.mb_load.mcp_server import list_tools, load_plan_section as mcp_load_plan_section, load_session as mcp_load_session
from loop.mb_load.schemas import MbLoadResult


def test_mcp_cli_parity(tmp_path):
    """TM-009: MCP load_session returns same JSON schema fields as CLI."""
    # Create activeContext.md and a dummy file in load_now in tmp_path
    act_ctx = tmp_path / "memory-bank" / "activeContext.md"
    act_ctx.parent.mkdir(parents=True, exist_ok=True)
    dummy_file = tmp_path / "dummy.txt"
    dummy_file.write_text("hello")
    act_ctx.write_text(
        "---\nschema: loop-handoff/v1\nrole: BACK\nmode: BACK IMPLEMENT\nstep_id: s01\nepic_id: T-HUB-045\n---\n\n## load_now\n- dummy.txt\n\n## Handoff\nTest context\n"
    )

    # 1. Direct Python MCP load_session call
    mcp_res = mcp_load_session(cwd=str(tmp_path))

    # 2. CLI subprocess call
    cli_cmd = [
        sys.executable,
        str(_REPO_ROOT / "harness" / "hooks" / "epic_resolve.py"),
        "mb-load",
        "session",
        "--cwd",
        str(tmp_path),
    ]
    proc = subprocess.run(cli_cmd, capture_output=True, text=True)
    assert proc.returncode == 0, f"CLI stderr: {proc.stderr}"
    cli_res = json.loads(proc.stdout)

    # Compare dictionary keys and schemas
    assert set(mcp_res.keys()) == set(cli_res.keys())
    assert mcp_res["ok"] == cli_res["ok"]
    assert mcp_res["fingerprint"] == cli_res["fingerprint"]
    assert mcp_res["schema"] == cli_res["schema"]
    assert mcp_res["meta"] == cli_res["meta"]
    assert len(mcp_res["files"]) == len(cli_res["files"])


def test_mcp_load_plan_section_parity(tmp_path):
    """Verify load_plan_section MCP tool wrapper."""
    plan_file = tmp_path / "memory-bank" / "back" / "plan" / "plan-T-HUB-045-test.md"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text("# Plan\n\n## Section 1\nContent 1\n\n## Section 2\nContent 2\n")

    act_ctx = tmp_path / "memory-bank" / "activeContext.md"
    act_ctx.write_text(
        "---\nschema: loop-handoff/v1\nrole: BACK\nmode: BACK IMPLEMENT\nstep_id: s01\nepic_id: T-HUB-045\n---\n\n## load_now\n- dummy.txt\n\n## Handoff\nTest context\n"
    )

    res = mcp_load_plan_section(cwd=str(tmp_path), section=1)
    assert res["ok"] is True
    assert "Content 1" in res["content"]
    assert res["error"] is None


def test_mcp_zero_dup_logic():
    """Verify mcp_server.py does not duplicate core logic or import core validate/extract directly."""
    mcp_file = _REPO_ROOT / "loop" / "mb_load" / "mcp_server.py"
    text = mcp_file.read_text(encoding="utf-8")
    assert "validate_active_context_shape" not in text
    assert "extract_load_now" not in text
    assert "fingerprint_context" not in text


def test_mcp_schema_field_guard():
    """Verify known required fields are present in MCP response model."""
    mcp_tools = list_tools()
    assert "tools" in mcp_tools
    tool_names = [t["name"] for t in mcp_tools["tools"]]
    assert "load_session" in tool_names
    assert "load_plan_section" in tool_names

    fields = set(MbLoadResult.model_fields.keys())
    expected_fields = {
        "schema",
        "ok",
        "status",
        "meta",
        "load_now",
        "files",
        "required_missing",
        "optional_missing",
        "forbidden_skipped",
        "fingerprint",
        "diagnostic_codes",
        "shape_errors",
    }
    assert expected_fields == fields, f"Schema drift detected! Fields: {fields}"
