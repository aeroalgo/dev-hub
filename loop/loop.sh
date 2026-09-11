#!/usr/bin/env bash
# Compatibility shim delegating to the Python loop supervisor.
# Usage: ./loop/loop.sh [EPIC] [MODEL] [MODE] [options]
set -euo pipefail

DEV_HUB="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export DEV_HUB
export HUB_ROOT="$DEV_HUB"
export CLAUDE_PROJECT_DIR="${PROJECT_ROOT:-$DEV_HUB}"

cd "$DEV_HUB"
exec python3 -m loop.runner "$@"
