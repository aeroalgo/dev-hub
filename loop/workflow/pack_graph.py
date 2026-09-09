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
from typing import Tuple

_REFERENCE_PATTERN = re.compile(r"@([a-zA-Z0-9_\-\./]+)")
_NON_FILE_REF_KEYWORDS = {
    "file", "user", "param", "returns", "see", "today", "now",
    "explorer", "sunset-inventory", "gate-repair", "reconcile-verify",
    "analyze-verify", "verify", "verify-bugfix", "verify-decompose",
    "verify-implement", "verify-publish", "verify-script", "verify-edit",
    "verify-qa", "default", "worker", "aNN", "rNN", "sNN",
}


_ARCHIVE_EXCLUSION_PATTERNS = [
    re.compile(r"_archive/"),
    re.compile(r"archive/"),
    re.compile(r"tasks/log/"),
    re.compile(r"tasks/"),
    re.compile(r"memory-bank/"),
    re.compile(r"\.git/"),
    re.compile(r"\.claude/runtime/"),
    re.compile(r"graphify-out/"),
]


_LEAN_GATE_PATTERN = re.compile(r"Gates(?:\*\*|\b)?[:\s]*@([^\s\n]+)")
_HUB_ROOT = Path(__file__).resolve().parents[2]

_COMPOSITE_STUB_PATTERNS = [
    re.compile(r"mainrule"),
    re.compile(r"token-economy"),
    re.compile(r"spec-first-replace-hard"),
    re.compile(r"finish-block"),
    re.compile(r"finish-doc-router"),
    re.compile(r"memory-bank-paths"),
    re.compile(r"epic-scoped-paths"),
    re.compile(r"context-session-economy"),
    re.compile(r"role-core-contract"),
    re.compile(r"test-timeout"),
    re.compile(r"_lean/"),
    re.compile(r"isolation_rules"),
]


def _is_composite_stub_or_router(path_str: str) -> bool:
    return any(p.search(path_str) for p in _COMPOSITE_STUB_PATTERNS)


def _is_peer_policy_pair(a: str, b: str) -> bool:
    return (
        "shared/" in a
        and "shared/" in b
        and Path(a).name.startswith("workflow-")
        and Path(b).name.startswith("workflow-")
    )



@dataclass
class CheckPackGraphResult:
    """Result of walking executable workflow pack graph."""
    ok: bool
    pack_id: str
    diagnostic_codes: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReferenceLocation:
    path: str
    line: int

    def to_dict(self) -> Dict[str, Any]:
        return {"path": self.path, "line": self.line}


@dataclass
class ReferenceEdge:
    source_path: str
    source_line: int
    raw_target: str
    target_path: Optional[str] = None
    target_canonical: Optional[str] = None


@dataclass
class ReferenceDiagnostic:
    code: str
    message: str
    target: str
    locations: List[Dict[str, Any]] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "target": self.target,
            "locations": self.locations,
            "details": self.details,
        }


def _resolve_reference_target(
    raw: str,
    source_file: Path,
    target_root: Path,
    hub_root: Path,
    rules_root: Path,
) -> Tuple[Optional[Path], Optional[str]]:
    path_part = raw.split("#")[0].split(":")[0]
    if path_part.startswith("./"):
        clean_rel = path_part[2:]
    else:
        clean_rel = path_part

    candidates = [
        target_root / clean_rel,
        hub_root / clean_rel,
        source_file.parent / clean_rel,
        rules_root / clean_rel,
        rules_root.parent / clean_rel,
    ]
    if clean_rel.startswith(".cursor/rules/"):
        suffix = clean_rel[len(".cursor/rules/"):]
        candidates.extend([
            target_root / "harness/cursor/rules" / suffix,
            hub_root / "harness/cursor/rules" / suffix,
        ])
    elif clean_rel.startswith("harness/cursor/rules/"):
        suffix = clean_rel[len("harness/cursor/rules/"):]
        candidates.extend([
            target_root / ".cursor/rules" / suffix,
            hub_root / ".cursor/rules" / suffix,
        ])
    elif clean_rel.startswith(".agents/skills/"):
        suffix = clean_rel[len(".agents/skills/"):]
        candidates.extend([
            target_root / "harness/skills" / suffix,
            hub_root / "harness/skills" / suffix,
        ])
    elif clean_rel.startswith(".claude/"):
        suffix = clean_rel[len(".claude/"):]
        candidates.extend([
            target_root / "harness/claude" / suffix,
            hub_root / "harness/claude" / suffix,
        ])

    for c in candidates:
        if c.is_file():
            resolved = c.resolve()
            try:
                canonical = str(resolved.relative_to(target_root.resolve()))
            except ValueError:
                try:
                    canonical = str(resolved.relative_to(hub_root.resolve()))
                except ValueError:
                    canonical = str(resolved)
            return resolved, canonical

    return None, None


