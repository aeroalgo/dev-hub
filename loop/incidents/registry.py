"""Registry loading, chain lookup, and callable resolution for diagnostic codes."""
from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml

logger = logging.getLogger(__name__)

DEFAULT_REGISTRY_PATH = Path(__file__).parent / "registry.yaml"


@dataclass(frozen=True)
class RepairStep:
    repair_fn: str
    verify_fn: str
    max_attempts: int


@dataclass(frozen=True)
class RegistryEntry:
    diagnostic_code: str
    description: str
    runbook_rel: str
    chain: tuple[RepairStep, ...]


def load_registry(path: str | Path | None = None) -> dict[str, RegistryEntry]:
    """Load and validate diagnostic code registry from YAML."""
    p = Path(path) if path else DEFAULT_REGISTRY_PATH
    if not p.is_file():
        logger.warning("Registry file not found: %s", p)
        return {}

    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "repairs" not in data:
        return {}

    entries: dict[str, RegistryEntry] = {}
    repairs = data.get("repairs", {})
    if not isinstance(repairs, dict):
        return {}

    for code, spec in repairs.items():
        if not isinstance(spec, dict):
            continue
        chain_list: list[RepairStep] = []
        raw_chain = spec.get("chain", [])
        if isinstance(raw_chain, list):
            for step in raw_chain:
                if isinstance(step, dict):
                    chain_list.append(
                        RepairStep(
                            repair_fn=str(step.get("repair_fn", "")),
                            verify_fn=str(step.get("verify_fn", "")),
                            max_attempts=int(step.get("max_attempts", 1)),
                        )
                    )
        entries[code] = RegistryEntry(
            diagnostic_code=str(code),
            description=str(spec.get("description", "")),
            runbook_rel=str(spec.get("runbook_rel", "")),
            chain=tuple(chain_list),
        )

    return entries


def get_chain(diagnostic_code: str, registry_path: str | Path | None = None) -> tuple[RepairStep, ...] | None:
    """Get repair step chain for a diagnostic code."""
    reg = load_registry(registry_path)
    entry = reg.get(diagnostic_code)
    if entry is None:
        return None
    return entry.chain


def resolve_callable(import_path: str) -> Callable[..., Any] | None:
    """Resolve an import path string (e.g. 'epic.core.repair_finish_desync') to a callable."""
    if not import_path:
        return None
    parts = import_path.split(".")
    if len(parts) < 2:
        return None
    module_name = ".".join(parts[:-1])
    attr_name = parts[-1]
    try:
        mod = importlib.import_module(module_name)
        func = getattr(mod, attr_name, None)
        if callable(func):
            return func
        return None
    except Exception as e:
        logger.error("Failed to resolve callable %s: %s", import_path, e)
        return None
