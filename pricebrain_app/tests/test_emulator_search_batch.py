"""Firestore Emulator — bounded 11번가 search batch E2E (V2 Phase 3)."""

from __future__ import annotations

import json
import pathlib
import uuid
from datetime import datetime, timezone

from pricebrain_app.crawler.parser.elevenst_search import parse_elevenst_search_json
from pricebrain_app.firebase.admin import get_firestore_client
from pricebrain_app.repository import constants as c
from pricebrain_app.search_batch import (
    MAX_SEARCH_LIMIT,
    SearchItemStatus,
    run_search_batch,
)
from pricebrain_app.tests.counting_firestore import CountingFirestoreClient
from pricebrain_app.tests.emulator_utils import emulator_env, requires_emulator

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "elevenst"
CRAWLED_AT = datetime(2026, 8, 26, 11, 0, 0, tzinfo=timezone.utc)


def _items(name: str, *, suffix: str):
    """Load fixture items, re-keyed per test run so reruns stay independent."""
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    items = parse_elevenst_search_json(payload, crawled_at=CRAWLED_AT)
    rekeyed = []
    for index, item in enumerate(items):
        product_id = f"93{suffix}{index:02d}"
        rekeyed.append(
            dict(
                item,
                product_id=product_id,
                product_url=f"https://www.11st.co.kr/products/{product_id}",
            )
        )
    return rekeyed


def _source(*pages):
    def search_page(_query: str, page: int):
        return pages[page - 1] if 1 <= page <= len(pages) else []

    return search_page


def _no_sleep(_seconds: float) -> None:
    return None


@requires_emulator
def test_phase3_emulator_dry_run_writes_nothing() -> None:
    """Dry-run against a real Firestore client must produce zero writes."""
    suffix = uuid.uuid4().hex[:6]
    with emulator_env():
        counting = CountingFirestoreClient(get_firestore_client(), block_writes=True)
        _results, summary = run_search_batch(
            query="RTX 5070",
            search_page=_source(_items("search_rtx.json", suffix=suffix)),
            db=counting,
            limit=MAX_SEARCH_LIMIT,
            dry_run=True,
        )

        assert counting.writes == 0
        assert counting.write_paths == []
        assert counting.reads > 0
        assert summary.persisted == 0
        assert summary.persist_candidates >= 1
        assert summary.quarantined >= 1


@requires_emulator
def test_phase3_emulator_live_batch_classifies_and_persists() -> None:
    """Live bounded batch: known models persist, unknown models quarantine."""
    suffix = uuid.uuid4().hex[:6]
    with emulator_env():
        db = get_firestore_client()
        for slug in ("rtx_4070", "rx_9070_xt"):
            db.collection(c.PENDING_GPU_MODELS).document(slug).delete()

        counting = CountingFirestoreClient(db)
        results, summary = run_search_batch(
            query="RTX 5070",
            search_page=_source(_items("search_rtx.json", suffix=suffix)),
            db=counting,
            limit=MAX_SEARCH_LIMIT,
            dry_run=False,
        )

        assert summary.persisted == 4
        assert summary.quarantined == 2
        assert summary.validation_failed == 0
        assert summary.irrelevant == 2
        assert summary.failed == 0
        assert counting.writes > 0

        persisted = [r for r in results if r.status is SearchItemStatus.PERSISTED]
        for item in persisted:
            assert db.collection(c.LISTINGS).document(item.listing_id).get().exists

        for slug in ("rtx_4070", "rx_9070_xt"):
            pending = db.collection(c.PENDING_GPU_MODELS).document(slug).get()
            assert pending.exists
            assert pending.to_dict()["status"] == "PENDING_REVIEW"
            # No automatic promotion into master.
            assert not db.collection(c.GPU_MODELS).document(slug).get().exists

        for item in results:
            if item.status in (
                SearchItemStatus.VALIDATION_FAILED,
                SearchItemStatus.IRRELEVANT,
            ):
                listing_id = f"ELEVENST_{item.external_product_id}"
                assert not db.collection(c.LISTINGS).document(listing_id).get().exists

        for slug in ("rtx_4070", "rx_9070_xt"):
            db.collection(c.PENDING_GPU_MODELS).document(slug).delete()


@requires_emulator
def test_phase3_emulator_pagination_dedupes_repeated_product() -> None:
    """Page 2 repeating a page 1 product must not create a second listing."""
    suffix = uuid.uuid4().hex[:6]
    with emulator_env():
        db = get_firestore_client()
        page1 = _items("search_rtx.json", suffix=suffix)
        page2 = [page1[0], *_items("search_rtx_p2.json", suffix=f"{suffix}b")]

        _results, summary = run_search_batch(
            query="RTX 5070",
            search_page=_source(page1, page2),
            db=db,
            limit=MAX_SEARCH_LIMIT,
            pages=2,
            dry_run=False,
            sleep_func=_no_sleep,
        )

        assert summary.search_api_calls == 2
        assert summary.duplicates_skipped == 1
        assert summary.collected == len(page1) + len(page2)
        assert summary.processed == summary.collected - 1


@requires_emulator
def test_phase3_emulator_same_product_two_queries_keeps_one_identity() -> None:
    """Product identity must survive being discovered by a second query."""
    suffix = uuid.uuid4().hex[:6]
    with emulator_env():
        db = get_firestore_client()
        items = _items("search_rtx.json", suffix=suffix)

        first, _ = run_search_batch(
            query="RTX 5070",
            search_page=_source(items),
            db=db,
            limit=MAX_SEARCH_LIMIT,
            dry_run=False,
        )
        second, _ = run_search_batch(
            query="지포스 RTX",
            search_page=_source(items),
            db=db,
            limit=MAX_SEARCH_LIMIT,
            dry_run=False,
        )

        first_ids = {
            r.external_product_id: (r.canonical_product_id, r.listing_id)
            for r in first
            if r.status is SearchItemStatus.PERSISTED
        }
        second_ids = {
            r.external_product_id: (r.canonical_product_id, r.listing_id)
            for r in second
            if r.status is SearchItemStatus.PERSISTED
        }

        assert first_ids
        assert first_ids == second_ids


