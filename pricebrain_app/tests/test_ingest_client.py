"""IngestClient unit tests — mocked HTTP, no production Firestore."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from pricebrain_app.crawler.client import IngestClient
from pricebrain_app.crawler.exceptions import (
    IngestClientConfigError,
    IngestClientHTTPError,
    IngestClientNetworkError,
    IngestClientTimeoutError,
)
from pricebrain_app.crawler.models import IngestListingPayload


def _sample_payload() -> dict:
    return IngestListingPayload(
        product_id="test-rtx5080-001",
        product_name="ZOTAC GAMING GeForce RTX 5080 16GB",
        mall_id="ssg",
        product_url="https://example.com/products/test-rtx5080",
        price=1_599_000,
        seller="PriceBrain Test",
        crawled_at=datetime(2026, 8, 21, 11, 0, 0, tzinfo=timezone.utc),
    ).to_dict()


def test_ingest_client_success_post_and_bearer_token() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("Authorization")
        captured["json"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "product_id": "ZOTAC-RTX5080-16GB",
                "listing_id": "SSG_test-rtx5080-001",
                "price_history_appended": True,
            },
        )

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport)
    client = IngestClient(
        base_url="http://127.0.0.1:8000",
        api_key="test-key",
        client=http,
    )
    try:
        result = client.send_listing(_sample_payload())
    finally:
        client.close()

    assert result["status"] == "ok"
    assert captured["authorization"] == "Bearer test-key"
    assert "test-rtx5080-001" in captured["json"]


def test_ingest_client_missing_api_key_raises() -> None:
    client = IngestClient(base_url="http://127.0.0.1:8000", api_key="")
    with pytest.raises(IngestClientConfigError, match="PRICEBRAIN_INGEST_API_KEY"):
        client.send_listing(_sample_payload())


def test_ingest_client_missing_api_url_raises() -> None:
    client = IngestClient(base_url="", api_key="test-key")
    with pytest.raises(IngestClientConfigError, match="PRICEBRAIN_INGEST_API_URL"):
        client.send_listing(_sample_payload())
    client.close()


def test_ingest_client_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport)
    client = IngestClient(
        base_url="http://invalid.local",
        api_key="test-key",
        client=http,
    )
    with pytest.raises(IngestClientNetworkError):
        client.send_listing(_sample_payload())
    client.close()


def test_ingest_client_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timed out", request=request)

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport)
    client = IngestClient(
        base_url="http://127.0.0.1:8000",
        api_key="test-key",
        client=http,
        timeout=1.0,
    )
    with pytest.raises(IngestClientTimeoutError):
        client.send_listing(_sample_payload())
    client.close()


def test_ingest_client_http_401() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(401, json={"detail": "Invalid API key"})
    )
    http = httpx.Client(transport=transport)
    client = IngestClient(base_url="http://127.0.0.1:8000", api_key="bad", client=http)
    with pytest.raises(IngestClientHTTPError) as exc_info:
        client.send_listing(_sample_payload())
    assert exc_info.value.status_code == 401
    client.close()


def test_ingest_client_http_422() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(422, json={"detail": "validation failed"})
    )
    http = httpx.Client(transport=transport)
    client = IngestClient(base_url="http://127.0.0.1:8000", api_key="test-key", client=http)
    with pytest.raises(IngestClientHTTPError) as exc_info:
        client.send_listing(_sample_payload())
    assert exc_info.value.status_code == 422
    client.close()


def test_ingest_client_http_500() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(500, json={"detail": "internal error"})
    )
    http = httpx.Client(transport=transport)
    client = IngestClient(base_url="http://127.0.0.1:8000", api_key="test-key", client=http)
    with pytest.raises(IngestClientHTTPError) as exc_info:
        client.send_listing(_sample_payload())
    assert exc_info.value.status_code == 500
    client.close()
