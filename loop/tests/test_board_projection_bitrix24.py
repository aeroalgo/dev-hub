from __future__ import annotations

import json
import httpx
import pytest

from loop.board_projection.adapters.bitrix24 import Bitrix24Adapter
from loop.board_projection.config import Bitrix24Config, BoardProjectionConfig, ProvidersConfig
from loop.board_projection.errors import AdapterExecutionError
from loop.board_projection.protocol import BoardProjectionAdapter, EpicRef
from loop.board_projection.registry import get_adapter


def make_fake_client(handler) -> httpx.Client:
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


def test_bitrix24_implements_protocol() -> None:
    cfg = Bitrix24Config(
        webhook_url="https://b24.example.com/rest/1/abc/",
        group_id=42,
        responsible_id=1,
        stage_map={"backlog": "10", "build": "20"},
    )
    adapter = Bitrix24Adapter(config=cfg)
    assert isinstance(adapter, BoardProjectionAdapter)
    assert adapter.provider_name == "bitrix24"


def test_bitrix24_ensure_card() -> None:
    recorded_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        assert request.url.path == "/rest/1/abc/tasks.task.add"
        body = json.loads(request.content.decode("utf-8"))
        assert body["fields"]["GROUP_ID"] == 42
        assert body["fields"]["RESPONSIBLE_ID"] == 1
        assert body["fields"]["STAGE_ID"] == "10"
        assert body["fields"]["TITLE"] == "[T-100] Implement login"
        assert body["fields"]["DESCRIPTION"] == "Login epic description"
        return httpx.Response(
            200,
            json={"result": {"task": {"id": "999", "createdBy": 1, "responsibleId": 1}}},
        )

    cfg = Bitrix24Config(
        webhook_url="https://b24.example.com/rest/1/abc/",
        group_id=42,
        responsible_id=1,
        stage_map={"backlog": "10", "design": "15"},
    )
    client = make_fake_client(handler)
    adapter = Bitrix24Adapter(config=cfg, client=client)

    epic = EpicRef(
        epic_id="T-100",
        title="Implement login",
        description="Login epic description",
        phase="QUEUED",
    )
    task_id = adapter.ensure_card(epic)
    assert task_id == "999"
    assert len(recorded_requests) == 1


def test_bitrix24_ensure_card_numeric_result_format() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"result": 888, "createdBy": 1, "responsibleId": 1})

    cfg = Bitrix24Config(
        webhook_url="https://b24.example.com/rest/1/abc/",
        group_id=42,
        responsible_id=1,
        stage_map={"backlog": "10"},
    )
    adapter = Bitrix24Adapter(config=cfg, client=make_fake_client(handler))
    epic = EpicRef(epic_id="T-200")
    task_id = adapter.ensure_card(epic)
    assert task_id == "888"


def test_bitrix24_move_card() -> None:
    recorded_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        assert request.url.path == "/rest/1/abc/task.stages.movetask"
        body = json.loads(request.content.decode("utf-8"))
        assert body["id"] == 999
        assert body["stageId"] == 20
        return httpx.Response(200, json={"result": True})

    cfg = Bitrix24Config(
        webhook_url="https://b24.example.com/rest/1/abc/",
        group_id=42,
        responsible_id=1,
        stage_map={"backlog": "10", "build": "20"},
    )
    client = make_fake_client(handler)
    adapter = Bitrix24Adapter(config=cfg, client=client)

    adapter.move_card("999", "IMPLEMENT")
    assert len(recorded_requests) == 1


def test_bitrix24_move_card_unknown_phase_raises() -> None:
    cfg = Bitrix24Config(
        webhook_url="https://b24.example.com/rest/1/abc/",
        group_id=42,
        responsible_id=1,
        stage_map={"backlog": "10"},
    )
    adapter = Bitrix24Adapter(config=cfg, client=make_fake_client(lambda r: httpx.Response(200)))
    with pytest.raises(AdapterExecutionError, match="unknown phase mapping"):
        adapter.move_card("999", "UNKNOWN_PHASE_999")


