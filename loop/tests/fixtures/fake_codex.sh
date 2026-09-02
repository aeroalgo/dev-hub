#!/usr/bin/env bash
set -euo pipefail
record_file="${FAKE_CODEX_RECORD_FILE:-/tmp/fake_codex_record.txt}"
prompt="$(cat)"
{
  printf 'argv:'
  printf ' %q' "$@"
  printf '\nprompt: %s\n' "$prompt"
} >> "$record_file"
exit 0
