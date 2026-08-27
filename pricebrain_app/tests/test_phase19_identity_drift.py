"""Phase 19 — classify top-level identity field usage (no policy change)."""

from __future__ import annotations

from datetime import datetime, timezone

from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.gpu_master_seed import seed_gpu_master
from pricebrain_app.repository.persist_service import persist_validated_product
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

CRAWLED_AT = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)


def test_phase19_top_level_name_is_not_authoritative_vs_snapshot() -> None:
    """listing.normalized_product_name is DISPLAY_ONLY; snapshot is AUTHORITATIVE for review."""
    db = FakeFirestoreClient()
    seed_gpu_master(db)
    first = {
        "mall": "ELEVENST",
        "product_id": "1940000001",
        "product_name": "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
        "price": 1_500_000,
        "seller": "A셀러",
        "product_url": "https://www.11st.co.kr/products/1940000001",
        "crawled_at": CRAWLED_AT,
    }
    persist_validated_product(
        db,
        dict(run_pipeline(dict(first))),
        external_product_id="1940000001",
        product_name=first["product_name"],
    )
    product_id = "ZOTAC-RTX5080-SOLIDOC-16GB"
    original = db.collection(c.PRODUCTS).document(product_id).get().to_dict()
    second = {
        **first,
        "product_id": "1940000002",
        "product_name": "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB 피씨디렉트",
        "seller": "B셀러",
        "product_url": "https://www.11st.co.kr/products/1940000002",
    }
    persist_validated_product(
        db,
        dict(run_pipeline(dict(second))),
        external_product_id="1940000002",
        product_name=second["product_name"],
    )
    stored = db.collection(c.PRODUCTS).document(product_id).get().to_dict()
    assert stored["identity_snapshot"] == original["identity_snapshot"]
    assert stored["vram_gb"] == original["vram_gb"]
    assert stored["board_partner_id"] == original["board_partner_id"]
    assert stored["gpu_model_id"] == original["gpu_model_id"]
    assert stored["identity_snapshot"]["normalized_product_name"] == original[
        "identity_snapshot"
    ]["normalized_product_name"]