def extract_reference_edges(
    file_path: Path,
    target_root: Path,
    hub_root: Path,
    rules_root: Path,
) -> List[ReferenceEdge]:
    edges: List[ReferenceEdge] = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return edges

    try:
        rel_source = str(file_path.resolve().relative_to(target_root.resolve()))
    except ValueError:
        try:
            rel_source = str(file_path.resolve().relative_to(hub_root.resolve()))
        except ValueError:
            rel_source = str(file_path)

    for line_no, line in enumerate(content.splitlines(), start=1):
        for m in _REFERENCE_PATTERN.finditer(line):
            chars_to_strip = ".,;:`*)'\""
            raw = m.group(1).rstrip(chars_to_strip)
            if not raw or raw in _NON_FILE_REF_KEYWORDS:
                continue
            if raw.endswith("/"):
                continue
            if any(pat.search(raw) for pat in _ARCHIVE_EXCLUSION_PATTERNS):
                continue
            if "/" not in raw and not any(raw.endswith(ext) for ext in (".mdc", ".md", ".yaml", ".yml", ".json", ".py", ".toml", ".sh", ".txt")):
                continue
            resolved, canonical = _resolve_reference_target(raw, file_path, target_root, hub_root, rules_root)
            if resolved is not None and resolved.is_dir():
                continue
            if canonical and any(pat.search(canonical) for pat in _ARCHIVE_EXCLUSION_PATTERNS):
                continue
            edges.append(ReferenceEdge(
                source_path=rel_source,
                source_line=line_no,
                raw_target=raw,
                target_path=str(resolved) if resolved else None,
                target_canonical=canonical or raw,
            ))
    return edges