@requires_emulator
def test_phase3_emulator_one_bad_item_does_not_abort_the_batch() -> None:
    """Phase 2.5 P2 regression guard, exercised against a real client."""
    suffix = uuid.uuid4().hex[:6]

    class Exploding:
        def __str__(self) -> str:
            raise RuntimeError("synthetic emulator item failure")

    with emulator_env():
        db = get_firestore_client()
        items = _items("search_rtx.json", suffix=suffix)
        broken = dict(items[0], product_id=f"94{suffix}00", product_name=Exploding())

        _results, summary = run_search_batch(
            query="RTX 5070",
            search_page=_source([broken, *items]),
            db=db,
            limit=MAX_SEARCH_LIMIT,
            dry_run=False,
        )

        assert summary.failed == 1
        assert summary.processed == len(items) + 1
        assert summary.persisted == 4
        assert summary.quarantined == 2


@requires_emulator
def test_r1_emulator_korean_partner_unknown_model_quarantines() -> None:
    """한글 partner + unknown model must quarantine, never auto-promote."""
    suffix = uuid.uuid4().hex[:6]
    product_id = f"95{suffix}01"
    slug = "rtx_4070"
    with emulator_env():
        db = get_firestore_client()
        db.collection(c.PENDING_GPU_MODELS).document(slug).delete()

        item = {
            "mall": "ELEVENST",
            "product_id": product_id,
            "product_name": "기가바이트 지포스 RTX 4070 GAMING OC D6X 12GB",
            "price": 899_000,
            "seller": "테스트셀러",
            "product_url": f"https://www.11st.co.kr/products/{product_id}",
            "crawled_at": CRAWLED_AT,
        }
        results, summary = run_search_batch(
            query="RTX 4070",
            search_page=_source([item]),
            db=db,
            limit=MAX_SEARCH_LIMIT,
            dry_run=False,
        )

        assert summary.quarantined == 1
        assert results[0].status is SearchItemStatus.QUARANTINED
        assert results[0].gpu_model_id == slug
        assert results[0].board_partner_id == "GIGABYTE"

        pending = db.collection(c.PENDING_GPU_MODELS).document(slug).get()
        assert pending.exists
        assert not db.collection(c.GPU_MODELS).document(slug).get().exists
        assert not db.collection(c.LISTINGS).document(f"ELEVENST_{product_id}").get().exists

        db.collection(c.PENDING_GPU_MODELS).document(slug).delete()


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


def _live_equivalent(status: SearchItemStatus) -> SearchItemStatus:
    if status is SearchItemStatus.PERSIST_CANDIDATE:
        return SearchItemStatus.PERSISTED
    return status


@requires_emulator
def test_phase6_emulator_mixed_batch_item_isolation() -> None:
    suffix = uuid.uuid4().hex[:6]
    with emulator_env():
        db = get_firestore_client()
        for slug in ("rtx_4070",):
            db.collection(c.PENDING_GPU_MODELS).document(slug).delete()

        page = [
            _item(f"96{suffix}01", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB"),
            _item(f"96{suffix}02", "MSI 지포스 RTX 4070 벤투스 3X D6X 12GB"),
            _item(f"96{suffix}03", "이엠텍 지포스 RTX 5070 MIRACLE WHITE D7 12GB"),
            _item(
                f"96{suffix}04",
                "라이젠7 7800X3D RTX5070_12GB RAM_32GB SSD_1TB 조립PC",
            ),
            _item(f"96{suffix}01", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB"),
            _item(f"96{suffix}05", "ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB"),
        ]
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

        for item in results:
            if item.status is SearchItemStatus.PERSISTED:
                assert db.collection(c.LISTINGS).document(item.listing_id).get().exists
                product = db.collection(c.PRODUCTS).document(item.canonical_product_id).get()
                assert product.exists
            elif item.status is SearchItemStatus.QUARANTINED:
                assert db.collection(c.PENDING_GPU_MODELS).document("rtx_4070").get().exists
            else:
                listing_id = f"ELEVENST_{item.external_product_id}"
                assert not db.collection(c.LISTINGS).document(listing_id).get().exists

        db.collection(c.PENDING_GPU_MODELS).document("rtx_4070").delete()


@requires_emulator
def test_phase6_emulator_dry_run_live_classification_match() -> None:
    suffix = uuid.uuid4().hex[:6]
    with emulator_env():
        db = get_firestore_client()
        page = _items("search_rtx.json", suffix=suffix)

        dry_results, dry_summary = run_search_batch(
            query="RTX 5070",
            search_page=_source(page),
            db=db,
            limit=MAX_SEARCH_LIMIT,
            dry_run=True,
        )

        live_db = get_firestore_client()
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


@requires_emulator
def test_phase6_emulator_known_gpu_writes_price_history() -> None:
    suffix = uuid.uuid4().hex[:6]
    product_id = f"97{suffix}01"
    with emulator_env():
        db = get_firestore_client()
        item = _item(product_id, "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")
        results, _summary = run_search_batch(
            query="RTX 5070",
            search_page=_source([item]),
            db=db,
            limit=1,
            dry_run=False,
        )
        listing_id = results[0].listing_id
        history = list(
            db.collection(c.LISTINGS)
            .document(listing_id)
            .collection(c.PRICE_HISTORY)
            .stream()
        )
        assert len(history) == 1
        assert history[0].to_dict()["price"] == item["price"]

