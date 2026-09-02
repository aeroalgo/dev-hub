#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX_HOME="${CODEX_HOME:-${HOME}/.codex}"
CONFIG_SRC="${ROOT}/omniroute.config.toml"
CONFIG_DST="${CODEX_HOME}/config.toml"
KEY_FILE="${OMNIROUTE_API_KEY_FILE:-${CODEX_HOME}/.omniroute_key}"
CLAUDE_SETTINGS="${HOME}/.claude/settings.json"

mkdir -p "$CODEX_HOME"
chmod +x "${ROOT}/bin/codex-omniroute.sh"

resolve_key() {
  if [[ -n "${OMNIROUTE_API_KEY:-}" ]]; then
    printf '%s' "$OMNIROUTE_API_KEY"
    return 0
  fi
  if [[ -f "$KEY_FILE" ]]; then
    tr -d '\n\r' < "$KEY_FILE"
    return 0
  fi
  if [[ -f "$CLAUDE_SETTINGS" ]]; then
    python3 - <<'PY' "$CLAUDE_SETTINGS"
import json, sys
path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    data = json.load(f)
env = data.get("env") or {}
for key in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
    val = env.get(key)
    if isinstance(val, str) and val.strip():
        print(val.strip())
        break
PY
    return 0
  fi
  return 1
}

KEY="$(resolve_key || true)"
if [[ -z "$KEY" ]]; then
  echo "OmniRoute API key not found." >&2
  echo "Set OMNIROUTE_API_KEY or create $KEY_FILE (key from http://localhost:20128)." >&2
  exit 1
fi

umask 077
printf '%s' "$KEY" > "$KEY_FILE"
chmod 600 "$KEY_FILE"

if [[ -f "$CONFIG_DST" ]] && grep -q 'model_provider = "omniroute"' "$CONFIG_DST" 2>/dev/null; then
  echo "OmniRoute block already present in $CONFIG_DST"
else
  if [[ -f "$CONFIG_DST" ]]; then
    cp "$CONFIG_DST" "${CONFIG_DST}.bak.$(date +%Y%m%d-%H%M%S)"
    {
      cat "$CONFIG_DST"
      echo
      cat "$CONFIG_SRC"
    } > "${CONFIG_DST}.new"
    mv "${CONFIG_DST}.new" "$CONFIG_DST"
  else
    cp "$CONFIG_SRC" "$CONFIG_DST"
  fi
  echo "Updated $CONFIG_DST"
fi

echo "Key file: $KEY_FILE"
echo "Wrapper: ${ROOT}/bin/codex-omniroute.sh"
echo
echo "Verify:"
echo "  ${ROOT}/bin/codex-omniroute.sh exec --ephemeral --dangerously-bypass-approvals-and-sandbox 'say hi'"
echo
echo "Optional shell export (for tools outside the wrapper):"
echo "  export OMNIROUTE_API_KEY=\"\$(tr -d '\\n\\r' < $KEY_FILE)\""
