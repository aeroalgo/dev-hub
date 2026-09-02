"""MCP thin wrapper for loop/mb_load."""

from typing import Any, Dict, Optional, Union

from loop.mb_load.plan_section import load_plan_section as _core_load_plan_section
from loop.mb_load.session import load_session as _core_load_session


def load_session(
    cwd: str = ".",
    plan_section: Optional[Union[int, str]] = None,
    max_file_bytes: int = 256 * 1024,
) -> Dict[str, Any]:
    """MCP tool wrapper for load_session. Calls core load_session and returns JSON dict."""
    res = _core_load_session(cwd=cwd, plan_section=plan_section, max_file_bytes=max_file_bytes)
    if not res.files and any("missing_file:" in d for d in res.diagnostic_codes):
        res.ok = False
    return res.model_dump(mode="json")


def load_plan_section(cwd: str = ".", section: Union[int, str] = 1) -> Dict[str, Any]:
    """MCP tool wrapper for load_plan_section. Calls core load_plan_section."""
    content, err = _core_load_plan_section(cwd=cwd, section=section)
    return {"ok": err is None, "content": content, "error": err}


TOOLS = [
    {
        "name": "load_session",
        "description": "Load activeContext session bundle, load_now files, and optional plan section.",
        "parameters": {
            "type": "object",
            "properties": {
                "cwd": {"type": "string", "default": "."},
                "plan_section": {"type": ["integer", "string", "null"], "default": None},
                "max_file_bytes": {"type": "integer", "default": 262144},
            },
        },
        "handler": load_session,
    },
    {
        "name": "load_plan_section",
        "description": "Extract a specific section from the active epic plan file.",
        "parameters": {
            "type": "object",
            "properties": {
                "cwd": {"type": "string", "default": "."},
                "section": {"type": ["integer", "string"], "default": 1},
            },
        },
        "handler": load_plan_section,
    },
]


def list_tools() -> Dict[str, Any]:
    """Return MCP tool descriptors for mb-load tools."""
    return {
        "tools": [
            {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            }
            for t in TOOLS
        ]
    }


app = {"list_tools": list_tools, "tools": TOOLS}
