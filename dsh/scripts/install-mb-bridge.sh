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
web_profile="$dsh_home/profiles/web"
[[ "$source" != "$destination" ]] || fail "plugin destination must differ from source"

mkdir -p "$dsh_home/plugins"
rm -rf "$destination"
cp -R "$source" "$destination"
printf 'Installed @dev-hub/dsh-mb-bridge to %s\n' "$destination"

if [[ ! -d "$web_profile" ]]; then
  fail "DSH web profile not installed: $web_profile (run dsh/scripts/install-profiles.sh or start dsh web once)"
fi

if ! command -v dsh >/dev/null 2>&1; then
  fail "dsh CLI not found in PATH"
fi

if ! command -v pnpm >/dev/null 2>&1; then
  fail "pnpm not found: install pnpm before registering mb-bridge in the web profile"
fi

dsh plugin --profile web add "link:$destination"
(
  cd "$web_profile"
  pnpm install --ignore-scripts
)

cat <<EOF

mb-bridge installed. Restart DSH Web so the task-board header controls load:

  DEV_HUB=$hub_root dsh web --no-open

In the task board, use the Workspace dropdown + "Sync workspace" button.
Ensure DEV_HUB is set whenever dsh web starts so hub-board can spawn.
EOF
