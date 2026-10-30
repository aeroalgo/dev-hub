from __future__ import annotations

import sys
from pathlib import Path
import pytest
import yaml

from loop.board_projection.errors import (
    AdapterExecutionError,
    ProjectionConfigError,
    ProviderMismatchError,
)
from loop.board_projection.mapping import (
    BoardEpicMap,
    EpicMapEntry,
    load_board_epic_map,
    save_board_epic_map,
)
from loop.board_projection.protocol import BoardProjectionAdapter, EpicRef
from loop.board_projection.service import project_epic_phase, project_after_transition


class FakeAdapter(BoardProjectionAdapter):
    def __init__(self, provider: str = "plane") -> None:
        self._provider = provider
        self.created_cards: list[EpicRef] = []
        self.moved_cards: list[tuple[str, str]] = []
        self.updated_cards: list[tuple[str, EpicRef]] = []
        self.fail_create: Exception | None = None
        self.fail_move: Exception | None = None
        self.next_external_id = "ext-101"

    @property
    def provider_name(self) -> str:
        return self._provider

    def ensure_card(self, epic: EpicRef) -> str:
        if self.fail_create:
            raise self.fail_create
        self.created_cards.append(epic)
        return self.next_external_id

    def move_card(self, external_id: str, phase: str) -> None:
        if self.fail_move:
            raise self.fail_move
        self.moved_cards.append((external_id, phase))

    def update_card(self, external_id: str, epic: EpicRef) -> None:
        self.updated_cards.append((external_id, epic))


