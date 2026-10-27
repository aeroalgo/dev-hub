from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from loop.board_projection.config import ProjectDocFile, load_projection_config
from loop.board_projection.errors import ProjectionConfigError
from loop.board_projection.registry import get_adapter


class ProjectDocsAdapter(Protocol):
    @property
    def provider_name(self) -> str: ...

    def publish_project_document(
        self,
        *,
        filename: str,
        content: bytes,
        folder_name: str = "docs",
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ProjectDocsResult:
    status: str
    published: list[dict[str, Any]] | None = None
    error: str | None = None
    disabled_reason: str | None = None


def _resolve_entries(
    project_root: Path,
    configured: list[ProjectDocFile],
    extra_paths: list[str] | None,
) -> list[tuple[Path, str]]:
    root = project_root.resolve()
    entries: list[tuple[Path, str]] = []
    seen: set[str] = set()

    def add(rel: str, as_name: str | None = None) -> None:
        path = (root / rel).resolve()
        if not str(path).startswith(str(root)):
            raise ProjectionConfigError(f"project doc path escapes project root: {rel}")
        if not path.is_file():
            raise ProjectionConfigError(f"project doc file not found: {rel}")
        name = (as_name or path.name).strip()
        key = name.lower()
        if key in seen:
            return
        seen.add(key)
        entries.append((path, name))

    for item in configured:
        add(item.path, item.as_name)
    for rel in extra_paths or []:
        add(rel)
    return entries


def publish_project_docs(
    project_root: Path | str,
    *,
    files: list[str] | None = None,
    folder_name: str | None = None,
    config_path: Path | str | None = None,
    adapter: ProjectDocsAdapter | None = None,
) -> ProjectDocsResult:
    """
    Manual-only publish of project documentation (workflow/gitflow/runbooks)
    into Bitrix group Disk / Plane project pages. Never called from finish/halt.
    Not epic-scoped.
    """
    root = Path(project_root)
    resolved_config_path = (
        Path(config_path) if config_path is not None else root / ".loop" / "board-projection.yaml"
    )
    config, disabled_reason = load_projection_config(resolved_config_path)
    if disabled_reason == "missing_config":
        return ProjectDocsResult(status="disabled", disabled_reason="missing_config")
    if config is None or config.provider == "none" or disabled_reason == "provider_none":
        return ProjectDocsResult(status="disabled", disabled_reason="provider_none")
    if disabled_reason:
        raise ProjectionConfigError(
            f"Active board projection provider '{config.provider}' is misconfigured: {disabled_reason}"
        )

    active = adapter
    if active is None:
        active = get_adapter(config)  # type: ignore[assignment]
    if active is None:
        return ProjectDocsResult(status="disabled", disabled_reason="provider_none")
    if not hasattr(active, "publish_project_document"):
        return ProjectDocsResult(
            status="error",
            error=f"provider {getattr(active, 'provider_name', '?')} does not support publish_project_document",
        )

    docs_cfg = config.project_docs
    target_folder = (folder_name or docs_cfg.folder_name or "docs").strip()
    try:
        entries = _resolve_entries(root, docs_cfg.files, files)
    except ProjectionConfigError as exc:
        return ProjectDocsResult(status="error", error=str(exc))

    if not entries:
        return ProjectDocsResult(
            status="error",
            error="no project docs selected: set project_docs.files in board-projection.yaml or pass --file",
        )

    published: list[dict[str, Any]] = []
    try:
        for path, name in entries:
            published.append(
                active.publish_project_document(
                    filename=name,
                    content=path.read_bytes(),
                    folder_name=target_folder,
                )
            )
    except Exception as exc:
        return ProjectDocsResult(status="error", published=published or None, error=str(exc))

    return ProjectDocsResult(status="success", published=published)
