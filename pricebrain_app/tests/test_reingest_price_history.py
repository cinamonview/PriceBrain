"""Re-ingest and price history verification — ZOTAC test-rtx5080-001 scenario."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository import constants as c
from pricebrain_app.repository._testing.persist_helpers import save_validated_product
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient
from pricebrain_app.tests.test_repository import (
    _history_count,
    _latest_history_price,
)


CANONICAL_PRODUCT_ID = "ZOTAC-RTX5080-16GB"
LISTING_ID = "SSG_test-rtx5080-001"


def _zotac_raw(
    *,
    price: int = 1_599_000,
    crawled_at: datetime | None = None,
) -> dict:
    raw = {
        "product_id": "test-rtx5080-001",
        "product_name": "ZOTAC GAMING GeForce RTX 5080 16GB",
        "mall_id": "ssg",
        "product_url": "https://example.com/products/test-rtx5080",
        "price": price,
        "seller": "PriceBrain Test",
    }
    if crawled_at is not None:
        raw["crawled_at"] = crawled_at
    return raw


def _product_count(fake_db: FakeFirestoreClient) -> int:
    return sum(1 for path in fake_db.paths() if path.startswith(f"{c.PRODUCTS}/"))


def _listing_count(fake_db: FakeFirestoreClient) -> int:
    return sum(
        1
        for path in fake_db.paths()
        if path.startswith(f"{c.LISTINGS}/") and f"/{c.PRICE_HISTORY}/" not in path
    )


def _validated(
    *,
    price: int = 1_599_000,
    crawled_at: datetime | None = None,
) -> dict:
    return dict(run_pipeline(_zotac_raw(price=price, crawled_at=crawled_at)))


@pytest.fixture
def zotac_db() -> FakeFirestoreClient:
    return FakeFirestoreClient()


def test_same_listing_does_not_create_duplicate_listing(zotac_db: FakeFirestoreClient) -> None:
    crawled_at = datetime(2026, 8, 21, 10, 0, 0, tzinfo=timezone.utc)
    first = save_validated_product(zotac_db, _validated(crawled_at=crawled_at))
    second = save_validated_product(zotac_db, _validated(crawled_at=crawled_at))

    assert first["listing_id"] == LISTING_ID
    assert second["listing_id"] == LISTING_ID
    assert _listing_count(zotac_db) == 1


def test_same_product_does_not_create_duplicate_product(zotac_db: FakeFirestoreClient) -> None:
    crawled_at = datetime(2026, 8, 21, 10, 0, 0, tzinfo=timezone.utc)
    first = save_validated_product(zotac_db, _validated(crawled_at=crawled_at))
    second = save_validated_product(zotac_db, _validated(crawled_at=crawled_at))

    assert first["product_id"] == CANONICAL_PRODUCT_ID
    assert second["product_id"] == CANONICAL_PRODUCT_ID
    assert _product_count(zotac_db) == 1


def test_same_listing_same_price_does_not_append_history(
    zotac_db: FakeFirestoreClient,
) -> None:
    crawled_at = datetime(2026, 8, 21, 10, 0, 0, tzinfo=timezone.utc)
    first = save_validated_product(zotac_db, _validated(price=1_599_000, crawled_at=crawled_at))
    assert first["price_history_appended"] is True
    assert _history_count(zotac_db, LISTING_ID) == 1

    second = save_validated_product(
        zotac_db,
        _validated(price=1_599_000, crawled_at=crawled_at),
    )
    assert second["price_history_appended"] is False
    assert _history_count(zotac_db, LISTING_ID) == 1

    listing = zotac_db.get_document(f"{c.LISTINGS}/{LISTING_ID}")
    assert listing is not None
    assert int(listing["current_price"]) == 1_599_000


def test_same_listing_price_change_appends_history(zotac_db: FakeFirestoreClient) -> None:
    first_crawled = datetime(2026, 8, 21, 10, 0, 0, tzinfo=timezone.utc)
    first = save_validated_product(
        zotac_db,
        _validated(price=1_599_000, crawled_at=first_crawled),
    )
    assert first["price_history_appended"] is True
    assert _history_count(zotac_db, LISTING_ID) == 1

    second_crawled = datetime(2026, 8, 21, 11, 0, 0, tzinfo=timezone.utc)
    second = save_validated_product(
        zotac_db,
        _validated(price=1_549_000, crawled_at=second_crawled),
    )
    assert second["price_history_appended"] is True
    assert second["listing_id"] == LISTING_ID
    assert _history_count(zotac_db, LISTING_ID) == 2
    assert _latest_history_price(zotac_db, LISTING_ID) == 1_549_000

    listing = zotac_db.get_document(f"{c.LISTINGS}/{LISTING_ID}")
    assert listing is not None
    assert int(listing["current_price"]) == 1_549_000

    history_prefix = f"{c.LISTINGS}/{LISTING_ID}/{c.PRICE_HISTORY}/"
    history_prices = {
        int(zotac_db.get_document(path)["price"])
        for path in zotac_db.paths()
        if path.startswith(history_prefix)
    }
    assert history_prices == {1_599_000, 1_549_000}


def test_zotac_swagger_payload_without_crawled_at_skips_price_history(
    zotac_db: FakeFirestoreClient,
) -> None:
    """Matches current Swagger test payload (no crawled_at field)."""
    validated = _validated(price=1_599_000, crawled_at=None)
    result = save_validated_product(zotac_db, validated)

    assert result["price_history_appended"] is False
    assert _history_count(zotac_db, LISTING_ID) == 0
    listing = zotac_db.get_document(f"{c.LISTINGS}/{LISTING_ID}")
    assert listing is not None
    assert int(listing["current_price"]) == 1_599_000

    repeat = save_validated_product(zotac_db, dict(validated))
    assert repeat["price_history_appended"] is False
    assert _history_count(zotac_db, LISTING_ID) == 0
    assert _listing_count(zotac_db) == 1
    assert _product_count(zotac_db) == 1
