import importlib
from pathlib import Path
from typing import Any, Dict, List, Set
import yaml

DEFAULT_REGISTRY_PATH = Path(__file__).parent.parent / "runtime_registry.yaml"


class InvalidRuntimeConfig(Exception):
    """Raised when runtime ID is invalid or not registered."""
    pass


class CapabilityError(Exception):
    """Raised when checked runtime ID is unknown."""
    pass


class RuntimeRegistry:
    def __init__(self, data: Dict[str, Any]):
        self.schema_version = data.get("schema_version")
        if self.schema_version != "runtime-registry/v1":
            raise InvalidRuntimeConfig(f"Unsupported schema version: {self.schema_version}")

        self.runtimes: Dict[str, Dict[str, Any]] = data.get("runtimes", {})

    def list_ids(self) -> List[str]:
        return list(self.runtimes.keys())

    def get_runtime(self, runtime_id: str) -> Dict[str, Any]:
        if runtime_id not in self.runtimes:
            raise InvalidRuntimeConfig(f"Unknown runtime id: {runtime_id}")
        return self.runtimes[runtime_id]

    def get_runtime_adapter_module(self, runtime_id: str) -> str:
        entry = self.get_runtime(runtime_id)
        return entry["adapter_module"]

    def get_runtime_adapter(self, runtime_id: str) -> Any:
        module_path = self.get_runtime_adapter_module(runtime_id)
        try:
            return importlib.import_module(module_path)
        except ImportError as e:
            raise InvalidRuntimeConfig(f"Could not load adapter module '{module_path}' for runtime '{runtime_id}': {e}")

    def has_capability(self, runtime_id: str, capability: str) -> bool:
        if runtime_id not in self.runtimes:
            raise CapabilityError(f"Unknown runtime id: {runtime_id}")
        caps = self.runtimes[runtime_id].get("capabilities", [])
        return capability in caps


def load_registry(path: Path | str = DEFAULT_REGISTRY_PATH) -> RuntimeRegistry:
    p = Path(path)
    if not p.exists():
        raise InvalidRuntimeConfig(f"Registry file not found: {p}")
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise InvalidRuntimeConfig("Malformed YAML: expected dictionary at root")
        return RuntimeRegistry(data)
    except yaml.YAMLError as e:
        raise InvalidRuntimeConfig(f"Malformed YAML: {e}")


_default_registry: RuntimeRegistry | None = None


def get_default_registry() -> RuntimeRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = load_registry()
    return _default_registry


def list_ids() -> List[str]:
    return get_default_registry().list_ids()


def get_runtime_adapter_module(runtime_id: str) -> str:
    return get_default_registry().get_runtime_adapter_module(runtime_id)


def get_runtime_adapter(runtime_id: str) -> Any:
    return get_default_registry().get_runtime_adapter(runtime_id)


def has_capability(runtime_id: str, capability: str) -> bool:
    return get_default_registry().has_capability(runtime_id, capability)
