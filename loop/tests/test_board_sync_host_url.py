from __future__ import annotations

from pathlib import Path

import pytest

from loop.board_sync.host_url import default_host_url


def test_default_host_url_prefers_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DSH_WEB_URL", "http://127.0.0.1:9999")
    assert default_host_url() == "http://127.0.0.1:9999"


def test_default_host_url_reads_web_host_url_file(tmp_path: Path) -> None:
    (tmp_path / "web-host-url").write_text("http://127.0.0.1:4242\n", encoding="utf-8")
    assert default_host_url(dsh_home=tmp_path) == "http://127.0.0.1:4242"


def test_default_host_url_falls_back_to_3080(tmp_path: Path) -> None:
    assert default_host_url(dsh_home=tmp_path) == "http://127.0.0.1:3080"
