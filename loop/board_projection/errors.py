from __future__ import annotations


class ProjectionError(Exception):
    """Base error for all board projection operations."""


class ProjectionConfigError(ProjectionError):
    """Configuration error for board projection (invalid YAML, unknown provider, schema error)."""


class ProviderMismatchError(ProjectionError):
    """Raised when existing card/mapping belongs to a different provider."""


class AdapterExecutionError(ProjectionError):
    """Raised when provider API communication fails (REST 500, timeout, 401)."""
