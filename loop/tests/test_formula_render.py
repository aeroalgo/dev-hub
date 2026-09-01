"""Tests for formula-render module and CLI subcommand."""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest
import yaml

from loop.formula_render import render_formula, find_formula_file


def test_dry_run_hooks_epic(capsys):
    res = render_formula("hooks-epic", "T-HUB-999", "test-slug", dry_run=True)
    captured = capsys.readouterr().out

    assert "index.yaml" in res
    assert len(res) >= 6  # index.yaml + at least 5 step shards

    assert "schema: epic-decompose-index/v1" in captured
    assert "plan_id: T-HUB-999-test-slug" in captured
    assert "s01-env-contract.yaml" in captured


def test_render_writes_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        written = render_formula("hooks-epic", "T-HUB-999", "test-slug", out_dir=tmp_path)

        assert (tmp_path / "index.yaml").is_file()
        assert (tmp_path / "s01-env-contract.yaml").is_file()
        assert len(written) >= 6

        index_content = yaml.safe_load((tmp_path / "index.yaml").read_text())
        assert index_content["schema"] == "epic-decompose-index/v1"
        assert index_data_has_steps(index_content)

        s01_content = yaml.safe_load((tmp_path / "s01-env-contract.yaml").read_text())
        assert s01_content["schema"] == "epic-decompose/v1"
        assert s01_content["step_id"] == "s01"


def test_no_overwrite_without_force():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        render_formula("hooks-epic", "T-HUB-999", "test-slug", out_dir=tmp_path)

        with pytest.raises(ValueError, match="already exists"):
            render_formula("hooks-epic", "T-HUB-999", "test-slug", out_dir=tmp_path, force=False)

        # Should succeed with force=True
        written = render_formula("hooks-epic", "T-HUB-999", "test-slug", out_dir=tmp_path, force=True)
        assert len(written) >= 6


def test_unknown_formula_exit1():
    with pytest.raises(ValueError, match="Formula 'non-existent-formula' not found"):
        render_formula("non-existent-formula", "T-HUB-999", "test-slug", dry_run=True)


def index_data_has_steps(data: dict) -> bool:
    return "steps" in data and len(data["steps"]) > 0
