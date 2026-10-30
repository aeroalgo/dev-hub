from __future__ import annotations

import json

import httpx
import pytest

from loop.board_projection.adapters.plane import PlaneAdapter
from loop.board_projection.config import (
    BoardProjectionConfig,
    PlaneConfig,
    ProvidersConfig,
)
from loop.board_projection.errors import AdapterExecutionError
from loop.board_projection.protocol import BoardProjectionAdapter, EpicRef
from loop.board_projection.registry import get_adapter


def make_fake_client(handler) -> httpx.Client:
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


def test_plane_implements_protocol() -> None:
    cfg = PlaneConfig(
        base_url="https://plane.example.com",
        api_key="secret-key",
        workspace_slug="acme",
        project_id="proj-uuid-1",
        state_map={"backlog": "state-1", "build": "state-2"},
    )
    adapter = PlaneAdapter(config=cfg)
    assert isinstance(adapter, BoardProjectionAdapter)
    assert adapter.provider_name == "plane"


def test_plane_ensure_card() -> None:
    recorded_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        assert request.method == "POST"
        assert request.url.path == "/api/v1/workspaces/acme/projects/proj-uuid-1/work-items/"
        assert request.headers.get("x-api-key") == "secret-key"
        body = json.loads(request.content.decode("utf-8"))
        assert body["name"] == "[T-100] Implement login"
        assert body["description_html"] == "Login epic description"
        assert body["state"] == "state-backlog"
        assert "state_id" not in body
        return httpx.Response(
            201,
            json={"id": "issue-uuid-123", "name": body["name"], "state": "state-backlog"},
        )

    cfg = PlaneConfig(
        base_url="https://plane.example.com",
        api_key="secret-key",
        workspace_slug="acme",
        project_id="proj-uuid-1",
        state_map={"backlog": "state-backlog", "design": "state-design"},
    )
    client = make_fake_client(handler)
    adapter = PlaneAdapter(config=cfg, client=client)

    epic = EpicRef(
        epic_id="T-100",
        title="Implement login",
        description="Login epic description",
        phase="QUEUED",
    )
    issue_id = adapter.ensure_card(epic)
    assert issue_id == "issue-uuid-123"
    assert len(recorded_requests) == 1


def test_plane_move_card_success() -> None:
    recorded_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        assert request.method == "PATCH"
        assert request.url.path == "/api/v1/workspaces/acme/projects/proj-uuid-1/work-items/issue-uuid-123/"
        assert request.headers.get("x-api-key") == "secret-key"
        body = json.loads(request.content.decode("utf-8"))
        assert body["state"] == "state-build"
        assert "state_id" not in body
        return httpx.Response(
            200,
            json={"id": "issue-uuid-123", "state": "state-build"},
        )

    cfg = PlaneConfig(
        base_url="https://plane.example.com",
        api_key="secret-key",
        workspace_slug="acme",
        project_id="proj-uuid-1",
        state_map={"backlog": "state-backlog", "build": "state-build"},
    )
    client = make_fake_client(handler)
    adapter = PlaneAdapter(config=cfg, client=client)

    adapter.move_card("issue-uuid-123", "IMPLEMENT")
    assert len(recorded_requests) == 1


def test_plane_move_card_fail_closed() -> None:
    # API returned 200 but state_id in response did not change (silent no-op)
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"id": "issue-uuid-123", "state": {"id": "old-state-backlog"}},
        )

    cfg = PlaneConfig(
        base_url="https://plane.example.com",
        api_key="secret-key",
        workspace_slug="acme",
        project_id="proj-uuid-1",
        state_map={"backlog": "old-state-backlog", "build": "target-state-build"},
    )
    client = make_fake_client(handler)
    adapter = PlaneAdapter(config=cfg, client=client)

    with pytest.raises(AdapterExecutionError, match="fail-closed"):
        adapter.move_card("issue-uuid-123", "IMPLEMENT")


def test_plane_move_card_unknown_phase_raises() -> None:
    cfg = PlaneConfig(
        base_url="https://plane.example.com",
        api_key="secret-key",
        workspace_slug="acme",
        project_id="proj-uuid-1",
        state_map={"backlog": "state-backlog"},
    )
    adapter = PlaneAdapter(config=cfg, client=make_fake_client(lambda r: httpx.Response(200)))
    with pytest.raises(AdapterExecutionError, match="unknown phase mapping"):
        adapter.move_card("issue-uuid-123", "UNKNOWN_PHASE_999")


def test_plane_http_status_error_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Invalid API key")

    cfg = PlaneConfig(
        base_url="https://plane.example.com",
        api_key="invalid-key",
        workspace_slug="acme",
        project_id="proj-uuid-1",
        state_map={"backlog": "state-backlog"},
    )
    adapter = PlaneAdapter(config=cfg, client=make_fake_client(handler))
    with pytest.raises(AdapterExecutionError, match="HTTP 401"):
        adapter.ensure_card(EpicRef(epic_id="T-100"))


def test_plane_registry_from_config() -> None:
    cfg = BoardProjectionConfig(
        provider="plane",
        providers=ProvidersConfig(
            plane=PlaneConfig(
                base_url="https://plane.example.com",
                api_key="key",
                workspace_slug="ws",
                project_id="prj",
                state_map={"backlog": "s1"},
            )
        ),
    )
    adapter = get_adapter(cfg)
    assert adapter is not None
    assert isinstance(adapter, PlaneAdapter)
    assert adapter.provider_name == "plane"


def test_plane_ensure_card_unknown_phase_raises() -> None:
    # BF-002: incomplete state_map must fail loudly without silent fallback to backlog
    cfg = PlaneConfig(
        base_url="https://plane.example.com",
        api_key="secret-key",
        workspace_slug="acme",
        project_id="proj-uuid-1",
        state_map={"backlog": "state-backlog"},
    )
    adapter = PlaneAdapter(config=cfg, client=make_fake_client(lambda r: httpx.Response(200)))
    with pytest.raises(AdapterExecutionError, match="unknown phase mapping"):
        adapter.ensure_card(EpicRef(epic_id="T-300", phase="IMPLEMENT"))


def test_plane_validate_mappings() -> None:
    # BF-002: validate state_map completeness against phase aliases
    incomplete_cfg = PlaneConfig(
        base_url="https://plane.example.com",
        api_key="secret-key",
        workspace_slug="acme",
        project_id="proj-uuid-1",
        state_map={"backlog": "state-backlog"},
    )
    adapter_inc = PlaneAdapter(config=incomplete_cfg)
    with pytest.raises(AdapterExecutionError, match="Incomplete Plane state_map"):
        adapter_inc.validate_mappings()

    complete_cfg = PlaneConfig(
        base_url="https://plane.example.com",
        api_key="secret-key",
        workspace_slug="acme",
        project_id="proj-uuid-1",
        state_map={"backlog": "s-1", "design": "s-2", "build": "s-3", "verify": "s-4", "uat": "s-5", "done": "s-6", "blocked": "s-7"},
    )
    adapter_complete = PlaneAdapter(config=complete_cfg)
    adapter_complete.validate_mappings()  # does not raise
