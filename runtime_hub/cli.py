"""Command-line interface for isolated runtime profiles."""

import argparse
import json
import sys
from collections.abc import Sequence

from .errors import RuntimeHubError
from .store import ProfileStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hub-runtime")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    commands.add_parser("status")
    use = commands.add_parser("use")
    use.add_argument("profile_id")
    use.add_argument("--force", action="store_true")
    return parser


def _profile_data(store: ProfileStore, profile_id: str) -> dict[str, object]:
    profile = store.load_profiles()[profile_id]
    return {
        "id": profile.id,
        "runtime": profile.runtime,
        "model": profile.model,
        "home": str(store.resolve_home(profile)),
        "executable": profile.executable,
        "env": dict(profile.env),
        "notes": profile.notes,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    store = ProfileStore()
    try:
        if args.command == "list":
            active = store.read_active()
            for profile in store.list_profiles():
                marker = " *" if profile.id == active else ""
                print(f"{profile.id}\t{profile.runtime}{marker}")
            return 0
        if args.command == "use":
            profile = store.use(args.profile_id, force=args.force)
            print(f"active: {profile.id} ({profile.runtime})")
            return 0

        profile = store.get_active()
        print(json.dumps(_profile_data(store, profile.id), sort_keys=True))
        return 0
    except RuntimeHubError as error:
        print(
            json.dumps(
                {"error": error.code, "message": error.message},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
