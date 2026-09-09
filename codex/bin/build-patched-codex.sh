#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BUILD_ROOT="${CODEX_PATCH_BUILD_DIR:-${REPO_ROOT}/codex/.build}"
SOURCE_DIR="${CODEX_PATCH_SOURCE_DIR:-${BUILD_ROOT}/source/codex-v0.152.0}"
PATCH_FILE="${CODEX_PATCH_FILE:-${REPO_ROOT}/codex/patches/codex-v0.152.0-flat-collaboration.patch}"
OUTPUT_BIN="${CODEX_PATCHED_BIN:-${BUILD_ROOT}/codex-v0.152.0}"
SOURCE_REPO="${CODEX_PATCH_SOURCE_REPO:-https://github.com/openai/codex.git}"
SOURCE_TAG="${CODEX_PATCH_SOURCE_TAG:-rust-v0.152.0}"

command -v git >/dev/null 2>&1 || { echo "Error: git is required." >&2; exit 127; }
command -v cargo >/dev/null 2>&1 || { echo "Error: cargo is required." >&2; exit 127; }
[[ -f "$PATCH_FILE" ]] || { echo "Error: patch not found: $PATCH_FILE" >&2; exit 1; }

if [[ ! -d "$SOURCE_DIR/.git" ]]; then
    mkdir -p "$(dirname "$SOURCE_DIR")"
    git clone --branch "$SOURCE_TAG" --depth 1 --filter=blob:none "$SOURCE_REPO" "$SOURCE_DIR"
fi

actual_tag="$(git -C "$SOURCE_DIR" describe --tags --exact-match 2>/dev/null || true)"
if [[ "$actual_tag" != "$SOURCE_TAG" ]]; then
    echo "Error: Codex source must be checked out at $SOURCE_TAG (got ${actual_tag:-unknown})." >&2
    echo "Set CODEX_PATCH_SOURCE_DIR to a clean checkout of the requested tag." >&2
    exit 1
fi

if git -C "$SOURCE_DIR" apply --reverse --check "$PATCH_FILE" >/dev/null 2>&1; then
    :
elif git -C "$SOURCE_DIR" apply --check "$PATCH_FILE" >/dev/null 2>&1; then
    git -C "$SOURCE_DIR" apply "$PATCH_FILE"
else
    echo "Error: collaboration patch does not apply cleanly to $SOURCE_TAG." >&2
    exit 1
fi

(cd "$SOURCE_DIR/codex-rs" && cargo build --release --bin codex)

compiled_bin="$SOURCE_DIR/codex-rs/target/release/codex"
[[ -x "$compiled_bin" ]] || { echo "Error: Codex build produced no executable: $compiled_bin" >&2; exit 1; }
mkdir -p "$(dirname "$OUTPUT_BIN")"
install -m 0755 "$compiled_bin" "$OUTPUT_BIN"
echo "$OUTPUT_BIN"
