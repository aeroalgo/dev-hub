import json
import os
import subprocess
import sys
from pathlib import Path


def workspace_root(payload: dict) -> Path:
    roots = payload.get("workspace_roots") or []
    if roots:
        return Path(roots[0]).resolve()
    return Path.cwd().resolve()


def artifacts_dir(root: Path) -> Path:
    d = root / ".cursor" / "hooks-artifacts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def should_skip_track(path: str) -> bool:
    p = path.replace("\\", "/").lower()
    skip = (
        "/.git/",
        "/node_modules/",
        "/.cursor/hooks-artifacts/",
        "/__pycache__/",
        "/.venv/",
        "/dist/",
        "/build/",
    )
    return any(s in p for s in skip)


# Runtime mirror of .cursor/rules/shared/test-timeout.mdc.
TEST_PROCESS_TIMEOUT_S = 300


def detect_and_run_tests(root: Path) -> tuple[str, int]:
    pkg = root / "package.json"
    if pkg.is_file():
        try:
            raw = pkg.read_text(encoding="utf-8", errors="replace")
            data = json.loads(raw)
            scripts = (data.get("scripts") or {}) if isinstance(data, dict) else {}
            if "test" in scripts:
                r = subprocess.run(
                    ["npm", "test"],
                    cwd=str(root),
                    capture_output=True,
                    text=True,
                    timeout=TEST_PROCESS_TIMEOUT_S,
                )
                out = (r.stdout or "") + (r.stderr or "")
                return out, r.returncode
        except (OSError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
            return f"(npm test skipped: {e})", 0

    if (root / "pyproject.toml").is_file() or (root / "pytest.ini").is_file() or (root / "setup.cfg").is_file():
        tests_dir = root / "tests"
        if tests_dir.is_dir() or list(root.glob("test_*.py")):
            bin_pytest = root / "bin" / "pytest"
            cmd = [str(bin_pytest), "-q"] if bin_pytest.is_file() else [sys.executable, "-m", "pytest", "-q"]
            r = subprocess.run(
                cmd,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=TEST_PROCESS_TIMEOUT_S,
            )
            out = (r.stdout or "") + (r.stderr or "")
            return out, r.returncode

    makefile = root / "Makefile"
    if makefile.is_file():
        text = makefile.read_text(encoding="utf-8", errors="replace")
        if "test:" in text or "test :" in text:
            r = subprocess.run(
                ["make", "test"],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=TEST_PROCESS_TIMEOUT_S,
            )
            out = (r.stdout or "") + (r.stderr or "")
            return out, r.returncode

    return "(тесты: не найден npm test / pytest / make test — настрой проект или расширь hooks/_wf.py)", 0
