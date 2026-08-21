"""Crawl target catalog seeding and bulk management tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pricebrain_app.crawler.results import CrawlerResult, CrawlerStatus
from pricebrain_app.crawler.target_management import (
    BulkUpdateFilter,
    bulk_set_enabled,
    load_catalog_entries_from_file,
    seed_catalog_entries,
)
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.crawler.targets import DEFAULT_TARGET_PRIORITY, build_target_id
from pricebrain_app.crawler.operations_view import CrawlerOperationsView, TargetListFilter
from pricebrain_app.scripts import list_crawl_targets, seed_gpu_targets, set_crawl_targets
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

PRODUCT_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906"
OTHER_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000123456789"
TARGET_ID = "ssg_1000832367906"
OTHER_TARGET_ID = "ssg_1000123456789"
NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def target_db() -> FakeFirestoreClient:
    return FakeFirestoreClient()


@pytest.fixture
def target_repo(target_db: FakeFirestoreClient) -> CrawlTargetRepository:
    return CrawlTargetRepository(target_db)


@pytest.fixture
def ops_view(target_repo: CrawlTargetRepository, target_db: FakeFirestoreClient) -> CrawlerOperationsView:
    return CrawlerOperationsView(target_repo, target_db)


def _catalog_payload() -> list[dict]:
    return [
        {
            "mall_id": "ssg",
            "product_url": PRODUCT_URL,
            "product_name": "ZOTAC GAMING GeForce RTX 5080 16GB",
            "category": "gpu",
            "tags": ["nvidia", "rtx5080", "zotac"],
            "crawl_interval_seconds": 3600,
            "enabled": True,
            "priority": 100,
        },
        {
            "mall_id": "ssg",
            "product_url": OTHER_URL,
            "product_name": "Example GPU Placeholder",
            "category": "gpu",
            "tags": ["nvidia", "rtx5080"],
            "crawl_interval_seconds": 7200,
            "enabled": False,
            "priority": 50,
        },
    ]


def test_seed_creates_new_targets(target_repo: CrawlTargetRepository, tmp_path: Path) -> None:
    entries = load_catalog_entries_from_file(_write_catalog_file(_catalog_payload(), tmp_path))
    result = seed_catalog_entries(target_repo, entries, now=NOW)

    assert result.created == 2
    assert result.updated == 0
    assert result.errors == []

    saved = target_repo.get(TARGET_ID)
    assert saved is not None
    assert saved.product_name == "ZOTAC GAMING GeForce RTX 5080 16GB"
    assert saved.category == "gpu"
    assert saved.tags == ["nvidia", "rtx5080", "zotac"]
    assert saved.priority == 100
    assert saved.external_product_id == "1000832367906"
    assert saved.enabled is True
    assert saved.next_crawl_at == NOW


def test_seed_is_idempotent_on_repeat(target_repo: CrawlTargetRepository, tmp_path: Path) -> None:
    catalog = _write_catalog_file(_catalog_payload(), tmp_path)
    entries = load_catalog_entries_from_file(catalog)
    first = seed_catalog_entries(target_repo, entries, now=NOW)
    second = seed_catalog_entries(target_repo, entries, now=NOW + timedelta(minutes=5))

    assert first.created == 2
    assert first.updated == 0
    assert second.created == 0
    assert second.updated == 2


def test_seed_preserves_operational_state(target_repo: CrawlTargetRepository, tmp_path: Path) -> None:
    entries = load_catalog_entries_from_file(_write_catalog_file(_catalog_payload(), tmp_path))
    seed_catalog_entries(target_repo, entries, now=NOW)

    crawled_at = NOW + timedelta(hours=1)
    next_run = crawled_at + timedelta(seconds=1800)
    target_repo.try_claim(TARGET_ID, "worker-a", crawled_at, lease_seconds=300)
    target_repo.update_after_crawl(
        TARGET_ID,
        result=CrawlerResult(
            status=CrawlerStatus.HTTP_ERROR,
            mall_id="ssg",
            product_url=PRODUCT_URL,
            message="SSG_ACCESS_DENIED",
            http_status_code=403,
        ),
        next_crawl_at=next_run,
        crawled_at=crawled_at,
    )

    updated_payload = _catalog_payload()
    updated_payload[0]["product_name"] = "Updated GPU Name"
    updated_payload[0]["crawl_interval_seconds"] = 900
    reseed = seed_catalog_entries(
        target_repo,
        load_catalog_entries_from_file(_write_catalog_file(updated_payload, tmp_path)),
        now=crawled_at + timedelta(minutes=1),
    )

    saved = target_repo.get(TARGET_ID)
    assert reseed.updated == 2
    assert saved is not None
    assert saved.product_name == "Updated GPU Name"
    assert saved.crawl_interval_seconds == 900
    assert saved.last_crawled_at == crawled_at
    assert saved.next_crawl_at == next_run
    assert saved.last_status == "HTTP_ERROR"
    assert saved.last_error_code == "SSG_ACCESS_DENIED"
    assert saved.last_error_message == "SSG_ACCESS_DENIED"
    assert saved.lease_until is None
    assert saved.lease_owner is None


def test_seed_disabled_target(target_repo: CrawlTargetRepository, tmp_path: Path) -> None:
    entries = load_catalog_entries_from_file(_write_catalog_file(_catalog_payload(), tmp_path))
    seed_catalog_entries(target_repo, entries, now=NOW)

    disabled = target_repo.get(OTHER_TARGET_ID)
    assert disabled is not None
    assert disabled.enabled is False


def test_seed_rejects_invalid_url(target_repo: CrawlTargetRepository, tmp_path: Path) -> None:
    payload = [
        {
            "mall_id": "ssg",
            "product_url": "https://example.com/not-ssg",
            "category": "gpu",
        }
    ]
    result = seed_catalog_entries(
        target_repo,
        load_catalog_entries_from_file(_write_catalog_file(payload, tmp_path)),
        now=NOW,
    )

    assert result.created == 0
    assert result.updated == 0
    assert len(result.errors) == 1
    assert "not an SSG product page" in result.errors[0]


def test_seed_rejects_invalid_mall_id(target_repo: CrawlTargetRepository, tmp_path: Path) -> None:
    payload = [
        {
            "mall_id": "unknown-mall",
            "product_url": PRODUCT_URL,
            "category": "gpu",
        }
    ]
    result = seed_catalog_entries(
        target_repo,
        load_catalog_entries_from_file(_write_catalog_file(payload, tmp_path)),
        now=NOW,
    )

    assert result.created == 0
    assert len(result.errors) == 1
    assert "Unsupported mall" in result.errors[0]


def test_bulk_disable_by_tag(target_repo: CrawlTargetRepository, tmp_path: Path) -> None:
    seed_catalog_entries(
        target_repo,
        load_catalog_entries_from_file(_write_catalog_file(_catalog_payload(), tmp_path)),
        now=NOW,
    )

    updated = bulk_set_enabled(
        target_repo,
        enabled=False,
        filters=BulkUpdateFilter(tag="rtx5080"),
        now=NOW,
    )

    assert updated == 1
    assert target_repo.get(TARGET_ID) is not None
    assert target_repo.get(TARGET_ID).enabled is False
    assert target_repo.get(OTHER_TARGET_ID) is not None
    assert target_repo.get(OTHER_TARGET_ID).enabled is False


def test_bulk_enable_by_mall_and_category(target_repo: CrawlTargetRepository, tmp_path: Path) -> None:
    seed_catalog_entries(
        target_repo,
        load_catalog_entries_from_file(_write_catalog_file(_catalog_payload(), tmp_path)),
        now=NOW,
    )

    bulk_set_enabled(
        target_repo,
        enabled=False,
        filters=BulkUpdateFilter(mall_id="ssg", category="gpu"),
        now=NOW,
    )
    updated = bulk_set_enabled(
        target_repo,
        enabled=True,
        filters=BulkUpdateFilter(mall_id="ssg", category="gpu"),
        now=NOW,
    )

    assert updated == 2
    assert target_repo.get(TARGET_ID).enabled is True
    assert target_repo.get(OTHER_TARGET_ID).enabled is True


def test_ops_view_filters_by_category_and_tag(
    target_repo: CrawlTargetRepository,
    ops_view: CrawlerOperationsView,
    tmp_path: Path,
) -> None:
    seed_catalog_entries(
        target_repo,
        load_catalog_entries_from_file(_write_catalog_file(_catalog_payload(), tmp_path)),
        now=NOW,
    )

    gpu_targets = ops_view.list_targets(
        filters=TargetListFilter(category="gpu"),
        now=NOW,
    )
    rtx_targets = ops_view.list_targets(
        filters=TargetListFilter(tag="zotac"),
        now=NOW,
    )

    assert {item.target_id for item in gpu_targets} == {TARGET_ID, OTHER_TARGET_ID}
    assert [item.target_id for item in rtx_targets] == [TARGET_ID]


def test_list_crawl_targets_json_output(
    target_repo: CrawlTargetRepository,
    target_db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    seed_catalog_entries(
        target_repo,
        load_catalog_entries_from_file(_write_catalog_file(_catalog_payload(), tmp_path)),
        now=NOW,
    )
    monkeypatch.setattr(
        list_crawl_targets,
        "build_operations_view",
        lambda: CrawlerOperationsView(target_repo, target_db),
    )

    exit_code = list_crawl_targets.main(["--category", "gpu", "--json"])
    assert exit_code == 0


def test_seed_gpu_targets_cli(
    target_repo: CrawlTargetRepository,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    catalog_path = _write_catalog_file(_catalog_payload(), tmp_path)
    monkeypatch.setattr(seed_gpu_targets, "get_firestore_client", lambda: target_repo._db)

    exit_code = seed_gpu_targets.main(["--file", str(catalog_path)])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["created"] == 2
    assert output["updated"] == 0
    assert target_repo.get(TARGET_ID) is not None


def test_set_crawl_targets_cli(
    target_repo: CrawlTargetRepository,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    seed_catalog_entries(
        target_repo,
        load_catalog_entries_from_file(_write_catalog_file(_catalog_payload(), tmp_path)),
        now=NOW,
    )
    monkeypatch.setattr(set_crawl_targets, "get_firestore_client", lambda: target_repo._db)

    exit_code = set_crawl_targets.main(
        ["--mall", "ssg", "--tag", "rtx5080", "--enabled", "false"]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["updated"] == 1
    assert target_repo.get(TARGET_ID).enabled is False


def test_list_due_orders_by_priority(target_repo: CrawlTargetRepository) -> None:
    low = target_repo.merge_catalog(
        mall_id="ssg",
        product_url=PRODUCT_URL,
        priority=10,
        now=NOW - timedelta(hours=1),
    )[0]
    high = target_repo.merge_catalog(
        mall_id="ssg",
        product_url=OTHER_URL,
        priority=100,
        enabled=True,
        now=NOW - timedelta(hours=1),
    )[0]
    target_repo.update_after_crawl(
        low.target_id,
        result=CrawlerResult(status=CrawlerStatus.SUCCESS, mall_id="ssg"),
        next_crawl_at=NOW - timedelta(minutes=1),
        crawled_at=NOW - timedelta(hours=1),
    )
    target_repo.update_after_crawl(
        high.target_id,
        result=CrawlerResult(status=CrawlerStatus.SUCCESS, mall_id="ssg"),
        next_crawl_at=NOW - timedelta(minutes=1),
        crawled_at=NOW - timedelta(hours=1),
    )

    due_ids = [item.target_id for item in target_repo.list_due(NOW)]
    assert due_ids == [high.target_id, low.target_id]


def test_existing_target_id_rule_unchanged() -> None:
    assert build_target_id("ssg", PRODUCT_URL) == TARGET_ID


def test_existing_upsert_regression(target_repo: CrawlTargetRepository) -> None:
    target = target_repo.upsert(mall_id="ssg", product_url=PRODUCT_URL, now=NOW)
    assert target.target_id == TARGET_ID
    assert target.priority == DEFAULT_TARGET_PRIORITY
    assert target.tags == []


def _write_catalog_file(payload: list[dict], directory: Path) -> Path:
    path = directory / "gpu_targets.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
