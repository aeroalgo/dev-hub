#!/usr/bin/env bash
set -euo pipefail
record_file="${FAKE_DSH_RECORD_FILE:-/tmp/fake_dsh_record.txt}"
{
  printf 'argv:'
  printf ' %s' "$@"
  printf '\nprompt: %s\n' "${*: -1}"
} >> "$record_file"
exit 0
