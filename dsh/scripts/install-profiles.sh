#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "$SCRIPT_DIR/../.." && pwd)
PROFILE_ROOT="$REPO_ROOT/dsh/profiles"
PATCH_ROOT="$REPO_ROOT/dsh/patches"
PLUGIN_ROOT="$REPO_ROOT/dsh/plugins"
DSH_HOME="${DSH_HOME:-$HOME/.dsh}"
DEST="$DSH_HOME/profiles"
PATCH_DEST="$DSH_HOME/patches"
PLUGIN_DEST="$DSH_HOME/plugins"
MODE=copy
DRY_RUN=0

same_path() {
  [[ "$(realpath -m -- "$1")" == "$(realpath -m -- "$2")" ]]
}

usage() {
  cat <<'EOF'
Usage: install-profiles.sh [--link] [--dry-run]

Install the repository's epic-* DSH profiles and their local bundle into
$DSH_HOME/profiles.
  --link     create symlinks instead of copying profile directories
  --dry-run  print planned changes without modifying the filesystem
  --help     show this help

The installer requires pnpm and installs each profile's dependencies without
running package lifecycle scripts.
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

shopt -s nullglob
profiles=("$PROFILE_ROOT"/epic-*)
if ((${#profiles[@]} == 0)); then
  printf 'no epic-* profiles found in %s\n' "$PROFILE_ROOT" >&2
  exit 1
fi

if ((DRY_RUN)); then
  printf 'Would install profiles to %s (%s) and local bundle to %s:\n' "$DEST" "$MODE" "$PATCH_DEST"
else
  command -v pnpm >/dev/null 2>&1 || {
    printf 'pnpm not found: install pnpm before installing DSH profiles\n' >&2
    exit 127
  }
  mkdir -p "$DEST"
  if [[ "$PATCH_DEST" != "$PATCH_ROOT" ]]; then
    rm -rf "$PATCH_DEST"
    cp -R "$PATCH_ROOT" "$PATCH_DEST"
  fi
  if [[ "$PLUGIN_DEST" != "$PLUGIN_ROOT" && -d "$PLUGIN_ROOT" ]]; then
    rm -rf "$PLUGIN_DEST"
    cp -R "$PLUGIN_ROOT" "$PLUGIN_DEST"
  fi
fi

for profile in "${profiles[@]}"; do
  [[ -d "$profile" ]] || continue
  name=${profile##*/}
  target="$DEST/$name"
  if ((DRY_RUN)); then
    printf '%s -> %s\n' "$profile" "$target"
    continue
  fi

  rm -rf "$target"
  if [[ "$MODE" == link ]]; then
    ln -s "$profile" "$target"
  else
    mkdir -p "$target"
    tar -C "$profile" --exclude=node_modules -cf - . | tar -C "$target" -xf -
  fi
  (cd "$target" && CI=true pnpm install --ignore-scripts)
done

if ((DRY_RUN)); then
  printf 'Would install local bundle from %s to %s.\n' "$PATCH_ROOT" "$PATCH_DEST"
  printf 'Dry run complete; no files changed.\n'
else
  printf 'Installed profiles and dependencies to %s\n' "$DEST"
fi

exit 0
