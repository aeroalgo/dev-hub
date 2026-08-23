from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
LIB_PATH = HOOKS / "_lib.py"


def _load_lib():
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    spec = importlib.util.spec_from_file_location("registry_file_wins_lib", LIB_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _agent(root: Path, filename: str, frontmatter: str) -> None:
    agents = root / ".claude" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / filename).write_text(f"---\n{frontmatter}\n---\nbody\n", encoding="utf-8")


def test_discover_registry_helper_file_wins_over_process_env(
    tmp_path: Path, monkeypatch
) -> None:
    """process_env MODEL_LOOP=0 + project.env MODEL_LOOP=1 → _discover_registry file wins."""
    _agent(
        tmp_path,
        "verify.md",
        "name: verify\noverlay:\n  managed: true\n  mode: gate\n"
        "  requires_model: true\n  default_loop: true\n  default_chat: false\n"
        "  verdict: pass-fail\n  allow_worktree: false",
    )
    env_dir = tmp_path / ".claude"
    env_dir.mkdir(parents=True, exist_ok=True)
    (env_dir / "project.env").write_text(
        "PROJECT_AGENT_VERIFY_MODEL=sonnet\n"
        "PROJECT_AGENT_VERIFY_MODEL_LOOP=1\n"
        "PROJECT_AGENT_VERIFY_MODEL_CHAT=0\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PROJECT_AGENT_VERIFY_MODEL", "sonnet")
    monkeypatch.setenv("PROJECT_AGENT_VERIFY_MODEL_LOOP", "0")
    monkeypatch.setenv("PROJECT_AGENT_VERIFY_MODEL_CHAT", "0")

    lib = _load_lib()
    via_helper = lib._discover_registry(tmp_path)
    assert via_helper.get("verify") is not None
    assert via_helper.get("verify").loop_enabled is True

    # Raw discover_registry keeps process wins (contrast).
    raw = lib.discover_registry(tmp_path)
    assert raw.get("verify") is not None
    assert raw.get("verify").loop_enabled is False
