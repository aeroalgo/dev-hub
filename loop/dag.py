from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

_ALLOWED_ROLES = {"BACK", "FRONT", "INTEG"}
_ALLOWED_SOURCE_KINDS = {"integration_gap", "manifest"}
_ALLOWED_ACTIONS = {"implement", "close"}
_ALLOWED_COMPLETION_TYPES = {"decompose", "artifact"}
# Role directory slugs must never appear as decompose-<slug> epic ids.
_RESERVED_ROLE_EPIC_IDS = frozenset({"back", "front", "integration", "integ"})
_DIAGNOSTIC_CODES = {
    "dag_manifest_missing",
    "schema_invalid",
    "duplicate_node",
    "missing_dependency",
    "cycle",
    "role_unknown",
    "path_invalid",
    "source_invalid",
    "ambiguous_pipeline",
    "epic_id_reserved",
}


def _diagnostic(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "message": message, **details}


def _safe_repo_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or value.startswith("/"):
        return False
    path = PurePosixPath(value)
    return ".." not in path.parts and not any(part == "" for part in path.parts)


def _validate_source(source: Any, diagnostics: list[dict[str, Any]]) -> None:
    if not isinstance(source, Mapping):
        diagnostics.append(_diagnostic("source_invalid", "source must be a mapping"))
        return
    if source.get("kind") not in _ALLOWED_SOURCE_KINDS:
        diagnostics.append(_diagnostic("source_invalid", "source kind is not supported"))
    artifacts = source.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts or not all(
        _safe_repo_path(item) for item in artifacts
    ):
        diagnostics.append(_diagnostic("path_invalid", "source artifacts must be safe repository paths"))


def _epic_id_from_decompose_field(value: str) -> str:
    path = PurePosixPath(value)
    parts = path.parts
    for index, part in enumerate(parts):
        if part == "plan" and index + 1 < len(parts):
            candidate = parts[index + 1]
            if candidate not in {"md", "yaml", "steps"} and not candidate.startswith("decompose-"):
                return candidate
    for part in reversed(parts):
        if part.startswith("decompose-"):
            return part[len("decompose-") :]
    name = path.name
    if name.startswith("decompose-"):
        return name[len("decompose-") :]
    return ""


