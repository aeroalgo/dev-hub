"""Loader for tool gate adapters."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Union
import yaml

from loop.workflow.tool_gates.protocol import ToolGateAdapter

_HUB_ROOT = Path(__file__).resolve().parents[3]


def load_tool_gate_adapter(
    gate_id: str,
    manifest: Optional[Union[Dict[str, Any], str, Path]] = None,
    cwd: Optional[Union[str, Path]] = None,
) -> ToolGateAdapter:
    """Load and instantiate a ToolGateAdapter given gate_id and manifest (or cwd to resolve manifest)."""
    cwd_path = Path(cwd).resolve() if cwd is not None else Path.cwd().resolve()

    manifest_data: Dict[str, Any]
    if manifest is None:
        from loop.workflow.registry import resolve_workflow_pack

        pack_res = resolve_workflow_pack(cwd=cwd_path)
        if not pack_res.ok or not pack_res.pack:
            raise ValueError(f"Failed to resolve workflow pack for tool gate {gate_id!r}: {pack_res.diagnostic_codes}")

        pack = pack_res.pack
        candidates = [
            cwd_path / Path(pack.phase_registry).parent / "manifest.yaml",
            cwd_path / "workflows" / pack.id / "manifest.yaml",
            _HUB_ROOT / Path(pack.phase_registry).parent / "manifest.yaml",
            _HUB_ROOT / "workflows" / pack.id / "manifest.yaml",
            cwd_path / "manifest.yaml",
        ]
        manifest_file: Optional[Path] = None
        for cand in candidates:
            if cand.is_file():
                manifest_file = cand
                break

        if manifest_file is None:
            raise FileNotFoundError(f"Manifest file not found for workflow pack {pack.id!r}")

        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest_data = yaml.safe_load(f) or {}
    elif isinstance(manifest, (str, Path)):
        m_path = Path(manifest)
        if not m_path.is_absolute():
            if (cwd_path / m_path).exists():
                m_path = cwd_path / m_path
            elif (_HUB_ROOT / m_path).exists():
                m_path = _HUB_ROOT / m_path
        if m_path.is_dir():
            m_path = m_path / "manifest.yaml"
        if not m_path.is_file():
            raise FileNotFoundError(f"Manifest file not found: {m_path}")
        with open(m_path, "r", encoding="utf-8") as f:
            manifest_data = yaml.safe_load(f) or {}
    elif isinstance(manifest, dict):
        manifest_data = manifest
    else:
        raise ValueError(f"Unsupported manifest parameter type: {type(manifest)}")

    if not isinstance(manifest_data, dict):
        raise ValueError(f"Invalid manifest data: expected dict, got {type(manifest_data)}")

    tool_gates = manifest_data.get("tool_gates") or {}
    if not isinstance(tool_gates, dict) or gate_id not in tool_gates:
        raise KeyError(f"Tool gate {gate_id!r} not found in manifest tool_gates: {list(tool_gates.keys())}")

    gate_cfg = tool_gates[gate_id]
    if not isinstance(gate_cfg, dict):
        raise ValueError(f"Invalid tool gate configuration for {gate_id!r}")

    adapter_rel = gate_cfg.get("adapter")
    class_name = gate_cfg.get("class")
    if not adapter_rel or not class_name:
        raise ValueError(f"Tool gate {gate_id!r} config missing 'adapter' or 'class'")

    adapter_path: Optional[Path] = None
    if Path(adapter_rel).is_absolute() and Path(adapter_rel).is_file():
        adapter_path = Path(adapter_rel)
    elif (cwd_path / adapter_rel).is_file():
        adapter_path = cwd_path / adapter_rel
    elif (_HUB_ROOT / adapter_rel).is_file():
        adapter_path = _HUB_ROOT / adapter_rel

    if adapter_path is None or not adapter_path.is_file():
        raise FileNotFoundError(f"Adapter file not found: {adapter_rel}")

    module_name = f"tool_gate_adapter_{gate_id}"
    spec = importlib.util.spec_from_file_location(module_name, adapter_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module spec from {adapter_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    if not hasattr(module, class_name):
        raise AttributeError(f"Adapter class {class_name!r} not found in {adapter_path}")

    adapter_cls = getattr(module, class_name)
    instance = adapter_cls()
    if not isinstance(instance, ToolGateAdapter):
        # We also check Protocol compatibility
        pass
    return instance
