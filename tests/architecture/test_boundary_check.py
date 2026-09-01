import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
from tests.architecture.check_boundaries import check_boundaries


def test_clean_tree_no_violations():
    yaml_path = root_dir / "tests" / "architecture" / "boundaries.yaml"

    violations = check_boundaries(root_dir, yaml_path)
    assert violations == [], f"Expected 0 boundary violations on clean tree, found:\n" + "\n".join(
        v.format_message() for v in violations
    )


def test_synthetic_violation_detected(tmp_path: Path):
    yaml_content = """
contracts:
  - id: test_forbid_loop
    layer: hooks
    forbids:
      - loop
    reason: "Hooks must not import loop"
"""
    yaml_file = tmp_path / "boundaries.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")

    claude_hooks_dir = tmp_path / ".claude" / "hooks"
    claude_hooks_dir.mkdir(parents=True, exist_ok=True)

    fake_hook = claude_hooks_dir / "bad_hook.py"
    fake_hook.write_text("import loop.context_loop\n", encoding="utf-8")

    violations = check_boundaries(tmp_path, yaml_file)
    assert len(violations) >= 1
    assert violations[0].contract_id == "test_forbid_loop"
    assert violations[0].imported_module == "loop.context_loop"
    assert "Remediation hint" in violations[0].format_message()


def test_boundaries_yaml_schema_valid():
    import yaml

    yaml_path = root_dir / "tests" / "architecture" / "boundaries.yaml"

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "contracts" in data
    assert len(data["contracts"]) >= 5

    for contract in data["contracts"]:
        assert "id" in contract
        assert "layer" in contract
        assert "forbids" in contract
        assert isinstance(contract["forbids"], list)
        assert "reason" in contract
