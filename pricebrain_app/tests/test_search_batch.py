"""Bounded search batch tests — V2 Phase 3.

Covers the two Phase 2.5 regressions that must never come back:
unknown GPU model → pending_gpu_models, and one bad item → batch keeps going.
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone

import pytest

from pricebrain_app.crawler.parser.elevenst_search import parse_elevenst_search_json
from pricebrain_app.search_batch import (
    DEFAULT_SEARCH_LIMIT,
    MAX_SEARCH_LIMIT,
    MAX_SEARCH_PAGES,
    SearchItemStatus,
    resolve_search_limit,
    resolve_search_pages,
    run_search_batch,
)
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.gpu_master_seed import seed_gpu_master
from pricebrain_app.tests.counting_firestore import (
    CountingFirestoreClient,
    FirestoreWriteBlocked,
)
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "elevenst"
CRAWLED_AT = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)


def load_items(name: str):
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return parse_elevenst_search_json(payload, crawled_at=CRAWLED_AT)


@pytest.fixture
def db() -> FakeFirestoreClient:
    client = FakeFirestoreClient()
    seed_gpu_master(client)
    return client


def pages_source(*pages):
    """Build a search_page callable from explicit per-page item lists."""

    def search_page(_query: str, page: int):
        return pages[page - 1] if 1 <= page <= len(pages) else []

    return search_page


def fixture_source(name: str = "search_rtx.json"):
    items = load_items(name)
    return pages_source(items)


def by_id(results):
    return {item.external_product_id: item for item in results}


def no_sleep(_seconds: float) -> None:
    return None


# --- limits and pages -------------------------------------------------------


def test_limit_defaults_are_small():
    assert resolve_search_limit(None) == DEFAULT_SEARCH_LIMIT
    assert DEFAULT_SEARCH_LIMIT <= 10


def test_limit_is_capped_at_hard_maximum():
    assert resolve_search_limit(10_000) == MAX_SEARCH_LIMIT
    assert resolve_search_limit(MAX_SEARCH_LIMIT + 1) == MAX_SEARCH_LIMIT
    assert resolve_search_limit(3) == 3


@pytest.mark.parametrize("limit", [0, -5])
def test_limit_rejects_non_positive(limit: int):
    with pytest.raises(ValueError, match="limit must be >= 1"):
        resolve_search_limit(limit)


def test_pages_are_capped():
    assert resolve_search_pages(None) == 1
    assert resolve_search_pages(99) == MAX_SEARCH_PAGES
    with pytest.raises(ValueError, match="pages must be >= 1"):
        resolve_search_pages(0)


def test_batch_never_processes_more_than_the_limit(db):
    items = load_items("search_rtx.json")
    _results, summary = run_search_batch(
        query="RTX 5070",
        search_page=pages_source(items),
        db=db,
        limit=3,
        dry_run=True,
    )
    assert summary.requested == 3
    assert summary.processed == 3


def test_batch_limit_holds_even_when_a_page_returns_many_items(db):
    """Guard: a large page must not slip past the cap."""
    big_page = load_items("search_rtx.json") * 40
    _results, summary = run_search_batch(
        query="RTX 5070",
        search_page=pages_source(big_page),
        db=db,
        limit=10_000,
        pages=1,
        dry_run=True,
    )
    assert summary.processed <= MAX_SEARCH_LIMIT


def test_query_is_required(db):
    for query in ("", "   "):
        with pytest.raises(ValueError, match="query is required"):
            run_search_batch(query=query, search_page=fixture_source(), db=db)


# --- classification ---------------------------------------------------------


def test_known_model_with_known_partner_is_a_persist_candidate(db):
    results, summary = run_search_batch(
        query="RTX 5070",
        search_page=fixture_source(),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=True,
    )
    item = by_id(results)["8875337696"]

    assert item.status is SearchItemStatus.PERSIST_CANDIDATE
    assert item.gpu_model_id == "rtx_5070"
    assert item.board_partner_id == "GIGABYTE"
    assert item.canonical_product_id
    assert summary.persist_candidates >= 1


def test_unknown_model_with_known_partner_is_quarantined(db):
    results, summary = run_search_batch(
        query="RTX 5070",
        search_page=fixture_source(),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=True,
    )
    indexed = by_id(results)

    assert indexed["8123456701"].status is SearchItemStatus.QUARANTINED
    assert indexed["8123456701"].gpu_model_id == "rtx_4070"
    assert indexed["8123456702"].status is SearchItemStatus.QUARANTINED
    assert indexed["8123456702"].gpu_model_id == "rx_9070_xt"
    assert summary.unknown_models == {"rtx_4070": 1, "rx_9070_xt": 1}


def test_korean_board_partner_is_a_persist_candidate(db):
    results, _summary = run_search_batch(
        query="RTX 5070",
        search_page=fixture_source(),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=True,
    )
    item = by_id(results)["8123456703"]

    assert item.status is SearchItemStatus.PERSIST_CANDIDATE
    assert item.board_partner_id == "GIGABYTE"
    assert item.gpu_model_id == "rtx_5070"


def test_bracketed_brand_is_preserved_as_persist_candidate(db):
    results, _summary = run_search_batch(
        query="RTX 5070",
        search_page=fixture_source(),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=True,
    )
    item = by_id(results)["8123456704"]

    assert item.status is SearchItemStatus.PERSIST_CANDIDATE
    assert item.board_partner_id == "INNO3D"
    assert item.gpu_model_id == "rtx_5070"


def test_prebuilt_pc_is_irrelevant_not_validation_failure(db):
    results, _summary = run_search_batch(
        query="RTX 5070",
        search_page=fixture_source(),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=True,
    )
    item = by_id(results)["8123456705"]

    assert item.status is SearchItemStatus.IRRELEVANT
    assert item.error_category == "PREBUILT_PC"


def test_non_gpu_accessory_is_irrelevant(db):
    results, summary = run_search_batch(
        query="RTX 5070",
        search_page=fixture_source(),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=True,
    )
    item = by_id(results)["8123456706"]

    assert item.status is SearchItemStatus.IRRELEVANT
    assert item.error_category == "GPU_ACCESSORY"
    assert summary.irrelevant == 2


def test_every_result_is_classified_into_exactly_one_bucket(db):
    results, summary = run_search_batch(
        query="RTX 5070",
        search_page=fixture_source(),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=True,
    )
    total = (
        summary.persisted
        + summary.persist_candidates
        + summary.quarantined
        + summary.validation_failed
        + summary.irrelevant
        + summary.failed
    )
    assert total == summary.processed == len(results)


def test_summary_records_observation_fields(db):
    results, summary = run_search_batch(
        query="RTX 5070",
        search_page=fixture_source(),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=True,
    )
    payload = results[0].to_dict()

    assert payload["query"] == "RTX 5070"
    assert payload["mall_id"] == "elevenst"
    assert payload["page"] == 1
    assert payload["rank"] == 0
    assert payload["product_url"].startswith("https://www.11st.co.kr/products/")
    assert payload["observed_at"]
    assert summary.to_dict()["mall"] == "elevenst"
    # No raw payload is retained anywhere in the record.
    assert "html" not in payload and "raw" not in payload


# --- failure isolation ------------------------------------------------------


def test_one_failing_item_does_not_abort_the_batch(db):
    boom = {
        "mall": "ELEVENST",
        "product_id": "9000000001",
        "product_name": "MSI 지포스 RTX 5070 D7 12GB",
        "price": 1_000_000,
        "seller": "테스트",
        "product_url": "https://www.11st.co.kr/products/9000000001",
        "crawled_at": "not-a-date-and-not-parseable-either",
    }
    items = load_items("search_rtx.json")
    results, summary = run_search_batch(
        query="RTX 5070",
        search_page=pages_source([boom, *items]),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=False,
    )

    assert summary.processed == len(items) + 1
    assert summary.persisted >= 1
    assert summary.quarantined >= 1


def test_multiple_failures_still_complete_the_batch(db):
    """A crash inside a pipeline stage must not escape the per-item boundary."""

    class Exploding:
        def __str__(self) -> str:
            raise RuntimeError("synthetic item failure")

    def exploding_item(product_id: str):
        return {
            "mall": "ELEVENST",
            "product_id": product_id,
            "product_name": Exploding(),
            "price": 1_000_000,
            "seller": "테스트",
            "product_url": f"https://www.11st.co.kr/products/{product_id}",
            "crawled_at": CRAWLED_AT,
        }

    items = load_items("search_rtx.json")
    page = [exploding_item("9000000002"), *items, exploding_item("9000000003")]
    results, summary = run_search_batch(
        query="RTX 5070",
        search_page=pages_source(page),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=True,
    )

    assert summary.failed == 2
    assert summary.processed == len(page)
    assert summary.persist_candidates >= 1


def test_failed_page_fetch_does_not_abort_remaining_pages(db):
    items = load_items("search_rtx_p2.json")

    def search_page(_query: str, page: int):
        if page == 1:
            raise TimeoutError("search page 1 timed out")
        return items

    results, summary = run_search_batch(
        query="RTX 5070",
        search_page=search_page,
        db=db,
        limit=MAX_SEARCH_LIMIT,
        pages=2,
        dry_run=True,
        sleep_func=no_sleep,
    )

    assert summary.search_api_calls == 2
    assert summary.failed == 1
    failure = next(r for r in results if r.status is SearchItemStatus.FAILED)
    assert failure.error_category == "TimeoutError"
    assert failure.page == 1
    assert summary.processed == len(items) + 1


def test_batch_failure_does_not_leak_partial_writes_for_failed_items(db):
    counting = CountingFirestoreClient(db)

    def search_page(_query: str, page: int):
        raise ConnectionError("network down")

    _results, summary = run_search_batch(
        query="RTX 5070",
        search_page=search_page,
        db=counting,
        limit=5,
        dry_run=False,
    )
    assert summary.failed == 1
    assert counting.writes == 0


# --- duplicates -------------------------------------------------------------


def test_same_product_across_pages_is_processed_once(db):
    page1 = load_items("search_rtx.json")
    page2 = load_items("search_rtx_p2.json")

    results, summary = run_search_batch(
        query="RTX 5070",
        search_page=pages_source(page1, page2),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        pages=2,
        dry_run=True,
        sleep_func=no_sleep,
    )
    ids = [item.external_product_id for item in results]

    assert summary.duplicates_skipped == 1
    assert ids.count("8875337696") == 1
    assert len(ids) == len(set(ids))
    assert summary.collected == len(page1) + len(page2)
    assert summary.processed == summary.collected - summary.duplicates_skipped


def test_same_product_across_queries_keeps_one_identity(db):
    items = load_items("search_rtx.json")
    seen: set[str] = set()

    first, first_summary = run_search_batch(
        query="RTX 5070",
        search_page=pages_source(items),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=True,
        seen_external_ids=seen,
    )
    second, second_summary = run_search_batch(
        query="지포스 RTX",
        search_page=pages_source(items),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=True,
        seen_external_ids=seen,
    )

    assert first_summary.duplicates_skipped == 0
    assert second_summary.duplicates_skipped == len(items)
    assert second_summary.processed == 0
    assert first_summary.query == "RTX 5070"
    assert second_summary.query == "지포스 RTX"


def test_same_product_from_two_queries_resolves_to_one_canonical_product(db):
    """Without a shared seen-set, identity must still converge on persist."""
    items = load_items("search_rtx.json")

    first, _ = run_search_batch(
        query="RTX 5070",
        search_page=pages_source(items),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=False,
    )
    products_after_first = [p for p in db.paths() if p.startswith(f"{c.PRODUCTS}/")]
    listings_after_first = [p for p in db.paths() if p.startswith(f"{c.LISTINGS}/")]

    second, _ = run_search_batch(
        query="지포스 RTX",
        search_page=pages_source(items),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=False,
    )
    products_after_second = [p for p in db.paths() if p.startswith(f"{c.PRODUCTS}/")]
    listings_after_second = [p for p in db.paths() if p.startswith(f"{c.LISTINGS}/")]

    assert products_after_first == products_after_second
    assert listings_after_first == listings_after_second

    first_ids = {i.external_product_id: i.canonical_product_id for i in first}
    second_ids = {i.external_product_id: i.canonical_product_id for i in second}
    assert first_ids == second_ids


# --- dry-run / write safety -------------------------------------------------


def test_dry_run_performs_zero_writes(db):
    counting = CountingFirestoreClient(db, block_writes=True)
    _results, summary = run_search_batch(
        query="RTX 5070",
        search_page=fixture_source(),
        db=counting,
        limit=MAX_SEARCH_LIMIT,
        dry_run=True,
    )

    assert counting.writes == 0
    assert counting.write_paths == []
    assert summary.persisted == 0
    assert summary.persist_candidates >= 1
    assert summary.quarantined >= 1
    assert counting.reads > 0


def test_dry_run_writes_nothing_to_any_protected_collection(db):
    before = set(db.paths())
    run_search_batch(
        query="RTX 5070",
        search_page=fixture_source(),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=True,
    )
    assert set(db.paths()) == before


def test_dry_run_does_not_create_pending_gpu_models(db):
    _results, summary = run_search_batch(
        query="RTX 5070",
        search_page=fixture_source(),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=True,
    )
    pending = [p for p in db.paths() if p.startswith(f"{c.PENDING_GPU_MODELS}/")]

    assert summary.quarantined >= 1
    assert pending == []


def test_write_guard_raises_if_a_live_batch_runs_against_a_blocked_client(db):
    counting = CountingFirestoreClient(db, block_writes=True)
    results, summary = run_search_batch(
        query="RTX 5070",
        search_page=fixture_source(),
        db=counting,
        limit=MAX_SEARCH_LIMIT,
        dry_run=False,
    )

    # The guard fires per item; each becomes FAILED instead of writing.
    assert counting.writes == 0
    assert summary.persisted == 0
    assert summary.failed >= 1
    assert any(r.error_category == FirestoreWriteBlocked.__name__ for r in results)


def test_dry_run_and_live_agree_on_classification(db):
    items = load_items("search_rtx.json")
    dry, dry_summary = run_search_batch(
        query="RTX 5070",
        search_page=pages_source(items),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=True,
    )
    live, live_summary = run_search_batch(
        query="RTX 5070",
        search_page=pages_source(items),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=False,
    )

    assert dry_summary.persist_candidates == live_summary.persisted
    assert dry_summary.quarantined == live_summary.quarantined
    assert dry_summary.validation_failed == live_summary.validation_failed
    assert dry_summary.irrelevant == live_summary.irrelevant
    assert dry_summary.unknown_models == live_summary.unknown_models

    for dry_item, live_item in zip(dry, live, strict=True):
        assert dry_item.external_product_id == live_item.external_product_id
        assert dry_item.gpu_model_id == live_item.gpu_model_id


# --- live persistence -------------------------------------------------------


def test_live_batch_persists_known_models_and_quarantines_unknown(db):
    results, summary = run_search_batch(
        query="RTX 5070",
        search_page=fixture_source(),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=False,
    )
    indexed = by_id(results)

    assert indexed["8875337696"].status is SearchItemStatus.PERSISTED
    assert indexed["8875337696"].listing_id
    assert summary.persisted >= 1

    pending = [p for p in db.paths() if p.startswith(f"{c.PENDING_GPU_MODELS}/")]
    assert f"{c.PENDING_GPU_MODELS}/rtx_4070" in pending
    assert f"{c.PENDING_GPU_MODELS}/rx_9070_xt" in pending


def test_quarantined_search_item_links_to_pending_document(db):
    run_search_batch(
        query="RTX 5070",
        search_page=fixture_source(),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=False,
    )
    doc = db.get_document(f"{c.PENDING_GPU_MODELS}/rtx_4070")

    assert doc is not None
    assert doc["status"] == "PENDING_REVIEW"
    assert doc["seen_count"] == 1
    assert doc["source_malls"] == ["elevenst"]
    assert any("RTX 4070" in name for name in doc["example_product_names"])


def test_unknown_models_are_never_promoted_into_gpu_master(db):
    before = {p for p in db.paths() if p.startswith(f"{c.GPU_MODELS}/")}
    run_search_batch(
        query="RTX 5070",
        search_page=fixture_source(),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        dry_run=False,
    )
    after = {p for p in db.paths() if p.startswith(f"{c.GPU_MODELS}/")}

    assert before == after
    assert f"{c.GPU_MODELS}/rtx_4070" not in after


def test_repeated_quarantine_across_pages_aggregates_one_document(db):
    unknown = {
        "mall": "ELEVENST",
        "product_id": "9100000001",
        "product_name": "MSI 지포스 RTX 4070 벤투스 3X D6X 12GB",
        "price": 899_000,
        "seller": "테스트",
        "product_url": "https://www.11st.co.kr/products/9100000001",
        "crawled_at": CRAWLED_AT,
    }
    other = dict(unknown, product_id="9100000002", product_url="https://www.11st.co.kr/products/9100000002")

    _results, summary = run_search_batch(
        query="RTX 4070",
        search_page=pages_source([unknown], [other]),
        db=db,
        pages=2,
        limit=MAX_SEARCH_LIMIT,
        dry_run=False,
        sleep_func=no_sleep,
    )
    pending = [p for p in db.paths() if p.startswith(f"{c.PENDING_GPU_MODELS}/")]
    doc = db.get_document(f"{c.PENDING_GPU_MODELS}/rtx_4070")

    assert summary.quarantined == 2
    assert pending == [f"{c.PENDING_GPU_MODELS}/rtx_4070"]
    assert doc["seen_count"] == 2


# --- pagination -------------------------------------------------------------


def test_pagination_walks_two_pages_and_respects_boundaries(db):
    page1 = load_items("search_rtx.json")
    page2 = load_items("search_rtx_p2.json")

    results, summary = run_search_batch(
        query="RTX 5070",
        search_page=pages_source(page1, page2),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        pages=2,
        dry_run=True,
        sleep_func=no_sleep,
    )
    pages_seen = {item.page for item in results}

    assert summary.search_api_calls == 2
    assert pages_seen == {1, 2}
    assert summary.processed == len(page1) + len(page2) - 1


def test_pagination_stops_once_the_limit_is_reached(db):
    page1 = load_items("search_rtx.json")
    page2 = load_items("search_rtx_p2.json")

    _results, summary = run_search_batch(
        query="RTX 5070",
        search_page=pages_source(page1, page2),
        db=db,
        limit=2,
        pages=2,
        dry_run=True,
        sleep_func=no_sleep,
    )
    assert summary.search_api_calls == 1
    assert summary.processed == 2


def test_pagination_handles_an_empty_second_page(db):
    page1 = load_items("search_rtx.json")

    _results, summary = run_search_batch(
        query="RTX 5070",
        search_page=pages_source(page1, []),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        pages=2,
        dry_run=True,
        sleep_func=no_sleep,
    )
    assert summary.search_api_calls == 2
    assert summary.processed == len(page1)


def test_request_interval_is_applied_between_pages(db):
    slept: list[float] = []
    run_search_batch(
        query="RTX 5070",
        search_page=pages_source(load_items("search_rtx.json"), []),
        db=db,
        limit=MAX_SEARCH_LIMIT,
        pages=2,
        dry_run=True,
        request_interval_seconds=1.5,
        sleep_func=slept.append,
    )
    assert slept == [1.5]
