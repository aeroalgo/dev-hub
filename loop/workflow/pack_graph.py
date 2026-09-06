"""Executable workflow pack graph validation and doctor integration."""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Union
import yaml

from loop.workflow.command_router import route_command, load_intent_routing
from loop.workflow.registry import load_registry, resolve_workflow_pack, get_pack
from loop.workflow.schemas import WorkflowPack
from loop.workflow.skill_refs import check_skill_refs
from loop.schemas.boundary_registry import BOUNDARY_REGISTRY
from harness.hooks.agent_registry import discover_registry


_LEAN_GATE_PATTERN = re.compile(r"Gates(?:\*\*|\b)?[:\s]*@([^\s\n]+)")
_HUB_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class CheckPackGraphResult:
    """Result of walking executable workflow pack graph."""
    ok: bool
    pack_id: str
    diagnostic_codes: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


def _check_lean_gates(rules_root: Path, diagnostic_codes: List[str], hub_root: Path) -> None:
    """Scan workflow mdc files for Gates: @path references and check existence."""
    if not rules_root.is_dir():
        return
    for mdc_path in rules_root.rglob("*.mdc"):
        if "_lean" in mdc_path.parts or "_archive" in mdc_path.parts:
            continue
        try:
            text = mdc_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for match in _LEAN_GATE_PATTERN.finditer(text):
            raw_gate_ref = match.group(1).strip()
            # Clean trailing formatting or quotes
            raw_gate_ref = raw_gate_ref.rstrip("`*.,;")
            if not raw_gate_ref:
                continue

            # Check if this points to _lean gate
            if "_lean" in raw_gate_ref:
                # Remove leading @, @., ./, etc.
                gate_rel = raw_gate_ref
                if gate_rel.startswith("@."):
                    gate_rel = gate_rel[2:].lstrip("/")
                elif gate_rel.startswith("@"):
                    gate_rel = gate_rel[1:].lstrip("/")
                elif gate_rel.startswith("./"):
                    gate_rel = gate_rel[2:].lstrip("/")

                target_path = hub_root / gate_rel
                if not target_path.is_file() and not (rules_root.parent / gate_rel).is_file():
                    if "pack_gate_missing" not in diagnostic_codes:
                        diagnostic_codes.append("pack_gate_missing")


def _check_verify_agents(
    pack: WorkflowPack,
    cwd: Path,
    hub_root: Path,
    diagnostic_codes: List[str],
) -> None:
    """Check that each phase in phase_registry has declared verify_agent in manifest or no_gate_reason."""
    phase_reg_path = cwd / pack.phase_registry
    if not phase_reg_path.is_file():
        phase_reg_path = hub_root / pack.phase_registry
    if not phase_reg_path.is_file():
        # missing phase registry is handled separately
        return

    try:
        data = yaml.safe_load(phase_reg_path.read_text(encoding="utf-8"))
    except Exception:
        return

    if not isinstance(data, dict) or "phases" not in data:
        return

    phases = data.get("phases") or {}
    if not isinstance(phases, dict):
        return

    # Discover agents from manifest / project root
    agent_reg = discover_registry(hub_root)
    declared_agent_ids: Set[str] = {a.id for a in agent_reg.definitions}

    # Also load harness/manifest.yaml if present
    harness_manifest = hub_root / "harness" / "manifest.yaml"
    if harness_manifest.is_file():
        try:
            h_data = yaml.safe_load(harness_manifest.read_text(encoding="utf-8"))
            if isinstance(h_data, dict) and "agents" in h_data and isinstance(h_data["agents"], dict):
                declared_agent_ids.update(h_data["agents"].keys())
        except Exception:
            pass

    for phase_name, phase_cfg in phases.items():
        if not isinstance(phase_cfg, dict):
            continue
        verify_agent = phase_cfg.get("verify_agent")
        no_gate_reason = phase_cfg.get("no_gate_reason")

        if verify_agent is not None:
            if str(verify_agent).strip() not in declared_agent_ids:
                if "pack_agent_missing" not in diagnostic_codes:
                    diagnostic_codes.append("pack_agent_missing")
        elif not no_gate_reason:
            # Neither verify_agent nor no_gate_reason provided
            finish_gates = phase_cfg.get("finish_gates") or {}
            finish_dict = phase_cfg.get("finish_gates_dict") or {}
            need_verify = finish_gates.get("need_verify") or finish_dict.get("need_verify")
            if need_verify:
                if "pack_agent_missing" not in diagnostic_codes:
                    diagnostic_codes.append("pack_agent_missing")


