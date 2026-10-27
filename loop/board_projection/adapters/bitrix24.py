from __future__ import annotations

import base64
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

    def validate_mappings(self) -> None:
        """Validate that all phase aliases resolve to a stage ID in stage_map; fail loudly if incomplete."""
        required_aliases = set(self.phase_alias.values())
        missing = [alias for alias in sorted(required_aliases) if not (self.config.stage_map.get(alias) or self.config.stage_map.get(alias.upper()))]
        if missing:
            raise AdapterExecutionError(
                f"Incomplete Bitrix24 stage_map: missing mapping for phase aliases {missing}"
            )

    def ensure_card(self, epic: EpicRef) -> str:
        """
        Create a task on Bitrix24 board using tasks.task.add webhook.
        Returns external task ID as string.
        """
        title = epic.title or epic.epic_id
        description = epic.description or f"Epic: {epic.epic_id}"
        phase = epic.phase or "QUEUED"
        stage_id = self.resolve_stage_id(phase)
        if not stage_id:
            raise AdapterExecutionError(
                f"Cannot create Bitrix24 task for epic {epic.epic_id}: unknown phase mapping for phase '{phase}'"
            )

        if self.config.responsible_id is None:
            raise AdapterExecutionError(
                f"Cannot create Bitrix24 task for epic {epic.epic_id}: responsible_id is required by tasks.task.add"
            )

        fields: dict[str, Any] = {
            "TITLE": f"[{epic.epic_id}] {title}" if not title.startswith(f"[{epic.epic_id}]") else title,
            "DESCRIPTION": description,
            "STAGE_ID": stage_id,
            "RESPONSIBLE_ID": self.config.responsible_id,
            "CREATED_BY": self.config.responsible_id,
        }
        if self.config.group_id is not None:
            fields["GROUP_ID"] = self.config.group_id

        payload = {"fields": fields}
        data = self._post("tasks.task.add", payload)

        result = data.get("result")
        task_info: dict[str, Any] = {}
        if isinstance(result, dict):
            nested = result.get("task")
            task_info = nested if isinstance(nested, dict) else result
            task_id = task_info.get("id") if isinstance(task_info, dict) else None
            if not task_id:
                task_id = result.get("id")
        else:
            task_id = result

        if not task_id:
            raise AdapterExecutionError(f"Failed to extract task ID from Bitrix24 response: {data}")

        task_id_str = str(task_id)
        created_by = str(task_info.get("createdBy") or task_info.get("CREATED_BY") or "")
        responsible = str(task_info.get("responsibleId") or task_info.get("RESPONSIBLE_ID") or "")
        expected = str(self.config.responsible_id)
        if created_by != expected or responsible != expected:
            raise AdapterExecutionError(
                f"Bitrix24 tasks.task.add returned wrong actors for epic {epic.epic_id}: "
                f"createdBy={created_by!r} responsibleId={responsible!r}, expected both {expected!r}. "
                f"Do not patch via tasks.task.update — recreate with CREATED_BY+RESPONSIBLE_ID on add."
            )

        return task_id_str

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

    def attach_document(self, external_id: str, filename: str, content: bytes) -> dict[str, Any]:
        """Attach a file to a Bitrix24 task card (epic). Prefer publish_project_document for project docs."""
        if not filename or not filename.strip():
            raise AdapterExecutionError("Bitrix24 attach_document requires non-empty filename")
        payload = {
            "taskId": int(external_id) if str(external_id).isdigit() else external_id,
            "fileParameters": {
                "NAME": filename.strip(),
                "CONTENT": base64.b64encode(content).decode("ascii"),
            },
        }
        data = self._post("task.item.addfile", payload)
        result = data.get("result")
        if not isinstance(result, dict):
            raise AdapterExecutionError(f"Bitrix24 task.item.addfile returned unexpected result: {data}")
        return {
            "provider": self.provider_name,
            "external_id": str(external_id),
            "filename": filename.strip(),
            "attachment_id": result.get("ATTACHMENT_ID"),
            "file_id": result.get("FILE_ID"),
            "name": result.get("NAME"),
            "download_url": result.get("DOWNLOAD_URL"),
            "view_url": result.get("VIEW_URL"),
            "raw": result,
        }

    def _group_root_folder_id(self) -> str:
        if self.config.group_id is None:
            raise AdapterExecutionError("Bitrix24 project docs require group_id (Sonet project)")
        data = self._post(
            "disk.storage.getlist",
            {
                "filter": {
                    "ENTITY_TYPE": "group",
                    "ENTITY_ID": str(self.config.group_id),
                }
            },
        )
        items = data.get("result") or []
        if not items:
            raise AdapterExecutionError(
                f"Bitrix24 disk storage not found for group_id={self.config.group_id}"
            )
        root_id = items[0].get("ROOT_OBJECT_ID") or items[0].get("ID")
        if not root_id:
            raise AdapterExecutionError(f"Bitrix24 disk storage missing ROOT_OBJECT_ID: {items[0]}")
        return str(root_id)

    def _ensure_subfolder(self, parent_id: str, folder_name: str) -> str:
        children = self._post("disk.folder.getchildren", {"id": int(parent_id) if parent_id.isdigit() else parent_id})
        for item in children.get("result") or []:
            if item.get("TYPE") == "folder" and item.get("NAME") == folder_name:
                return str(item.get("ID"))
        created = self._post(
            "disk.folder.addsubfolder",
            {
                "id": int(parent_id) if parent_id.isdigit() else parent_id,
                "data": {"NAME": folder_name},
            },
        )
        result = created.get("result") or {}
        folder_id = result.get("ID")
        if not folder_id:
            raise AdapterExecutionError(f"Bitrix24 failed to create folder {folder_name!r}: {created}")
        return str(folder_id)

    def publish_project_document(
        self,
        *,
        filename: str,
        content: bytes,
        folder_name: str = "docs",
    ) -> dict[str, Any]:
        """
        Publish a documentation file into the Bitrix project (group) Disk folder.
        Creates/updates file in group storage — not attached to an epic task.
        """
        if not filename or not filename.strip():
            raise AdapterExecutionError("Bitrix24 publish_project_document requires non-empty filename")
        name = filename.strip()
        root_id = self._group_root_folder_id()
        folder_id = self._ensure_subfolder(root_id, folder_name.strip() or "docs")
        b64 = base64.b64encode(content).decode("ascii")

        children = self._post(
            "disk.folder.getchildren",
            {"id": int(folder_id) if folder_id.isdigit() else folder_id},
        )
        existing_id = None
        for item in children.get("result") or []:
            if item.get("TYPE") == "file" and item.get("NAME") == name:
                existing_id = item.get("ID")
                break

        if existing_id is not None:
            data = self._post(
                "disk.file.uploadversion",
                {
                    "id": int(existing_id) if str(existing_id).isdigit() else existing_id,
                    "fileContent": [name, b64],
                },
            )
            action = "updated"
        else:
            data = self._post(
                "disk.folder.uploadfile",
                {
                    "id": int(folder_id) if folder_id.isdigit() else folder_id,
                    "data": {"NAME": name},
                    "fileContent": [name, b64],
                },
            )
            action = "created"

        result = data.get("result") or {}
        if not isinstance(result, dict) or not result.get("ID"):
            raise AdapterExecutionError(f"Bitrix24 project doc publish failed: {data}")
        return {
            "provider": self.provider_name,
            "action": action,
            "filename": name,
            "folder_name": folder_name,
            "folder_id": folder_id,
            "file_id": result.get("ID"),
            "download_url": result.get("DOWNLOAD_URL"),
            "detail_url": result.get("DETAIL_URL"),
            "raw": result,
        }


# Register Bitrix24 adapter in the registry
register_adapter("bitrix24", Bitrix24Adapter.from_config)
