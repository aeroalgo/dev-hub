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
