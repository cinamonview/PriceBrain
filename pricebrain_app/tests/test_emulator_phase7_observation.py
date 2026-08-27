"""Firestore Emulator — Phase 7 multi-query observation scenarios."""

from __future__ import annotations

import json
import pathlib
import uuid
from datetime import datetime, timezone

from pricebrain_app.crawler.parser.elevenst_search import parse_elevenst_search_json
from pricebrain_app.firebase.admin import get_firestore_client
from pricebrain_app.repository import constants as c
from pricebrain_app.search_batch import (
    DEFAULT_SEARCH_LIMIT,
    MAX_SEARCH_LIMIT,
    SearchItemStatus,
    run_search_batch,
)
from pricebrain_app.search_observation import (
    fixture_map_for_queries,
    run_multi_query_observation,
)
from pricebrain_app.tests.emulator_utils import emulator_env, requires_emulator

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "elevenst"
CRAWLED_AT = datetime(2026, 8, 26, 11, 0, 0, tzinfo=timezone.utc)


def _items(name: str, *, suffix: str):
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    items = parse_elevenst_search_json(payload, crawled_at=CRAWLED_AT)
    rekeyed = []
    for index, item in enumerate(items):
        product_id = f"98{suffix}{index:02d}"
        rekeyed.append(
            dict(
                item,
                product_id=product_id,
                product_url=f"https://www.11st.co.kr/products/{product_id}",
            )
        )
    return rekeyed


def _item(product_id: str, product_name: str, *, price: int = 1_259_000) -> dict:
    return {
        "mall": "ELEVENST",
        "product_id": product_id,
        "product_name": product_name,
        "price": price,
        "seller": "테스트셀러",
        "product_url": f"https://www.11st.co.kr/products/{product_id}",
        "crawled_at": CRAWLED_AT,
    }


@requires_emulator
def test_phase7_scenario_a_multi_query_one_product_one_listing() -> None:
    suffix = uuid.uuid4().hex[:6]
    with emulator_env():
        db = get_firestore_client()
        items = _items("search_rtx.json", suffix=suffix)
        fixtures = {"RTX 5070": items, "지포스 RTX": items}

        run_multi_query_observation(
            queries=("RTX 5070", "지포스 RTX"),
            search_page_for_query=fixture_map_for_queries(fixtures),
            db=db,
            limit=MAX_SEARCH_LIMIT,
            dry_run=False,
        )

        products = list(db.collection(c.PRODUCTS).stream())
        listings = list(db.collection(c.LISTINGS).stream())
        assert len(products) >= 1
        assert len(listings) >= 1
        # Second query should skip all duplicates.
        assert len(products) == len(
            {doc.id for doc in db.collection(c.PRODUCTS).stream()}
        )


@requires_emulator
def test_phase7_scenario_b_mixed_outcomes_multi_query() -> None:
    suffix = uuid.uuid4().hex[:6]
    with emulator_env():
        db = get_firestore_client()
        db.collection(c.PENDING_GPU_MODELS).document("rtx_4070").delete()

        q1 = [
            _item(f"99{suffix}01", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB"),
            _item(f"99{suffix}02", "MSI 지포스 RTX 4070 벤투스 3X D6X 12GB"),
        ]
        q2 = [
            _item(f"99{suffix}03", "이엠텍 지포스 RTX 5070 MIRACLE WHITE D7 12GB"),
            _item(f"99{suffix}04", "라이젠7 7800X3D RTX5070_12GB RAM_32GB SSD_1TB 조립PC"),
        ]
        fixtures = {"RTX 5070": q1, "RTX 4070": q2}
        report = run_multi_query_observation(
            queries=("RTX 5070", "RTX 4070"),
            search_page_for_query=fixture_map_for_queries(fixtures),
            db=db,
            limit=MAX_SEARCH_LIMIT,
            dry_run=False,
        )

        statuses = {item.status for obs in report.queries for item in obs.results}
        assert SearchItemStatus.PERSISTED in statuses
        assert SearchItemStatus.QUARANTINED in statuses
        assert SearchItemStatus.VALIDATION_FAILED in statuses
        assert SearchItemStatus.IRRELEVANT in statuses
        assert db.collection(c.PENDING_GPU_MODELS).document("rtx_4070").get().exists
        db.collection(c.PENDING_GPU_MODELS).document("rtx_4070").delete()


@requires_emulator
def test_phase7_scenario_c_unknown_gpu_merged_across_queries() -> None:
    suffix = uuid.uuid4().hex[:6]
    with emulator_env():
        db = get_firestore_client()
        db.collection(c.PENDING_GPU_MODELS).document("rtx_4070").delete()

        unknown = _item(f"91{suffix}01", "MSI 지포스 RTX 4070 벤투스 3X D6X 12GB")
        fixtures = {
            "RTX 4070": [unknown],
            "RTX 5070": [dict(unknown, product_id=f"91{suffix}02")],
        }
        report = run_multi_query_observation(
            queries=("RTX 4070", "RTX 5070"),
            search_page_for_query=fixture_map_for_queries(fixtures),
            db=db,
            limit=MAX_SEARCH_LIMIT,
            dry_run=False,
        )

        assert report.aggregate.quarantined == 2
        pending = db.collection(c.PENDING_GPU_MODELS).document("rtx_4070").get()
        assert pending.exists
        assert pending.to_dict()["seen_count"] == 2
        assert not db.collection(c.GPU_MODELS).document("rtx_4070").get().exists
        for pid in (f"91{suffix}01", f"91{suffix}02"):
            assert not db.collection(c.LISTINGS).document(f"ELEVENST_{pid}").get().exists

        db.collection(c.PENDING_GPU_MODELS).document("rtx_4070").delete()


@requires_emulator
def test_phase7_scenario_d_pagination_duplicate_skip() -> None:
    suffix = uuid.uuid4().hex[:6]
    with emulator_env():
        db = get_firestore_client()
        listings_before = {doc.id for doc in db.collection(c.LISTINGS).stream()}
        page1 = _items("search_rtx.json", suffix=suffix)
        page2 = [page1[0], *_items("search_rtx_p2.json", suffix=f"{suffix}b")]

        def search_page(_query: str, page: int):
            return page1 if page == 1 else page2

        _results, summary = run_search_batch(
            query="RTX 5070",
            search_page=search_page,
            db=db,
            limit=MAX_SEARCH_LIMIT,
            pages=2,
            dry_run=False,
            sleep_func=lambda _s: None,
        )

        assert summary.duplicates_skipped >= 1
        listings_after = {doc.id for doc in db.collection(c.LISTINGS).stream()}
        new_listings = listings_after - listings_before
        assert len(new_listings) == summary.persisted
