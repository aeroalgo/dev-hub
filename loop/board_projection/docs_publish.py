from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from loop.board_projection.card_copy import prompt_md_path
from loop.board_projection.config import load_projection_config
from loop.board_projection.errors import ProjectionConfigError
from loop.board_projection.mapping import load_board_epic_map, resolve_map_path
from loop.board_projection.registry import get_adapter
from loop.kernel.index import plan_path, resolve_epic_kind, resolve_epic_role


class DocumentAttachAdapter(Protocol):
    @property
    def provider_name(self) -> str: ...

    def attach_document(self, external_id: str, filename: str, content: bytes) -> dict[str, Any]: ...


@dataclass(frozen=True)
class BoardDocsResult:
    status: str
    epic_id: str
    external_id: str | None = None
    local_path: str | None = None
    attached: list[dict[str, Any]] | None = None
    error: str | None = None
    disabled_reason: str | None = None


def publish_board_docs(
    project_root: Path | str,
    epic_id: str,
    role: str = "back",
    kind: str | None = None,
    *,
    include_plan: bool = True,
    include_prompt: bool = True,
    config_path: Path | str | None = None,
    map_path: Path | str | None = None,
    adapter: DocumentAttachAdapter | None = None,
) -> BoardDocsResult:
    """
    Manual-only: attach epic prompt.md + plan.md to the mapped board card.
    Never called from finish/halt. Lean set — no generated brief.
    """
    root = Path(project_root)
    resolved_config_path = (
        Path(config_path) if config_path is not None else root / ".loop" / "board-projection.yaml"
    )
    resolved_map_path = resolve_map_path(project_root=root, explicit_path=map_path)

    config, disabled_reason = load_projection_config(resolved_config_path)
    if disabled_reason == "missing_config":
        return BoardDocsResult(
            status="disabled",
            epic_id=epic_id,
            disabled_reason="missing_config",
        )
    if config is None or config.provider == "none" or disabled_reason == "provider_none":
        return BoardDocsResult(
            status="disabled",
            epic_id=epic_id,
            disabled_reason="provider_none",
        )
    if disabled_reason:
        raise ProjectionConfigError(
            f"Active board projection provider '{config.provider}' is misconfigured: {disabled_reason}"
        )

    try:
        resolved_role = resolve_epic_role(root, epic_id, role=role, kind=kind)
        resolved_kind = resolve_epic_kind(root, epic_id, kind=kind, role=resolved_role)
    except (ValueError, FileNotFoundError, OSError) as exc:
        return BoardDocsResult(status="error", epic_id=epic_id, error=str(exc))

    if not config.is_role_allowed(resolved_role):
        return BoardDocsResult(
            status="disabled",
            epic_id=epic_id,
            disabled_reason="role_not_allowed",
        )

    board_map = load_board_epic_map(resolved_map_path)
    entry = board_map.epics.get(epic_id)
    if entry is None or not entry.external_id:
        return BoardDocsResult(
            status="error",
            epic_id=epic_id,
            error="board card missing: run board-sync/finish first to create mapping",
        )

    if board_map.provider and board_map.provider.strip().lower() != config.provider.strip().lower():
        return BoardDocsResult(
            status="error",
            epic_id=epic_id,
            external_id=entry.external_id,
            error=(
                f"provider mismatch: map={board_map.provider!r} config={config.provider!r}"
            ),
        )

    active = adapter
    if active is None:
        active = get_adapter(config)  # type: ignore[assignment]
    if active is None:
        return BoardDocsResult(
            status="disabled",
            epic_id=epic_id,
            disabled_reason="provider_none",
        )
    if not hasattr(active, "attach_document"):
        return BoardDocsResult(
            status="error",
            epic_id=epic_id,
            external_id=entry.external_id,
            error=f"provider {getattr(active, 'provider_name', '?')} does not support attach_document",
        )

    prompt_file = prompt_md_path(root, epic_id, role=resolved_role, kind=resolved_kind)
    plan_file = plan_path(root, resolved_role, epic_id, kind=resolved_kind)
    local_path = None
    if prompt_file.is_file():
        local_path = str(prompt_file.relative_to(root))
    elif plan_file.is_file():
        local_path = str(plan_file.relative_to(root))

    attachments: list[tuple[str, Path]] = []
    if include_prompt:
        if not prompt_file.is_file():
            return BoardDocsResult(
                status="error",
                epic_id=epic_id,
                external_id=entry.external_id,
                error=f"prompt.md missing: {prompt_file}",
            )
        attachments.append((f"{epic_id}-prompt.md", prompt_file))
    if include_plan:
        if not plan_file.is_file():
            return BoardDocsResult(
                status="error",
                epic_id=epic_id,
                external_id=entry.external_id,
                error=f"plan.md missing: {plan_file}",
            )
        attachments.append((f"{epic_id}-plan.md", plan_file))

    if not attachments:
        return BoardDocsResult(
            status="error",
            epic_id=epic_id,
            external_id=entry.external_id,
            error="nothing to attach: enable prompt and/or plan",
        )

    attached: list[dict[str, Any]] = []
    try:
        for filename, path in attachments:
            attached.append(
                active.attach_document(
                    entry.external_id,
                    filename,
                    path.read_bytes(),
                )
            )
    except Exception as exc:
        return BoardDocsResult(
            status="error",
            epic_id=epic_id,
            external_id=entry.external_id,
            local_path=local_path,
            attached=attached or None,
            error=str(exc),
        )

    return BoardDocsResult(
        status="success",
        epic_id=epic_id,
        external_id=entry.external_id,
        local_path=local_path,
        attached=attached,
    )