def write_config(path: Path, provider: str = "plane", role_allowlist: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    roles = role_allowlist if role_allowlist is not None else ["back"]
    data = {
        "schema": "loop-board-projection/v1",
        "provider": provider,
        "role_allowlist": roles,
        "phase_alias": {
            "QUEUED": "backlog",
            "PLAN": "design",
            "IMPLEMENT": "build",
            "QA": "verify",
            "DONE": "done",
            "HALT": "blocked",
        },
        "providers": {
            "bitrix24": {
                "webhook_url": "https://bx.example.com/rest/1/webhook",
                "group_id": 42,
                "responsible_id": 1,
                "stage_map": {"backlog": "1", "design": "2", "build": "3", "verify": "4", "done": "5", "blocked": "6"},
            },
            "plane": {
                "base_url": "https://plane.example.com",
                "api_key": "plane-key-123",
                "workspace_slug": "ws-demo",
                "project_id": "proj-999",
                "state_map": {"backlog": "s-1", "design": "s-2", "build": "s-3", "verify": "s-4", "done": "s-5", "blocked": "s-6"},
            },
        },
    }
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def test_mapping_lifecycle(tmp_path: Path):
    map_file = tmp_path / ".loop" / "board-epic-map.yaml"
    # Load non-existent
    initial_map = load_board_epic_map(map_file)
    assert initial_map.provider == ""
    assert initial_map.epics == {}

    # Save and reload
    initial_map.provider = "plane"
    initial_map.epics["T-HUB-108"] = EpicMapEntry(
        external_id="issue-42",
        last_phase="IMPLEMENT",
        sync_error=None,
    )
    save_board_epic_map(initial_map, map_file)

    loaded = load_board_epic_map(map_file)
    assert loaded.schema_version == "loop-board-epic-map/v1"
    assert loaded.provider == "plane"
    assert "T-HUB-108" in loaded.epics
    entry = loaded.epics["T-HUB-108"]
    assert entry.external_id == "issue-42"
    assert entry.last_phase == "IMPLEMENT"
    assert entry.sync_error is None


def test_provider_mismatch_fails_closed(tmp_path: Path):
    cfg_file = tmp_path / ".loop" / "board-projection.yaml"
    write_config(cfg_file, provider="plane")

    map_file = tmp_path / ".loop" / "board-epic-map.yaml"
    save_board_epic_map(
        BoardEpicMap(
            provider="bitrix24",
            epics={"T-HUB-108": EpicMapEntry(external_id="bx-task-1", last_phase="PLAN")},
        ),
        map_file,
    )

    adapter = FakeAdapter(provider="plane")

    with pytest.raises(ProviderMismatchError) as exc_info:
        project_epic_phase(
            project_root=tmp_path,
            epic_id="T-HUB-108",
            phase="IMPLEMENT",
            config_path=cfg_file,
            map_path=map_file,
            adapter=adapter,
        )

    assert "mismatch" in str(exc_info.value).lower()
    assert len(adapter.created_cards) == 0
    assert len(adapter.moved_cards) == 0


def test_soft_fail_records_sync_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    cfg_file = tmp_path / ".loop" / "board-projection.yaml"
    write_config(cfg_file, provider="plane")
    map_file = tmp_path / ".loop" / "board-epic-map.yaml"

    adapter = FakeAdapter(provider="plane")
    adapter.fail_create = AdapterExecutionError("REST API 500 Internal Server Error")

    result = project_epic_phase(
        project_root=tmp_path,
        epic_id="T-HUB-108",
        phase="PLAN",
        config_path=cfg_file,
        map_path=map_file,
        adapter=adapter,
    )

    assert result.status == "soft_fail"
    assert result.error is not None
    assert "500" in result.error
    assert result.diagnostic_id
    assert result.diagnostic_path == str(tmp_path / ".loop" / "diagnostics" / "last-exception.json")
    assert (tmp_path / ".loop" / "diagnostics" / "last-exception.json").is_file()

    # Stderr check
    captured = capsys.readouterr()
    assert "soft-fail" in captured.err.lower()

    # Map sidecar check
    saved_map = load_board_epic_map(map_file)
    assert "T-HUB-108" in saved_map.epics
    entry = saved_map.epics["T-HUB-108"]
    assert entry.external_id is None
    assert "500" in (entry.sync_error or "")


def test_lazy_create_and_move_idempotence(tmp_path: Path):
    cfg_file = tmp_path / ".loop" / "board-projection.yaml"
    write_config(cfg_file, provider="plane")
    map_file = tmp_path / ".loop" / "board-epic-map.yaml"

    adapter = FakeAdapter(provider="plane")
    adapter.next_external_id = "issue-88"

    # 1. First call: lazy create
    res1 = project_epic_phase(
        project_root=tmp_path,
        epic_id="T-HUB-108",
        phase="PLAN",
        title="Epic Title",
        config_path=cfg_file,
        map_path=map_file,
        adapter=adapter,
    )
    assert res1.status == "success"
    assert res1.external_id == "issue-88"
    assert len(adapter.created_cards) == 1
    assert adapter.created_cards[0].epic_id == "T-HUB-108"
    assert len(adapter.moved_cards) == 0

    saved_map = load_board_epic_map(map_file)
    assert saved_map.epics["T-HUB-108"].external_id == "issue-88"
    assert saved_map.epics["T-HUB-108"].last_phase == "PLAN"

    # 2. Second call: move card to IMPLEMENT
    res2 = project_epic_phase(
        project_root=tmp_path,
        epic_id="T-HUB-108",
        phase="IMPLEMENT",
        config_path=cfg_file,
        map_path=map_file,
        adapter=adapter,
    )
    assert res2.status == "success"
    assert res2.external_id == "issue-88"
    assert len(adapter.created_cards) == 1  # No second create!
    assert len(adapter.moved_cards) == 1
    assert adapter.moved_cards[0] == ("issue-88", "IMPLEMENT")

    # 3. Third call: same phase IMPLEMENT (idempotence, BN-005)
    res3 = project_epic_phase(
        project_root=tmp_path,
        epic_id="T-HUB-108",
        phase="IMPLEMENT",
        config_path=cfg_file,
        map_path=map_file,
        adapter=adapter,
    )
    assert res3.status == "success"
    assert len(adapter.created_cards) == 1
    assert len(adapter.moved_cards) == 1  # Idempotent: no redundant move call


def test_existing_card_explicit_content_is_updated_even_when_phase_is_unchanged(tmp_path: Path):
    cfg_file = tmp_path / ".loop" / "board-projection.yaml"
    write_config(cfg_file, provider="plane")
    map_file = tmp_path / ".loop" / "board-epic-map.yaml"
    save_board_epic_map(
        BoardEpicMap(
            provider="plane",
            epics={"T-HUB-108": EpicMapEntry(external_id="issue-88", last_phase="PLAN")},
        ),
        map_file,
    )

    adapter = FakeAdapter(provider="plane")
    result = project_epic_phase(
        project_root=tmp_path,
        epic_id="T-HUB-108",
        phase="PLAN",
        title="Updated title",
        description="Updated description",
        config_path=cfg_file,
        map_path=map_file,
        adapter=adapter,
    )

    assert result.status == "success"
    assert adapter.moved_cards == []
    assert len(adapter.updated_cards) == 1
    external_id, epic = adapter.updated_cards[0]
    assert external_id == "issue-88"
    assert epic.title == "Updated title"
    assert epic.description == "Updated description"


def test_role_not_allowed(tmp_path: Path):
    cfg_file = tmp_path / ".loop" / "board-projection.yaml"
    write_config(cfg_file, provider="plane", role_allowlist=["front"])
    map_file = tmp_path / ".loop" / "board-epic-map.yaml"

    adapter = FakeAdapter(provider="plane")
    res = project_epic_phase(
        project_root=tmp_path,
        epic_id="T-HUB-108",
        phase="PLAN",
        role="back",
        config_path=cfg_file,
        map_path=map_file,
        adapter=adapter,
    )
    assert res.status == "disabled"
    assert res.disabled_reason == "role_not_allowed"
    assert len(adapter.created_cards) == 0


def test_service_empty_external_id_fails_loudly(tmp_path: Path):
    cfg_file = tmp_path / ".loop" / "board-projection.yaml"
    write_config(cfg_file, provider="plane")
    map_file = tmp_path / ".loop" / "board-epic-map.yaml"

    adapter = FakeAdapter(provider="plane")
    adapter.next_external_id = ""  # empty id returned

    res = project_epic_phase(
        project_root=tmp_path,
        epic_id="T-HUB-108",
        phase="PLAN",
        config_path=cfg_file,
        map_path=map_file,
        adapter=adapter,
    )
    assert res.status == "soft_fail"
    assert "empty external_id" in (res.error or "")
    saved_map = load_board_epic_map(map_file)
    assert saved_map.epics["T-HUB-108"].external_id is None
    assert "empty external_id" in (saved_map.epics["T-HUB-108"].sync_error or "")


def test_service_real_adapter_incomplete_mapping_fails_loudly(tmp_path: Path):
    # BF-003: Real adapter with incomplete stage_map must fail loudly via validate_mappings, not report soft_fail/disabled
    from loop.board_projection.adapters.bitrix24 import Bitrix24Adapter
    from loop.board_projection.config import Bitrix24Config
    import httpx

    cfg_file = tmp_path / ".loop" / "board-projection.yaml"
    write_config(cfg_file, provider="bitrix24")
    map_file = tmp_path / ".loop" / "board-epic-map.yaml"

    # Adapter with only backlog mapped; phase is IMPLEMENT
    b24_cfg = Bitrix24Config(
        webhook_url="https://b24.example.com/rest/1/abc/",
        group_id=42,
        responsible_id=1,
        stage_map={"backlog": "10"},
    )
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"result": 999}))
    adapter = Bitrix24Adapter(config=b24_cfg, client=httpx.Client(transport=transport))

    with pytest.raises(AdapterExecutionError) as exc_info:
        project_epic_phase(
            project_root=tmp_path,
            epic_id="T-HUB-108",
            phase="IMPLEMENT",
            config_path=cfg_file,
            map_path=map_file,
            adapter=adapter,
        )
    assert "incomplete bitrix24 stage_map" in str(exc_info.value).lower()


