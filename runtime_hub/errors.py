"""Errors raised by the runtime hub."""


class RuntimeHubError(Exception):
    """Base error with a stable machine-readable reason."""

    code = "runtime_hub_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidProfileConfig(RuntimeHubError):
    """The profile registry is missing or does not match its schema."""

    code = "invalid_profile_config"


class UnknownProfile(RuntimeHubError):
    """The requested profile id is not registered."""

    code = "unknown_profile"


class ActiveConflict(RuntimeHubError):
    """Changing the active profile requires an explicit force."""

    code = "active_conflict"


class NoActiveProfile(RuntimeHubError):
    """An operation requires an active profile but none is selected."""

    code = "no_active_profile"
