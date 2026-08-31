"""Tier-1 incident classification and eligibility logic."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

yaml: Any
try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

from loop.incidents.schema import IncidentRecord

DEFAULT_ELIGIBILITY_PATH = Path(__file__).parent / "tier1_eligibility.yaml"


def load_eligibility_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load tier-1 eligibility whitelist configuration from YAML."""
    if path is None:
        env_path = os.environ.get("EPIC_TIER1_ELIGIBILITY_PATH")
        if env_path:
            path = Path(env_path)
        else:
            path = DEFAULT_ELIGIBILITY_PATH
    else:
        path = Path(path)

    if not path.is_file() or yaml is None:
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    return {}


def is_tier1_eligible(
    incident: IncidentRecord,
    config_path: str | Path | None = None,
) -> bool:
    """Determine whether an incident is eligible for Tier-1 autopilot resolution.

    Returns False if:
    - product_test_failed in metadata is truthy
    - diagnostic_codes is empty
    - any diagnostic code is unknown or marked tier1_eligible: false (fail-closed)
    """
    prod_test = incident.metadata.get("product_test_failed")
    if prod_test is True or (isinstance(prod_test, str) and prod_test.lower() in ("true", "1", "yes")):
        return False

    if not incident.diagnostic_codes:
        return False

    config = load_eligibility_config(config_path)
    codes_config = config.get("codes", {})
    if not isinstance(codes_config, dict):
        return False

    for code in incident.diagnostic_codes:
        spec = codes_config.get(code)
        if not isinstance(spec, dict):
            return False
        if not spec.get("tier1_eligible", False):
            return False

    return True
