import json
import os
import sys
from pathlib import Path

def main() -> None:
    if os.environ.get("EPIC_INCIDENT_SESSION") != "1":
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = data.get("tool", "")
    if tool_name not in ("Write", "Edit", "NotebookEdit"):
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not file_path:
        sys.exit(0)

    # Resolve tier1_scope.json location
    # Default path pattern or from environment
    scope_file_env = os.environ.get("TIER1_SCOPE_FILE")
    if scope_file_env:
        scope_file = Path(scope_file_env)
    else:
        # Fallback search or default path
        incident_id = os.environ.get("EPIC_INCIDENT_ID", "")
        project_root = Path(os.environ.get("PROJECT_ROOT", ".")).resolve()
        if incident_id:
            scope_file = project_root / "runtime" / incident_id / "epic" / "tier1_scope.json"
        else:
            sys.exit(0)

    if not scope_file.exists():
        # Scope file missing while incident session active -> block for safety
        sys.stderr.write(f"Pretool guard error: scope file {scope_file} missing\n")
        sys.exit(2)

    try:
        with scope_file.open("r", encoding="utf-8") as f:
            scope_data = json.load(f)
        allowlist = scope_data.get("allowlist", [])
    except Exception as e:
        sys.stderr.write(f"Pretool guard error reading scope file: {e}\n")
        sys.exit(2)

    # Check path against allowlist using loop/incidents/scope.py logic
    try:
        target = Path(file_path).resolve()
    except Exception:
        sys.stderr.write(f"Pretool guard error: invalid target path {file_path}\n")
        sys.exit(2)

    target_str = str(target)
    allowed = False

    for item in allowlist:
        try:
            allowed_path = Path(item).resolve()
        except Exception:
            continue

        allowed_str = str(allowed_path)
        if target_str == allowed_str:
            allowed = True
            break

        try:
            if target.is_relative_to(allowed_path):
                allowed = True
                break
        except AttributeError:
            if target_str.startswith(allowed_str + os.sep):
                allowed = True
                break

    if not allowed:
        sys.stderr.write(f"Pretool guard BLOCKED: write to {file_path} is out of incident scope\n")
        sys.exit(2)

    sys.exit(0)

if __name__ == "__main__":
    main()
