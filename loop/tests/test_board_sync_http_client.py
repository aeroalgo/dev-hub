from __future__ import annotations

import httpx
import pytest

from loop.board_sync.client import BoardClientError, HttpHostClient


from loop.board_sync.diff import BoardTask


def _client(handler, *, token: str | None = None) -> HttpHostClient:
    transport = httpx.MockTransport(handler)
    return HttpHostClient("http://dsh.test/", proxy_token=token, transport=transport)


def test_list_tasks_ok() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/task-board/state"
        return httpx.Response(
            200,
            json={
                "tasks": [
                    {
                        "id": "mb-demo-back-t-demo-s01",
                        "title": "[BACK] T-DEMO s01 — Step",
                        "description": "metadata",
                        "prompt": "BACK IMPLEMENT",
                        "workspace_id": "demo",
                        "status": "todo",
                    }
                ]
            },
        )

    tasks = _client(handler).list_tasks()

    assert tasks == [
        BoardTask(
            id="mb-demo-back-t-demo-s01",
            title="[BACK] T-DEMO s01 — Step",
            description="metadata",
            prompt="BACK IMPLEMENT",
            workspace_id="demo",
            status="todo",
        )
    ]


def test_list_tasks_404() -> None:
    client = _client(lambda _: httpx.Response(404, text="missing"))

    with pytest.raises(BoardClientError) as error:
        client.list_tasks()

    assert error.value.status_code == 404


def test_upsert_create_200() -> None:
    requests: list[httpx.Request] = []
    card = BoardTask("task-1", "Title", "Description", "BACK IMPLEMENT")

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    _client(handler).upsert(card)

    assert requests[-1].url.path == "/api/task-board/action"
    payload = requests[-1].read()
    assert b'"kind":"create"' in payload
    assert b'"id":"task-1"' in payload
    assert b'"requestId"' in payload


def test_upsert_non2xx() -> None:
    card = BoardTask("task-1", "Title", "Description", "BACK IMPLEMENT")
    client = _client(lambda _: httpx.Response(500, text="upstream failed"))

    with pytest.raises(BoardClientError) as error:
        client.upsert(card)

    assert error.value.status_code == 500
    assert error.value.body == "upstream failed"


def test_lock_conflict() -> None:
    card = BoardTask("task-1", "Title", "Description", "BACK IMPLEMENT")
    client = _client(
        lambda _: httpx.Response(409, json={"error": "lock_conflict"})
    )

    with pytest.raises(BoardClientError) as error:
        client.upsert(card)

    assert error.value.lock_conflict is True


def test_proxy_token_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer secret"
        assert request.headers["x-proxy-token"] == "secret"
        return httpx.Response(200, json={"tasks": []})

    _client(handler, token="secret").list_tasks()


def test_archive_ok() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    _client(handler).archive("task-1")

    assert requests[0].url.path == "/api/task-board/action"
    assert b'"kind":"archive"' in requests[0].read()
    assert b'"taskId":"task-1"' in requests[0].read()
