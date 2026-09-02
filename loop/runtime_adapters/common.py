from __future__ import annotations

from typing import Any

from loop.runtime.registry import get_runtime_adapter, InvalidRuntimeConfig
from loop.runtime_adapters.base import RuntimeAdapter


def get_adapter_for_runtime(runtime_id: str) -> RuntimeAdapter:
    """Factory creating RuntimeAdapter instance for given runtime_id using registry."""
    try:
        obj = get_runtime_adapter(runtime_id)
    except InvalidRuntimeConfig as e:
        raise ValueError(f"Unknown runtime: {runtime_id}") from e

    if isinstance(obj, type):
        return obj()

    # Module loaded from registry
    attr_name = f"{runtime_id.capitalize()}Adapter"
    if hasattr(obj, attr_name):
        cls = getattr(obj, attr_name)
        return cls()

    # Fallback scan module attributes for RuntimeAdapter subclass/implementation
    for name in dir(obj):
        if name.endswith("Adapter") and name != "RuntimeAdapter":
            cls = getattr(obj, name)
            if isinstance(cls, type):
                return cls()

    raise ValueError(f"No RuntimeAdapter implementation found in adapter module for runtime '{runtime_id}'")
