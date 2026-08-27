"""Phase 8 — product identity collision investigation gate tests."""

from __future__ import annotations

import json
import pathlib
from collections import defaultdict
from datetime import datetime, timezone

import pytest

from pricebrain_app.crawler.parser.elevenst_search import parse_elevenst_search_json
from pricebrain_app.pipeline.product_matcher import build_canonical_product_id, match_product
from pricebrain_app.repository.gpu_master_seed import seed_gpu_master
from pricebrain_app.repository.listing_repository import build_listing_document_id
from pricebrain_app.search_batch import DEFAULT_SEARCH_LIMIT, SearchItemStatus, run_search_batch
from pricebrain_app.search_observation import (
    PHASE7_BOUNDED_QUERIES,
    fixture_map_for_queries,
    observe_identity,
    run_multi_query_observation,
)
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

PHASE4_SAMPLE = pathlib.Path("_phase4_sample")
CRAWLED_AT = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)


def _load_phase4(filename: str) -> list[dict]:
    path = PHASE4_SAMPLE / filename
    if not path.exists():
        pytest.skip(f"missing phase4 sample: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return parse_elevenst_search_json(payload, crawled_at=CRAWLED_AT)


@pytest.fixture
def db() -> FakeFirestoreClient:
    client = FakeFirestoreClient()
    seed_gpu_master(client)
    return client


def test_phase8_canonical_id_priority_order() -> None:
    """docs/05 §2.1 — MPN > model_name > brand+gpu+vram+variant > name hash."""
    assert build_canonical_product_id({"manufacturer_part_number": "GV-N5080AERO-16GD"}) == "GVN5080AERO16GD"
    assert build_canonical_product_id({"model_name": "RTX5080-SOLID"}) == "RTX5080SOLID"
    assert build_canonical_product_id(
        {
            "brand": "ZOTAC",
            "gpu_model": "RTX 5080",
            "vram_gb": 16,
            "normalized_product_name": "ZOTAC GAMING RTX 5080 SOLID CORE OC D7 16GB",
        }
    ) == "ZOTAC-RTX5080-SOLIDCORE-16GB"
    assert build_canonical_product_id({"normalized_product_name": "orphan gpu listing"}) == "NAME-67DDC468DA8E8FF8"


def test_phase8_variant_tokens_are_bounded() -> None:
    """Only parser-backed variant tokens participate in priority-3 identity."""
    base = {
        "brand": "GIGABYTE",
        "gpu_model": "RTX 5080",
        "vram_gb": 16,
    }
    windforce = dict(base, normalized_product_name="GIGABYTE RTX 5080 WINDFORCE OC 16GB")
    gaming_oc = dict(base, normalized_product_name="GIGABYTE RTX 5080 GAMING OC 16GB")
    plain = dict(base, normalized_product_name="GIGABYTE RTX 5080 AORUS MASTER 16GB")

    assert build_canonical_product_id(windforce) == "GIGABYTE-RTX5080-WINDFORCE-16GB"
    assert build_canonical_product_id(gaming_oc) == "GIGABYTE-RTX5080-GAMINGOC-16GB"
    assert build_canonical_product_id(plain) == "GIGABYTE-RTX5080-MASTER-16GB"


def test_phase8_board_partner_separates_same_model(db: FakeFirestoreClient) -> None:
    """Scenario D contract — different board partners must not share canonical ID."""
    gigabyte = {
        "mall": "ELEVENST",
        "product_id": "9800000001",
        "product_name": "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB",
        "price": 900_000,
        "seller": "셀러A",
        "product_url": "https://www.11st.co.kr/products/9800000001",
        "crawled_at": CRAWLED_AT,
    }
    manli = {
        "mall": "ELEVENST",
        "product_id": "9800000002",
        "product_name": "MANLI 지포스 RTX 5070 GAMING OC D7 12GB",
        "price": 850_000,
        "seller": "셀러B",
        "product_url": "https://www.11st.co.kr/products/9800000002",
        "crawled_at": CRAWLED_AT,
    }

    results, _ = run_search_batch(
        query="RTX 5070",
        search_page=lambda _q, page: [gigabyte, manli] if page == 1 else [],
        db=db,
        limit=DEFAULT_SEARCH_LIMIT,
        dry_run=True,
    )
    canonical_ids = {
        item.canonical_product_id
        for item in results
        if item.status is SearchItemStatus.PERSIST_CANDIDATE and item.canonical_product_id
    }
    assert len(canonical_ids) == 2
    assert "GIGABYTE" in next(c for c in canonical_ids if "GIGABYTE" in c)
    assert "MANLI" in next(c for c in canonical_ids if "MANLI" in c)


def test_phase8_same_product_different_sellers_two_listings(db: FakeFirestoreClient) -> None:
    """Scenario B — one product, two listings when seller/external_id differ."""
    product_name = "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB"
    item_a = {
        "mall": "ELEVENST",
        "product_id": "9700000001",
        "product_name": product_name,
        "price": 900_000,
        "seller": "셀러A",
        "product_url": "https://www.11st.co.kr/products/9700000001",
        "crawled_at": CRAWLED_AT,
    }
    item_b = {
        "mall": "ELEVENST",
        "product_id": "9700000002",
        "product_name": product_name,
        "price": 890_000,
        "seller": "셀러B",
        "product_url": "https://www.11st.co.kr/products/9700000002",
        "crawled_at": CRAWLED_AT,
    }

    results, summary = run_search_batch(
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
    assert summary.duplicates_skipped == 0


def test_phase8_sku_variant_observation_white_vs_black(db: FakeFirestoreClient) -> None:
    """Scenario C — current policy may merge distinct SKU lines (observation only)."""
    white = {
        "mall": "ELEVENST",
        "product_id": "9600000101",
        "product_name": "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
        "price": 1_500_000,
        "seller": "셀러A",
        "product_url": "https://www.11st.co.kr/products/9600000101",
        "crawled_at": CRAWLED_AT,
    }
    black = {
        "mall": "ELEVENST",
        "product_id": "9600000102",
        "product_name": "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
        "price": 1_450_000,
        "seller": "셀러B",
        "product_url": "https://www.11st.co.kr/products/9600000102",
        "crawled_at": CRAWLED_AT,
    }

    results, _ = run_search_batch(
        query="RTX 5080",
        search_page=lambda _q, page: [white, black] if page == 1 else [],
        db=db,
        limit=DEFAULT_SEARCH_LIMIT,
        dry_run=True,
    )
    blocked = [r for r in results if r.status is SearchItemStatus.IDENTITY_REVIEW_BLOCKED]
    canonical_ids = {r.canonical_product_id for r in blocked}
    assert len(blocked) == 2
    assert len(canonical_ids) == 1
    assert canonical_ids.pop() == "ZOTAC-RTX5080-SOLIDOC-16GB"
    assert all(item.review_required for item in blocked)


def test_phase8_duplicate_vs_canonical_collision_are_distinct(db: FakeFirestoreClient) -> None:
    """duplicate = same external_id; canonical collision = different external_id, same canonical."""
    product_name = "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB"
    first = {
        "mall": "ELEVENST",
        "product_id": "9500000001",
        "product_name": product_name,
        "price": 900_000,
        "seller": "셀러A",
        "product_url": "https://www.11st.co.kr/products/9500000001",
        "crawled_at": CRAWLED_AT,
    }
    second = dict(first, product_id="9500000002", seller="셀러B")
    duplicate = dict(first)

    fixtures = {"RTX 5070": [first, second], "지포스 RTX": [duplicate]}
    report = run_multi_query_observation(
        queries=("RTX 5070", "지포스 RTX"),
        search_page_for_query=fixture_map_for_queries(fixtures),
        db=db,
        limit=DEFAULT_SEARCH_LIMIT,
        dry_run=True,
    )

    assert report.aggregate.duplicates_skipped == 1
    identity = report.identity
    assert identity.canonical_id_collisions == 1
    assert identity.unique_external_ids == 2


def test_phase8_m7_mutation_board_partner_merge_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    """M7 — removing brand from canonical ID must merge different board partners (regression guard)."""

    def _broken_canonical(data: dict) -> str | None:
        gpu_model = data.get("gpu_model")
        vram_gb = data.get("vram_gb")
        normalized_name = data.get("normalized_product_name")
        if gpu_model and vram_gb is not None:
            model_compact = str(gpu_model).replace(" ", "").upper()
            return f"{model_compact}-{int(vram_gb)}GB"
        if normalized_name:
            return "NAME-BROKEN"
        return None

    monkeypatch.setattr(
        "pricebrain_app.pipeline.product_matcher.build_canonical_product_id",
        _broken_canonical,
    )

    gigabyte = match_product(
        {
            "brand": "GIGABYTE",
            "gpu_model": "RTX 5070",
            "vram_gb": 12,
            "normalized_product_name": "GIGABYTE RTX 5070 12GB",
        }
    )
    manli = match_product(
        {
            "brand": "MANLI",
            "gpu_model": "RTX 5070",
            "vram_gb": 12,
            "normalized_product_name": "MANLI RTX 5070 12GB",
        }
    )
    assert gigabyte["canonical_product_id"] == manli["canonical_product_id"]


@pytest.mark.skipif(not PHASE4_SAMPLE.exists(), reason="phase4 sample not present")
def test_phase8_phase7_sample_five_canonical_collisions(db: FakeFirestoreClient) -> None:
    """Reproduce Phase 7 bounded observation identity metric on saved sample."""
    fixture_files = {
        "RTX 4070": "p4_RTX_4070_p1.json",
        "RTX 5070": "p4_RTX_5070_p1.json",
        "RTX 5080": "p4_RTX_5080_p1.json",
        "RX 9070": "p4_RX_9070_p1.json",
        "그래픽카드": "p4_그래픽카드_p1.json",
        "지포스 RTX": "p4_지포스_RTX_p1.json",
    }
    fixtures = {
        query: _load_phase4(filename)[:DEFAULT_SEARCH_LIMIT]
        for query, filename in fixture_files.items()
    }
    report = run_multi_query_observation(
        queries=PHASE7_BOUNDED_QUERIES,
        search_page_for_query=fixture_map_for_queries(fixtures),
        db=db,
        limit=DEFAULT_SEARCH_LIMIT,
        pages=1,
        dry_run=True,
    )

    identity = observe_identity(item for obs in report.queries for item in obs.results)
    assert identity.canonical_id_collisions >= 1

    by_canonical: dict[str, list] = defaultdict(list)
    for obs in report.queries:
        for item in obs.results:
            if item.canonical_product_id and item.external_product_id:
                by_canonical[item.canonical_product_id].append(item)

    collision_groups = {cid: items for cid, items in by_canonical.items() if len(items) > 1}
    assert collision_groups
    assert collision_groups["GIGABYTE-RTX5080-WINDFORCE-16GB"]
    assert "ZOTAC-RTX5080-SOLIDOC-16GB" in collision_groups

    # Listing IDs remain distinct per external_product_id even when canonical collides.
    for _cid, members in collision_groups.items():
        listing_ids = {
            build_listing_document_id("elevenst", m.external_product_id)
            for m in members
            if m.external_product_id
        }
        external_ids = {m.external_product_id for m in members}
        assert len(listing_ids) == len(external_ids)
