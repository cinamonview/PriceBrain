"""Firestore Emulator E2E — Pipeline → Repository → Firestore (Gate B-2C)."""

from __future__ import annotations

from datetime import datetime, timezone

import uuid

import pytest

from pricebrain_app.firebase.admin import get_firestore_client
from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.listing_repository import build_price_history_document_id
from pricebrain_app.repository.service import save_validated_product
from pricebrain_app.tests.emulator_utils import emulator_env, requires_emulator


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
        "crawled_at": datetime(2026, 8, 19, 10, 0, 0, tzinfo=timezone.utc),
    }


@pytest.fixture
def dedup_raw_product() -> dict:
    product_id = f"e2e{uuid.uuid4().hex[:12]}"
    return {
        "mall": "SSG",
        "product_id": product_id,
        "product_name": "HIT ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB",
        "price": 2429000,
        "seller": "히트정보",
        "product_url": f"https://www.ssg.com/item/itemView.ssg?itemId={product_id}",
        "image_url": f"https://sitem.ssgcdn.com/itemimage/{product_id}.jpg",
        "crawled_at": datetime(2026, 8, 19, 10, 0, 0, tzinfo=timezone.utc),
    }


def _history_count(db, listing_id: str) -> int:
    ref = (
        db.collection(c.LISTINGS)
        .document(listing_id)
        .collection(c.PRICE_HISTORY)
    )
    return sum(1 for _ in ref.stream())


@requires_emulator
def test_emulator_pipeline_repository_persist(sample_raw_product: dict) -> None:
    with emulator_env():
        validated = run_pipeline(sample_raw_product)
        db = get_firestore_client()
        result = save_validated_product(db, dict(validated))

        product_id = result["product_id"]
        listing_id = result["listing_id"]
        assert product_id == "ZOTAC-RTX5080-SOLIDCORE-16GB"
        assert listing_id == "SSG_1000832367906"

        product_doc = db.collection(c.PRODUCTS).document(product_id).get()
        assert product_doc.exists
        product_data = product_doc.to_dict()
        assert product_data is not None
        assert product_data["gpu_model_id"] == "rtx_5080"
        assert product_data["vram_gb"] == 16
        assert product_data["brand"] == "ZOTAC"

        listing_doc = db.collection(c.LISTINGS).document(listing_id).get()
        assert listing_doc.exists
        listing_data = listing_doc.to_dict()
        assert listing_data is not None
        assert listing_data["product_id"] == product_id
        assert listing_data["mall_id"] == "SSG"
        assert listing_data["external_product_id"] == "1000832367906"
        assert listing_data["current_price"] == 2429000

        history_id = build_price_history_document_id(
            int(sample_raw_product["crawled_at"].timestamp() * 1000)
        )
        history_doc = (
            db.collection(c.LISTINGS)
            .document(listing_id)
            .collection(c.PRICE_HISTORY)
            .document(history_id)
            .get()
        )
        assert history_doc.exists
        history_data = history_doc.to_dict()
        assert history_data is not None
        assert history_data["price"] == 2429000


@requires_emulator
def test_emulator_price_history_dedup_and_append(dedup_raw_product: dict) -> None:
    with emulator_env():
        validated = dict(run_pipeline(dedup_raw_product))
        db = get_firestore_client()

        first = save_validated_product(db, validated)
        listing_id = str(first["listing_id"])
        assert listing_id.startswith("SSG_e2e")
        first_count = _history_count(db, listing_id)
        assert first_count >= 1
        assert first["price_history_appended"] is True

        second = save_validated_product(db, validated)
        assert second["price_history_appended"] is False
        assert _history_count(db, listing_id) == first_count

        changed = dict(validated)
        changed["price"] = 2399000
        changed["crawled_at"] = datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc)
        third = save_validated_product(db, changed)
        assert third["price_history_appended"] is True
        assert _history_count(db, listing_id) == first_count + 1

        listing_doc = db.collection(c.LISTINGS).document(listing_id).get()
        assert int(listing_doc.to_dict()["current_price"]) == 2399000