def _check_tool_gates(
    pack: WorkflowPack,
    cwd: Path,
    hub_root: Path,
    diagnostic_codes: List[str],
) -> None:
    """Check tool gates declared in pack / manifest.

    FR-015: Only fail with pack_tool_gate_missing if tool_gates.required is true.
    """
    candidates = [
        cwd / Path(pack.phase_registry).parent / "manifest.yaml",
        cwd / "workflows" / pack.id / "manifest.yaml",
        hub_root / Path(pack.phase_registry).parent / "manifest.yaml",
        hub_root / "workflows" / pack.id / "manifest.yaml",
    ]
    manifest_file = next((c for c in candidates if c.is_file()), None)
    if not manifest_file:
        return

    try:
        manifest_data = yaml.safe_load(manifest_file.read_text(encoding="utf-8")) or {}
    except Exception:
        return

    if not isinstance(manifest_data, dict):
        return

    tool_gates = manifest_data.get("tool_gates")
    if isinstance(tool_gates, dict):
        # Check if any tool gate is required but adapter missing or broken
        is_required = tool_gates.get("required", False)
        for gate_id, gate_cfg in tool_gates.items():
            if gate_id == "required":
                continue
            if isinstance(gate_cfg, dict):
                gate_req = gate_cfg.get("required", is_required)
                adapter_rel = gate_cfg.get("adapter")
                if not adapter_rel:
                    if gate_req and "pack_tool_gate_missing" not in diagnostic_codes:
                        diagnostic_codes.append("pack_tool_gate_missing")
                else:
                    adapter_path = hub_root / adapter_rel if not Path(adapter_rel).is_absolute() else Path(adapter_rel)
                    if not adapter_path.is_file() and gate_req:
                        if "pack_tool_gate_missing" not in diagnostic_codes:
                            diagnostic_codes.append("pack_tool_gate_missing")


def _check_schemas(
    pack: WorkflowPack,
    cwd: Path,
    hub_root: Path,
    diagnostic_codes: List[str],
) -> None:
    """Check schema declarations for pack if schemas are declared."""
    # Check if pack explicitly declares schemas in its manifest or phase_registry
    candidates = [
        cwd / Path(pack.phase_registry).parent / "manifest.yaml",
        cwd / "workflows" / pack.id / "manifest.yaml",
        hub_root / Path(pack.phase_registry).parent / "manifest.yaml",
        hub_root / "workflows" / pack.id / "manifest.yaml",
    ]
    manifest_file = next((c for c in candidates if c.is_file()), None)
    if not manifest_file:
        return

    try:
        manifest_data = yaml.safe_load(manifest_file.read_text(encoding="utf-8")) or {}
    except Exception:
        return

    if not isinstance(manifest_data, dict):
        return

    declared_schemas = manifest_data.get("schemas") or []
    if isinstance(declared_schemas, list):
        for s_id in declared_schemas:
            if s_id not in BOUNDARY_REGISTRY:
                if "schema_missing" not in diagnostic_codes and "pack_schema_missing" not in diagnostic_codes:
                    diagnostic_codes.append("schema_missing")


