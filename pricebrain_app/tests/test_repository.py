from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository.exceptions import RepositoryValidationError
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.listing_repository import (
    ListingRepository,
    build_listing_document_id,
    build_price_history_document_id,
)
from pricebrain_app.repository.price_history_repository import PriceHistoryRepository
from pricebrain_app.repository.product_repository import ProductRepository
from pricebrain_app.repository._testing.persist_helpers import save_validated_product
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient


def _history_count(fake_db: FakeFirestoreClient, listing_id: str) -> int:
    prefix = f"{c.LISTINGS}/{listing_id}/{c.PRICE_HISTORY}/"
    return sum(1 for path in fake_db.paths() if path.startswith(prefix))


def _latest_history_price(fake_db: FakeFirestoreClient, listing_id: str) -> int | None:
    prefix = f"{c.LISTINGS}/{listing_id}/{c.PRICE_HISTORY}/"
    latest_price: int | None = None
    latest_crawled_at: datetime | None = None
    for path in fake_db.paths():
        if not path.startswith(prefix):
            continue
        data = fake_db.get_document(path)
        if not data or data.get("price") is None or data.get("crawled_at") is None:
            continue
        crawled_at = data["crawled_at"]
        if latest_crawled_at is None or crawled_at > latest_crawled_at:
            latest_crawled_at = crawled_at
            latest_price = int(data["price"])
    return latest_price


@pytest.fixture
def c1_validated_product() -> dict:
    product_id = f"c1{uuid.uuid4().hex[:10]}"
    raw = {
        "mall": "SSG",
        "product_id": product_id,
        "product_name": "HIT ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB",
        "price": 100000,
        "seller": "히트정보",
        "product_url": f"https://www.ssg.com/item/itemView.ssg?itemId={product_id}",
        "image_url": f"https://sitem.ssgcdn.com/itemimage/{product_id}.jpg",
        "crawled_at": datetime(2026, 8, 19, 10, 0, 0, tzinfo=timezone.utc),
    }
    return dict(run_pipeline(raw))

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
def validated_product(sample_raw_product: dict) -> dict:
    return dict(run_pipeline(sample_raw_product))


def test_listing_document_id() -> None:
    assert build_listing_document_id("SSG", "1000832367906") == "SSG_1000832367906"


def test_price_history_document_id() -> None:
    assert build_price_history_document_id(1724047200000) == "1724047200000"


def test_product_upsert(fake_db: FakeFirestoreClient, validated_product: dict) -> None:
    repo = ProductRepository(fake_db)
    product_id = repo.upsert_from_validated(validated_product)
    assert product_id == "ZOTAC-RTX5080-SOLIDCORE-16GB"
    stored = fake_db.get_document(f"{c.PRODUCTS}/{product_id}")
    assert stored is not None
    assert stored["gpu_model_id"] == "rtx_5080"
    assert stored["vram_gb"] == 16


def test_listing_upsert(fake_db: FakeFirestoreClient, validated_product: dict) -> None:
    product_repo = ProductRepository(fake_db)
    listing_repo = ListingRepository(fake_db)
    canonical_id = product_repo.upsert_from_validated(validated_product)
    listing_id = listing_repo.upsert_from_validated(validated_product, canonical_id)
    assert listing_id == "SSG_1000832367906"
    stored = fake_db.get_document(f"{c.LISTINGS}/{listing_id}")
    assert stored is not None
    assert stored["product_id"] == canonical_id
    assert stored["current_price"] == 2429000


def test_price_history_append(fake_db: FakeFirestoreClient, validated_product: dict) -> None:
    product_repo = ProductRepository(fake_db)
    listing_repo = ListingRepository(fake_db)
    history_repo = PriceHistoryRepository(fake_db)
    canonical_id = product_repo.upsert_from_validated(validated_product)
    listing_id = listing_repo.upsert_from_validated(validated_product, canonical_id)
    crawled_at = validated_product["crawled_at"]
    appended = history_repo.append_if_changed(listing_id, 2429000, crawled_at)
    assert appended is True
    history_id = build_price_history_document_id(int(crawled_at.timestamp() * 1000))
    history_path = f"{c.LISTINGS}/{listing_id}/{c.PRICE_HISTORY}/{history_id}"
    assert fake_db.get_document(history_path) is not None


def test_save_validated_product(fake_db: FakeFirestoreClient, validated_product: dict) -> None:
    result = save_validated_product(fake_db, validated_product)
    assert result["product_id"] == "ZOTAC-RTX5080-SOLIDCORE-16GB"
    assert result["listing_id"] == "SSG_1000832367906"
    assert result["price_history_appended"] is True
    assert fake_db.get_document(f"{c.MALLS}/SSG") is not None
    assert fake_db.get_document(f"{c.BOARD_PARTNERS}/ZOTAC") is not None
    assert fake_db.get_document(f"{c.GPU_MODELS}/rtx_5080") is not None


