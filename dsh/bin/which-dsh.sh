#!/usr/bin/env bash
set -euo pipefail

# 1. DSH_BIN override
if [[ -n "${DSH_BIN:-}" && -x "$DSH_BIN" ]]; then
  echo "$DSH_BIN"
  exit 0
fi

# 2. global dsh
if command -v dsh >/dev/null 2>&1; then
  command -v dsh
  exit 0
fi

# 3. npx fallback
if command -v npx >/dev/null 2>&1; then
  printf '%s\n' npx -y @deepseek-ai/dsh
  exit 0
fi

echo "dsh not found: install via npm install -g @deepseek-ai/dsh or set DSH_BIN" >&2
exit 127
