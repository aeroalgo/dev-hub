"""Validated runtime profile models."""

from dataclasses import dataclass, field
from collections.abc import Mapping
from typing import Literal

from .errors import InvalidProfileConfig

RuntimeName = Literal["codex", "claude", "agy"]
_RUNTIMES = frozenset(("codex", "claude", "agy"))


@dataclass(frozen=True, slots=True)
class Profile:
    """A named runtime and its isolated home configuration."""

    id: str
    runtime: RuntimeName
    home: str
    model: str | None = None
    executable: str | None = None
    env: Mapping[str, str] = field(default_factory=dict)
    notes: str | None = None

    @classmethod
    def from_mapping(cls, value: object, *, source: str = "profile") -> "Profile":
        if not isinstance(value, Mapping):
            raise InvalidProfileConfig(f"{source} must be a mapping")

        required = ("id", "runtime", "home")
        missing = [name for name in required if name not in value]
        if missing:
            names = ", ".join(missing)
            raise InvalidProfileConfig(f"{source} missing required field(s): {names}")

        profile_id = value["id"]
        runtime = value["runtime"]
        home = value["home"]
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise InvalidProfileConfig(f"{source}.id must be a non-empty string")
        if (
            profile_id != profile_id.strip()
            or profile_id in {".", ".."}
            or "/" in profile_id
            or "\\" in profile_id
        ):
            raise InvalidProfileConfig(f"{source}.id must be a simple profile id")
        if not isinstance(runtime, str) or runtime not in _RUNTIMES:
            allowed = ", ".join(sorted(_RUNTIMES))
            raise InvalidProfileConfig(f"{source}.runtime must be one of: {allowed}")
        if not isinstance(home, str) or not home.strip():
            raise InvalidProfileConfig(f"{source}.home must be a non-empty string")

        if isinstance(home, str) and not home.startswith("/"):
            parts = home.split("/")
            if "\\" in home or any(part in ("", ".", "..") for part in parts):
                raise InvalidProfileConfig(f"{source}.home must stay under profiles/")

        optional_strings = ("model", "executable", "notes")
        for name in optional_strings:
            item = value.get(name)
            if item is not None and not isinstance(item, str):
                raise InvalidProfileConfig(f"{source}.{name} must be a string")

        env = value.get("env", {})
        if not isinstance(env, Mapping) or any(
            not isinstance(key, str) or not isinstance(item, str)
            for key, item in env.items()
        ):
            raise InvalidProfileConfig(f"{source}.env must be a string map")

        return cls(
            id=profile_id,
            runtime=runtime,
            home=home,
            model=value.get("model"),
            executable=value.get("executable"),
            env=dict(env),
            notes=value.get("notes"),
        )
