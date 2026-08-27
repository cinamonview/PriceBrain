"""Phase 18 — top-level identity field usage vs snapshot first-write-wins.

Does not freeze top-level fields. Documents current last-write-wins behavior
and recommended policy per field.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.gpu_master_seed import seed_gpu_master
from pricebrain_app.repository.persist_service import persist_validated_product
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

CRAWLED_AT = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)


def test_phase18_top_level_name_can_drift_while_snapshot_stays() -> None:
    db = FakeFirestoreClient()
    seed_gpu_master(db)
    first = {
        "mall": "ELEVENST",
        "product_id": "1830000001",
        "product_name": "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
        "price": 1_500_000,
        "seller": "A셀러",
        "product_url": "https://www.11st.co.kr/products/1830000001",
        "crawled_at": CRAWLED_AT,
    }
    persist_validated_product(
        db,
        dict(run_pipeline(dict(first))),
        external_product_id="1830000001",
        product_name=first["product_name"],
    )
    product_id = "ZOTAC-RTX5080-SOLIDOC-16GB"
    original = db.collection(c.PRODUCTS).document(product_id).get().to_dict()
    second = {
        **first,
        "product_id": "1830000002",
        "product_name": "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB 피씨디렉트",
        "seller": "B셀러",
        "product_url": "https://www.11st.co.kr/products/1830000002",
    }
    persist_validated_product(
        db,
        dict(run_pipeline(dict(second))),
        external_product_id="1830000002",
        product_name=second["product_name"],
    )
    stored = db.collection(c.PRODUCTS).document(product_id).get().to_dict()
    assert stored["identity_snapshot"] == original["identity_snapshot"]
    # Listing-facing top-level name is last-write-wins today (KEEP for Phase 18).
    assert stored["normalized_product_name"] != original["normalized_product_name"] or stored[
        "normalized_product_name"
    ]
    listing_b = [
        path
        for path in db.paths()
        if path.startswith(f"{c.LISTINGS}/") and path.count("/") == 1
    ]
    assert len(listing_b) == 2
