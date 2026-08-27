"""Phase 6 — Search Batch persist dry-run & emulator persist gate tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pricebrain_app.repository import constants as c
from pricebrain_app.repository.gpu_master_seed import seed_gpu_master
from pricebrain_app.repository.listing_repository import build_listing_document_id
from pricebrain_app.search_batch import (
    MAX_SEARCH_LIMIT,
    SearchItemStatus,
    run_search_batch,
)
from pricebrain_app.tests.counting_firestore import CountingFirestoreClient
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

CRAWLED_AT = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)


def _live_equivalent(dry_status: SearchItemStatus) -> SearchItemStatus:
    if dry_status is SearchItemStatus.PERSIST_CANDIDATE:
        return SearchItemStatus.PERSISTED
    return dry_status


@pytest.fixture
def db() -> FakeFirestoreClient:
    client = FakeFirestoreClient()
    seed_gpu_master(client)
    return client


def _item(
    product_id: str,
    product_name: str,
    *,
    price: int = 1_259_000,
    seller: str = "테스트셀러",
) -> dict:
    return {
        "mall": "ELEVENST",
        "product_id": product_id,
        "product_name": product_name,
        "price": price,
        "seller": seller,
        "product_url": f"https://www.11st.co.kr/products/{product_id}",
        "crawled_at": CRAWLED_AT,
    }


def _source(*pages):
    def search_page(_query: str, page: int):
        return pages[page - 1] if 1 <= page <= len(pages) else []

    return search_page


def _no_sleep(_seconds: float) -> None:
    return None


def test_phase6_mixed_batch_item_isolation(db: FakeFirestoreClient) -> None:
    """Known → quarantine → validation → irrelevant → duplicate skip → known."""
    known1 = _item("9600000001", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")
    unknown = _item("9600000002", "MSI 지포스 RTX 4070 벤투스 3X D6X 12GB")
    validation_fail = _item(
        "9600000003", "이엠텍 지포스 RTX 5070 MIRACLE WHITE D7 12GB"
    )
    irrelevant = _item(
        "9600000004",
        "라이젠7 7800X3D RTX5070_12GB RAM_32GB SSD_1TB 조립PC 게이밍 컴퓨터",
    )
    duplicate = dict(known1)
    known2 = _item("9600000005", "MSI 지포스 RTX 5070 Ti 게이밍 트리오 OC D7 16GB")

    page = [known1, unknown, validation_fail, irrelevant, duplicate, known2]
    results, summary = run_search_batch(
        query="RTX 5070",
        search_page=_source(page),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=False,
    )

    assert summary.duplicates_skipped == 1
    assert summary.processed == 5
    assert [r.status for r in results] == [
        SearchItemStatus.PERSISTED,
        SearchItemStatus.QUARANTINED,
        SearchItemStatus.VALIDATION_FAILED,
        SearchItemStatus.IRRELEVANT,
        SearchItemStatus.PERSISTED,
    ]
    assert summary.persisted == 2
    assert summary.quarantined == 1
    assert summary.validation_failed == 1
    assert summary.irrelevant == 1
    assert summary.failed == 0


def test_phase6_dry_run_live_classification_equivalence(db: FakeFirestoreClient) -> None:
    """PERSIST_CANDIDATE (dry) must mirror PERSISTED (live) for the same inputs."""
    known1 = _item("9610000001", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")
    unknown = _item("9610000002", "MSI 지포스 RTX 4070 벤투스 3X D6X 12GB")
    validation_fail = _item(
        "9610000003", "이엠텍 지포스 RTX 5070 MIRACLE WHITE D7 12GB"
    )
    irrelevant = _item(
        "9610000004",
        "라이젠7 7800X3D RTX5070_12GB RAM_32GB SSD_1TB 조립PC",
    )
    known2 = _item("9610000005", "ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB")
    page = [known1, unknown, validation_fail, irrelevant, known2]

    dry_db = FakeFirestoreClient()
    seed_gpu_master(dry_db)
    dry_results, dry_summary = run_search_batch(
        query="RTX 5070",
        search_page=_source(page),
        db=dry_db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=True,
    )

    live_db = FakeFirestoreClient()
    seed_gpu_master(live_db)
    live_results, live_summary = run_search_batch(
        query="RTX 5070",
        search_page=_source(page),
        db=live_db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=False,
    )

    assert dry_summary.persist_candidates == live_summary.persisted
    assert dry_summary.quarantined == live_summary.quarantined
    assert dry_summary.validation_failed == live_summary.validation_failed
    assert dry_summary.irrelevant == live_summary.irrelevant

    for dry_item, live_item in zip(dry_results, live_results, strict=True):
        assert dry_item.external_product_id == live_item.external_product_id
        assert _live_equivalent(dry_item.status) == live_item.status
        assert dry_item.gpu_model_id == live_item.gpu_model_id
        assert dry_item.board_partner_id == live_item.board_partner_id
        assert dry_item.canonical_product_id == live_item.canonical_product_id


def test_phase6_known_gpu_data_integrity(db: FakeFirestoreClient) -> None:
    product_id = "9620000001"
    raw = _item(product_id, "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")
    results, _summary = run_search_batch(
        query="RTX 5070",
        search_page=_source([raw]),
        db=db,
        limit=1,
        dry_run=False,
    )
    item = results[0]
    assert item.status is SearchItemStatus.PERSISTED
    assert item.canonical_product_id
    assert item.listing_id

    product = db.get_document(f"{c.PRODUCTS}/{item.canonical_product_id}")
    assert product is not None
    assert product["canonical_product_id"] == item.canonical_product_id
    assert product["gpu_model_id"] == "rtx_5070"
    assert product["board_partner_id"] == "GIGABYTE"

    listing_id = build_listing_document_id("ELEVENST", product_id)
    assert item.listing_id == listing_id
    listing = db.get_document(f"{c.LISTINGS}/{listing_id}")
    assert listing is not None
    assert listing["product_id"] == item.canonical_product_id
    assert listing["mall_id"] == "ELEVENST"
    assert listing["external_product_id"] == product_id
    assert listing["seller_id"]
    assert listing["current_price"] == raw["price"]
    assert listing["product_url"] == raw["product_url"]
    assert listing["availability"] is True
    assert listing["crawled_at"] == CRAWLED_AT

    history_paths = [
        p
        for p in db.paths()
        if p.startswith(f"{c.LISTINGS}/{listing_id}/{c.PRICE_HISTORY}/")
    ]
    assert len(history_paths) == 1
    history = db.get_document(history_paths[0])
    assert history is not None
    assert history["price"] == raw["price"]
    assert history["crawled_at"] == CRAWLED_AT


def test_phase6_repeated_persist_keeps_one_product_and_listing(db: FakeFirestoreClient) -> None:
    raw = _item("9620000002", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")
    first, _ = run_search_batch(
        query="RTX 5070",
        search_page=_source([raw]),
        db=db,
        limit=1,
        dry_run=False,
    )
    products_after_first = [p for p in db.paths() if p.startswith(f"{c.PRODUCTS}/")]
    listings_after_first = [p for p in db.paths() if p.startswith(f"{c.LISTINGS}/")]

    second, _ = run_search_batch(
        query="지포스 RTX",
        search_page=_source([raw]),
        db=db,
        limit=1,
        dry_run=False,
    )

    assert first[0].canonical_product_id == second[0].canonical_product_id
    assert first[0].listing_id == second[0].listing_id
    assert products_after_first == [p for p in db.paths() if p.startswith(f"{c.PRODUCTS}/")]
    assert listings_after_first == [p for p in db.paths() if p.startswith(f"{c.LISTINGS}/")]


def test_phase6_unknown_gpu_ten_sightings_one_pending_document(
    db: FakeFirestoreClient,
) -> None:
    items = [
        _item(
            f"963000000{index}",
            "MSI 지포스 RTX 4070 벤투스 3X D6X 12GB",
            seller=f"seller-{index}",
        )
        for index in range(10)
    ]
    _results, summary = run_search_batch(
        query="RTX 4070",
        search_page=_source(items),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=False,
    )

    assert summary.quarantined == 10
    pending = db.get_document(f"{c.PENDING_GPU_MODELS}/rtx_4070")
    assert pending is not None
    assert pending["seen_count"] == 10
    assert pending["status"] == "PENDING_REVIEW"
    assert "elevenst" in pending["source_malls"]
    assert db.get_document(f"{c.GPU_MODELS}/rtx_4070") is None
    listing_paths = [p for p in db.paths() if p.startswith(f"{c.LISTINGS}/")]
    product_paths = [p for p in db.paths() if p.startswith(f"{c.PRODUCTS}/")]
    assert listing_paths == []
    assert product_paths == []


def test_phase6_dry_run_blocks_all_writes(db: FakeFirestoreClient) -> None:
    counting = CountingFirestoreClient(db, block_writes=True)
    _results, summary = run_search_batch(
        query="RTX 5070",
        search_page=_source(
            [
                _item("9640000001", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB"),
                _item("9640000002", "MSI 지포스 RTX 4070 벤투스 3X D6X 12GB"),
            ]
        ),
        db=counting,
        limit=MAX_SEARCH_LIMIT,
        dry_run=True,
    )

    assert counting.writes == 0
    assert counting.write_paths == []
    assert summary.persisted == 0
    assert summary.persist_candidates >= 1
    assert summary.quarantined >= 1
    assert [p for p in db.paths() if p.startswith(f"{c.PENDING_GPU_MODELS}/")] == []


def test_phase6_irrelevant_and_validation_leave_no_persist_artifacts(
    db: FakeFirestoreClient,
) -> None:
    page = [
        _item("9650000001", "라이젠7 7800X3D RTX5070 조립PC"),
        _item("9650000002", "이엠텍 지포스 RTX 5070 MIRACLE WHITE D7 12GB"),
    ]
    results, summary = run_search_batch(
        query="RTX 5070",
        search_page=_source(page),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=False,
    )

    assert summary.irrelevant == 1
    assert summary.validation_failed == 1
    assert summary.persisted == 0
    assert results[0].status is SearchItemStatus.IRRELEVANT
    assert results[1].status is SearchItemStatus.VALIDATION_FAILED
    assert [p for p in db.paths() if p.startswith(f"{c.PRODUCTS}/")] == []
    assert [p for p in db.paths() if p.startswith(f"{c.LISTINGS}/")] == []
    assert [p for p in db.paths() if p.startswith(f"{c.PENDING_GPU_MODELS}/")] == []