def check_pack_graph(
    pack_or_id: Optional[Union[WorkflowPack, str]] = None,
    cwd: Optional[Union[Path, str]] = None,
    hub_root: Optional[Union[Path, str]] = None,
) -> CheckPackGraphResult:
    """Walk and validate executable workflow pack graph.

    Walks:
    - Registry entry & pack resolution
    - rules_root exists
    - Each role index exists if role subdirs present
    - Each intent -> pipeline command routes and resolves to an existing file
    - Each _lean gate referenced by workflow mdc exists
    - Each phase verify_agent in manifest or no_gate_reason documented
    - Skill @ references via check_skill_refs
    - Schemas in BOUNDARY_REGISTRY if declared
    - Optional tool gates
    """
    cwd_path = Path(cwd).resolve() if cwd is not None else Path.cwd().resolve()
    hub_root_path = Path(hub_root).resolve() if hub_root is not None else _HUB_ROOT

    diagnostic_codes: List[str] = []

    try:
        target_root = cwd_path if cwd is not None else (hub_root_path if hub_root is not None else Path.cwd().resolve())

        if isinstance(pack_or_id, WorkflowPack):
            pack = pack_or_id
            pack_id = pack.id
        elif isinstance(pack_or_id, str) and pack_or_id:
            pack_id = pack_or_id
            try:
                reg = load_registry(hub_root=target_root)
            except Exception:
                reg = load_registry(hub_root=hub_root_path)
            pack = get_pack(reg, pack_id)
            if pack is None:
                return CheckPackGraphResult(
                    ok=False,
                    pack_id=pack_id,
                    diagnostic_codes=["invalid_workflow_pack"],
                )
        else:
            res = resolve_workflow_pack(cwd=target_root, hub_root=hub_root_path)
            if not res.ok or res.pack is None:
                codes = res.diagnostic_codes or ["pack_resolve_failed"]
                return CheckPackGraphResult(
                    ok=False,
                    pack_id=res.pack_id,
                    diagnostic_codes=codes,
                )
            pack = res.pack
            pack_id = res.pack_id

        rules_root_path = target_root / pack.rules_root
        if not rules_root_path.is_dir():
            diagnostic_codes.append("pack_rules_missing")

        phase_reg_path = target_root / pack.phase_registry
        if not phase_reg_path.is_file():
            diagnostic_codes.append("pack_phase_registry_missing")

        # Memory bank root check
        mb_path = target_root / pack.memory_bank
        if not mb_path.exists():
            diagnostic_codes.append("mb_root_missing")
        elif not mb_path.is_dir():
            diagnostic_codes.append("mb_root_not_dir")
        elif not os.access(mb_path, os.W_OK):
            diagnostic_codes.append("mb_root_not_writable")

        # 1. Check intent routes mapping to this pack
        try:
            try:
                intent_table = load_intent_routing(hub_root=target_root)
            except Exception:
                intent_table = load_intent_routing(hub_root=hub_root_path)

            for intent_name, intent_route in intent_table.intents.items():
                if intent_route.pack == pack_id:
                    for step in intent_route.pipeline:
                        c_res = route_command(pack, step.command, hub_root=target_root)
                        if not c_res.ok:
                            for c in c_res.diagnostic_codes:
                                if c not in diagnostic_codes:
                                    diagnostic_codes.append(c)
        except Exception:
            if "workflow_pack_check_error" not in diagnostic_codes:
                diagnostic_codes.append("workflow_pack_check_error")

        # 2. Also check standard commands for pack roles/prefixes if any rules exist
        if rules_root_path.is_dir():
            _check_lean_gates(rules_root_path, diagnostic_codes, target_root)

        # 3. Check phase registry verify agents
        _check_verify_agents(pack, target_root, hub_root_path, diagnostic_codes)

        # 4. Check skill references across rules_root
        if rules_root_path.is_dir():
            # Check skill references in pack's rules_root
            rel_rules_root = str(pack.rules_root).rstrip("/")
            corpus_globs = [
                f"{rel_rules_root}/**/*.mdc",
                f"{rel_rules_root}/**/*.md",
            ]
            try:
                missing_skills = check_skill_refs(
                    target_root,
                    corpus_globs=corpus_globs,
                )
                if missing_skills:
                    if "skill_ref_missing" not in diagnostic_codes:
                        diagnostic_codes.append("skill_ref_missing")
            except Exception:
                pass

        # 5. Check tool gates
        _check_tool_gates(pack, target_root, hub_root_path, diagnostic_codes)

        # 6. Check schemas
        _check_schemas(pack, target_root, hub_root_path, diagnostic_codes)

        ok = len(diagnostic_codes) == 0
        return CheckPackGraphResult(
            ok=ok,
            pack_id=pack_id,
            diagnostic_codes=diagnostic_codes,
        )
    except Exception as e:
        return CheckPackGraphResult(
            ok=False,
            pack_id=str(pack_or_id or ""),
            diagnostic_codes=["workflow_pack_check_error"],
            details={"error": str(e)},
        )
