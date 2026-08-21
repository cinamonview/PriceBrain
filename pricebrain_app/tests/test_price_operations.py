"""Price snapshot calculations and read-only operations tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from pricebrain_app.config.settings import clear_settings_cache
from pricebrain_app.crawler.price_calculations import (
    build_price_history_views,
    build_price_summary,
    calculate_price_change,
    calculate_price_change_percent,
    classify_price_change,
    is_valid_price,
)
from pricebrain_app.crawler.price_ops_models import PriceChangeClassification
from pricebrain_app.crawler.price_operations_view import PriceListFilter, PriceOperationsView
from pricebrain_app.crawler.results import CrawlerResult, CrawlerStatus
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.crawler.targets import CrawlTarget
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.listing_repository import build_listing_document_id
from pricebrain_app.scripts import list_price_drops, list_price_increases, show_gpu_prices, show_price_history
from pricebrain_app.tests.conftest import TEST_INGEST_API_KEY
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
PRODUCT_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906"
TARGET_ID = "ssg_1000832367906"
LISTING_ID = build_listing_document_id("ssg", "1000832367906")
PRODUCT_ID = "ZOTAC-RTX5080-16GB"


@pytest.fixture
def price_db() -> FakeFirestoreClient:
    return FakeFirestoreClient()


@pytest.fixture
def price_repo(price_db: FakeFirestoreClient) -> CrawlTargetRepository:
    return CrawlTargetRepository(price_db)


@pytest.fixture
def price_view(price_db: FakeFirestoreClient, price_repo: CrawlTargetRepository) -> PriceOperationsView:
    return PriceOperationsView(price_repo, price_db)


def _gpu_target(**overrides: object) -> CrawlTarget:
    payload = {
        "target_id": TARGET_ID,
        "mall_id": "ssg",
        "product_url": PRODUCT_URL,
        "product_name": "ZOTAC RTX 5080",
        "category": "gpu",
        "tags": ["zotac", "rtx5080"],
        "priority": 100,
        "enabled": True,
    }
    payload.update(overrides)
    return CrawlTarget(**payload)


def _seed_gpu_target(repo: CrawlTargetRepository) -> None:
    repo.merge_catalog(
        mall_id="ssg",
        product_url=PRODUCT_URL,
        product_name="ZOTAC RTX 5080",
        category="gpu",
        tags=["zotac", "rtx5080"],
        priority=100,
        now=NOW,
    )


def _seed_history(db: FakeFirestoreClient, *, prices: list[tuple[int, int | None, int | None]]) -> None:
    db.collection(c.LISTINGS).document(LISTING_ID).set(
        {
            "product_id": PRODUCT_ID,
            "normalized_product_name": "ZOTAC RTX 5080",
            "current_price": prices[-1][0],
            "crawled_at": NOW,
        }
    )
    for index, (price, previous, change) in enumerate(prices, start=1):
        payload = {"price": price, "crawled_at": NOW.replace(hour=index)}
        if previous is not None:
            payload["previous_price"] = previous
        if change is not None:
            payload["price_change"] = change
        db.collection(c.LISTINGS).document(LISTING_ID).collection(c.PRICE_HISTORY).document(str(index)).set(
            payload
        )


def test_price_calculation_unchanged() -> None:
    assert classify_price_change(1_599_000, 1_599_000, has_history=True) is PriceChangeClassification.UNCHANGED
    assert calculate_price_change(1_599_000, 1_599_000) == 0


def test_price_calculation_down() -> None:
    assert classify_price_change(1_549_000, 1_599_000, has_history=True) is PriceChangeClassification.PRICE_DOWN
    assert calculate_price_change(1_549_000, 1_599_000) == -50_000
    assert calculate_price_change_percent(1_549_000, 1_599_000) == pytest.approx(-3.13)


def test_price_calculation_up() -> None:
    assert classify_price_change(1_599_000, 1_549_000, has_history=True) is PriceChangeClassification.PRICE_UP


def test_price_calculation_no_previous() -> None:
    assert classify_price_change(1_599_000, None, has_history=False) is PriceChangeClassification.NO_HISTORY


def test_price_calculation_no_current() -> None:
    assert classify_price_change(None, 1_599_000, has_history=False) is PriceChangeClassification.NO_HISTORY


def test_price_calculation_invalid_zero_and_negative() -> None:
    assert is_valid_price(0) is False
    assert is_valid_price(-100) is False
    assert classify_price_change(0, 1_599_000, has_history=True) is PriceChangeClassification.INVALID_PRICE
    assert calculate_price_change_percent(1_549_000, 0) is None


def test_price_summary_without_history() -> None:
    summary = build_price_summary(
        _gpu_target(),
        listing_id=None,
        listing_data=None,
        history_entries=[],
    )
    assert summary.classification is PriceChangeClassification.NO_HISTORY
    assert summary.current_price is None
    assert summary.history_count == 0


def test_price_summary_single_history_entry() -> None:
    summary = build_price_summary(
        _gpu_target(),
        listing_id=LISTING_ID,
        listing_data={"normalized_product_name": "ZOTAC RTX 5080", "current_price": 1_599_000},
        history_entries=[{"price": 1_599_000, "crawled_at": NOW.isoformat()}],
        product_id=PRODUCT_ID,
    )
    assert summary.current_price == 1_599_000
    assert summary.first_price == 1_599_000
    assert summary.lowest_price == 1_599_000
    assert summary.highest_price == 1_599_000
    assert summary.history_count == 1


def test_price_summary_multiple_history_entries() -> None:
    history = [
        {"price": 1_699_000, "crawled_at": NOW.replace(hour=10).isoformat()},
        {
            "price": 1_599_000,
            "previous_price": 1_699_000,
            "price_change": -100_000,
            "crawled_at": NOW.replace(hour=11).isoformat(),
        },
        {
            "price": 1_549_000,
            "previous_price": 1_599_000,
            "price_change": -50_000,
            "crawled_at": NOW.replace(hour=12).isoformat(),
        },
    ]
    summary = build_price_summary(
        _gpu_target(),
        listing_id=LISTING_ID,
        listing_data={"current_price": 1_549_000},
        history_entries=history,
    )
    assert summary.current_price == 1_549_000
    assert summary.previous_price == 1_599_000
    assert summary.first_price == 1_699_000
    assert summary.lowest_price == 1_549_000
    assert summary.highest_price == 1_699_000
    assert summary.classification is PriceChangeClassification.PRICE_DOWN


def test_403_target_has_no_price_observation(
    price_view: PriceOperationsView,
    price_repo: CrawlTargetRepository,
) -> None:
    _seed_gpu_target(price_repo)
    price_repo.update_after_crawl(
        TARGET_ID,
        result=CrawlerResult(
            status=CrawlerStatus.HTTP_ERROR,
            mall_id="ssg",
            product_url=PRODUCT_URL,
            message="SSG_ACCESS_DENIED",
        ),
        next_crawl_at=NOW,
        crawled_at=NOW,
    )
    summary = price_view.get_price_summary(TARGET_ID)
    assert summary is not None
    assert summary.current_price is None
    assert summary.classification is PriceChangeClassification.NO_HISTORY
    assert summary.has_price_observation is False


def test_operations_list_price_drops_and_increases(
    price_view: PriceOperationsView,
    price_repo: CrawlTargetRepository,
    price_db: FakeFirestoreClient,
) -> None:
    _seed_gpu_target(price_repo)
    _seed_history(price_db, prices=[(1_599_000, None, None), (1_549_000, 1_599_000, -50_000)])

    drops = price_view.list_price_drops()
    assert len(drops) == 1
    assert drops[0].target_id == TARGET_ID
    assert drops[0].classification is PriceChangeClassification.PRICE_DOWN

    increases = price_view.list_price_increases()
    assert increases == []


def test_operations_filter_by_tag(
    price_view: PriceOperationsView,
    price_repo: CrawlTargetRepository,
    price_db: FakeFirestoreClient,
) -> None:
    _seed_gpu_target(price_repo)
    _seed_history(price_db, prices=[(1_599_000, None, None), (1_549_000, 1_599_000, -50_000)])

    filtered = price_view.list_price_summaries(filters=PriceListFilter(tag="rtx5080"))
    assert len(filtered) == 1
    assert filtered[0].target_id == TARGET_ID


def test_gpu_price_status_summary(
    price_view: PriceOperationsView,
    price_repo: CrawlTargetRepository,
    price_db: FakeFirestoreClient,
) -> None:
    _seed_gpu_target(price_repo)
    status = price_view.summarize_gpu_prices()
    assert status.targets == 1
    assert status.without_price == 1
    assert status.no_history == 1

    _seed_history(price_db, prices=[(1_599_000, None, None), (1_549_000, 1_599_000, -50_000)])
    status = price_view.summarize_gpu_prices()
    assert status.with_price == 1
    assert status.price_down == 1


def test_show_gpu_prices_cli_json(
    price_view: PriceOperationsView,
    price_repo: CrawlTargetRepository,
    price_db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _seed_gpu_target(price_repo)
    _seed_history(price_db, prices=[(1_599_000, None, None), (1_549_000, 1_599_000, -50_000)])
    monkeypatch.setattr(show_gpu_prices, "build_price_operations_view", lambda: price_view)

    exit_code = show_gpu_prices.main(["--target-id", TARGET_ID, "--json"])
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["classification"] == "PRICE_DOWN"


def test_list_price_drops_cli(
    price_view: PriceOperationsView,
    price_repo: CrawlTargetRepository,
    price_db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_gpu_target(price_repo)
    _seed_history(price_db, prices=[(1_599_000, None, None), (1_549_000, 1_599_000, -50_000)])
    monkeypatch.setattr(list_price_drops, "build_price_operations_view", lambda: price_view)
    assert list_price_drops.main(["--json"]) == 0


def test_list_price_increases_cli(
    price_view: PriceOperationsView,
    price_repo: CrawlTargetRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_gpu_target(price_repo)
    monkeypatch.setattr(list_price_increases, "build_price_operations_view", lambda: price_view)
    assert list_price_increases.main(["--json"]) == 0


def test_show_price_history_cli(
    price_view: PriceOperationsView,
    price_repo: CrawlTargetRepository,
    price_db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_gpu_target(price_repo)
    _seed_history(price_db, prices=[(1_599_000, None, None), (1_549_000, 1_599_000, -50_000)])
    monkeypatch.setattr(show_price_history, "build_price_operations_view", lambda: price_view)
    assert show_price_history.main(["--target-id", TARGET_ID]) == 0


def test_price_history_views_from_entries() -> None:
    views = build_price_history_views(
        [
            {"price": 1_599_000, "crawled_at": NOW.isoformat()},
            {
                "price": 1_549_000,
                "previous_price": 1_599_000,
                "price_change": -50_000,
                "crawled_at": NOW.replace(hour=13).isoformat(),
            },
        ]
    )
    assert len(views) == 2
    assert views[-1].price == 1_549_000


def test_security_json_masks_api_key(
    price_view: PriceOperationsView,
    price_repo: CrawlTargetRepository,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _seed_gpu_target(price_repo)
    monkeypatch.setenv("PRICEBRAIN_INGEST_API_KEY", TEST_INGEST_API_KEY)
    clear_settings_cache()
    monkeypatch.setattr(show_gpu_prices, "build_price_operations_view", lambda: price_view)

    show_gpu_prices.main(["--status", "--json"])
    text = capsys.readouterr().out
    assert TEST_INGEST_API_KEY not in text
    assert "Authorization" not in text


def test_price_ops_reads_pipeline_written_history(
    price_view: PriceOperationsView,
    price_repo: CrawlTargetRepository,
    price_db: FakeFirestoreClient,
) -> None:
    _seed_gpu_target(price_repo)
    _seed_history(
        price_db,
        prices=[
            (1_599_000, None, None),
            (1_549_000, 1_599_000, -50_000),
        ],
    )
    summary = price_view.get_price_summary(TARGET_ID)
    assert summary is not None
    assert summary.history_count == 2
    assert summary.current_price == 1_549_000
    assert summary.classification is PriceChangeClassification.PRICE_DOWN
