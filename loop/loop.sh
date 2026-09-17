#!/usr/bin/env bash
# Compatibility shim delegating to the canonical bin/loop entrypoint.
# Usage: ./bin/loop [EPIC] [MODEL] [MODE] [options]
set -euo pipefail

DEV_HUB="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$DEV_HUB/bin/loop" "$@"
