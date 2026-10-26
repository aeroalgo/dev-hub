from __future__ import annotations

from typing import Any
import httpx

from loop.board_projection.config import Bitrix24Config, BoardProjectionConfig, DEFAULT_PHASE_ALIASES
from loop.board_projection.errors import AdapterExecutionError
from loop.board_projection.protocol import BoardProjectionAdapter, EpicRef
from loop.board_projection.registry import register_adapter


class Bitrix24Adapter(BoardProjectionAdapter):
    """Adapter for Bitrix24 tasks integration via incoming webhook REST API."""

    def __init__(
        self,
        config: Bitrix24Config,
        phase_alias: dict[str, str] | None = None,
        client: httpx.Client | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.config = config
        self.phase_alias = phase_alias if phase_alias is not None else dict(DEFAULT_PHASE_ALIASES)
        self.timeout = timeout
        self._client = client

    @property
    def provider_name(self) -> str:
        return "bitrix24"

    @classmethod
    def from_config(cls, config: BoardProjectionConfig) -> Bitrix24Adapter:
        return cls(
            config=config.providers.bitrix24,
            phase_alias=config.phase_alias,
        )

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=self.timeout)

    def _post(self, method: str, json_data: dict[str, Any]) -> dict[str, Any]:
        webhook_url = self.config.webhook_url.rstrip("/")
        url = f"{webhook_url}/{method}"
        client = self._get_client()
        try:
            resp = client.post(url, json=json_data)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            raise AdapterExecutionError(
                f"Bitrix24 REST API returned HTTP {exc.response.status_code} for {method}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise AdapterExecutionError(
                f"Bitrix24 REST API request failed for {method}: {exc}"
            ) from exc
        except Exception as exc:
            raise AdapterExecutionError(
                f"Unexpected error calling Bitrix24 REST API {method}: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise AdapterExecutionError(f"Bitrix24 REST API returned non-dict response for {method}: {data}")

        if "error" in data:
            err_desc = data.get("error_description", data.get("error"))
            raise AdapterExecutionError(f"Bitrix24 REST API error for {method}: {err_desc}")

        return data

    def resolve_stage_id(self, phase: str) -> str | None:
        """Resolve stage ID from phase using phase_alias and stage_map."""
        normalized_phase = phase.strip()
        alias = self.phase_alias.get(normalized_phase, self.phase_alias.get(normalized_phase.upper(), normalized_phase.lower()))
        return self.config.stage_map.get(alias, self.config.stage_map.get(normalized_phase))

    def ensure_card(self, epic: EpicRef) -> str:
        """
        Create a task on Bitrix24 board using tasks.task.add webhook.
        Returns external task ID as string.
        """
        title = epic.title or epic.epic_id
        description = epic.description or f"Epic: {epic.epic_id}"
        phase = epic.phase or "QUEUED"
        stage_id = self.resolve_stage_id(phase) or self.config.stage_map.get("backlog")

        fields: dict[str, Any] = {
            "TITLE": f"[{epic.epic_id}] {title}" if not title.startswith(f"[{epic.epic_id}]") else title,
            "DESCRIPTION": description,
        }
        if self.config.group_id is not None:
            fields["GROUP_ID"] = self.config.group_id
        if stage_id:
            fields["STAGE_ID"] = stage_id

        payload = {"fields": fields}
        data = self._post("tasks.task.add", payload)

        result = data.get("result")
        if isinstance(result, dict):
            task_info = result.get("task", {})
            task_id = task_info.get("id") if isinstance(task_info, dict) else None
            if not task_id:
                task_id = result.get("id")
        else:
            task_id = result

        if not task_id:
            raise AdapterExecutionError(f"Failed to extract task ID from Bitrix24 response: {data}")

        return str(task_id)

    def move_card(self, external_id: str, phase: str) -> None:
        """Move card to stage corresponding to phase using task.stages.movetask."""
        stage_id = self.resolve_stage_id(phase)
        if not stage_id:
            raise AdapterExecutionError(
                f"Cannot move Bitrix24 task {external_id}: unknown phase mapping for phase '{phase}'"
            )

        payload = {
            "id": int(external_id) if external_id.isdigit() else external_id,
            "stageId": int(stage_id) if stage_id.isdigit() else stage_id,
        }
        self._post("task.stages.movetask", payload)


# Register Bitrix24 adapter in the registry
register_adapter("bitrix24", Bitrix24Adapter.from_config)
