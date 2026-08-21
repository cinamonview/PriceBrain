from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from pricebrain_app.api.deps import get_firestore
from pricebrain_app.main import app
from pricebrain_app.repository import constants as c
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient


@pytest.fixture
def sample_raw_product() -> dict:
    return {
        "mall": "SSG",
        "product_id": "1000832367906",
        "product_name": "HIT ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB",
        "price": 2429000,
        "seller": "히트정보",
        "product_url": "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906",
        "image_url": "https://sitem.ssgcdn.com/itemimage/1000832367906.jpg",
        "crawled_at": datetime(2026, 8, 19, 10, 0, 0, tzinfo=timezone.utc).isoformat(),
    }


def test_api_ingest_flow(
    sample_raw_product: dict, ingest_auth_env: dict[str, str]
) -> None:
    from pricebrain_app.repository.gpu_master_seed import seed_gpu_master

    fake_db = FakeFirestoreClient()
    seed_gpu_master(fake_db)

    def override_get_firestore():
        yield fake_db

    app.dependency_overrides[get_firestore] = override_get_firestore
    try:
        client = TestClient(app)
        response = client.post(
            "/internal/ingest/listing",
            json=sample_raw_product,
            headers=ingest_auth_env,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["listing_id"] == "SSG_1000832367906"
        assert fake_db.get_document(f"{c.PRODUCTS}/ZOTAC-RTX5080-SOLIDCORE-16GB") is not None
    finally:
        app.dependency_overrides.clear()


def test_api_ingest_invalid_payload(ingest_auth_env: dict[str, str]) -> None:
    fake_db = FakeFirestoreClient()

    def override_get_firestore():
        yield fake_db

    app.dependency_overrides[get_firestore] = override_get_firestore
    try:
        client = TestClient(app)
        response = client.post(
            "/internal/ingest/listing",
            json={"mall": "SSG"},
            headers=ingest_auth_env,
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
