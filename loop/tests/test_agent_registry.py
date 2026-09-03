from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / ".claude" / "hooks" / "agent_registry.py"


def _load():
    spec = importlib.util.spec_from_file_location("agent_registry_test", REGISTRY_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _agent(root: Path, filename: str, frontmatter: str) -> None:
    agents = root / ".claude" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / filename).write_text(f"---\n{frontmatter}\n---\nbody\n", encoding="utf-8")


def test_valid_definition_and_matching_model_are_auto_registered(tmp_path: Path) -> None:
    registry = _load()
    _agent(tmp_path, "researcher.md", "name: researcher\ndescription: Research\noverlay:\n  managed: true\n  requires_model: true\n  default_loop: true")

    result = registry.discover_registry(
        tmp_path,
        process_env={"PROJECT_AGENT_RESEARCHER_MODEL": "sonnet"},
        project_env_local={},
        project_env={},
    )

    definition = result.get("researcher")
    assert definition is not None
    assert definition.model == "sonnet"
    assert definition.runnable is True
    assert not result.diagnostics
    assert result.revision.startswith("sha256:")


def test_malformed_and_missing_model_are_diagnostics_and_not_runnable(tmp_path: Path) -> None:
    registry = _load()
    _agent(tmp_path, "broken.md", "name: broken\noverlay:\n  managed: true\n  requires_model: true")
    _agent(tmp_path, "unclosed.md", "name: unclosed")

    result = registry.discover_registry(tmp_path, process_env={}, project_env_local={}, project_env={})

    assert result.get("broken") is not None
    assert result.get("broken").runnable is False
    assert {item.code for item in result.diagnostics} >= {"model_missing"}
    assert result.get("unclosed") is not None


def test_duplicate_ids_and_orphan_env_fail_closed(tmp_path: Path) -> None:
    registry = _load()
    _agent(tmp_path, "one.md", "name: duplicate")
    (tmp_path / ".claude" / "agents" / "two.md").write_text(
        "---\nname: duplicate\n---\nbody\n", encoding="utf-8"
    )
    (tmp_path / ".claude" / "agents" / "three.md").write_text(
        "---\nname: duplicate\n---\nbody\n", encoding="utf-8"
    )

    result = registry.discover_registry(
        tmp_path,
        process_env={"PROJECT_AGENT_UNKNOWN_MODEL": "sonnet"},
        project_env_local={},
        project_env={},
    )

    assert result.get("duplicate") is None
    assert {item.code for item in result.diagnostics} >= {"definition_invalid", "orphan_env"}
    assert not any(item.code == "duplicate_agent_id" for item in result.diagnostics)


def test_malicious_yaml_is_not_executed_and_unrelated_markdown_is_ignored(tmp_path: Path) -> None:
    registry = _load()
    _agent(tmp_path, "safe.md", "name: safe\ndescription: '!!python/object/apply:os.system [touch /tmp/pwned]'")
    agents = tmp_path / ".claude" / "agents"
    (agents / "notes.txt").write_text("name: ignored", encoding="utf-8")

    result = registry.discover_registry(tmp_path, process_env={}, project_env_local={}, project_env={})

    assert result.get("safe") is not None
    assert not (Path("/tmp") / "pwned").exists()
    assert result.get("notes") is None


def test_legacy_definitions_get_compatibility_defaults(tmp_path: Path) -> None:
    registry = _load()
    _agent(tmp_path, "verify.md", "name: verify")
    _agent(tmp_path, "reviewer.md", "name: reviewer")
    _agent(tmp_path, "explorer.md", "name: explorer")

    result = registry.discover_registry(
        tmp_path,
        process_env={
            "PROJECT_AGENT_VERIFY_MODEL": "haiku",
            "PROJECT_AGENT_REVIEWER_MODEL": "haiku",
        },
        project_env_local={},
        project_env={},
    )

    assert result.get("verify").mode == "gate"
    assert result.get("reviewer").verdict == "pass-blocked-fail"
    assert result.get("explorer").mode == "search"
    assert all(agent.runnable for agent in result.definitions)


def test_normalize_type_verify_alias() -> None:
    sys.path.insert(0, str(ROOT / ".claude" / "hooks"))
    from _lib import normalize_type
    assert normalize_type("verify") == "verify-implement"
    assert normalize_type("explore") == "explorer"
    assert normalize_type("verify-implement") == "verify-implement"


def test_agent_file_exists_verify_implement() -> None:
    assert (ROOT / ".claude" / "agents" / "verify-implement.md").is_file()


def test_sunset_alias() -> None:
    registry = _load()
    assert registry.AGENT_ALIASES.get("sunset") == "sunset-inventory"
    assert registry.resolve_agent_alias("sunset") == "sunset-inventory"


def test_sunset_discovered(tmp_path: Path) -> None:
    registry = _load()
    _agent(
        tmp_path,
        "sunset-inventory.md",
        "name: sunset-inventory\noverlay:\n  managed: true\n  mode: search\n  verdict: none",
    )
    result = registry.discover_registry(tmp_path, process_env={}, project_env_local={}, project_env={})
    agent = result.get("sunset-inventory")
    assert agent is not None
    assert agent.mode == "search"
    assert agent.verdict == "none"
    assert agent.runnable is True


