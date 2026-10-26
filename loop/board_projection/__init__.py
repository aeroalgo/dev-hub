from __future__ import annotations

from loop.board_projection.errors import (
    AdapterExecutionError,
    ProjectionConfigError,
    ProjectionError,
    ProviderMismatchError,
)
from loop.board_projection.protocol import (
    BoardProjectionAdapter,
    EpicRef,
    ProjectionResult,
)
from loop.board_projection.config import (
    Bitrix24Config,
    BoardProjectionConfig,
    PlaneConfig,
    load_projection_config,
)
from loop.board_projection.registry import (
    get_adapter,
    register_adapter,
    unregister_adapter,
)

__all__ = [
    "AdapterExecutionError",
    "Bitrix24Config",
    "BoardProjectionAdapter",
    "BoardProjectionConfig",
    "EpicRef",
    "PlaneConfig",
    "ProjectionConfigError",
    "ProjectionError",
    "ProjectionResult",
    "ProviderMismatchError",
    "get_adapter",
    "load_projection_config",
    "register_adapter",
    "unregister_adapter",
]
