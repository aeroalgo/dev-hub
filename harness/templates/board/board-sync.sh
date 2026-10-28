#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "missing .env — copy from .env.example and fill Bitrix keys" >&2
  exit 2
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

ACTORS_FILE="${BOARD_ACTORS_FILE:-$ROOT/.loop/board-actors.yaml}"
if [[ ! -f "$ACTORS_FILE" ]]; then
  echo "missing actors file: $ACTORS_FILE" >&2
  echo "Seed via: make hub-link  (or copy harness/templates/board/board-actors.yaml.example)" >&2
  exit 2
fi

DEV_HUB="$(cat .dev-hub 2>/dev/null || true)"
if [[ -z "$DEV_HUB" ]]; then
  DEV_HUB="../dev-hub"
fi
DEV_HUB="$(cd "$ROOT" && cd "$DEV_HUB" && pwd)"
LOOP_PY="$DEV_HUB/bin/loop.py"

usage() {
  cat >&2 <<'EOF'
Usage:
  scripts/board-sync.sh <epic-id> [epic-id...]
  scripts/board-sync.sh --all

Resolves Bitrix actor (CREATED_BY + RESPONSIBLE_ID) from .loop/board-actors.yaml
per epic, then calls loop board-sync.
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 2
fi

mapfile -t EPICS < <(
  python3 - "$ACTORS_FILE" "$@" <<'PY'
import sys
from pathlib import Path
import yaml

actors_path = Path(sys.argv[1])
args = sys.argv[2:]
cfg = yaml.safe_load(actors_path.read_text()) or {}
actors = cfg.get("actors") or {}
default_actor = cfg.get("default_actor")
epic_map = cfg.get("epics") or {}

if args == ["--all"]:
    epics = list(epic_map.keys())
    if not epics:
        raise SystemExit("epics: map is empty in board-actors.yaml")
else:
    epics = args

for epic in epics:
    actor_key = epic_map.get(epic, default_actor)
    if not actor_key:
        raise SystemExit(f"{epic}: no actor mapping and no default_actor")
    actor = actors.get(actor_key)
    if not isinstance(actor, dict) or actor.get("bitrix_user_id") is None:
        raise SystemExit(f"{epic}: unknown actor {actor_key!r}")
    uid = int(actor["bitrix_user_id"])
    name = actor.get("display_name") or actor_key
    role = "front" if epic.startswith("T-F") else "back"
    print(f"{epic}\t{uid}\t{actor_key}\t{name}\t{role}")
PY
)

for row in "${EPICS[@]}"; do
  IFS=$'\t' read -r epic uid actor_key name role <<<"$row"
  echo "=== board-sync $epic actor=$actor_key ($name) id=$uid role=$role ==="
  BITRIX_RESPONSIBLE_ID="$uid" \
    python3 "$LOOP_PY" board-sync --project "$ROOT" --epic "$epic" --role "$role" --json
  echo
done
