"""TM-009: MCP descriptor parity test."""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from loop.mb_finish.mcp_server import list_tools
from loop.mb_finish.schemas import HandoffBody, LoadNowItem, LoopHandoffMeta, MbFinishRequest


def test_mcp_descriptors_parity():
    """Verify that MCP tool descriptors match CLI subcommands and schemas."""
    descriptors = list_tools()
    assert "tools" in descriptors
    tools = {t["name"]: t for t in descriptors["tools"]}

    expected_cmds = [
        "finish_handoff",
        "finish_implement",
        "finish_qa",
        "finish_bugfix",
        "finish_decompose",
        "finish_plan",
        "finish_analyze",
        "finish_audit",
        "finish_creative",
        "finish_reflect",
    ]

    for cmd in expected_cmds:
        assert cmd in tools, f"Tool {cmd} missing from MCP descriptors"
        tool = tools[cmd]
        assert "description" in tool and tool["description"]
        assert "parameters" in tool and isinstance(tool["parameters"], dict)

    # Check MbFinishRequest schema parity
    req_schema = MbFinishRequest.model_json_schema()
    for cmd in expected_cmds:
        if cmd == "finish_handoff":
            assert tools[cmd]["parameters"]["meta"] == LoopHandoffMeta.model_json_schema()
            assert tools[cmd]["parameters"]["load_now"]["items"] == LoadNowItem.model_json_schema()
            assert tools[cmd]["parameters"]["body"] == HandoffBody.model_json_schema()
        else:
            assert tools[cmd]["parameters"] == req_schema


def test_mcp_server_startup():
    """Verify server app startup dict."""
    from loop.mb_finish.mcp_server import app
    assert "list_tools" in app
    assert callable(app["list_tools"])
