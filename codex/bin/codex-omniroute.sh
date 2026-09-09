#!/usr/bin/env bash
set -euo pipefail

KEY_FILE="${OMNIROUTE_API_KEY_FILE:-${HOME}/.codex/.omniroute_key}"
CODEX_HOME="${CODEX_HOME:-${HOME}/.codex}"
PROFILE_NAME="${CODEX_PROFILE:-dev-hub}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCHED_CODEX="${CODEX_PATCHED_BIN:-${SCRIPT_DIR}/../.build/codex-v0.152.0}"
OMNIROUTE_MARKER="${CODEX_OMNIROUTE_MARKER:-${CODEX_HOME}/.omniroute_collaboration_fix}"

if [[ -z "${OMNIROUTE_API_KEY:-}" && -f "$KEY_FILE" ]]; then
  OMNIROUTE_API_KEY="$(tr -d '\n\r' < "$KEY_FILE")"
  export OMNIROUTE_API_KEY
fi

if [[ -z "${OMNIROUTE_API_KEY:-}" ]]; then
  echo "Error: OMNIROUTE_API_KEY is not set and key file is missing: $KEY_FILE" >&2
  echo "Run: $(dirname "$0")/setup-omniroute.sh" >&2
  exit 127
fi

if [[ -n "${CODEX_BIN_REAL:-}" ]]; then
  REAL_CODEX="$CODEX_BIN_REAL"
elif [[ -x "$PATCHED_CODEX" ]]; then
  REAL_CODEX="$PATCHED_CODEX"
elif command -v codex >/dev/null 2>&1; then
  REAL_CODEX="$(command -v codex)"
else
  echo "Error: codex binary not found in PATH." >&2
  exit 127
fi

if [[ "$REAL_CODEX" != "$PATCHED_CODEX" \
  && "${CODEX_ALLOW_UNPATCHED:-0}" != "1" \
  && ! -f "$OMNIROUTE_MARKER" ]]; then
  echo "Error: OmniRoute collaboration transport is not patched." >&2
  echo "Build it with: ${SCRIPT_DIR}/build-patched-codex.sh" >&2
  echo "Or apply the OmniRoute container fix with: ${SCRIPT_DIR}/apply-omniroute-collaboration-fix.sh" >&2
  exit 126
fi

PROFILE_ARGS=()
if [[ -f "${CODEX_HOME}/${PROFILE_NAME}.config.toml" ]]; then
  profile_requested=0
  for arg in "$@"; do
    if [[ "$arg" == "--profile" || "$arg" == "-p" ]]; then
      profile_requested=1
      break
    fi
  done
  if [[ "$profile_requested" == "0" ]]; then
    PROFILE_ARGS=(--profile "$PROFILE_NAME")
  fi
fi

exec "$REAL_CODEX" "${PROFILE_ARGS[@]}" -c 'model_provider="omniroute"' "$@"