def test_missing_reference_raises_for_seller_id(
    fake_db: FakeFirestoreClient,
    validated_product: dict,
) -> None:
    validated_product.pop("seller_id")
    with pytest.raises(RepositoryValidationError, match="seller_id"):
        save_validated_product(fake_db, validated_product)


def test_invalid_validated_product(fake_db: FakeFirestoreClient, validated_product: dict) -> None:
    validated_product.pop("canonical_product_id")
    with pytest.raises(RepositoryValidationError, match="canonical_product_id"):
        save_validated_product(fake_db, validated_product)


def test_repository_does_not_modify_pipeline(validated_product: dict) -> None:
    original = dict(validated_product)
    from pricebrain_app.repository.gpu_master_seed import seed_gpu_master

    fake_db = FakeFirestoreClient()
    seed_gpu_master(fake_db)
    save_validated_product(fake_db, validated_product)
    assert validated_product == original


def test_c1_01_first_ingest_appends_history(
    fake_db: FakeFirestoreClient, c1_validated_product: dict
) -> None:
    result = save_validated_product(fake_db, c1_validated_product)
    listing_id = str(result["listing_id"])
    assert result["price_history_appended"] is True
    assert _history_count(fake_db, listing_id) == 1
    assert _latest_history_price(fake_db, listing_id) == 100000


def test_c1_02_same_price_reingest_skips_history(
    fake_db: FakeFirestoreClient, c1_validated_product: dict
) -> None:
    first = save_validated_product(fake_db, c1_validated_product)
    listing_id = str(first["listing_id"])
    assert _history_count(fake_db, listing_id) == 1

    second = save_validated_product(fake_db, dict(c1_validated_product))
    assert second["price_history_appended"] is False
    assert _history_count(fake_db, listing_id) == 1


def test_c1_03_price_change_reingest_appends_history(
    fake_db: FakeFirestoreClient, c1_validated_product: dict
) -> None:
    first = save_validated_product(fake_db, c1_validated_product)
    listing_id = str(first["listing_id"])

    changed = dict(c1_validated_product)
    changed["price"] = 110000
    changed["crawled_at"] = datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc)
    second = save_validated_product(fake_db, changed)

    assert second["price_history_appended"] is True
    assert _history_count(fake_db, listing_id) == 2
    assert _latest_history_price(fake_db, listing_id) == 110000


def test_c1_04_same_price_after_change_reingest_skips_history(
    fake_db: FakeFirestoreClient, c1_validated_product: dict
) -> None:
    save_validated_product(fake_db, c1_validated_product)
    changed = dict(c1_validated_product)
    changed["price"] = 110000
    changed["crawled_at"] = datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc)
    second = save_validated_product(fake_db, changed)
    listing_id = str(second["listing_id"])
    assert _history_count(fake_db, listing_id) == 2

    repeat = dict(changed)
    repeat["crawled_at"] = datetime(2026, 8, 21, 10, 0, 0, tzinfo=timezone.utc)
    third = save_validated_product(fake_db, repeat)
    assert third["price_history_appended"] is False
    assert _history_count(fake_db, listing_id) == 2


def test_c1_05_save_validated_product_full_flow_price_change(
    fake_db: FakeFirestoreClient, c1_validated_product: dict
) -> None:
    """C1-05: save_validated_product() listing upsert + price_history full path."""
    first = save_validated_product(fake_db, c1_validated_product)
    listing_id = str(first["listing_id"])
    assert first["price_history_appended"] is True
    assert fake_db.get_document(f"{c.LISTINGS}/{listing_id}")["current_price"] == 100000

    changed = dict(c1_validated_product)
    changed["price"] = 110000
    changed["crawled_at"] = datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc)
    second = save_validated_product(fake_db, changed)

    assert second["price_history_appended"] is True
    assert _history_count(fake_db, listing_id) == 2
    listing = fake_db.get_document(f"{c.LISTINGS}/{listing_id}")
    assert listing is not None
    assert int(listing["current_price"]) == 110000
    assert _latest_history_price(fake_db, listing_id) == 110000


def test_c1_float_price_normalization_dedup(
    fake_db: FakeFirestoreClient, c1_validated_product: dict
) -> None:
    first = save_validated_product(fake_db, c1_validated_product)
    listing_id = str(first["listing_id"])
    listing_path = f"{c.LISTINGS}/{listing_id}"
    listing = fake_db.get_document(listing_path)
    assert listing is not None
    listing["current_price"] = 100000.0
    fake_db._data[listing_path] = listing

    second = save_validated_product(fake_db, dict(c1_validated_product))
    assert second["price_history_appended"] is False
    assert _history_count(fake_db, listing_id) == 1
