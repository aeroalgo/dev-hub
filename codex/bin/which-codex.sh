#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OMNIROUTE_WRAP="${SCRIPT_DIR}/codex-omniroute.sh"
CODEX_HOME="${CODEX_HOME:-${HOME}/.codex}"

use_omniroute_wrap() {
    [[ "${CODEX_USE_OMNIROUTE:-1}" == "1" ]] || return 1
    [[ -x "$OMNIROUTE_WRAP" ]] || return 1
    [[ -f "${CODEX_HOME}/.omniroute_key" ]] || return 1
    grep -q 'model_provider = "omniroute"' "${CODEX_HOME}/config.toml" 2>/dev/null
}

# Check explicit CODEX_BIN env override first
if [[ -n "${CODEX_BIN:-}" ]]; then
    if [[ -x "$CODEX_BIN" ]]; then
        echo "$CODEX_BIN"
        exit 0
    else
        echo "Error: CODEX_BIN is set to '$CODEX_BIN' but it is not executable." >&2
        exit 127
    fi
fi

if use_omniroute_wrap; then
    echo "$OMNIROUTE_WRAP"
    exit 0
fi

# Fallback to PATH search
if command -v codex >/dev/null 2>&1; then
    command -v codex
    exit 0
fi

echo "Error: codex binary not found in PATH or CODEX_BIN." >&2
exit 127
