#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: scripts/deploy-remote.sh [--skip-tests]

Reads .deploy.env from PROJECT_ROOT (cwd or DEPLOY_PROJECT_ROOT).
Detects current git repo basename, SSHes to server, git pull in matching path.

Required in .deploy.env:
  DEPLOY_SSH=user@host
  DEPLOY_REMOTE_BASE=/path/to/repos   # remote dir = BASE/<repo-basename>
Optional:
  DEPLOY_REMOTE_DIR=/abs/path/on/server   # overrides BASE/basename
  DEPLOY_BRANCH=main                      # default: current local branch
  DEPLOY_REMOTE_CMD='docker compose up -d --build'  # after pull
  TEST_CMD='bin/pytest -q'                # default auto
EOF
  exit 2
}

SKIP_TESTS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --skip-tests) SKIP_TESTS=1; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1" >&2; usage ;;
  esac
done

PROJECT_ROOT="${DEPLOY_PROJECT_ROOT:-$(pwd)}"
cd "$PROJECT_ROOT"

ENV_FILE="${DEPLOY_ENV_FILE:-$PROJECT_ROOT/.deploy.env}"
if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE — copy .deploy.env.example and set DEPLOY_SSH / paths." >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a
# shellcheck source=/dev/null
. "$ENV_FILE"
set +a

if [ -z "${DEPLOY_SSH:-}" ]; then
  echo "DEPLOY_SSH is empty in $ENV_FILE" >&2
  exit 1
fi

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "Not a git repository: $PROJECT_ROOT" >&2
  exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
REPO_NAME="$(basename "$REPO_ROOT")"
LOCAL_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
BRANCH="${DEPLOY_BRANCH:-$LOCAL_BRANCH}"

if [ -n "${DEPLOY_REMOTE_DIR:-}" ]; then
  REMOTE_DIR="$DEPLOY_REMOTE_DIR"
elif [ -n "${DEPLOY_REMOTE_BASE:-}" ]; then
  REMOTE_DIR="${DEPLOY_REMOTE_BASE%/}/$REPO_NAME"
else
  echo "Set DEPLOY_REMOTE_BASE or DEPLOY_REMOTE_DIR in $ENV_FILE" >&2
  exit 1
fi

if [ -z "${TEST_CMD:-}" ]; then
  if [ -x "$PROJECT_ROOT/bin/pytest" ]; then
    TEST_CMD='bin/pytest -q'
  elif [ -x "$PROJECT_ROOT/.venv/bin/pytest" ]; then
    TEST_CMD='.venv/bin/pytest -q'
  else
    TEST_CMD='pytest -q'
  fi
fi

echo "repo=$REPO_NAME branch=$BRANCH"
echo "remote=$DEPLOY_SSH:$REMOTE_DIR"

if [ "$SKIP_TESTS" -eq 0 ]; then
  echo "tests: $TEST_CMD"
  # shellcheck disable=SC2086
  (cd "$PROJECT_ROOT" && eval "$TEST_CMD")
else
  echo "tests: skipped"
fi

REMOTE_SCRIPT=$(cat <<EOF
set -euo pipefail
cd $(printf '%q' "$REMOTE_DIR")
if [ ! -d .git ]; then
  echo "Not a git repo on remote: $REMOTE_DIR" >&2
  exit 1
fi
git fetch --all --prune
git checkout $(printf '%q' "$BRANCH")
git pull --ff-only origin $(printf '%q' "$BRANCH")
EOF
)

if [ -n "${DEPLOY_REMOTE_CMD:-}" ]; then
  REMOTE_SCRIPT+=$'\n'"${DEPLOY_REMOTE_CMD}"
fi

ssh "$DEPLOY_SSH" "bash -s" <<<"$REMOTE_SCRIPT"
echo "deploy ok: $REPO_NAME → $DEPLOY_SSH:$REMOTE_DIR"
