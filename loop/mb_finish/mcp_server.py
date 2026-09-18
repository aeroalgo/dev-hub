"""MCP thin wrapper for loop/mb_finish (FastAPI or pure dict descriptors)."""

from typing import Any, Dict
from loop.mb_finish.finish_implement import finish_implement_step
from loop.mb_finish.impl import (
    finish_analyze,
    finish_audit,
    finish_bugfix,
    finish_creative,
    finish_decompose,
    finish_plan,
    finish_qa,
)
from loop.mb_finish.schemas import MbFinishRequest

TOOLS = [
    {
        "name": "finish_implement",
        "description": "Finish implement step",
        "parameters": MbFinishRequest.model_json_schema(),
        "handler": finish_implement_step,
    },
    {
        "name": "finish_qa",
        "description": "Finish QA step",
        "parameters": MbFinishRequest.model_json_schema(),
        "handler": finish_qa,
    },
    {
        "name": "finish_bugfix",
        "description": "Finish bugfix step",
        "parameters": MbFinishRequest.model_json_schema(),
        "handler": finish_bugfix,
    },
    {
        "name": "finish_decompose",
        "description": "Finish decompose step",
        "parameters": MbFinishRequest.model_json_schema(),
        "handler": finish_decompose,
    },
    {
        "name": "finish_plan",
        "description": "Finish plan step",
        "parameters": MbFinishRequest.model_json_schema(),
        "handler": finish_plan,
    },
    {
        "name": "finish_analyze",
        "description": "Finish analyze step",
        "parameters": MbFinishRequest.model_json_schema(),
        "handler": finish_analyze,
    },
    {
        "name": "finish_audit",
        "description": "Finish audit step",
        "parameters": MbFinishRequest.model_json_schema(),
        "handler": finish_audit,
    },
    {
        "name": "finish_creative",
        "description": "Finish creative step",
        "parameters": MbFinishRequest.model_json_schema(),
        "handler": finish_creative,
    },
]


def list_tools() -> Dict[str, Any]:
    """Return MCP tool descriptors for mb-finish subcommands."""
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
