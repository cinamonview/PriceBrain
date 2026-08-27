"""Firestore Emulator — Phase 8 identity collision scenarios A–D."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pricebrain_app.firebase.admin import get_firestore_client
from pricebrain_app.repository import constants as c
from pricebrain_app.search_batch import (
    DEFAULT_SEARCH_LIMIT,
    SearchItemStatus,
    run_search_batch,
)
from pricebrain_app.search_observation import (
    fixture_map_for_queries,
    run_multi_query_observation,
)
from pricebrain_app.tests.emulator_utils import emulator_env, requires_emulator

CRAWLED_AT = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)


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


@requires_emulator
def test_phase8_scenario_a_same_product_different_query() -> None:
    suffix = uuid.uuid4().hex[:6]
    with emulator_env():
        db = get_firestore_client()
        listings_before = {doc.id for doc in db.collection(c.LISTINGS).stream()}
        shared = _item(
            f"88{suffix}01",
            "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB",
        )
        fixtures = {"RTX 5070": [shared], "지포스 RTX": [dict(shared)]}
        report = run_multi_query_observation(
            queries=("RTX 5070", "지포스 RTX"),
            search_page_for_query=fixture_map_for_queries(fixtures),
            db=db,
            limit=DEFAULT_SEARCH_LIMIT,
            dry_run=False,
        )

        first_persisted = [
            item
            for item in report.queries[0].results
            if item.status is SearchItemStatus.PERSISTED
        ]
        assert len(first_persisted) == 1
        assert report.aggregate.duplicates_skipped == 1
        assert report.queries[1].summary.processed == 0
        new_listings = {
            doc.id for doc in db.collection(c.LISTINGS).stream()
        } - listings_before
        assert len(new_listings) == 1


@requires_emulator
def test_phase8_scenario_b_same_product_different_sellers() -> None:
    suffix = uuid.uuid4().hex[:6]
    with emulator_env():
        db = get_firestore_client()
        listings_before = {doc.id for doc in db.collection(c.LISTINGS).stream()}
        name = "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB"
        item_a = _item(f"87{suffix}01", name, seller="셀러A")
        item_b = _item(f"87{suffix}02", name, seller="셀러B")

        results, _ = run_search_batch(
            query="RTX 5070",
            search_page=lambda _q, page: [item_a, item_b] if page == 1 else [],
            db=db,
            limit=DEFAULT_SEARCH_LIMIT,
            dry_run=False,
        )
        persisted = [r for r in results if r.status is SearchItemStatus.PERSISTED]
        assert len(persisted) == 2
        assert len({r.canonical_product_id for r in persisted}) == 1
        assert len({r.listing_id for r in persisted}) == 2
        new_listings = {
            doc.id for doc in db.collection(c.LISTINGS).stream()
        } - listings_before
        assert len(new_listings) == 2
        canonical_id = persisted[0].canonical_product_id
        assert db.collection(c.PRODUCTS).document(canonical_id).get().exists


@requires_emulator
def test_phase8_scenario_c_sku_variant_same_canonical_observation() -> None:
    suffix = uuid.uuid4().hex[:6]
    with emulator_env():
        db = get_firestore_client()
        listings_before = {doc.id for doc in db.collection(c.LISTINGS).stream()}
        white = _item(
            f"86{suffix}01",
            "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
        )
        black = _item(
            f"86{suffix}02",
            "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
        )
        results, _ = run_search_batch(
            query="RTX 5080",
            search_page=lambda _q, page: [white, black] if page == 1 else [],
            db=db,
            limit=DEFAULT_SEARCH_LIMIT,
            dry_run=False,
        )
        blocked = [
            r for r in results if r.status is SearchItemStatus.IDENTITY_REVIEW_BLOCKED
        ]
        assert len(blocked) == 2
        canonical_ids = {r.canonical_product_id for r in blocked}
        assert len(canonical_ids) == 1
        assert canonical_ids.pop() == "ZOTAC-RTX5080-SOLIDOC-16GB"
        new_listings = {
            doc.id for doc in db.collection(c.LISTINGS).stream()
        } - listings_before
        assert len(new_listings) == 0


@requires_emulator
def test_phase8_scenario_d_different_board_partner_separate_products() -> None:
    suffix = uuid.uuid4().hex[:6]
    with emulator_env():
        db = get_firestore_client()
        gigabyte = _item(
            f"85{suffix}01",
            "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB",
        )
        manli = _item(
            f"85{suffix}02",
            "MANLI 지포스 RTX 5070 GAMING OC D7 12GB",
        )
        results, _ = run_search_batch(
            query="RTX 5070",
            search_page=lambda _q, page: [gigabyte, manli] if page == 1 else [],
            db=db,
            limit=DEFAULT_SEARCH_LIMIT,
            dry_run=False,
        )
        persisted = [r for r in results if r.status is SearchItemStatus.PERSISTED]
        assert len(persisted) == 2
        canonical_ids = {r.canonical_product_id for r in persisted}
        assert len(canonical_ids) == 2
        assert any("GIGABYTE" in cid for cid in canonical_ids)
        assert any("MANLI" in cid for cid in canonical_ids)
        for cid in canonical_ids:
            assert db.collection(c.PRODUCTS).document(cid).get().exists
