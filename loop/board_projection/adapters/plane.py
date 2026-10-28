from __future__ import annotations

import mimetypes
from typing import Any
import httpx

from loop.board_projection.config import BoardProjectionConfig, DEFAULT_PHASE_ALIASES, PlaneConfig
from loop.board_projection.errors import AdapterExecutionError
from loop.board_projection.protocol import BoardProjectionAdapter, EpicRef
from loop.board_projection.registry import register_adapter


class PlaneAdapter(BoardProjectionAdapter):
    """Adapter for Plane project management integration via REST API."""

    def __init__(
        self,
        config: PlaneConfig,
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
        return "plane"

    @classmethod
    def from_config(cls, config: BoardProjectionConfig) -> PlaneAdapter:
        return cls(
            config=config.providers.plane,
            phase_alias=config.phase_alias,
        )

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=self.timeout)

    def _get_headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.config.api_key,
            "Content-Type": "application/json",
        }

    def _get_issues_url(self) -> str:
        base = self.config.base_url.rstrip("/")
        return f"{base}/api/v1/workspaces/{self.config.workspace_slug}/projects/{self.config.project_id}/issues/"

    def _request(self, method: str, url: str, json_data: dict[str, Any] | None = None) -> dict[str, Any]:
        client = self._get_client()
        headers = self._get_headers()
        try:
            resp = client.request(method, url, json=json_data, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            raise AdapterExecutionError(
                f"Plane REST API returned HTTP {exc.response.status_code} for {method} {url}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise AdapterExecutionError(
                f"Plane REST API request failed for {method} {url}: {exc}"
            ) from exc
        except Exception as exc:
            raise AdapterExecutionError(
                f"Unexpected error calling Plane REST API {method} {url}: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise AdapterExecutionError(f"Plane REST API returned non-dict response for {method} {url}: {data}")

        return data

    def resolve_state_id(self, phase: str) -> str | None:
        """Resolve state ID from phase using phase_alias and state_map."""
        normalized_phase = phase.strip()
        alias = self._phase_alias(normalized_phase)
        return self.config.state_map.get(alias, self.config.state_map.get(normalized_phase))

    def _phase_alias(self, phase: str) -> str:
        normalized_phase = phase.strip()
        return self.phase_alias.get(
            normalized_phase,
            self.phase_alias.get(normalized_phase.upper(), normalized_phase.lower()),
        )

    def validate_phase_mapping(self, phase: str) -> None:
        """Validate the state needed for this transition only."""
        alias = self._phase_alias(phase)
        if not self.resolve_state_id(phase):
            raise AdapterExecutionError(
                f"Incomplete Plane state_map: missing mapping for phase aliases [{alias!r}]"
            )

    def validate_mappings(self) -> None:
        """Validate that all phase aliases resolve to a state ID in state_map; fail loudly if incomplete."""
        required_aliases = set(self.phase_alias.values())
        missing = [alias for alias in sorted(required_aliases) if not (self.config.state_map.get(alias) or self.config.state_map.get(alias.upper()))]
        if missing:
            raise AdapterExecutionError(
                f"Incomplete Plane state_map: missing mapping for phase aliases {missing}"
            )

    def ensure_card(self, epic: EpicRef) -> str:
        """
        Create work item / issue in Plane via POST /api/v1/workspaces/{slug}/projects/{project_id}/issues/.
        Returns external issue ID as string.
        """
        title = epic.title or epic.epic_id
        description = epic.description or f"Epic: {epic.epic_id}"
        phase = epic.phase or "QUEUED"
        state_id = self.resolve_state_id(phase)
        if not state_id:
            raise AdapterExecutionError(
                f"Cannot create Plane work item for epic {epic.epic_id}: unknown phase mapping for phase '{phase}'"
            )

        payload: dict[str, Any] = {
            "name": f"[{epic.epic_id}] {title}" if not title.startswith(f"[{epic.epic_id}]") else title,
            "description_html": description,
            "description": description,
            "state_id": state_id,
            "state": state_id,
        }

        url = self._get_issues_url()
        data = self._request("POST", url, payload)

        issue_id = data.get("id") or data.get("issue_id")
        if not issue_id:
            raise AdapterExecutionError(f"Failed to extract issue ID from Plane response: {data}")

        return str(issue_id)

    def move_card(self, external_id: str, phase: str) -> None:
        """
        Update work item state in Plane via PATCH /api/v1/workspaces/{slug}/projects/{project_id}/issues/{issue_id}/.
        Validates returned state fail-closed to protect against silent no-op.
        """
        target_state_id = self.resolve_state_id(phase)
        if not target_state_id:
            raise AdapterExecutionError(
                f"Cannot move Plane work item {external_id}: unknown phase mapping for phase '{phase}'"
            )

        payload = {
            "state_id": target_state_id,
            "state": target_state_id,
        }
        url = f"{self._get_issues_url()}{external_id}/"
        data = self._request("PATCH", url, payload)

        # Fail-closed check: verify state in response matches target_state_id
        actual_state = data.get("state_id")
        if actual_state is None:
            raw_state = data.get("state")
            if isinstance(raw_state, dict):
                actual_state = raw_state.get("id")
            elif isinstance(raw_state, str):
                actual_state = raw_state

        if str(actual_state) != str(target_state_id):
            raise AdapterExecutionError(
                f"Plane issue {external_id} state update failed (fail-closed): expected state '{target_state_id}', got '{actual_state}' in response"
            )

    def _attachments_url(self, external_id: str) -> str:
        base = self.config.base_url.rstrip("/")
        return (
            f"{base}/api/v1/workspaces/{self.config.workspace_slug}"
            f"/projects/{self.config.project_id}/work-items/{external_id}/attachments/"
        )

    def attach_document(self, external_id: str, filename: str, content: bytes) -> dict[str, Any]:
        """
        Attach a file to a Plane work item (3-step: credentials → storage upload → complete).
        Manual board-docs only; never called from finish/halt.
        """
        if not filename or not filename.strip():
            raise AdapterExecutionError("Plane attach_document requires non-empty filename")
        name = filename.strip()
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        size = len(content)
        if size < 1:
            raise AdapterExecutionError("Plane attach_document requires non-empty content")

        credentials = self._request(
            "POST",
            self._attachments_url(external_id),
            {
                "name": name,
                "type": mime,
                "size": size,
                "external_source": "dev-hub-loop",
            },
        )

        upload_data = credentials.get("upload_data") or credentials.get("upload") or {}
        if not isinstance(upload_data, dict):
            upload_data = {}
        upload_url = (
            upload_data.get("url")
            or credentials.get("upload_url")
            or "https://planefs-uploads.s3.amazonaws.com/"
        )
        fields = upload_data.get("fields") if isinstance(upload_data.get("fields"), dict) else {}
        if not fields:
            # flatten common top-level credential keys into form fields
            for key in ("key", "policy", "x-amz-signature", "Content-Type", "AWSAccessKeyId", "acl"):
                if key in upload_data:
                    fields[key] = upload_data[key]
                elif key in credentials:
                    fields[key] = credentials[key]
        if "Content-Type" not in fields:
            fields["Content-Type"] = mime

        attachment_obj = credentials.get("attachment")
        asset_id = credentials.get("asset_id") or credentials.get("id")
        if not asset_id and isinstance(attachment_obj, dict):
            asset_id = attachment_obj.get("id")
        if not asset_id:
            raise AdapterExecutionError(
                f"Plane attach_document missing asset_id in credentials response: {credentials}"
            )

        client = self._get_client()
        try:
            upload_resp = client.post(
                upload_url,
                data=fields,
                files={"file": (name, content, mime)},
            )
            if upload_resp.status_code >= 400:
                raise AdapterExecutionError(
                    f"Plane storage upload failed HTTP {upload_resp.status_code}: {upload_resp.text}"
                )
        except httpx.RequestError as exc:
            raise AdapterExecutionError(f"Plane storage upload request failed: {exc}") from exc

        complete_url = f"{self._attachments_url(external_id)}{asset_id}/"
        self._request("PATCH", complete_url, {"is_uploaded": True})

        return {
            "provider": self.provider_name,
            "external_id": str(external_id),
            "filename": name,
            "attachment_id": str(asset_id),
            "mime": mime,
            "size": size,
        }

    def _pages_url(self) -> str:
        base = self.config.base_url.rstrip("/")
        return (
            f"{base}/api/v1/workspaces/{self.config.workspace_slug}"
            f"/projects/{self.config.project_id}/pages/"
        )

    def publish_project_document(
        self,
        *,
        filename: str,
        content: bytes,
        folder_name: str = "docs",
    ) -> dict[str, Any]:
        """
        Publish project-level documentation as a Plane project page (not an issue attachment).
        Page name = folder_name / filename for grouping label in title.
        """
        if not filename or not filename.strip():
            raise AdapterExecutionError("Plane publish_project_document requires non-empty filename")
        name = filename.strip()
        title = f"{folder_name.strip() or 'docs'} / {name}"
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("utf-8", errors="replace")
        # Plane pages expect HTML-ish description; keep markdown in a pre block for fidelity
        html = f"<h1>{name}</h1><pre>{_html_escape(text)}</pre>"

        listing = self._request("GET", self._pages_url())
        pages = listing.get("results") if isinstance(listing.get("results"), list) else []
        if not pages and isinstance(listing, list):
            pages = listing
        existing_id = None
        for page in pages:
            if not isinstance(page, dict):
                continue
            page_name = page.get("name") or page.get("title") or ""
            if page_name == title or page_name == name:
                existing_id = page.get("id")
                break

        payload = {
            "name": title,
            "description_html": html,
            "description": text,
        }
        if existing_id:
            data = self._request("PATCH", f"{self._pages_url()}{existing_id}/", payload)
            action = "updated"
            page_id = existing_id
        else:
            data = self._request("POST", self._pages_url(), payload)
            action = "created"
            page_id = data.get("id")
        if not page_id:
            raise AdapterExecutionError(f"Plane project page publish missing id: {data}")
        return {
            "provider": self.provider_name,
            "action": action,
            "filename": name,
            "folder_name": folder_name,
            "page_id": str(page_id),
            "title": title,
            "raw": data,
        }


def _html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# Register Plane adapter in the registry
register_adapter("plane", PlaneAdapter.from_config)