def validate_reference_graph(
    rules_root: Path,
    target_root: Path,
    hub_root: Path,
    active_only: bool = False,
) -> List[ReferenceDiagnostic]:
    diagnostics: List[ReferenceDiagnostic] = []
    if not rules_root.is_dir():
        return diagnostics

    files: List[Path] = []
    for p in sorted(rules_root.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix not in (".md", ".mdc", ".yaml", ".yml", ".json"):
            continue
        rel_str = str(p)
        try:
            rel_str = str(p.resolve().relative_to(target_root.resolve()))
        except ValueError:
            try:
                rel_str = str(p.resolve().relative_to(hub_root.resolve()))
            except ValueError:
                pass
        if any(pat.search(rel_str) for pat in _ARCHIVE_EXCLUSION_PATTERNS) or any(part in ("_archive", "archive", "tasks", "graphify-out", ".git", ".claude/runtime", "memory-bank") for part in p.parts):
            continue
        files.append(p)

    file_edges: Dict[Path, List[ReferenceEdge]] = {}
    for f in files:
        edges = extract_reference_edges(f, target_root, hub_root, rules_root)
        if edges:
            file_edges[f.resolve()] = edges

    if active_only:
        active_files = {
            f.resolve() for f in files
            if f.name.startswith("workflow")
        }
        reachable_files = set(active_files)
        pending = list(active_files)
        while pending:
            current = pending.pop()
            for edge in file_edges.get(current, []):
                if edge.target_path is None:
                    continue
                target = Path(edge.target_path).resolve()
                if target in file_edges and target not in reachable_files:
                    reachable_files.add(target)
                    pending.append(target)
        files = [f for f in files if f.resolve() in reachable_files]
        file_edges = {
            path: edges for path, edges in file_edges.items()
            if path in reachable_files
        }

    # 1. Dangling references & 2. Direct duplicate edges
    for f in files:
        try:
            rel_source = str(f.resolve().relative_to(target_root.resolve()))
        except ValueError:
            try:
                rel_source = str(f.resolve().relative_to(hub_root.resolve()))
            except ValueError:
                rel_source = str(f)
        edges = file_edges.get(f.resolve(), [])
        target_lines: Dict[str, List[int]] = {}
        for edge in edges:
            if edge.target_path is None:
                diagnostics.append(ReferenceDiagnostic(
                    code="pack_reference_dangling",
                    message=f"Dangling reference to '{edge.raw_target}' in {rel_source}:{edge.source_line}",
                    target=edge.raw_target,
                    locations=[{"path": rel_source, "line": edge.source_line}],
                    details={"source_path": rel_source, "source_line": edge.source_line, "target": edge.raw_target},
                ))
            target_key = edge.target_canonical or edge.raw_target
            target_lines.setdefault(target_key, []).append(edge.source_line)

        for target_key, lines in target_lines.items():
            if len(lines) > 1:
                diagnostics.append(ReferenceDiagnostic(
                    code="pack_reference_duplicate",
                    message=f"Direct duplicate reference to '{target_key}' in {rel_source} at lines {lines}",
                    target=target_key,
                    locations=[{"path": rel_source, "line": ln} for ln in lines],
                    details={"source_path": rel_source, "lines": lines, "target": target_key},
                ))

    # 3. Transitive owner ambiguity
    adj: Dict[str, List[Tuple[str, int]]] = {}
    for edges in file_edges.values():
        if not edges:
            continue
        source = edges[0].source_path
        for edge in edges:
            if edge.target_canonical and edge.target_path is not None:
                adj.setdefault(source, []).append((edge.target_canonical, edge.source_line))

    for source, direct_list in adj.items():
        if _is_composite_stub_or_router(source):
            continue
        for direct_target, direct_line in direct_list:
            if _is_composite_stub_or_router(direct_target) or "templates/" in direct_target or "skills/" in direct_target:
                continue
            for intermediate, _ in direct_list:
                if intermediate == direct_target or _is_composite_stub_or_router(intermediate) or "templates/" in intermediate or "skills/" in intermediate:
                    continue
                if "workflow-" in Path(intermediate).name and "workflow-" in Path(source).name and "shared/" not in intermediate:
                    continue
                if _is_peer_policy_pair(direct_target, intermediate):
                    continue
                for nxt, nxt_line in adj.get(intermediate, []):
                    if nxt == direct_target:
                        diagnostics.append(ReferenceDiagnostic(
                            code="pack_reference_transitive_ambiguity",
                            message=(
                                f"Transitive owner ambiguity for '{direct_target}': directly referenced in '{source}' "
                                f"(line {direct_line}) and transitively via '{intermediate}' (line {nxt_line})"
                            ),
                            target=direct_target,
                            locations=[
                                {"path": source, "line": direct_line},
                                {"path": intermediate, "line": nxt_line},
                            ],
                            details={
                                "source_path": source,
                                "direct_line": direct_line,
                                "transitive_owner": intermediate,
                                "transitive_line": nxt_line,
                                "target": direct_target,
                            },
                        ))

    return diagnostics


def _check_reference_graph(
    pack: WorkflowPack,
    target_root: Path,
    hub_root: Path,
    diagnostic_codes: List[str],
    details: Dict[str, Any],
) -> None:
    rules_root_path = target_root / pack.rules_root
    if not rules_root_path.is_dir():
        rules_root_path = hub_root / pack.rules_root
    if not rules_root_path.is_dir():
        return

    diags = validate_reference_graph(
        rules_root_path,
        target_root,
        hub_root,
        active_only=True,
    )
    if diags:
        details.setdefault("reference_diagnostics", []).extend([d.to_dict() for d in diags])
        for d in diags:
            if d.code not in diagnostic_codes:
                diagnostic_codes.append(d.code)


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
                try:
                    intent_table = load_intent_routing(hub_root=hub_root_path)
                except Exception:
                    intent_table = load_intent_routing(hub_root=_HUB_ROOT)

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

        # 7. Check reference graph (direct duplicate, transitive ambiguity, dangling reference)
        details: Dict[str, Any] = {}
        if rules_root_path.is_dir():
            _check_reference_graph(pack, target_root, hub_root_path, diagnostic_codes, details)

        ok = len(diagnostic_codes) == 0
        return CheckPackGraphResult(
            ok=ok,
            pack_id=pack_id,
            diagnostic_codes=diagnostic_codes,
            details=details,
        )
    except Exception as e:
        return CheckPackGraphResult(
            ok=False,
            pack_id=str(pack_or_id or ""),
            diagnostic_codes=["workflow_pack_check_error"],
            details={"error": str(e)},
        )

def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    from loop.doctor.checks.workflow_pack import run_doctor_workflow_pack
    parser = argparse.ArgumentParser(description="Workflow pack graph checker & doctor")
    parser.add_argument("command", nargs="?", default="doctor", choices=["check", "doctor"])
    parser.add_argument("--pack", dest="pack_id", default=None)
    parser.add_argument("--cwd", dest="cwd", default=None)
    parser.add_argument("--hub-root", dest="hub_root", default=None)
    args = parser.parse_args(argv)
    return run_doctor_workflow_pack(cwd=args.cwd, hub_root=args.hub_root, pack_id=args.pack_id)


if __name__ == "__main__":
    import sys
    sys.exit(main())
