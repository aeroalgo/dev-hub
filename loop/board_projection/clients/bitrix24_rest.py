from __future__ import annotations

from typing import Any

import httpx

from loop.board_projection.errors import AdapterExecutionError


class Bitrix24RestError(AdapterExecutionError):
    """Raised when a Bitrix24 REST call cannot be completed successfully."""

    def __init__(
        self,
        message: str,
        *,
        method: str | None = None,
        status_code: int | None = None,
        url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.method = method
        self.status_code = status_code
        self.url = url


class Bitrix24RestClient:
    """Small transport client for Bitrix24 incoming-webhook REST calls."""

    def __init__(
        self,
        webhook_url: str,
        client: httpx.Client | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.webhook_url = webhook_url.rstrip("/")
        self.timeout = timeout
        self._client = client

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=self.timeout)

    def call(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Call a Bitrix24 webhook method and return its dictionary response."""
        url = f"{self.webhook_url}/{method.lstrip('/')}"
        client = self._get_client()

        try:
            response = client.post(url, json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise Bitrix24RestError(
                f"Bitrix24 REST API returned HTTP {exc.response.status_code} for {method}: "
                f"{exc.response.text}",
                method=method,
                status_code=exc.response.status_code,
                url=url,
            ) from exc
        except httpx.RequestError as exc:
            raise Bitrix24RestError(
                f"Bitrix24 REST API request failed for {method}: {exc}",
                method=method,
                url=url,
            ) from exc
        except Exception as exc:
            raise Bitrix24RestError(
                f"Unexpected error calling Bitrix24 REST API {method}: {exc}",
                method=method,
                url=url,
            ) from exc

        try:
            data = response.json()
        except (TypeError, ValueError) as exc:
            raise Bitrix24RestError(
                f"Bitrix24 REST API returned invalid JSON for {method}: {exc}",
                method=method,
                url=url,
            ) from exc

        if not isinstance(data, dict):
            raise Bitrix24RestError(
                f"Bitrix24 REST API returned non-dict response for {method}: {data}",
                method=method,
                url=url,
            )

        if "error" in data:
            error_description = data.get("error_description") or data.get("error")
            raise Bitrix24RestError(
                f"Bitrix24 REST API error for {method}: {error_description}",
                method=method,
                url=url,
            )

        return data
