#!/usr/bin/env bash
set -euo pipefail

CONFIGURED_KEY_FILE="${OMNIROUTE_API_KEY_FILE:-${HOME}/.codex/.omniroute_key}"
if [[ "$CONFIGURED_KEY_FILE" == "~" ]]; then
  KEY_FILE="$HOME"
elif [[ "$CONFIGURED_KEY_FILE" == "~/"* ]]; then
  KEY_FILE="${HOME}/${CONFIGURED_KEY_FILE#\~/}"
else
  KEY_FILE="$CONFIGURED_KEY_FILE"
fi
OMNIROUTE_API_URL="${OMNIROUTE_API_URL:-http://localhost:20128/v1}"
CODEX_HOME="${CODEX_HOME:-${HOME}/.codex}"
PROFILE_NAME="${CODEX_PROFILE:-dev-hub}"

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
elif command -v codex >/dev/null 2>&1; then
  REAL_CODEX="$(command -v codex)"
else
  echo "Error: codex binary not found in PATH." >&2
  exit 127
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

exec "$REAL_CODEX" "${PROFILE_ARGS[@]}" \
  -c 'model_provider="omniroute"' \
  -c "model_providers.omniroute.base_url=\"${OMNIROUTE_API_URL}\"" \
  "$@"
