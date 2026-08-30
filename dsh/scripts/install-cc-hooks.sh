#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "$SCRIPT_DIR/../.." && pwd)
PROFILE_ROOT="$REPO_ROOT/dsh/profiles"
PATCH_SOURCE="$REPO_ROOT/dsh/patches/cc-hooks-bridge.yml"
DSH_HOME="${DSH_HOME:-$HOME/.dsh}"
PROFILE_DEST="$DSH_HOME/profiles"
PATCH_DEST="$DSH_HOME/patches"
PATCH_TARGET="$PATCH_DEST/cc-hooks-bridge.yml"
MODE=copy
DRY_RUN=0

same_path() {
  [[ "$(realpath -m -- "$1")" == "$(realpath -m -- "$2")" ]]
}

usage() {
  cat <<'EOF'
Usage: install-cc-hooks.sh [--link] [--dry-run]

Mount the Claude Code command-hook bridge into installed epic-* DSH profiles.
  --link     symlink the bridge fragment instead of copying it
  --dry-run  print planned changes without modifying the filesystem
  --help     show this help

The installer requires pnpm and installs each existing profile's dependencies
without running package lifecycle scripts. Run install-profiles.sh first when
profiles have not yet been installed.
EOF
}

while (($#)); do
  case "$1" in
    --link) MODE=link ;;
    --dry-run) DRY_RUN=1 ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

[[ -f "$PATCH_SOURCE" ]] || {
  printf 'bridge fragment not found: %s\n' "$PATCH_SOURCE" >&2
  exit 1
}

shopt -s nullglob
profiles=("$PROFILE_ROOT"/epic-*)
if ((${#profiles[@]} == 0)); then
  printf 'no epic-* profiles found in %s\n' "$PROFILE_ROOT" >&2
  exit 1
fi

if ((DRY_RUN)); then
  printf 'Dry run: would mount bridge fragment to %s (%s).\n' "$PATCH_TARGET" "$MODE"
else
  command -v pnpm >/dev/null 2>&1 || {
    printf 'pnpm not found: install pnpm before installing DSH profiles\n' >&2
    exit 127
  }
  mkdir -p "$PATCH_DEST"
  if same_path "$PATCH_SOURCE" "$PATCH_TARGET"; then
    printf 'Bridge fragment already mounted at %s\n' "$PATCH_TARGET"
  else
    rm -rf "$PATCH_TARGET"
    if [[ "$MODE" == link ]]; then
      ln -s "$PATCH_SOURCE" "$PATCH_TARGET"
    else
      cp "$PATCH_SOURCE" "$PATCH_TARGET"
    fi
  fi
fi

for profile in "${profiles[@]}"; do
  [[ -d "$profile" ]] || continue
  name=${profile##*/}
  target="$PROFILE_DEST/$name"
  if [[ ! -d "$target" ]]; then
    printf 'Warning: profile not installed: %s\n' "$target" >&2
    continue
  fi
  if ((DRY_RUN)); then
    printf 'Would install dependencies: %s\n' "$target"
  else
    (cd "$target" && pnpm install --ignore-scripts)
  fi
done

if ((DRY_RUN)); then
  printf 'Dry run complete; no files changed.\n'
else
  printf 'Mounted Claude Code hooks bridge and installed dependencies for available profiles in %s\n' "$PROFILE_DEST"
fi
