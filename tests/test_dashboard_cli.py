"""Tests for CLI dashboard-render subcommand."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from loop.context_loop import _cmd_dashboard_render


def test_cli_creates_html_file(tmp_path: Path):
    args = MagicMock()
    args.days = 7
    args.format = "html"

    # mock collect and render_html
    mock_report = MagicMock()
    with patch("loop.dashboard.collect.collect", return_value=mock_report) as mock_collect, \
         patch("loop.dashboard.render.render_html", return_value="<html>Dashboard</html>") as mock_render:
        exit_code = _cmd_dashboard_render(args, tmp_path)
        assert exit_code == 0
        mock_collect.assert_called_once_with(tmp_path, days=7)
        mock_render.assert_called_once_with(mock_report)

    # verify file written
    reports_dir = tmp_path / "runtime" / "reports"
    assert reports_dir.is_dir()
    files = list(reports_dir.glob("dashboard-*.html"))
    assert len(files) == 1
    assert files[0].read_text(encoding="utf-8") == "<html>Dashboard</html>"


def test_cli_creates_json_file(tmp_path: Path):
    args = MagicMock()
    args.days = 14
    args.format = "json"

    mock_report = MagicMock()
    with patch("loop.dashboard.collect.collect", return_value=mock_report) as mock_collect, \
         patch("loop.dashboard.render.render_json", return_value='{"status": "ok"}') as mock_render:
        exit_code = _cmd_dashboard_render(args, tmp_path)
        assert exit_code == 0
        mock_collect.assert_called_once_with(tmp_path, days=14)
        mock_render.assert_called_once_with(mock_report)

    reports_dir = tmp_path / "runtime" / "reports"
    assert reports_dir.is_dir()
    files = list(reports_dir.glob("dashboard-*.json"))
    assert len(files) == 1
    assert files[0].read_text(encoding="utf-8") == '{"status": "ok"}'


def test_cli_creates_both_files(tmp_path: Path):
    args = MagicMock()
    args.days = 7
    args.format = "both"

    mock_report = MagicMock()
    with patch("loop.dashboard.collect.collect", return_value=mock_report), \
         patch("loop.dashboard.render.render_html", return_value="<html>Dashboard</html>"), \
         patch("loop.dashboard.render.render_json", return_value='{"status": "ok"}'):
        exit_code = _cmd_dashboard_render(args, tmp_path)
        assert exit_code == 0

    reports_dir = tmp_path / "runtime" / "reports"
    html_files = list(reports_dir.glob("dashboard-*.html"))
    json_files = list(reports_dir.glob("dashboard-*.json"))
    assert len(html_files) == 1
    assert len(json_files) == 1
