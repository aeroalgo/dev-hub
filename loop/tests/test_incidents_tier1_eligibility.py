"""Unit tests for tier-1 incident eligibility classification."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from loop.incidents.schema import IncidentRecord, compute_incident_id
from loop.incidents.tier1 import is_tier1_eligible, load_eligibility_config


def _make_incident(
    diagnostic_codes: list[str],
    metadata: dict | None = None,
) -> IncidentRecord:
    codes = diagnostic_codes or ["active_context_shape_invalid"]
    iid = compute_incident_id(
        project_root="/tmp/test",
        epic_id="T-HUB-018",
        step_id="s01",
        session_id="sess-1",
        diagnostic_codes=codes,
        fingerprint="fp1",
    )
    return IncidentRecord(
        incident_id=iid,
        opened_at="2026-08-30T22:00:00Z",
        project_root="/tmp/test",
        epic_id="T-HUB-018",
        step_id="s01",
        phase="BACK IMPLEMENT",
        session_id="sess-1",
        source="test",
        diagnostic_codes=diagnostic_codes,
        fingerprint="fp1",
        metadata=metadata or {},
    )


def test_orchestration_eligible_code_returns_true():
    """cp1: orchestration-only diagnostic code -> is_tier1_eligible=True."""
    inc = _make_incident(["active_context_shape_invalid"])
    assert is_tier1_eligible(inc) is True

    inc2 = _make_incident(["mark_index_missing", "index_mirror_drift"])
    assert is_tier1_eligible(inc2) is True


def test_product_test_not_eligible_returns_false():
    """cp2: product_test_failed=true in metadata -> is_tier1_eligible=False."""
    inc = _make_incident(["active_context_shape_invalid"], metadata={"product_test_failed": True})
    assert is_tier1_eligible(inc) is False

    inc_str = _make_incident(["index_step_missing"], metadata={"product_test_failed": "true"})
    assert is_tier1_eligible(inc_str) is False


def test_unknown_code_false_returns_false():
    """cp3: unknown diagnostic_code -> is_tier1_eligible=False (fail-closed)."""
    inc = _make_incident(["unknown_custom_code_xyz"])
    assert is_tier1_eligible(inc) is False


def test_mixed_codes_false_returns_false():
    """cp4: mixed codes (one orchestration + one product failure or unknown) -> False."""
    inc = _make_incident(
        ["active_context_shape_invalid"],
        metadata={"product_test_failed": True},
    )
    assert is_tier1_eligible(inc) is False

    inc_unknown_mixed = _make_incident(["active_context_shape_invalid", "unknown_code_abc"])
    assert is_tier1_eligible(inc_unknown_mixed) is False


def test_load_eligibility_config_reads_yaml():
    config = load_eligibility_config()
    assert isinstance(config, dict)
    assert "codes" in config
    assert "active_context_shape_invalid" in config["codes"]
    assert config["codes"]["active_context_shape_invalid"]["tier1_eligible"] is True


def test_eligibility_config_override_env_path(tmp_path: Path):
    custom_yaml = tmp_path / "custom_tier1.yaml"
    custom_yaml.write_text(
        "schema: loop-incident-eligibility/v1\ncodes:\n  custom_code:\n    tier1_eligible: true\n",
        encoding="utf-8",
    )
    os.environ["EPIC_TIER1_ELIGIBILITY_PATH"] = str(custom_yaml)
    try:
        config = load_eligibility_config()
        assert "custom_code" in config.get("codes", {})

        inc = _make_incident(["custom_code"])
        assert is_tier1_eligible(inc) is True
    finally:
        os.environ.pop("EPIC_TIER1_ELIGIBILITY_PATH", None)
