"""Tests for the product-root pretool boundary."""

from pathlib import Path

from _lib import bash_project_boundary_deny_reason, project_boundary_deny_reason


def test_project_file_is_allowed(tmp_path: Path) -> None:
    target = tmp_path / "memory-bank" / "activeContext.md"
    assert project_boundary_deny_reason(tmp_path, target) is None


def test_direct_external_path_is_denied(tmp_path: Path) -> None:
    external = tmp_path.parent / "outside.txt"
    reason = project_boundary_deny_reason(tmp_path, external)
    assert reason is not None
    assert "outside project root" in reason


def test_only_approved_shared_link_prefix_is_allowed(tmp_path: Path) -> None:
    allowed_link = tmp_path / ".cursor" / "rules" / "workflow.mdc"
    denied_link = tmp_path / "harness" / "hooks" / "stop-gate.py"
    shared_rule = Path(__file__).resolve().parents[3] / "harness" / "cursor" / "rules" / "mainrule.mdc"
    external_file = tmp_path.parent / "outside-hook.py"
    external_file.write_text("# fixture\n", encoding="utf-8")
    denied_link.parent.mkdir(parents=True)
    denied_link.symlink_to(external_file)
    allowed_link.parent.mkdir(parents=True)
    allowed_link.symlink_to(shared_rule)

    assert project_boundary_deny_reason(tmp_path, allowed_link) is None
    reason = project_boundary_deny_reason(tmp_path, denied_link)
    assert reason is not None
    assert "external symlink target" in reason


def test_shared_harness_is_allowed_except_hooks(tmp_path: Path) -> None:
    shared_file = Path(__file__).resolve().parents[3] / "harness" / "cursor" / "rules" / "mainrule.mdc"
    shared_hook = Path(__file__).resolve().parents[3] / "harness" / "hooks" / "stop-gate.py"
    harness_file = tmp_path / "harness" / "cursor" / "rules" / "mainrule.mdc"
    harness_hook = tmp_path / "harness" / "hooks" / "stop-gate.py"
    harness_file.parent.mkdir(parents=True)
    harness_hook.parent.mkdir(parents=True)
    harness_file.symlink_to(shared_file)
    harness_hook.symlink_to(shared_hook)

    assert project_boundary_deny_reason(tmp_path, harness_file) is None
    reason = project_boundary_deny_reason(tmp_path, harness_hook)
    assert reason is not None
    assert "external symlink target" in reason


def test_bash_external_path_is_denied(tmp_path: Path) -> None:
    external = tmp_path.parent / "outside.txt"
    reason = bash_project_boundary_deny_reason(tmp_path, f"cat {external}")
    assert reason is not None
    assert "project_boundary" in reason


def test_bash_project_relative_command_is_allowed(tmp_path: Path) -> None:
    assert bash_project_boundary_deny_reason(tmp_path, "bin/pytest tests -q") is None
