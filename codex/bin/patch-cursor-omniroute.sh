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
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

wrapper = json.loads(os.environ["WRAPPER_JSON"])
wrapper_literal = json.dumps(wrapper)

# 1) Route CLI executable through OmniRoute wrapper.
# openai.chatgpt ≤26.908 used yI/mn/fh/za; ≥26.1021 uses W1/to/G1/wc (+ dead `let r=void 0` hook).
marker_wrapper = "process.env.CODEX_OMNIROUTE_WRAPPER||"
resolver_repls = [
    (
        'function yI(t,e){let r=mn("cliExecutable");if(r&&r.trim().length>0)return r;'
        'let n=fh(e),o=(e??process.platform)==="win32"?"codex.exe":"codex";'
        'return za.Uri.joinPath(t,`${n}/${o}`).fsPath}',
        (
            f'function yI(t,e){{let r={marker_wrapper}{wrapper_literal};'
            f'if((e??process.platform)!=="win32"&&r.trim().length>0)return r;'
            f'let n=mn("cliExecutable");if(n&&n.trim().length>0)return n;'
            f'let o=(e??process.platform)==="win32"?"codex.exe":"codex";'
            f'return za.Uri.joinPath(t,`${{fh(e)}}/${{o}}`).fsPath}}'
        ),
    ),
    (
        'function W1(t,e){let r=void 0;if(r)return r;let n=to("cliExecutable");'
        'if(n&&n.trim().length>0)return n;let o=G1(e),'
        'i=(e??process.platform)==="win32"?"codex.exe":"codex";'
        'return wc.Uri.joinPath(t,`${o}/${i}`).fsPath}',
        (
            f'function W1(t,e){{let r={marker_wrapper}{wrapper_literal};'
            f'if((e??process.platform)!=="win32"&&r.trim().length>0)return r;'
            f'let n=to("cliExecutable");if(n&&n.trim().length>0)return n;'
            f'let o=G1(e),i=(e??process.platform)==="win32"?"codex.exe":"codex";'
            f'return wc.Uri.joinPath(t,`${{o}}/${{i}}`).fsPath}}'
        ),
    ),
]

# 2) After unexpected app-server exit, respawn once so the sidebar does not stay dead.
# Stock code only logs fatal and never restarts (manual kill / crash → permanent "process not available").
marker_autorestart = "OMNIROUTE_APP_SERVER_AUTORESTART"
old_finish = (
    'else this.logger.info("Codex app-server process exited successfully.");'
    "this.teardownProcess()}"
)
new_finish = (
    'else this.logger.info("Codex app-server process exited successfully.");'
    "this.teardownProcess();"
    f"/*{marker_autorestart}*/"
    "queueMicrotask(()=>{try{this.startCodexProcess()}catch(r)"
    "{this.logger.warning(\"OmniRoute app-server autorestart failed\","
    "{safe:{},sensitive:{error:String(r)}})}})}"
)

# Strip deprecated kill-tree teardown if a previous patch left it in place.
stock_teardown = (
    "teardownProcess(){this.failPendingRequests(),"
    "this.requestUserInputAutoResolutionCoordinator.clearPendingRequests(),"
    "this.proc&&(this.proc.removeAllListeners(),"
    "!this.proc.killed&&this.proc.exitCode==null&&this.proc.kill(),"
    "this.proc=null),"
)
kill_tree_re = re.compile(
    r"teardownProcess\(\)\{this\.failPendingRequests\(\),"
    r"this\.requestUserInputAutoResolutionCoordinator\.clearPendingRequests\(\),"
    r"this\.proc&&\(this\.proc\.removeAllListeners\(\),\(\(\)=>\{/\*OMNIROUTE_TEARDOWN_KILL_TREE\*/.*?\}\)\(\),this\.proc=null\),",
    re.S,
)

patched = 0
unsupported = 0
for raw_path in sys.argv[1:]:
    path = Path(raw_path)
    text = path.read_text(encoding="utf-8")
    changed = False

    if "OMNIROUTE_TEARDOWN_KILL_TREE" in text:
        text2, n = kill_tree_re.subn(stock_teardown, text, count=1)
        if n != 1:
            print(f"failed to strip kill-tree teardown: {path}", file=sys.stderr)
            unsupported += 1
            continue
        text = text2
        changed = True
        print(f"stripped kill-tree teardown: {path}")

    if marker_wrapper not in text:
        matched = False
        for old_res, new_res in resolver_repls:
            if old_res in text:
                text = text.replace(old_res, new_res, 1)
                changed = True
                matched = True
                print(f"cli resolver wrapper patched: {path}")
                break
        if not matched:
            print(f"unsupported cli resolver: {path}", file=sys.stderr)
            unsupported += 1
            continue
    else:
        print(f"cli resolver already patched: {path}")

    if marker_autorestart not in text:
        if old_finish not in text:
            print(f"unsupported finishProcessExitIfReady: {path}", file=sys.stderr)
            unsupported += 1
            continue
        text = text.replace(old_finish, new_finish, 1)
        changed = True
        print(f"app-server autorestart patched: {path}")
    else:
        print(f"app-server autorestart already patched: {path}")

    if changed:
        backup = path.with_name(
            path.name + ".omniroute.bak." + datetime.now().strftime("%Y%m%d-%H%M%S")
        )
        shutil.copy2(path, backup)
        path.write_text(text, encoding="utf-8")
        print(f"backup: {backup}")
        patched += 1

if unsupported:
    raise SystemExit(f"Unsupported Codex extension bundles: {unsupported}")
if patched == 0:
    print("No new patches applied (already up to date).")
PY

echo "OmniRoute Cursor patches installed. Reload Cursor windows once to revive Codex."
