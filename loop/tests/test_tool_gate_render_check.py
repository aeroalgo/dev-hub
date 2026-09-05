"""Tests for ToolGateAdapter and RenderCheckAdapter."""
from pathlib import Path
from unittest.mock import patch

from loop.workflow.tool_gates.protocol import (
    ToolGateAdapter,
    ToolGateContext,
    ToolGateResult,
)
from workflows.video.tools.render_check import RenderCheckAdapter


def test_protocol_conformance() -> None:
    adapter = RenderCheckAdapter()
    assert isinstance(adapter, ToolGateAdapter)
    assert adapter.id == "render"


def test_render_fail_missing(tmp_path: Path) -> None:
    adapter = RenderCheckAdapter()
    ctx = ToolGateContext(cwd=tmp_path, phase="EDIT", pack_id="video-production")
    result = adapter.check(ctx)
    assert result.ok is False
    assert result.diagnostic_codes == ["render_output_missing"]


def test_render_fail_zero_size(tmp_path: Path) -> None:
    adapter = RenderCheckAdapter()
    out_file = tmp_path / "outputs" / "final.mp4"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(b"")

    ctx = ToolGateContext(cwd=tmp_path, phase="EDIT", pack_id="video-production")
    with patch("shutil.which", return_value=None):
        result = adapter.check(ctx)
    assert result.ok is False
    assert result.diagnostic_codes == ["render_duration_zero"]


def test_render_fail_zero_duration_ffprobe(tmp_path: Path) -> None:
    adapter = RenderCheckAdapter()
    out_file = tmp_path / "outputs" / "final.mp4"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(b"some content")

    ctx = ToolGateContext(cwd=tmp_path, phase="EDIT", pack_id="video-production")
    with patch("shutil.which", return_value="/usr/bin/ffprobe"):
        with patch.object(adapter, "_probe_duration_ffprobe", return_value=0.0):
            result = adapter.check(ctx)
    assert result.ok is False
    assert result.diagnostic_codes == ["render_duration_zero"]


def test_render_pass_fixture(tmp_path: Path) -> None:
    adapter = RenderCheckAdapter()
    out_file = tmp_path / "outputs" / "final.mp4"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(b"dummy mp4 fixture payload")

    ctx = ToolGateContext(cwd=tmp_path, phase="EDIT", pack_id="video-production")
    with patch.object(adapter, "_probe_duration_ffprobe", return_value=12.5):
        result = adapter.check(ctx)
    assert result.ok is True
    assert result.diagnostic_codes == []


def test_render_no_ffprobe_fallback_pass(tmp_path: Path) -> None:
    adapter = RenderCheckAdapter()
    out_file = tmp_path / "outputs" / "final.mp4"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(b"mp4 content")

    ctx = ToolGateContext(cwd=tmp_path, phase="EDIT", pack_id="video-production")
    with patch("shutil.which", return_value=None):
        result = adapter.check(ctx)
    assert result.ok is True
    assert result.diagnostic_codes == []
