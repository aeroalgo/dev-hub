"""Unit tests for pure project verification context classifier."""

from pathlib import Path
import pytest
import yaml

from loop.stack_profiles.context import classify_project_verification_context


def test_classify_managed(tmp_path: Path):
    """classify_project_verification_context returns 'managed' when valid dev-hub.project.yaml exists."""
    manifest = {
        "schema": "dev-hub-project/v1",
        "targets": {
            "backend": {
                "profile": "python",
                "root": "backend",
            }
        },
    }
    manifest_file = tmp_path / "dev-hub.project.yaml"
    manifest_file.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    # Test with Path object
    assert classify_project_verification_context(tmp_path) == "managed"

    # Test with string path
    assert classify_project_verification_context(str(tmp_path)) == "managed"


def test_classify_hub_and_corrupt(tmp_path: Path):
    """classify_project_verification_context returns 'hub' when manifest is absent and fails closed on invalid manifest."""
    # Absent manifest -> 'hub'
    assert classify_project_verification_context(tmp_path) == "hub"
    assert classify_project_verification_context(str(tmp_path)) == "hub"

    # Corrupt YAML -> fail closed (ValueError)
    manifest_file = tmp_path / "dev-hub.project.yaml"
    manifest_file.write_text(":::invalid yaml:::", encoding="utf-8")
    with pytest.raises(ValueError, match="manifest exists but is invalid"):
        classify_project_verification_context(tmp_path)

    # Manifest is not a dict/mapping -> fail closed (ValueError)
    manifest_file.write_text(yaml.safe_dump(["item1", "item2"]), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest exists but is invalid"):
        classify_project_verification_context(tmp_path)

    # Manifest with invalid schema (missing required targets) -> fail closed (ValueError)
    invalid_schema = {
        "schema": "dev-hub-project/v1",
        "targets": {},
    }
    manifest_file.write_text(yaml.safe_dump(invalid_schema), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest exists but is invalid"):
        classify_project_verification_context(tmp_path)

    # Manifest with invalid schema version -> fail closed (ValueError)
    invalid_version = {
        "schema": "invalid-schema/v1",
        "targets": {
            "backend": {
                "profile": "python",
                "root": "backend",
            }
        },
    }
    manifest_file.write_text(yaml.safe_dump(invalid_version), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest exists but is invalid"):
        classify_project_verification_context(tmp_path)


def test_deterministic_no_env_bypass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """NFR-001: Classification is purely deterministic from filesystem; env vars do not bypass."""
    monkeypatch.setenv("PROJECT_CONTEXT", "managed")
    monkeypatch.setenv("DEV_HUB_CONTEXT", "managed")
    assert classify_project_verification_context(tmp_path) == "hub"
