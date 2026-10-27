from __future__ import annotations

from typing import Callable, Type
from loop.board_projection.config import BoardProjectionConfig
from loop.board_projection.errors import ProjectionConfigError
from loop.board_projection.protocol import BoardProjectionAdapter

AdapterFactory = Callable[[BoardProjectionConfig], BoardProjectionAdapter]

_REGISTRY: dict[str, AdapterFactory] = {}


def register_adapter(provider_name: str, factory: AdapterFactory) -> None:
    """Register adapter factory for a given provider."""
    _REGISTRY[provider_name.lower().strip()] = factory


def unregister_adapter(provider_name: str) -> None:
    """Unregister an adapter factory."""
    _REGISTRY.pop(provider_name.lower().strip(), None)


def get_adapter(config: BoardProjectionConfig) -> BoardProjectionAdapter | None:
    """
    Get configured adapter for active provider.
    Returns None if provider is 'none'.
    Raises ProjectionConfigError if active provider is not registered in registry.
    """
    provider = config.provider.lower().strip()
    if provider == "none":
        return None

    factory = _REGISTRY.get(provider)
    if factory is None:
        if provider == "bitrix24":
            import loop.board_projection.adapters.bitrix24  # noqa: F401
            factory = _REGISTRY.get(provider)
        elif provider == "plane":
            import loop.board_projection.adapters.plane  # noqa: F401
            factory = _REGISTRY.get(provider)

    if factory is None:
        raise ProjectionConfigError(
            f"No adapter registered for board projection provider '{provider}'."
        )

    return factory(config)
