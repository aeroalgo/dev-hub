#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTAINER="${OMNIROUTE_CONTAINER_NAME:-omniroute}"
PATCHER="${SCRIPT_DIR}/../omniroute/apply-built-identity-fix.mjs"
CODEX_HOME="${CODEX_HOME:-${HOME}/.codex}"
MARKER="${CODEX_OMNIROUTE_MARKER:-${CODEX_HOME}/.omniroute_collaboration_fix}"

command -v docker >/dev/null 2>&1 || { echo "Error: docker is required." >&2; exit 127; }
[[ -f "$PATCHER" ]] || { echo "Error: patcher not found: $PATCHER" >&2; exit 1; }
docker inspect "$CONTAINER" >/dev/null 2>&1 || {
  echo "Error: OmniRoute container not found: $CONTAINER" >&2
  exit 1
}

# Codex sends web_search; virgin OmniRoute maps it to googleSearch and drops
# functionDeclarations → model sees only google:search. Local patch keeps tools.
LOCAL_GEMINI_TOOLS="${OMNIROUTE_LOCAL_PATCHES:-${HOME}/.local/share/omniroute-patches}/apply-gemini-tools-with-search.sh"
if [[ -x "$LOCAL_GEMINI_TOOLS" ]]; then
  OMNIROUTE_CONTAINER="$CONTAINER" "$LOCAL_GEMINI_TOOLS"
else
  echo "Warn: missing $LOCAL_GEMINI_TOOLS — Gemini may only see google:search" >&2
fi

docker cp "$PATCHER" "$CONTAINER:/tmp/dev-hub-omniroute-identity-fix.mjs"
STATS="$(
  docker exec "$CONTAINER" sh -lc \
    'find /app/.build/next/server/chunks -type f -name "*.js" -print0 | xargs -0 node /tmp/dev-hub-omniroute-identity-fix.mjs'
)"
docker restart "$CONTAINER" >/dev/null
mkdir -p "$CODEX_HOME"
install -m 600 /dev/null "$MARKER"
echo "Applied OmniRoute Responses namespace identity + GeminiTools collision fix to $CONTAINER."
echo "Patch stats: ${STATS}"