def test_service_validates_only_target_phase_mapping(tmp_path: Path):
    """A build transition is not blocked by an unrelated missing blocked stage."""
    from loop.board_projection.adapters.bitrix24 import Bitrix24Adapter
    from loop.board_projection.config import Bitrix24Config
    import httpx

    cfg_file = tmp_path / ".loop" / "board-projection.yaml"
    write_config(cfg_file, provider="bitrix24")
    map_file = tmp_path / ".loop" / "board-epic-map.yaml"
    save_board_epic_map(
        BoardEpicMap(
            provider="bitrix24",
            epics={"T-HUB-108": EpicMapEntry(external_id="bx-task-1", last_phase="PLAN")},
        ),
        map_file,
    )
    b24_cfg = Bitrix24Config(
        webhook_url="https://b24.example.com/rest/1/abc/",
        group_id=42,
        responsible_id=1,
        stage_map={"build": "20"},
    )
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"result": True})

    adapter = Bitrix24Adapter(
        config=b24_cfg,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = project_epic_phase(
        project_root=tmp_path,
        epic_id="T-HUB-108",
        phase="IMPLEMENT",
        config_path=cfg_file,
        map_path=map_file,
        adapter=adapter,
    )

    assert result.status == "success"
    assert len(requests) == 1


def test_service_active_provider_incomplete_config_raises_explicit_error(tmp_path: Path):
    # BF-003: Incomplete active provider config must raise ProjectionConfigError, not return disabled
    cfg_file = tmp_path / ".loop" / "board-projection.yaml"
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    # Bitrix24 config missing webhook_url and group_id
    bad_data = {
        "schema": "loop-board-projection/v1",
        "provider": "bitrix24",
        "role_allowlist": ["back"],
        "providers": {
            "bitrix24": {
                "webhook_url": "",
                "group_id": None,
                "responsible_id": 1,
            }
        },
    }
    cfg_file.write_text(yaml.safe_dump(bad_data), encoding="utf-8")

    with pytest.raises(ProjectionConfigError) as exc_info:
        project_epic_phase(
            project_root=tmp_path,
            epic_id="T-HUB-108",
            phase="IMPLEMENT",
            config_path=cfg_file,
        )
    assert "misconfigured: incomplete_provider_config" in str(exc_info.value)


def test_service_active_provider_invalid_yaml_raises_explicit_error(tmp_path: Path):
    # BF-003: Corrupt YAML must raise ProjectionConfigError, not return disabled
    cfg_file = tmp_path / ".loop" / "board-projection.yaml"
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text("provider: bitrix24\nthis: [is, not, valid: yaml\n", encoding="utf-8")

    with pytest.raises(ProjectionConfigError) as exc_info:
        project_epic_phase(
            project_root=tmp_path,
            epic_id="T-HUB-108",
            phase="IMPLEMENT",
            config_path=cfg_file,
        )
    assert "Failed to parse YAML" in str(exc_info.value)


def test_service_active_provider_plane_incomplete_mapping_fails_loudly(tmp_path: Path):
    # BF-003: Plane provider with incomplete state_map must fail loudly
    cfg_file = tmp_path / ".loop" / "board-projection.yaml"
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_data = {
        "schema": "loop-board-projection/v1",
        "provider": "plane",
        "role_allowlist": ["back"],
        "providers": {
            "plane": {
                "base_url": "https://plane.example.com",
                "api_key": "plane-key-123",
                "workspace_slug": "ws-demo",
                "project_id": "proj-999",
                "state_map": {"backlog": "s-1"},  # missing other phases
            },
        },
    }
    cfg_file.write_text(yaml.safe_dump(cfg_data), encoding="utf-8")

    with pytest.raises(AdapterExecutionError) as exc_info:
        project_epic_phase(
            project_root=tmp_path,
            epic_id="T-HUB-108",
            phase="IMPLEMENT",
            config_path=cfg_file,
        )
    assert "incomplete plane state_map" in str(exc_info.value).lower()
