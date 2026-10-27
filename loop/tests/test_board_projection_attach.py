from __future__ import annotations

import base64
from typing import Any

import httpx

from loop.board_projection.adapters.bitrix24 import Bitrix24Adapter
from loop.board_projection.adapters.plane import PlaneAdapter
from loop.board_projection.config import Bitrix24Config, PlaneConfig


class _FakeTransport(httpx.BaseTransport):
    def __init__(self, handler):
        self.handler = handler
        self.calls: list[tuple[str, str, Any]] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        raw = request.read()
        body: Any
        if raw:
            try:
                body = httpx.Response(200, content=raw).json()
            except Exception:
                body = raw
        else:
            body = None
        self.calls.append((request.method, str(request.url), body))
        return self.handler(request)


def test_bitrix_attach_document_uses_task_item_addfile():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/task.item.addfile")
        data = httpx.Response(200, content=request.content).json()
        assert data["taskId"] == 34861
        assert data["fileParameters"]["NAME"] == "brief.md"
        assert base64.b64decode(data["fileParameters"]["CONTENT"]) == b"hello"
        return httpx.Response(
            200,
            json={"result": {"ATTACHMENT_ID": 9, "FILE_ID": "1", "NAME": "brief.md"}},
        )

    transport = _FakeTransport(handler)
    client = httpx.Client(transport=transport)
    adapter = Bitrix24Adapter(
        config=Bitrix24Config(
            webhook_url="https://example.test/rest/1/x",
            group_id=26,
            responsible_id=274,
            stage_map={"done": "1"},
        ),
        client=client,
    )
    out = adapter.attach_document("34861", "brief.md", b"hello")
    assert out["attachment_id"] == 9
    assert out["filename"] == "brief.md"


def test_plane_attach_document_three_step_upload():
    state = {"step": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["step"] += 1
        if request.method == "POST" and request.url.path.endswith("/attachments/"):
            return httpx.Response(
                200,
                json={
                    "asset_id": "asset-1",
                    "upload_data": {
                        "url": "https://storage.example/upload",
                        "fields": {"key": "k", "policy": "p", "x-amz-signature": "s"},
                    },
                },
            )
        if request.method == "POST" and "storage.example" in str(request.url):
            return httpx.Response(204)
        if request.method == "PATCH" and request.url.path.endswith("/asset-1/"):
            return httpx.Response(200, json={"is_uploaded": True})
        return httpx.Response(500, text=f"unexpected {request.method} {request.url}")

    transport = _FakeTransport(handler)
    client = httpx.Client(transport=transport)
    adapter = PlaneAdapter(
        config=PlaneConfig(
            base_url="https://plane.example",
            api_key="k",
            workspace_slug="ws",
            project_id="proj",
            state_map={"done": "s"},
        ),
        client=client,
    )
    out = adapter.attach_document("issue-1", "brief.md", b"hello-plane")
    assert out["attachment_id"] == "asset-1"
    assert out["filename"] == "brief.md"
    assert state["step"] >= 3
