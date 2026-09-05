"""Forbidden bundle load policies dispatched by ArtifactLayout."""
from __future__ import annotations

import re
from typing import Protocol, Union, runtime_checkable

from loop.paths.pack_layout import ArtifactLayout

_PLAN_MD_RE = re.compile(r"(?:^|/)plan-[^/]+\.md$")


class ForbiddenPolicyError(Exception):
    """Raised when forbidden policy resolution or execution fails."""
    pass


@runtime_checkable
class ForbiddenPolicy(Protocol):
    """Protocol for layout-specific bundle load forbidden policies."""

    def is_forbidden(self, path: str, mode: str | None) -> bool:
        """Return True if path should be forbidden and skipped from load bundle."""
        ...


class SoftwareEpicV1Policy:
    """Forbidden policy for software-epic-v1 layout.

    Forbids full plan-*.md files during execution phases (IMPLEMENT, QA, BUGFIX, etc.),
    while allowing them during DECOMPOSE.
    """

    def is_forbidden(self, path: str, mode: str | None) -> bool:
        mode_upper = (mode or "").strip().upper()
        if _PLAN_MD_RE.search(path):
            return mode_upper != "DECOMPOSE"
        return False


class ProductionEpicV1Policy:
    """Forbidden policy for production-epic-v1 layout.

    Forbids full plan-*.md files during execution phases, allowing during DECOMPOSE.
    """

    def is_forbidden(self, path: str, mode: str | None) -> bool:
        mode_upper = (mode or "").strip().upper()
        if _PLAN_MD_RE.search(path):
            return mode_upper != "DECOMPOSE"
        return False


def policy_for_layout(
    artifact_layout: Union[ArtifactLayout, str, None],
) -> ForbiddenPolicy:
    """Dispatch forbidden policy based on artifact_layout.

    Fail-closed: raises ForbiddenPolicyError if artifact_layout is unsupported or None.
    """
    if artifact_layout is None:
        raise ForbiddenPolicyError("artifact_layout cannot be None")

    layout_val = (
        artifact_layout.value
        if isinstance(artifact_layout, ArtifactLayout)
        else str(artifact_layout)
    )

    if layout_val == ArtifactLayout.software_epic_v1.value or layout_val == "software-epic-v1":
        return SoftwareEpicV1Policy()
    if layout_val == ArtifactLayout.production_epic_v1.value or layout_val == "production-epic-v1":
        return ProductionEpicV1Policy()

    raise ForbiddenPolicyError(f"Unsupported artifact layout for forbidden policy: {layout_val!r}")
