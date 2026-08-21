"""Crawl target model and repository tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pricebrain_app.crawler.results import CrawlerResult, CrawlerStatus
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.crawler.targets import (
    DEFAULT_CRAWL_INTERVAL_SECONDS,
    build_target_id,
    validate_target_url,
)
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

PRODUCT_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906"
TARGET_ID = "ssg_1000832367906"


@pytest.fixture
def target_db() -> FakeFirestoreClient:
    return FakeFirestoreClient()


@pytest.fixture
def target_repo(target_db: FakeFirestoreClient) -> CrawlTargetRepository:
    return CrawlTargetRepository(target_db)


def test_build_target_id_from_ssg_url() -> None:
    assert build_target_id("ssg", PRODUCT_URL) == TARGET_ID


def test_validate_target_url_reuses_ssg_validator() -> None:
    assert validate_target_url("ssg", PRODUCT_URL) == PRODUCT_URL


def test_upsert_creates_target(target_repo: CrawlTargetRepository) -> None:
    target = target_repo.upsert(mall_id="ssg", product_url=PRODUCT_URL)

    assert target.target_id == TARGET_ID
    assert target.mall_id == "ssg"
    assert target.enabled is True
    assert target.crawl_interval_seconds == DEFAULT_CRAWL_INTERVAL_SECONDS
    assert target.next_crawl_at is not None
    assert target.created_at is not None


def test_upsert_merges_existing_target(target_repo: CrawlTargetRepository) -> None:
    first = target_repo.upsert(mall_id="ssg", product_url=PRODUCT_URL, crawl_interval_seconds=7200)
    second = target_repo.upsert(
        mall_id="ssg",
        product_url=PRODUCT_URL,
        enabled=False,
        crawl_interval_seconds=1800,
    )

    assert second.target_id == first.target_id
    assert second.enabled is False
    assert second.crawl_interval_seconds == 1800
    assert second.created_at == first.created_at


def test_list_enabled_excludes_disabled(target_repo: CrawlTargetRepository) -> None:
    target_repo.upsert(mall_id="ssg", product_url=PRODUCT_URL, enabled=True)
    target_repo.upsert(
        mall_id="ssg",
        product_url="https://www.ssg.com/item/itemView.ssg?itemId=1000123456789",
        enabled=False,
    )

    enabled = target_repo.list_enabled()
    assert len(enabled) == 1
    assert enabled[0].target_id == TARGET_ID


def test_list_due_returns_only_past_next_crawl_at(target_repo: CrawlTargetRepository) -> None:
    now = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
    due = target_repo.upsert(
        mall_id="ssg",
        product_url=PRODUCT_URL,
        now=now - timedelta(hours=2),
    )
    future = target_repo.upsert(
        mall_id="ssg",
        product_url="https://www.ssg.com/item/itemView.ssg?itemId=1000123456789",
        now=now,
    )
    target_repo.update_after_crawl(
        future.target_id,
        result=CrawlerResult(status=CrawlerStatus.SUCCESS, mall_id="ssg"),
        next_crawl_at=now + timedelta(hours=1),
        crawled_at=now,
    )

    due_targets = target_repo.list_due(now)
    assert [item.target_id for item in due_targets] == [due.target_id]


def test_update_after_crawl_persists_result_fields(target_repo: CrawlTargetRepository) -> None:
    target = target_repo.upsert(mall_id="ssg", product_url=PRODUCT_URL)
    now = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)
    next_run = now + timedelta(seconds=3600)

    updated = target_repo.update_after_crawl(
        target.target_id,
        result=CrawlerResult(
            status=CrawlerStatus.HTTP_ERROR,
            mall_id="ssg",
            product_url=PRODUCT_URL,
            message="SSG_ACCESS_DENIED",
            http_status_code=403,
        ),
        next_crawl_at=next_run,
        crawled_at=now,
    )

    assert updated.last_status == "HTTP_ERROR"
    assert updated.last_error_code == "SSG_ACCESS_DENIED"
    assert updated.last_error_message == "SSG_ACCESS_DENIED"
    assert updated.next_crawl_at == next_run
    assert updated.last_crawled_at == now
