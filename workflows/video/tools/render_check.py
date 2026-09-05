"""Render check tool gate adapter."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from loop.workflow.tool_gates.protocol import (
    ToolGateAdapter,
    ToolGateContext,
    ToolGateResult,
)


class RenderCheckAdapter:
    """Checks render output artifact existence and duration."""
    id: str = "render"

    def __init__(self, output_relpath: str = "outputs/final.mp4") -> None:
        self.output_relpath = output_relpath

    def _probe_duration_ffprobe(self, target_path: Path) -> Optional[float]:
        """Probe duration using ffprobe if available. Returns None if ffprobe missing or fails."""
        ffprobe_bin = shutil.which("ffprobe")
        if not ffprobe_bin:
            return None
        cmd = [
            ffprobe_bin,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(target_path),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
            if res.returncode == 0 and res.stdout.strip():
                return float(res.stdout.strip())
        except Exception:
            return None
        return None

    def check(self, ctx: ToolGateContext) -> ToolGateResult:
        """Check output file presence and duration."""
        target_path = ctx.cwd / self.output_relpath
        if not target_path.exists() or not target_path.is_file():
            return ToolGateResult(ok=False, diagnostic_codes=["render_output_missing"])

        # Check duration: ffprobe if available, otherwise stat size fallback
        duration = self._probe_duration_ffprobe(target_path)
        if duration is not None:
            if duration <= 0:
                return ToolGateResult(ok=False, diagnostic_codes=["render_duration_zero"])
        else:
            # Fallback: stat file size > 0
            try:
                if target_path.stat().st_size <= 0:
                    return ToolGateResult(ok=False, diagnostic_codes=["render_duration_zero"])
            except OSError:
                return ToolGateResult(ok=False, diagnostic_codes=["render_output_missing"])

        return ToolGateResult(ok=True, diagnostic_codes=[])
