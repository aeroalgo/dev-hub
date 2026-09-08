#!/usr/bin/env bash
set -euo pipefail

EXTENSIONS_DIR="${CURSOR_EXTENSIONS_DIR:-${HOME}/.cursor/extensions}"
WRAPPER="${OMNIROUTE_WRAPPER:-$(cd "$(dirname "$0")" && pwd)/codex-omniroute.sh}"

if [[ ! -x "$WRAPPER" ]]; then
  echo "OmniRoute wrapper is not executable: $WRAPPER" >&2
  exit 1
fi

mapfile -t EXTENSIONS < <(find "$EXTENSIONS_DIR" -maxdepth 3 -path '*/openai.chatgpt-*/out/extension.js' -type f -print | sort)
if [[ "${#EXTENSIONS[@]}" -eq 0 ]]; then
  echo "Codex Cursor extension was not found under: $EXTENSIONS_DIR" >&2
  exit 1
fi

WRAPPER_JSON="$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$WRAPPER")"
export WRAPPER_JSON

python3 - "${EXTENSIONS[@]}" <<'PY'
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import json
wrapper = json.loads(os.environ["WRAPPER_JSON"])
wrapper_literal = json.dumps(wrapper)

old = 'function QP(t,e){let r=pn("cliExecutable");if(r&&r.trim().length>0)return r;let n=rh(e),o=(e??process.platform)==="win32"?"codex.exe":"codex";return Ga.Uri.joinPath(t,`${n}/${o}`).fsPath}'
new = f'function QP(t,e){{let r=process.env.CODEX_OMNIROUTE_WRAPPER||{wrapper_literal};if((e??process.platform)!=="win32"&&r.trim().length>0)return r;let n=pn("cliExecutable");if(n&&n.trim().length>0)return n;let o=(e??process.platform)==="win32"?"codex.exe":"codex";return Ga.Uri.joinPath(t,`${{rh(e)}}/${{o}}`).fsPath}}'
marker = 'process.env.CODEX_OMNIROUTE_WRAPPER||'

patched = 0
unsupported = 0
for raw_path in sys.argv[1:]:
    path = Path(raw_path)
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"already patched: {path}")
        continue
    if old not in text:
        print(f"unsupported extension bundle: {path}", file=sys.stderr)
        unsupported += 1
        continue
    backup = path.with_name(path.name + ".omniroute.bak." + datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(path, backup)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"patched: {path}")
    print(f"backup: {backup}")
    patched += 1

if unsupported:
    raise SystemExit(f"Unsupported Codex extension bundles: {unsupported}")
if patched == 0 and not any(marker in Path(p).read_text(encoding="utf-8") for p in sys.argv[1:]):
    raise SystemExit("No compatible Codex extension bundle was patched")
PY

echo "OmniRoute executable resolver installed. Reload Cursor window to restart Codex."
