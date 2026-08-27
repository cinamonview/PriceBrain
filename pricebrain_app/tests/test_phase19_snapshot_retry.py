"""Phase 19 — snapshot first-write-wins across Fake retry simulation."""

from __future__ import annotations

from datetime import datetime, timezone

from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.gpu_master_seed import seed_gpu_master
from pricebrain_app.repository.persist_service import persist_validated_product
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

CRAWLED_AT = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)
PRODUCT_ID = "ZOTAC-RTX5080-SOLIDOC-16GB"


def _item(product_id: str, product_name: str, *, seller: str) -> dict:
    return {
        "mall": "ELEVENST",
        "product_id": product_id,
        "product_name": product_name,
        "price": 1_500_000,
        "seller": seller,
        "product_url": f"https://www.11st.co.kr/products/{product_id}",
        "crawled_at": CRAWLED_AT,
    }


def _persist(db, raw: dict) -> None:
    persist_validated_product(
        db,
        dict(run_pipeline(dict(raw))),
        external_product_id=str(raw["product_id"]),
        product_name=str(raw["product_name"]),
    )


def test_phase19_fake_retry_keeps_snapshot_on_c2_reingest() -> None:
    db = FakeFirestoreClient()
    seed_gpu_master(db)
    first = _item("1930000001", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB", seller="A셀러")
    _persist(db, first)
    original = db.collection(c.PRODUCTS).document(PRODUCT_ID).get().to_dict()[
        "identity_snapshot"
    ]
    db.simulate_transaction_retries = 2
    db.transaction_callback_runs = 0
    second = _item(
        "1930000002",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB 피씨디렉트",
        seller="B셀러",
    )
    _persist(db, second)
    assert db.transaction_callback_runs >= 3
    stored = db.collection(c.PRODUCTS).document(PRODUCT_ID).get().to_dict()
    assert stored["identity_snapshot"] == original
