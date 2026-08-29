#!/usr/bin/env bash
set -euo pipefail

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

if [[ -z "${DEV_HUB:-}" ]]; then
  fail "DEV_HUB is required: set it to the dev-hub checkout"
fi

hub_root=$(realpath -m -- "$DEV_HUB")
[[ -d "$hub_root" ]] || fail "DEV_HUB directory not found: $DEV_HUB"

source="$hub_root/dsh/plugins/mb-bridge"
[[ -d "$source" ]] || fail "mb-bridge plugin not found under DEV_HUB: $source"

dsh_home=$(realpath -m -- "${DSH_HOME:-$HOME/.dsh}")
destination="$dsh_home/plugins/mb-bridge"
[[ "$source" != "$destination" ]] || fail "plugin destination must differ from source"

mkdir -p "$dsh_home/plugins"
rm -rf "$destination"
cp -R "$source" "$destination"
printf 'Installed @dev-hub/dsh-mb-bridge to %s\n' "$destination"
