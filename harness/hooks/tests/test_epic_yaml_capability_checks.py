from pathlib import Path
"""Tests for decompose YAML capability_checks validation."""

import pytest
from pydantic import ValidationError

from harness.hooks.epic_yaml import EpicDecomposeDoc


def test_decompose_capability_checks_valid():
    raw_doc = {
        "schema": "epic-decompose/v1",
        "role": "back",
        "step_id": "s01",
        "plan_id": "T-HUB-076",
        "title": "test step",
        "next_phase": "BACK IMPLEMENT",
        "capability_checks": [
            {
                "target": "api",
                "capability": "test.full",
            },
            {
                "target": "worker",
                "capability": "test.targeted",
                "selector": "tests/test_job.py",
            },
        ],
    }
    doc = EpicDecomposeDoc.model_validate(raw_doc)
    assert len(doc.capability_checks) == 2
    assert doc.capability_checks[0].target == "api"
    assert doc.capability_checks[0].capability == "test.full"
    assert doc.capability_checks[1].target == "worker"
    assert doc.capability_checks[1].selector == "tests/test_job.py"


def test_decompose_capability_check_without_target_is_fail_closed():
    raw_doc = {
        "schema": "epic-decompose/v1",
        "role": "back",
        "step_id": "s01",
        "plan_id": "T-HUB-076",
        "title": "test step",
        "next_phase": "BACK IMPLEMENT",
        "capability_checks": [
            {
                "capability": "test.full",
            }
        ],
    }
    with pytest.raises(ValidationError) as exc:
        EpicDecomposeDoc.model_validate(raw_doc)
    assert "target" in str(exc.value)


def test_decompose_capability_check_rejects_raw_process_controls():
    raw_doc = {
        "schema": "epic-decompose/v1",
        "role": "back",
        "step_id": "s01",
        "plan_id": "T-HUB-076",
        "title": "test step",
        "next_phase": "BACK IMPLEMENT",
        "capability_checks": [
            {
                "target": "api",
                "capability": "test.full",
                "command": "pytest",
            }
        ],
    }
    with pytest.raises(ValidationError) as exc:
        EpicDecomposeDoc.model_validate(raw_doc)
    assert "extra" in str(exc.value).lower() or "Extra inputs are not permitted" in str(exc.value)


def test_managed_finish_requires_capability_checks(tmp_path: Path):
    """FR-002: Managed project finish validation requires non-empty capability_checks on decompose shard."""
    import yaml
    from harness.hooks.epic_yaml import (
        EpicImplementDoc,
        validate_shard_yaml_full,
        implement_ready_for_finalize_doc,
    )

    # 1. Setup managed project with dev-hub.project.yaml
    manifest = {
        "schema": "dev-hub-project/v1",
        "targets": {
            "core": {
                "profile": "python",
                "root": "core",
            }
        },
    }
    (tmp_path / "dev-hub.project.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    (tmp_path / "core").mkdir(exist_ok=True)
    (tmp_path / "core" / "app.py").write_text("# app\n", encoding="utf-8")

    # 2. Create decompose and implement shards with capability_checks=[] and hub tests
    steps_dir = tmp_path / "memory-bank" / "back" / "plan" / "T-APP-001" / "yaml" / "steps"
    steps_dir.mkdir(parents=True, exist_ok=True)
    impl_dir = tmp_path / "memory-bank" / "back" / "implement" / "T-APP-001"
    impl_dir.mkdir(parents=True, exist_ok=True)

    dec_path = steps_dir / "s01-test-step.yaml"
    impl_path = impl_dir / "s01-test-step.yaml"

    dec_doc = {
        "schema": "epic-decompose/v1",
        "role": "back",
        "step_id": "s01",
        "plan_id": "T-APP-001",
        "title": "Test Step",
        "next_phase": "BACK IMPLEMENT",
        "goal": "Outcome goal",
        "delta": ["Some change"],
        "checkpoints": [{"id": "cp1", "criterion": "Done", "verify": "bin/pytest tests/test_foo.py -q"}],
        "capability_checks": [],
    }
    dec_path.write_text(yaml.safe_dump(dec_doc), encoding="utf-8")

    impl_doc_data = {
        "schema": "epic-implement/v1",
        "role": "back",
        "step_id": "s01",
        "plan_id": "T-APP-001",
        "title": "Test Step",
        "status": "in_progress",
        "date": "2026-09-14",
        "decompose_ref": str(dec_path.relative_to(tmp_path)),
        "done": ["Work done"],
        "files": ["core/app.py"],
        "integration_check": ["Checked"],
        "tests": ["`bin/pytest tests/test_foo.py -q` — PASS"],
        "checkpoints": [{"id": "cp1", "criterion": "Done", "status": "done"}],
    }
    impl_path.write_text(yaml.safe_dump(impl_doc_data), encoding="utf-8")

    # 3. In managed context, finish validation fails because capability_checks are missing
    errors, warnings = validate_shard_yaml_full(impl_path, finish=True)
    assert any("managed_verification_requires_capability_checks" in e for e in errors)

    impl_doc_obj = EpicImplementDoc.model_validate(impl_doc_data)
    ready_errs = implement_ready_for_finalize_doc(impl_doc_obj, cwd=tmp_path)
    assert any("managed_verification_requires_capability_checks" in e for e in ready_errs)

    # 4. In hub context (manifest removed), finish validation passes with hub tests
    (tmp_path / "dev-hub.project.yaml").unlink()
    errors_hub, warnings_hub = validate_shard_yaml_full(impl_path, finish=True)
    assert not errors_hub
    ready_errs_hub = implement_ready_for_finalize_doc(impl_doc_obj, cwd=tmp_path)
    assert not ready_errs_hub
