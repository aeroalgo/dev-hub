"""Tests for template pack authoring and validation (T-HUB-051: s07 / TM-005)."""
from __future__ import annotations

from pathlib import Path
import pytest
import yaml

from loop.workflow.schemas import WorkflowPack


def test_template_files_exist() -> None:
    """Check that workflows/_template has manifest.yaml, phase_registry.yaml, README.md."""
    template_dir = Path("workflows/_template")
    assert template_dir.is_dir()
    manifest_file = template_dir / "manifest.yaml"
    phase_registry_file = template_dir / "phase_registry.yaml"
    readme_file = template_dir / "README.md"

    assert manifest_file.is_file()
    assert phase_registry_file.is_file()
    assert readme_file.is_file()


def test_validate_template_filled(tmp_path: Path) -> None:
    """Copy template manifest, replace placeholders, and validate using WorkflowPack schema."""
    template_manifest = Path("workflows/_template/manifest.yaml").read_text(encoding="utf-8")
    filled_content = (
        template_manifest.replace("TODO_PACK_ID_PLACEHOLDER", "custom-pack")
        .replace("TODO_ROLE_PLACEHOLDER", "custom_role")
        .replace("TODO_PREFIX_PLACEHOLDER", "CUSTOM")
        .replace("workflows/your-pack/phase_registry.yaml", "workflows/custom-pack/phase_registry.yaml")
        .replace("memory-bank/your-pack", "memory-bank/custom-pack")
        .replace(".cursor/rules/your-pack", ".cursor/rules/custom-pack")
    )

    data = yaml.safe_load(filled_content)
    pack = WorkflowPack.model_validate(data)

    assert pack.id == "custom-pack"
    assert pack.roles == ["custom_role"]
    assert pack.command_prefixes == ["CUSTOM"]
    assert pack.phase_registry == "workflows/custom-pack/phase_registry.yaml"
    assert pack.memory_bank == "memory-bank/custom-pack"
    assert pack.rules_root == ".cursor/rules/custom-pack"
    assert pack.artifact_layout == "software-epic-v1"