def test_bitrix24_rest_error_response_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"error": "ERROR_TASKS_STAGE_NOT_FOUND", "error_description": "Stage not found in group"},
        )

    cfg = Bitrix24Config(
        webhook_url="https://b24.example.com/rest/1/abc/",
        group_id=42,
        responsible_id=1,
        stage_map={"backlog": "10"},
    )
    adapter = Bitrix24Adapter(config=cfg, client=make_fake_client(handler))
    with pytest.raises(AdapterExecutionError, match="Stage not found in group"):
        adapter.ensure_card(EpicRef(epic_id="T-101"))


def test_bitrix24_http_status_error_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    cfg = Bitrix24Config(
        webhook_url="https://b24.example.com/rest/1/abc/",
        group_id=42,
        responsible_id=1,
        stage_map={"backlog": "10"},
    )
    adapter = Bitrix24Adapter(config=cfg, client=make_fake_client(handler))
    with pytest.raises(AdapterExecutionError, match="HTTP 500"):
        adapter.ensure_card(EpicRef(epic_id="T-101"))


def test_bitrix24_registry_get_adapter() -> None:
    full_cfg = BoardProjectionConfig(
        provider="bitrix24",
        providers=ProvidersConfig(
            bitrix24=Bitrix24Config(
                webhook_url="https://b24.example.com/rest/1/abc/",
                group_id=12,
                responsible_id=1,
                stage_map={"backlog": "10"},
            )
        ),
    )
    adapter = get_adapter(full_cfg)
    assert adapter is not None
    assert isinstance(adapter, Bitrix24Adapter)
    assert adapter.provider_name == "bitrix24"


def test_bitrix24_ensure_card_missing_responsible_id_raises() -> None:
    cfg = Bitrix24Config(
        webhook_url="https://b24.example.com/rest/1/abc/",
        group_id=42,
        responsible_id=None,
        stage_map={"backlog": "10"},
    )
    adapter = Bitrix24Adapter(config=cfg, client=make_fake_client(lambda r: httpx.Response(200)))
    with pytest.raises(AdapterExecutionError, match="responsible_id is required"):
        adapter.ensure_card(EpicRef(epic_id="T-301", phase="QUEUED"))


def test_bitrix24_ensure_card_unknown_phase_raises() -> None:
    # BF-002: incomplete stage_map must fail loudly without silent fallback to backlog
    cfg = Bitrix24Config(
        webhook_url="https://b24.example.com/rest/1/abc/",
        group_id=42,
        responsible_id=1,
        stage_map={"backlog": "10"},
    )
    adapter = Bitrix24Adapter(config=cfg, client=make_fake_client(lambda r: httpx.Response(200)))
    with pytest.raises(AdapterExecutionError, match="unknown phase mapping"):
        adapter.ensure_card(EpicRef(epic_id="T-300", phase="IMPLEMENT"))


def test_bitrix24_validate_mappings() -> None:
    # BF-002: validate stage_map completeness against phase aliases
    incomplete_cfg = Bitrix24Config(
        webhook_url="https://b24.example.com/rest/1/abc/",
        group_id=42,
        responsible_id=1,
        stage_map={"backlog": "10"},
    )
    adapter_inc = Bitrix24Adapter(config=incomplete_cfg)
    with pytest.raises(AdapterExecutionError, match="Incomplete Bitrix24 stage_map"):
        adapter_inc.validate_mappings()

    complete_cfg = Bitrix24Config(
        webhook_url="https://b24.example.com/rest/1/abc/",
        group_id=42,
        responsible_id=1,
        stage_map={"backlog": "1", "design": "2", "build": "3", "verify": "4", "uat": "5", "done": "6", "blocked": "7"},
    )
    adapter_complete = Bitrix24Adapter(config=complete_cfg)
    adapter_complete.validate_mappings()  # does not raise


def test_bitrix24_validate_phase_mapping_does_not_block_build_on_unrelated_alias() -> None:
    cfg = Bitrix24Config(
        webhook_url="https://b24.example.com/rest/1/abc/",
        group_id=42,
        responsible_id=1,
        stage_map={"build": "20"},
    )
    adapter = Bitrix24Adapter(config=cfg)

    adapter.validate_phase_mapping("IMPLEMENT")
    with pytest.raises(AdapterExecutionError, match="blocked"):
        adapter.validate_phase_mapping("HALT")
