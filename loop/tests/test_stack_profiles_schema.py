"""Unit tests for dev-hub-project/v1 schemas, vocabulary, and containment."""

from pathlib import Path
import pytest
from pydantic import ValidationError

from loop.stack_profiles.schemas import (
    CapabilityName,
    CapabilityRequest,
    CapabilityResolution,
    Diagnostic,
    DiagnosticCode,
    ProjectManifest,
    validate_workspace_containment,
)


def test_valid_manifest():
    data = {
        "schema": "dev-hub-project/v1",
        "workflow_pack": "dev-hub-software",
        "default_target": "backend",
        "targets": {
            "backend": {
                "root": "services/backend",
                "profile": "python",
            },
            "worker": {
                "root": "services/worker",
                "profile": "rust",
            },
            "web": {
                "root": "apps/web",
                "profile": "javascript",
                "package_manager": "pnpm",
                "scripts": {
                    "format:check": "prettier --check .",
                },
            },
        },
    }
    manifest = ProjectManifest.model_validate(data)
    assert manifest.schema_version == "dev-hub-project/v1"
    assert manifest.default_target == "backend"
    assert len(manifest.targets) == 3
    assert manifest.targets["backend"].profile == "python"
    assert manifest.targets["web"].package_manager == "pnpm"


def test_unknown_or_extra_keys_fail():
    data = {
        "schema": "dev-hub-project/v1",
        "targets": {
            "backend": {
                "root": "services/backend",
                "profile": "python",
            }
        },
        "extra_key": "forbidden",
    }
    with pytest.raises(ValidationError) as exc:
        ProjectManifest.model_validate(data)
    assert "extra_forbidden" in str(exc.value) or "Extra inputs are not permitted" in str(exc.value)


def test_forbidden_fields_on_manifest_and_targets():
    # Targets cannot carry command/argv/shell/env/cwd/import/registry
    data = {
        "schema": "dev-hub-project/v1",
        "command": "python -m pytest",
        "targets": {
            "backend": {
                "root": "services/backend",
                "profile": "python",
                "argv": ["pytest"],
            }
        },
    }
    with pytest.raises(ValidationError):
        ProjectManifest.model_validate(data)

    # Python/Rust target cannot have scripts
    data_python_scripts = {
        "schema": "dev-hub-project/v1",
        "targets": {
            "backend": {
                "root": "services/backend",
                "profile": "python",
                "scripts": {"lint": "ruff check"},
            }
        },
    }
    with pytest.raises(ValidationError):
        ProjectManifest.model_validate(data_python_scripts)


def test_invalid_schema_version():
    data = {
        "schema": "invalid-schema/v1",
        "targets": {
            "backend": {
                "root": "services/backend",
                "profile": "python",
            }
        },
    }
    with pytest.raises(ValidationError):
        ProjectManifest.model_validate(data)


def test_default_target_must_exist_in_targets():
    data = {
        "schema": "dev-hub-project/v1",
        "default_target": "non_existent",
        "targets": {
            "backend": {
                "root": "services/backend",
                "profile": "python",
            }
        },
    }
    with pytest.raises(ValidationError, match="default_target 'non_existent' is not defined in targets"):
        ProjectManifest.model_validate(data)


def test_duplicate_target_root_fails():
    data = {
        "schema": "dev-hub-project/v1",
        "targets": {
            "backend1": {
                "root": "services/backend",
                "profile": "python",
            },
            "backend2": {
                "root": "services/backend",
                "profile": "python",
            },
        },
    }
    with pytest.raises(ValidationError, match="Duplicate target root"):
        ProjectManifest.model_validate(data)


def test_workspace_containment_valid(tmp_path: Path):
    project_root = tmp_path / "my_project"
    project_root.mkdir()
    target_root = "services/backend"
    (project_root / target_root).mkdir(parents=True)

    resolved = validate_workspace_containment(project_root, target_root)
    assert resolved == (project_root / "services/backend").resolve()


def test_workspace_containment_absolute_root_fails(tmp_path: Path):
    project_root = tmp_path / "my_project"
    project_root.mkdir()
    abs_target = (tmp_path / "somewhere_else").resolve()

    with pytest.raises(ValueError, match="target root must be workspace-relative"):
        validate_workspace_containment(project_root, str(abs_target))


def test_workspace_containment_escaping_root_fails(tmp_path: Path):
    project_root = tmp_path / "my_project"
    project_root.mkdir()
    escaping_target = "../outside"

    with pytest.raises(ValueError, match="escapes workspace root"):
        validate_workspace_containment(project_root, escaping_target)


def test_capability_vocabulary_enum():
    assert set(CapabilityName) == {
        "format.check",
        "lint",
        "typecheck",
        "test.targeted",
        "test.full",
        "build",
    }


def test_unknown_capability_fails():
    for unknown in ["run", "migrate", "generate", "deploy", "custom"]:
        with pytest.raises(ValueError):
            CapabilityName(unknown)


def test_capability_request_selector_rules():
    # test.targeted requires nonempty selector
    with pytest.raises(ValidationError, match="selector is required for capability test.targeted"):
        CapabilityRequest(capability=CapabilityName.TEST_TARGETED, selector=None)

    with pytest.raises(ValidationError, match="selector is required for capability test.targeted"):
        CapabilityRequest(capability=CapabilityName.TEST_TARGETED, selector="")

    valid_targeted = CapabilityRequest(
        capability=CapabilityName.TEST_TARGETED, selector="tests/unit/test_foo.py::test_bar"
    )
    assert valid_targeted.selector == "tests/unit/test_foo.py::test_bar"

    # Other capabilities forbid selector
    for cap in [
        CapabilityName.FORMAT_CHECK,
        CapabilityName.LINT,
        CapabilityName.TYPECHECK,
        CapabilityName.TEST_FULL,
        CapabilityName.BUILD,
    ]:
        with pytest.raises(ValidationError, match=f"selector is forbidden for capability '{cap}'"):
            CapabilityRequest(capability=cap, selector="something")

        # None or empty is allowed
        req = CapabilityRequest(capability=cap)
        assert req.selector is None


def test_diagnostic_codes_and_manifest_missing_literals():
    # TM-001 assertion that project_manifest_missing diagnostic is supported
    diag = Diagnostic(
        code="project_manifest_missing",
        message="Root manifest dev-hub.project.yaml not found",
    )
    assert diag.code == "project_manifest_missing"
    assert "dev-hub.project.yaml" in diag.message

    res = CapabilityResolution(
        ok=False,
        diagnostics=[diag],
    )
    assert not res.ok
    assert res.diagnostics[0].code == "project_manifest_missing"
