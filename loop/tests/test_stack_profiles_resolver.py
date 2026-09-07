"""Tests for stack profile registry and pure capability resolver."""

import tempfile
from pathlib import Path
import pytest
import yaml

from loop.stack_profiles.registry import get_bundled_registry
from loop.stack_profiles.resolver import load_project_manifest, resolve_capability
from loop.stack_profiles.schemas import CapabilityName, ProfileName


def create_monorepo_fixture(tmp_path: Path) -> Path:
    """Create a sample multi-target monorepo for tests."""
    project_root = tmp_path / "workspace"
    project_root.mkdir()

    # Create target directories
    (project_root / "services" / "api").mkdir(parents=True)
    (project_root / "services" / "api" / "Cargo.toml").write_text("[package]\nname='api'\n", encoding="utf-8")

    (project_root / "services" / "worker").mkdir(parents=True)
    (project_root / "services" / "worker" / "pyproject.toml").write_text("[project]\nname='worker'\n", encoding="utf-8")

    (project_root / "frontend").mkdir(parents=True)
    (project_root / "frontend" / "pnpm-lock.yaml").write_text("lockfileVersion: 5.4\n", encoding="utf-8")
    (project_root / "frontend" / "package.json").write_text('{"name": "frontend"}\n', encoding="utf-8")

    manifest = {
        "schema": "dev-hub-project/v1",
        "default_target": "api",
        "targets": {
            "api": {
                "root": "services/api",
                "profile": "rust",
            },
            "worker": {
                "root": "services/worker",
                "profile": "python",
            },
            "web": {
                "root": "frontend",
                "profile": "javascript",
            },
        },
    }
    (project_root / "dev-hub.project.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    return project_root


def test_bundled_registry_structure():
    """Verify registry has exactly python, rust, javascript profiles and all 6 capabilities."""
    registry = get_bundled_registry()
    assert set(registry.profiles.keys()) == {ProfileName.PYTHON, ProfileName.RUST, ProfileName.JAVASCRIPT}

    expected_caps = {
        CapabilityName.FORMAT_CHECK,
        CapabilityName.LINT,
        CapabilityName.TYPECHECK,
        CapabilityName.TEST_TARGETED,
        CapabilityName.TEST_FULL,
        CapabilityName.BUILD,
    }

    for prof_name, prof_def in registry.profiles.items():
        assert set(prof_def.capabilities.keys()) == expected_caps


def test_cp1_rust_resolver_us001(tmp_path: Path):
    """CP1: US-001 / TM-006 / Independent Test — rust target test.full returns exact argv/cwd."""
    root = create_monorepo_fixture(tmp_path)

    # Put a dummy python file in api to ensure python files in sibling/target dirs are irrelevant
    (root / "services" / "api" / "some_script.py").write_text("print('irrelevant')", encoding="utf-8")

    res = resolve_capability(root, "test.full", target="api")
    assert res.ok is True
    assert res.profile == "rust"
    assert res.target == "api"
    assert res.cwd == str((root / "services" / "api").resolve())
    assert res.argv == ["cargo", "test", "--all-targets"]
    assert res.diagnostics == []

    # Test all 6 Rust capabilities exact argv
    assert resolve_capability(root, "format.check", target="api").argv == ["cargo", "fmt", "--", "--check"]
    assert resolve_capability(root, "lint", target="api").argv == ["cargo", "clippy", "--all-targets", "--", "-D", "warnings"]
    assert resolve_capability(root, "typecheck", target="api").argv == ["cargo", "check", "--all-targets"]
    assert resolve_capability(root, "test.full", target="api").argv == ["cargo", "test", "--all-targets"]
    assert resolve_capability(root, "build", target="api").argv == ["cargo", "build", "--all-targets"]

    res_targeted = resolve_capability(root, "test.targeted", target="api", selector="tests::test_api")
    assert res_targeted.ok is True
    assert res_targeted.argv == ["cargo", "test", "--", "tests::test_api"]


def test_cp2_python_resolver_us002(tmp_path: Path):
    """CP2: US-002 / TM-005 / TM-009 / FR-008/009 — Python all six exact argv; selector is one atom."""
    root = create_monorepo_fixture(tmp_path)

    assert resolve_capability(root, "format.check", target="worker").argv == ["python", "-m", "ruff", "format", "--check", "."]
    assert resolve_capability(root, "lint", target="worker").argv == ["python", "-m", "ruff", "check", "."]
    assert resolve_capability(root, "typecheck", target="worker").argv == ["python", "-m", "mypy", "."]
    assert resolve_capability(root, "test.full", target="worker").argv == ["python", "-m", "pytest"]
    assert resolve_capability(root, "build", target="worker").argv == ["python", "-m", "build"]

    # test.targeted with selector
    selector = "tests/test_worker.py::test_job"
    res_targeted = resolve_capability(root, "test.targeted", target="worker", selector=selector)
    assert res_targeted.ok is True
    assert res_targeted.argv == ["python", "-m", "pytest", selector]
    assert res_targeted.argv[3] == selector

    # test.targeted missing selector
    res_missing_sel = resolve_capability(root, "test.targeted", target="worker")
    assert res_missing_sel.ok is False
    assert res_missing_sel.argv == []
    assert res_missing_sel.diagnostics[0].code == "selector_required"

    # other capability with forbidden selector
    res_forbid_sel = resolve_capability(root, "test.full", target="worker", selector="some_selector")
    assert res_forbid_sel.ok is False
    assert res_forbid_sel.argv == []
    assert res_forbid_sel.diagnostics[0].code == "selector_forbidden"


def test_cp3_javascript_resolver_us003(tmp_path: Path):
    """CP3: US-003 / TM-007 / TM-008 / FR-010 — JS lockfiles, ambiguity, overrides."""
    root = create_monorepo_fixture(tmp_path)

    # 1. Default pnpm lockfile in fixture
    res = resolve_capability(root, "test.full", target="web")
    assert res.ok is True
    assert res.argv == ["pnpm", "run", "test"]

    res_targeted = resolve_capability(root, "test.targeted", target="web", selector="src/App.test.tsx")
    assert res_targeted.ok is True
    assert res_targeted.argv == ["pnpm", "run", "test", "--", "src/App.test.tsx"]

    # 2. Ambiguous lockfiles: add package-lock.json alongside pnpm-lock.yaml
    (root / "frontend" / "package-lock.json").write_text("{}", encoding="utf-8")
    res_ambig = resolve_capability(root, "test.full", target="web")
    assert res_ambig.ok is False
    assert res_ambig.argv == []
    assert res_ambig.diagnostics[0].code == "js_package_manager_ambiguous"

    # 3. Explicit override resolves ambiguity
    manifest = {
        "schema": "dev-hub-project/v1",
        "targets": {
            "web": {
                "root": "frontend",
                "profile": "javascript",
                "package_manager": "npm",
                "scripts": {
                    "test": "test:ci",
                },
            }
        },
    }
    (root / "dev-hub.project.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    res_override = resolve_capability(root, "test.full", target="web")
    assert res_override.ok is True
    assert res_override.argv == ["npm", "run", "test:ci"]

    # 4. Missing lockfile and no override
    (root / "frontend" / "package-lock.json").unlink()
    (root / "frontend" / "pnpm-lock.yaml").unlink()
    manifest_no_override = {
        "schema": "dev-hub-project/v1",
        "targets": {
            "web": {
                "root": "frontend",
                "profile": "javascript",
            }
        },
    }
    (root / "dev-hub.project.yaml").write_text(yaml.safe_dump(manifest_no_override), encoding="utf-8")
    res_missing_lock = resolve_capability(root, "test.full", target="web")
    assert res_missing_lock.ok is False
    assert res_missing_lock.argv == []
    assert res_missing_lock.diagnostics[0].code == "js_package_manager_missing"


def test_cp4_negatives_us004_missing_manifest_selection_unsafe_walk(tmp_path: Path):
    """CP4: US-004 / TM-001/003/004 / FR-003/013 / Independent Test negatives."""
    root = create_monorepo_fixture(tmp_path)

    # 1. Missing manifest
    (root / "dev-hub.project.yaml").unlink()
    res_no_manifest = resolve_capability(root, "test.full")
    assert res_no_manifest.ok is False
    assert res_no_manifest.argv == []
    assert res_no_manifest.diagnostics[0].code == "project_manifest_missing"

    # 2. Multi-target without default_target and no target specified
    manifest_no_default = {
        "schema": "dev-hub-project/v1",
        "targets": {
            "backend": {"root": "services/worker", "profile": "python"},
            "frontend": {"root": "frontend", "profile": "javascript", "package_manager": "npm"},
        },
    }
    (root / "dev-hub.project.yaml").write_text(yaml.safe_dump(manifest_no_default), encoding="utf-8")
    res_no_target = resolve_capability(root, "test.full")
    assert res_no_target.ok is False
    assert res_no_target.argv == []
    assert res_no_target.diagnostics[0].code == "target_selection_required"

    # 3. Target root escape / traversal
    manifest_escape = {
        "schema": "dev-hub-project/v1",
        "default_target": "bad",
        "targets": {
            "bad": {"root": "../outside", "profile": "python"},
        },
    }
    (root / "dev-hub.project.yaml").write_text(yaml.safe_dump(manifest_escape), encoding="utf-8")
    res_escape = resolve_capability(root, "test.full")
    assert res_escape.ok is False
    assert res_escape.argv == []
    assert res_escape.diagnostics[0].code == "target_root_unsafe"

    # 4. Target root missing
    manifest_missing_root = {
        "schema": "dev-hub-project/v1",
        "default_target": "missing",
        "targets": {
            "missing": {"root": "nonexistent/path", "profile": "python"},
        },
    }
    (root / "dev-hub.project.yaml").write_text(yaml.safe_dump(manifest_missing_root), encoding="utf-8")
    res_missing_dir = resolve_capability(root, "test.full")
    assert res_missing_dir.ok is False
    assert res_missing_dir.argv == []
    assert res_missing_dir.diagnostics[0].code == "target_root_missing"

    # 5. Unknown capability
    (root / "dev-hub.project.yaml").write_text(yaml.safe_dump(manifest_no_default), encoding="utf-8")
    res_unknown_cap = resolve_capability(root, "deploy", target="backend")
    assert res_unknown_cap.ok is False
    assert res_unknown_cap.argv == []
    assert res_unknown_cap.diagnostics[0].code == "capability_unknown"