def _validate_nodes(nodes: Any, diagnostics: list[dict[str, Any]]) -> None:
    if not isinstance(nodes, list) or not nodes:
        diagnostics.append(_diagnostic("schema_invalid", "nodes must be a non-empty list"))
        return
    ids: list[str] = []
    by_id: dict[str, Mapping[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, Mapping) or not isinstance(node.get("id"), str) or not node["id"]:
            diagnostics.append(_diagnostic("schema_invalid", "each node requires an id"))
            continue
        node_id = node["id"]
        if node_id in by_id:
            diagnostics.append(_diagnostic("duplicate_node", f"duplicate node id: {node_id}", node=node_id))
        ids.append(node_id)
        by_id[node_id] = node
        role = node.get("role")
        if role not in _ALLOWED_ROLES:
            diagnostics.append(_diagnostic("role_unknown", f"unknown role: {role}", node=node_id))
        for field in ("decompose", "artifact"):
            if field in node and not _safe_repo_path(node[field]):
                diagnostics.append(_diagnostic("path_invalid", f"invalid {field} path", node=node_id))
        decompose = node.get("decompose")
        if isinstance(decompose, str) and decompose:
            epic_id = _epic_id_from_decompose_field(decompose)
            if epic_id.lower() in _RESERVED_ROLE_EPIC_IDS:
                diagnostics.append(
                    _diagnostic(
                        "epic_id_reserved",
                        f"decompose epic_id must not be a role slug: {epic_id!r}",
                        node=node_id,
                        epic_id=epic_id,
                    )
                )
        dependencies = node.get("depends_on", [])
        if not isinstance(dependencies, list) or any(not isinstance(dep, str) for dep in dependencies):
            diagnostics.append(_diagnostic("schema_invalid", "depends_on must be a list of ids", node=node_id))
        elif node_id in dependencies:
            diagnostics.append(_diagnostic("cycle", f"node depends on itself: {node_id}", node=node_id))
        completion = node.get("completion")
        if not isinstance(completion, Mapping) or completion.get("type") not in _ALLOWED_COMPLETION_TYPES:
            diagnostics.append(_diagnostic("schema_invalid", "completion type is required", node=node_id))
        if node.get("action") not in _ALLOWED_ACTIONS:
            diagnostics.append(_diagnostic("schema_invalid", "action is required", node=node_id))
    node_ids = set(ids)
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        for dependency in node.get("depends_on", []):
            if dependency not in node_ids:
                diagnostics.append(_diagnostic("missing_dependency", f"missing dependency: {dependency}", node=node.get("id")))
    graph = {
        node_id: [dependency for dependency in node.get("depends_on", []) if dependency in node_ids]
        for node_id, node in by_id.items()
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            diagnostics.append(_diagnostic("cycle", f"dependency cycle includes: {node_id}", node=node_id))
            return
        if node_id in visited:
            return
        visiting.add(node_id)
        for dependency in graph[node_id]:
            visit(dependency)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in graph:
        visit(node_id)


def validate_manifest(manifest: Mapping[str, Any] | None) -> dict[str, Any]:
    diagnostics: list[dict[str, Any]] = []
    if not isinstance(manifest, Mapping):
        return {"ok": False, "manifest": {}, "diagnostics": [_diagnostic("dag_manifest_missing", "manifest is missing")]}
    if manifest.get("schema") != "loop-dag/v2":
        diagnostics.append(_diagnostic("schema_invalid", "manifest schema must be loop-dag/v2"))
    pipeline = manifest.get("pipeline")
    if not isinstance(pipeline, Mapping) or not isinstance(pipeline.get("id"), str) or not pipeline["id"]:
        diagnostics.append(_diagnostic("ambiguous_pipeline", "pipeline.id is required"))
    execution = manifest.get("execution")
    if not isinstance(execution, Mapping) or not isinstance(execution.get("autonomous"), bool):
        diagnostics.append(_diagnostic("schema_invalid", "execution.autonomous is required"))
    _validate_source(manifest.get("source"), diagnostics)
    _validate_nodes(manifest.get("nodes"), diagnostics)
    return {"ok": not diagnostics, "manifest": dict(manifest), "diagnostics": diagnostics}


def migrate_manifest(
    legacy: Mapping[str, Any] | None,
    *,
    compatibility_mode: bool = False,
) -> dict[str, Any]:
    """Migrate a v1 manifest only when compatibility mode is explicit."""
    if isinstance(legacy, Mapping) and legacy.get("schema") == "loop-dag/v1" and not compatibility_mode:
        return {
            "ok": False,
            "manifest": {},
            "migrated": False,
            "autonomous": False,
            "diagnostics": [_diagnostic("compatibility_mode_required", "v1 DAG migration requires explicit compatibility mode")],
        }
    result = adapt_manifest(legacy)
    if isinstance(legacy, Mapping) and legacy.get("schema") == "loop-dag/v1":
        result["migrated"] = bool(result.get("ok"))
    else:
        result["migrated"] = False
    return result


def adapt_manifest(legacy: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(legacy, Mapping):
        return {"ok": False, "manifest": {}, "autonomous": False, "diagnostics": [_diagnostic("dag_manifest_missing", "manifest is missing")]}
    if legacy.get("schema") != "loop-dag/v1":
        result = validate_manifest(legacy)
        result["autonomous"] = bool(result["ok"])
        return result
    nodes: list[dict[str, Any]] = []
    for old in legacy.get("nodes", []):
        if not isinstance(old, Mapping):
            continue
        role_dir = str(old.get("role_dir", "")).upper()
        role = role_dir if role_dir in _ALLOWED_ROLES else "INTEG"
        node: dict[str, Any] = {
            "id": old.get("id"),
            "role": role,
            "depends_on": old.get("depends_on", []),
            "completion": {"type": "decompose" if old.get("decompose") else "artifact"},
            "action": "implement",
        }
        if old.get("decompose"):
            node["decompose"] = old["decompose"]
        nodes.append(node)
    pipeline_id = legacy.get("pipeline_id")
    manifest = {
        "schema": "loop-dag/v2",
        "pipeline": {"id": pipeline_id},
        "source": {"kind": "manifest", "artifacts": [f"loop/dag/{pipeline_id}.yaml"]},
        "execution": {"autonomous": False},
        "nodes": nodes,
    }
    result = validate_manifest(manifest)
    result["autonomous"] = False
    result["diagnostics"].append(_diagnostic("legacy_gap_inference", "legacy v1 manifest is compatibility-only"))
    return result


def _arm_dag_next(cwd: Any, epic_id: str, role: str) -> dict[str, Any]:
    """Adapter connecting DAG epic scheduling to Transition Engine.

    Evaluates next phase for (epic_id, role) via loop.epic_transition.resolve_next
    and arms it via loop.epic_transition.arm_phase.
    """
    from pathlib import Path
    from loop.epic_transition import arm_phase, get_phase_config, resolve_next

    cwd_path = Path(cwd)
    action = resolve_next(cwd_path, epic_id, role)
    phase = action.phase
    # Validate phase fail-closed via registry config lookup
    get_phase_config(phase)

    kwargs: dict[str, Any] = {}
    if action.decompose_rel:
        kwargs["decompose_rel"] = action.decompose_rel
    if action.plan_rel:
        kwargs["plan_rel"] = action.plan_rel

    return arm_phase(cwd_path, epic_id, phase, role, **kwargs)


def dag_advance_epic(cwd: Any, epic_id: str, role: str) -> dict[str, Any]:
    """Public API for advancing an epic in DAG pipeline using _arm_dag_next."""
    return _arm_dag_next(cwd, epic_id, role)
