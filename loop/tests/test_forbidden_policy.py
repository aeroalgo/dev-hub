"""Tests for loop.paths.forbidden_policy module."""

import pytest
from loop.paths.forbidden_policy import (
    ForbiddenPolicy,
    ForbiddenPolicyError,
    ProductionEpicV1Policy,
    SoftwareEpicV1Policy,
    policy_for_layout,
)
from loop.paths.pack_layout import ArtifactLayout


def test_policy_for_layout_software_epic_v1():
    """policy_for_layout(ArtifactLayout.software_epic_v1) -> SoftwareEpicV1Policy."""
    policy = policy_for_layout(ArtifactLayout.software_epic_v1)
    assert isinstance(policy, SoftwareEpicV1Policy)
    assert isinstance(policy, ForbiddenPolicy)

    # String input also works
    policy_str = policy_for_layout("software-epic-v1")
    assert isinstance(policy_str, SoftwareEpicV1Policy)

    # Behavior: rejects plan-*.md unless mode is DECOMPOSE
    assert policy.is_forbidden("memory-bank/back/plan/plan-T-HUB-001.md", mode="IMPLEMENT") is True
    assert policy.is_forbidden("memory-bank/back/plan/plan-T-HUB-001.md", mode="QA") is True
    assert policy.is_forbidden("memory-bank/back/plan/plan-T-HUB-001.md", mode="BUGFIX") is True
    assert policy.is_forbidden("memory-bank/back/plan/plan-T-HUB-001.md", mode="DECOMPOSE") is False
    assert policy.is_forbidden("memory-bank/back/plan/plan-T-HUB-001.md", mode="decompose") is False

    # Non-plan files are not forbidden
    assert policy.is_forbidden("memory-bank/back/plan/T-HUB-001/yaml/steps/s01.yaml", mode="IMPLEMENT") is False
    assert policy.is_forbidden("memory-bank/activeContext.md", mode="IMPLEMENT") is False


def test_policy_for_layout_production_epic_v1():
    """policy_for_layout(ArtifactLayout.production_epic_v1) -> ProductionEpicV1Policy."""
    policy = policy_for_layout(ArtifactLayout.production_epic_v1)
    assert isinstance(policy, ProductionEpicV1Policy)
    assert isinstance(policy, ForbiddenPolicy)

    # String input also works
    policy_str = policy_for_layout("production-epic-v1")
    assert isinstance(policy_str, ProductionEpicV1Policy)

    # Behavior for production-epic-v1:
    # Rejects raw plan files in execution modes (IMPLEMENT / QA / BUGFIX)
    assert policy.is_forbidden("memory-bank/video/script/plan/plan-V-001.md", mode="IMPLEMENT") is True
    assert policy.is_forbidden("memory-bank/video/script/plan/plan-V-001.md", mode="QA") is True
    assert policy.is_forbidden("memory-bank/video/script/plan/plan-V-001.md", mode="DECOMPOSE") is False
    assert policy.is_forbidden("memory-bank/video/script/plan/steps/s01.yaml", mode="IMPLEMENT") is False


def test_policy_for_layout_unknown():
    """unknown layout -> ForbiddenPolicyError (fail-closed)."""
    with pytest.raises(ForbiddenPolicyError, match="Unsupported artifact layout"):
        policy_for_layout("unknown-layout")

    with pytest.raises(ForbiddenPolicyError):
        policy_for_layout(None)  # type: ignore
