"""Phase 7 — bounded multi-query Search Batch observation gate tests."""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone

import pytest

from pricebrain_app.crawler.parser.elevenst_search import parse_elevenst_search_json
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.gpu_master_seed import BOARD_PARTNERS, seed_gpu_master
from pricebrain_app.search_batch import (
    DEFAULT_SEARCH_LIMIT,
    MAX_SEARCH_LIMIT,
    MAX_SEARCH_PAGES,
    SearchItemStatus,
    run_search_batch,
)
from pricebrain_app.search_observation import (
    PHASE7_BOUNDED_QUERIES,
    MultiQueryObservationReport,
    aggregate_query_summaries,
    classify_observation_items,
    fixture_map_for_queries,
    is_production_quota_failure,
    observe_identity,
    run_multi_query_observation,
)
from pricebrain_app.tests.counting_firestore import CountingFirestoreClient
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "elevenst"
PHASE4_SAMPLE = pathlib.Path("_phase4_sample")
CRAWLED_AT = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)


def _load_fixture(name: str) -> list[dict]:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return parse_elevenst_search_json(payload, crawled_at=CRAWLED_AT)


def _load_phase4(query_file: str) -> list[dict]:
    path = PHASE4_SAMPLE / query_file
    if not path.exists():
        pytest.skip(f"missing phase4 sample: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return parse_elevenst_search_json(payload, crawled_at=CRAWLED_AT)


@pytest.fixture
def db() -> FakeFirestoreClient:
    client = FakeFirestoreClient()
    seed_gpu_master(client)
    return client


def test_phase7_query_scope_is_fixed_and_bounded() -> None:
    assert len(PHASE7_BOUNDED_QUERIES) == 6
    assert "RTX 5070" in PHASE7_BOUNDED_QUERIES
    assert "지포스 RTX" in PHASE7_BOUNDED_QUERIES


def test_phase7_board_partner_master_count() -> None:
    slugs = {str(partner["slug"]) for partner in BOARD_PARTNERS}
    assert len(slugs) == 15
    assert {"MANLI", "POWERCOLOR"}.issubset(slugs)
    assert "EMTEK" not in slugs


def test_phase7_quota_failure_is_detected_separately() -> None:
    from pricebrain_app.search_batch import SearchItemResult

    quota_item = SearchItemResult(
        status=SearchItemStatus.FAILED,
        mall_id="elevenst",
        query="RTX 5070",
        page=1,
        rank=0,
        error_category="ResourceExhausted",
        message="429 Quota exceeded.",
    )
    assert is_production_quota_failure(quota_item) is True

    pipeline_item = SearchItemResult(
        status=SearchItemStatus.FAILED,
        mall_id="elevenst",
        query="RTX 5070",
        page=1,
        rank=0,
        error_category="RuntimeError",
        message="synthetic item failure",
    )
    assert is_production_quota_failure(pipeline_item) is False


def test_phase7_multi_query_shared_dedup_skips_second_query_items(db: FakeFirestoreClient) -> None:
    items = _load_fixture("search_rtx.json")
    fixtures = {
        "RTX 5070": items,
        "지포스 RTX": items,
    }
    report = run_multi_query_observation(
        queries=("RTX 5070", "지포스 RTX"),
        search_page_for_query=fixture_map_for_queries(fixtures),
        db=db,
        limit=DEFAULT_SEARCH_LIMIT,
        dry_run=True,
    )

    first, second = report.queries
    assert first.summary.duplicates_skipped == 0
    assert second.summary.duplicates_skipped == len(items)
    assert second.summary.processed == 0
    assert report.aggregate.duplicates_skipped == len(items)
    assert report.identity.unique_external_ids == first.summary.processed


def test_phase7_multi_query_dry_run_zero_writes(db: FakeFirestoreClient) -> None:
    items = _load_fixture("search_rtx.json")
    fixtures = {query: items for query in PHASE7_BOUNDED_QUERIES[:2]}
    counting = CountingFirestoreClient(db, block_writes=True)
    before = set(db.paths())

    report = run_multi_query_observation(
        queries=tuple(fixtures.keys()),
        search_page_for_query=fixture_map_for_queries(fixtures),
        db=counting,
        dry_run=True,
    )

    assert counting.writes == 0
    assert set(db.paths()) == before
    assert report.aggregate.persisted == 0
    assert report.aggregate.persist_candidates >= 1


def test_phase7_aggregate_totals_match_per_query(db: FakeFirestoreClient) -> None:
    items = _load_fixture("search_rtx.json")
    fixtures = {"RTX 5070": items, "RTX 5080": items[:3]}
    report = run_multi_query_observation(
        queries=tuple(fixtures.keys()),
        search_page_for_query=fixture_map_for_queries(fixtures),
        db=db,
        limit=DEFAULT_SEARCH_LIMIT,
        dry_run=True,
    )

    manual = aggregate_query_summaries(report.queries, dry_run=True)
    assert manual.processed == report.aggregate.processed
    assert manual.persist_candidates == report.aggregate.persist_candidates
    assert manual.quarantined == report.aggregate.quarantined


def test_phase7_classification_breakdown(db: FakeFirestoreClient) -> None:
    items = _load_fixture("search_rtx.json")
    report = run_multi_query_observation(
        queries=("RTX 5070",),
        search_page_for_query=fixture_map_for_queries({"RTX 5070": items}),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=True,
    )
    breakdown = classify_observation_items(
        item for obs in report.queries for item in obs.results
    )
    assert breakdown.known_gpu >= 1
    assert breakdown.unknown_gpu >= 1
    assert breakdown.gpu_accessory >= 1 or breakdown.prebuilt_pc >= 1


def test_phase7_hard_caps_unchanged() -> None:
    assert DEFAULT_SEARCH_LIMIT == 10
    assert MAX_SEARCH_LIMIT == 50
    assert MAX_SEARCH_PAGES == 3


def test_phase7_one_bad_query_does_not_abort_remaining(db: FakeFirestoreClient) -> None:
    good = _load_fixture("search_rtx.json")

    def search_page(query: str, page: int):
        if query == "BAD":
            raise TimeoutError("search timeout")
        if page != 1:
            return []
        return good

    report = run_multi_query_observation(
        queries=("BAD", "RTX 5070"),
        search_page_for_query=search_page,
        db=db,
        limit=DEFAULT_SEARCH_LIMIT,
        dry_run=True,
    )

    assert report.queries[0].summary.failed == 1
    assert report.queries[1].summary.processed >= 1


@pytest.mark.skipif(not PHASE4_SAMPLE.exists(), reason="phase4 sample not present")
def test_phase7_phase4_sample_multi_query_observation(db: FakeFirestoreClient) -> None:
    """Full bounded query set against saved Phase 4 JSON (read-only)."""
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

    assert len(report.queries) == 6
    assert report.aggregate.search_api_calls == 6
    assert report.aggregate.processed <= 6 * DEFAULT_SEARCH_LIMIT
    assert isinstance(report, MultiQueryObservationReport)
    identity = observe_identity(
        item for obs in report.queries for item in obs.results
    )
    # Same canonical across different external listings is observed, not a gate failure.
    assert identity.unique_external_ids > 0
    assert identity.unique_canonical_product_ids > 0


def test_phase7_live_multi_query_identity_no_duplicate_products(
    db: FakeFirestoreClient,
) -> None:
    items = _load_fixture("search_rtx.json")
    seen: set[str] = set()

    first_results, _ = run_search_batch(
        query="RTX 5070",
        search_page=lambda _q, page: items if page == 1 else [],
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=False,
        seen_external_ids=seen,
    )
    products_after_first = [p for p in db.paths() if p.startswith(f"{c.PRODUCTS}/")]

    second_results, second_summary = run_search_batch(
        query="지포스 RTX",
        search_page=lambda _q, page: items if page == 1 else [],
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=False,
        seen_external_ids=seen,
    )
    products_after_second = [p for p in db.paths() if p.startswith(f"{c.PRODUCTS}/")]

    first_map = {
        r.external_product_id: (r.canonical_product_id, r.listing_id)
        for r in first_results
        if r.status is SearchItemStatus.PERSISTED
    }
    assert second_summary.duplicates_skipped == len(items)
    assert second_summary.processed == 0
    assert products_after_first == products_after_second
    assert first_map
