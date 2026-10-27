from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import yaml

from loop.board_projection.adapters.bitrix24 import Bitrix24Adapter
from loop.board_projection.config import Bitrix24Config
from loop.board_projection.project_docs import publish_project_docs
from loop.kernel.cli import main


class CapturingProjectDocsAdapter:
    provider_name = "bitrix24"

    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []

    def publish_project_document(
        self,
        *,
        filename: str,
        content: bytes,
        folder_name: str = "docs",
    ) -> dict[str, Any]:
        item = {
            "provider": "bitrix24",
            "action": "created",
            "filename": filename,
            "folder_name": folder_name,
            "size": len(content),
        }
        self.published.append(item)
        return item


def _write_cfg(tmp_path: Path, files: list[dict[str, str]]) -> Path:
    cfg = {
        "schema": "loop-board-projection/v1",
        "provider": "bitrix24",
        "role_allowlist": ["back"],
        "phase_alias": {"DONE": "done"},
        "providers": {
            "bitrix24": {
                "webhook_url": "https://example.test/rest/1/x/",
                "group_id": 26,
                "responsible_id": 274,
                "stage_map": {"done": "1"},
            },
            "plane": {
                "base_url": "https://example.test",
                "api_key": "k",
                "workspace_slug": "w",
                "project_id": "p",
                "state_map": {"done": "s"},
            },
        },
        "project_docs": {
            "folder_name": "docs",
            "files": files,
        },
    }
    path = tmp_path / ".loop/board-projection.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return path


def test_publish_project_docs_from_config(tmp_path: Path):
    docs = tmp_path / "docs/runbooks"
    docs.mkdir(parents=True)
    (docs / "workflow.md").write_text("# workflow\n", encoding="utf-8")
    _write_cfg(tmp_path, [{"path": "docs/runbooks/workflow.md"}])
    adapter = CapturingProjectDocsAdapter()
    result = publish_project_docs(tmp_path, adapter=adapter)
    assert result.status == "success"
    assert len(adapter.published) == 1
    assert adapter.published[0]["filename"] == "workflow.md"
    assert adapter.published[0]["folder_name"] == "docs"


def test_publish_project_docs_cli_file_override(tmp_path: Path, monkeypatch):
    (tmp_path / "memory-bank").mkdir()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "gitflow.md").write_text("# gitflow\n", encoding="utf-8")
    _write_cfg(tmp_path, [])
    adapter = CapturingProjectDocsAdapter()
    monkeypatch.setattr("loop.board_projection.project_docs.get_adapter", lambda _cfg: adapter)
    rc = main(
        [
            "project-docs",
            "--project",
            str(tmp_path),
            "--file",
            "docs/gitflow.md",
            "--json",
        ]
    )
    assert rc == 0
    assert adapter.published[0]["filename"] == "gitflow.md"


def test_bitrix_publish_project_document_create_and_update():
    files_in_docs: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        raw = request.read()
        payload = httpx.Response(200, content=raw).json() if raw else {}
        path = request.url.path
        if path.endswith("/disk.storage.getlist"):
            return httpx.Response(
                200,
                json={"result": [{"ID": "295", "ROOT_OBJECT_ID": "991698", "ENTITY_ID": "26"}]},
            )
        if path.endswith("/disk.folder.getchildren"):
            folder_id = str(payload.get("id"))
            if folder_id == "991698":
                return httpx.Response(
                    200,
                    json={"result": [{"ID": "10", "NAME": "docs", "TYPE": "folder"}]},
                )
            if folder_id == "10":
                children = [
                    {"ID": file_id, "NAME": name, "TYPE": "file"}
                    for name, file_id in files_in_docs.items()
                ]
                return httpx.Response(200, json={"result": children})
            return httpx.Response(200, json={"result": []})
        if path.endswith("/disk.folder.uploadfile"):
            name = (payload.get("data") or {}).get("NAME")
            files_in_docs[name] = "99"
            return httpx.Response(
                200,
                json={"result": {"ID": "99", "NAME": name, "DOWNLOAD_URL": "http://x"}},
            )
        if path.endswith("/disk.file.uploadversion"):
            return httpx.Response(
                200,
                json={"result": {"ID": "99", "NAME": "workflow.md", "GLOBAL_CONTENT_VERSION": 2}},
            )
        return httpx.Response(500, text=f"unexpected {path} {payload}")

    client = httpx.Client(transport=_Transport(handler))
    adapter = Bitrix24Adapter(
        config=Bitrix24Config(
            webhook_url="https://example.test/rest/1/x",
            group_id=26,
            responsible_id=274,
            stage_map={"done": "1"},
        ),
        client=client,
    )
    created = adapter.publish_project_document(
        filename="workflow.md",
        content=b"# v1\n",
        folder_name="docs",
    )
    assert created["action"] == "created"
    updated = adapter.publish_project_document(
        filename="workflow.md",
        content=b"# v2\n",
        folder_name="docs",
    )
    assert updated["action"] == "updated"


class _Transport(httpx.BaseTransport):
    def __init__(self, handler):
        self.handler = handler

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return self.handler(request)
