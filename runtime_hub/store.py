"""Filesystem-backed profile registry and active pointer."""

import os
import tempfile
from pathlib import Path
from typing import Iterable

import yaml

from .errors import (
    ActiveConflict,
    InvalidProfileConfig,
    NoActiveProfile,
    UnknownProfile,
)
from .models import Profile

DEFAULT_HOME = Path("~/.dev-hub/runtime-hub")
FORCE_ENV = "HUB_RUNTIME_REQUIRE_FORCE"


class ProfileStore:
    """Read profiles and atomically select their isolated homes."""

    def __init__(self, root: str | os.PathLike[str] | None = None) -> None:
        configured = root if root is not None else os.environ.get("RUNTIME_HUB_HOME")
        self.root = Path(configured).expanduser() if configured else DEFAULT_HOME.expanduser()
        self.profiles_file = self.root / "profiles.yaml"
        self.active_file = self.root / "active"
        self.profiles_dir = self.root / "profiles"
        self.dirty_file = self.root / "dirty"

    def load_profiles(self) -> dict[str, Profile]:
        if not self.profiles_file.is_file():
            raise InvalidProfileConfig(f"missing profile registry: {self.profiles_file}")
        try:
            with self.profiles_file.open(encoding="utf-8") as stream:
                raw = yaml.safe_load(stream)
        except (OSError, yaml.YAMLError) as error:
            raise InvalidProfileConfig(f"cannot read {self.profiles_file}: {error}") from error

        records = self._records(raw)
        profiles: dict[str, Profile] = {}
        for index, record in enumerate(records):
            profile = Profile.from_mapping(record, source=f"profiles[{index}]")
            if profile.id in profiles:
                raise InvalidProfileConfig(f"duplicate profile id: {profile.id}")
            profiles[profile.id] = profile
        return profiles

    @staticmethod
    def _records(raw: object) -> Iterable[object]:
        if isinstance(raw, dict) and "profiles" in raw:
            raw = raw["profiles"]
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            records: list[object] = []
            for profile_id, value in raw.items():
                if not isinstance(value, dict):
                    records.append(value)
                    continue
                record = dict(value)
                record.setdefault("id", profile_id)
                records.append(record)
            return records
        raise InvalidProfileConfig("profiles.yaml must contain a profiles list or mapping")

    def read_active(self) -> str | None:
        try:
            value = self.active_file.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return None
        except OSError as error:
            raise InvalidProfileConfig(f"cannot read {self.active_file}: {error}") from error
        return value or None

    def list_profiles(self) -> list[Profile]:
        return list(self.load_profiles().values())

    def get_active(self) -> Profile:
        profiles = self.load_profiles()
        active_id = self.read_active()
        if active_id is None:
            raise NoActiveProfile("no active profile selected")
        try:
            return profiles[active_id]
        except KeyError as error:
            raise InvalidProfileConfig(
                f"active profile is not registered: {active_id}"
            ) from error

    def resolve_home(self, profile: Profile) -> Path:
        if profile.home.startswith("~"):
            raise InvalidProfileConfig(
                f"profile home must not use a user-home shortcut: {profile.home}"
            )
        configured = Path(profile.home)
        profiles_root = self.profiles_dir.resolve()
        home = configured.resolve() if configured.is_absolute() else (self.profiles_dir / configured).resolve()
        if home != profiles_root and profiles_root not in home.parents:
            raise InvalidProfileConfig(f"profile home escapes profiles/: {profile.home}")
        return home

    def use(self, profile_id: str, *, force: bool = False) -> Profile:
        profiles = self.load_profiles()
        try:
            profile = profiles[profile_id]
        except KeyError as error:
            raise UnknownProfile(f"unknown profile: {profile_id}") from error

        current = self.read_active()
        requires_force = os.environ.get(FORCE_ENV) == "1"
        try:
            dirty = self.dirty_file.stat()
        except FileNotFoundError:
            dirty = None
        except OSError as error:
            raise InvalidProfileConfig(f"cannot inspect {self.dirty_file}: {error}") from error
        if not force and (requires_force or dirty is not None):
            raise ActiveConflict("profile activation requires --force")
        if not force and current is not None and current != profile.id:
            raise ActiveConflict(f"active profile is already {current}; use --force")

        home = self.resolve_home(profile)
        try:
            home.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise InvalidProfileConfig(f"cannot create profile home {home}: {error}") from error
        try:
            self._write_active(profile.id)
        except OSError as error:
            raise InvalidProfileConfig(f"cannot write {self.active_file}: {error}") from error
        return profile

    def _write_active(self, profile_id: str) -> None:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise InvalidProfileConfig(f"cannot create runtime hub home {self.root}: {error}") from error
        descriptor, temporary = tempfile.mkstemp(prefix=".active-", dir=self.root)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(f"{profile_id}\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.active_file)
        except OSError:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
