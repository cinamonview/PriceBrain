"""HTTP client for POST /internal/ingest/listing — Crawler → FastAPI (docs/07, docs/09 §8)."""

from __future__ import annotations

from typing import Any

import httpx

from pricebrain_app.config.settings import get_settings
from pricebrain_app.crawler.exceptions import (
    IngestClientConfigError,
    IngestClientHTTPError,
    IngestClientNetworkError,
    IngestClientTimeoutError,
)


class IngestClient:
    """Send RawProductData-compatible payloads to the internal ingest API."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        settings = get_settings()
        if base_url is not None:
            self._base_url = base_url.rstrip("/")
        else:
            self._base_url = settings.pricebrain_ingest_api_url.rstrip("/")
        self._api_key = api_key if api_key is not None else settings.pricebrain_ingest_api_key
        self._timeout = timeout
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> IngestClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def send_listing(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /internal/ingest/listing with Bearer auth."""
        if not self._base_url:
            raise IngestClientConfigError("PRICEBRAIN_INGEST_API_URL is not configured")
        if not self._api_key:
            raise IngestClientConfigError("PRICEBRAIN_INGEST_API_KEY is not configured")

        url = f"{self._base_url}/internal/ingest/listing"
        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            response = self._client.post(
                url,
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise IngestClientTimeoutError(
                f"Ingest request timed out: {url}",
                url=url,
            ) from exc
        except httpx.RequestError as exc:
            raise IngestClientNetworkError(
                f"Ingest network error for {url}: {exc}",
                url=url,
            ) from exc

        if response.status_code >= 400:
            detail: str | object | None
            try:
                body = response.json()
                detail = body.get("detail", body)
            except ValueError:
                detail = response.text
            raise IngestClientHTTPError(
                f"Ingest HTTP {response.status_code} for {url}",
                status_code=response.status_code,
                url=url,
                detail=detail,
            )

        return response.json()
