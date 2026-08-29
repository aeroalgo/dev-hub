"""Discover eligible product workspaces from the DSH registry."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class WorkspaceRef:
    """A registered workspace that contains a usable memory-bank."""

    path: Path
    workspace_id: str


class WorkspacesError(RuntimeError):
    """Raised when the DSH workspace registry cannot be read safely."""

    def __init__(self, message: str, *, diagnostic_code: str) -> None:
        super().__init__(message)
        self.diagnostic_code = diagnostic_code


def is_eligible(path: Path) -> bool:
    """Return whether *path* is an existing project with a memory-bank directory."""

    return path.is_dir() and (path / "memory-bank").is_dir()


def discover(dsh_home: Path) -> list[WorkspaceRef]:
    """Read ``workspace.json`` and return only registered eligible workspaces.

    Invalid or missing registry state fails closed. Individual registered paths
    that no longer exist or lack ``memory-bank`` are skipped.
    """

    dsh_home = Path(dsh_home).expanduser()
    if not dsh_home.is_dir():
        raise WorkspacesError(
            f"DSH_HOME does not exist or is not a directory: {dsh_home}",
            diagnostic_code="dsh_home_missing",
        )

    registry_path = dsh_home / "storages" / "workspace.json"
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkspacesError(
            f"workspace registry does not exist: {registry_path}",
            diagnostic_code="workspace_missing",
        ) from exc
    except (OSError, UnicodeError) as exc:
        raise WorkspacesError(
            f"cannot read workspace registry: {registry_path}",
            diagnostic_code="workspace_unreadable",
        ) from exc
    except json.JSONDecodeError as exc:
        raise WorkspacesError(
            f"invalid JSON in workspace registry: {registry_path}",
            diagnostic_code="workspace_invalid_json",
        ) from exc

    entries = _workspace_entries(payload)
    result: list[WorkspaceRef] = []
    for workspace_id, entry in entries:
        if not isinstance(workspace_id, str) or not isinstance(entry, dict):
            continue
        path_value = entry.get("path")
        if not isinstance(path_value, str) or not path_value:
            continue
        path = Path(path_value).expanduser()
        if is_eligible(path):
            result.append(WorkspaceRef(path=path.resolve(), workspace_id=workspace_id))
    return result


def _workspace_entries(payload: Any) -> list[tuple[str, Any]]:
    if not isinstance(payload, dict):
        raise WorkspacesError(
            "workspace registry must contain a JSON object",
            diagnostic_code="workspace_invalid_shape",
        )
    tables = payload.get("tables")
    if not isinstance(tables, dict):
        raise WorkspacesError(
            "workspace registry is missing tables",
            diagnostic_code="workspace_invalid_shape",
        )
    workspaces = tables.get("workspaces")
    if not isinstance(workspaces, dict):
        raise WorkspacesError(
            "workspace registry is missing tables.workspaces",
            diagnostic_code="workspace_invalid_shape",
        )
    return list(workspaces.items())
