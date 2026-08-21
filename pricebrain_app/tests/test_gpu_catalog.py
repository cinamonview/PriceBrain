"""GPU catalog validation, seeding, dry-run, filters, and statistics tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pricebrain_app.crawler.gpu_catalog import (
    format_rtx_tag,
    gpu_model_label_from_target,
    load_gpu_catalog_file,
    parse_gpu_catalog_item,
)
from pricebrain_app.crawler.operations_view import CrawlerOperationsView, TargetListFilter
from pricebrain_app.crawler.results import CrawlerResult, CrawlerStatus
from pricebrain_app.crawler.target_management import seed_gpu_catalog_file
from pricebrain_app.crawler.target_repository import CrawlTargetRepository
from pricebrain_app.crawler.targets import build_target_id
from pricebrain_app.scripts import list_crawl_targets, seed_gpu_targets
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

PRODUCT_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906"
OTHER_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000123456789"
THIRD_URL = "https://www.ssg.com/item/itemView.ssg?itemId=1000999888777"
TARGET_ID = "ssg_1000832367906"
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


def _valid_entry(**overrides: object) -> dict:
    payload = {
        "mall_id": "ssg",
        "product_url": PRODUCT_URL,
        "external_product_id": "example-rtx5080-001",
        "product_name": "Example RTX 5080",
        "brand": "Example Vendor",
        "category": "gpu",
        "tags": ["rtx5080", "nvidia", "16gb"],
        "priority": 100,
        "enabled": True,
    }
    payload.update(overrides)
    return payload


def _write_catalog(payload: list[dict], directory: Path) -> Path:
    path = directory / "gpu_catalog.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _document_count(db: FakeFirestoreClient) -> int:
    return len(list(db.collection("crawler_targets").stream()))


def test_catalog_validation_accepts_valid_json() -> None:
    item = parse_gpu_catalog_item(_valid_entry())
    assert item.mall_id == "ssg"
    assert item.priority == 100
    assert item.external_product_id == "example-rtx5080-001"


def test_catalog_validation_requires_mall_id() -> None:
    with pytest.raises(ValueError, match="mall_id is required"):
        parse_gpu_catalog_item(_valid_entry(mall_id=""))


def test_catalog_validation_requires_product_url() -> None:
    with pytest.raises(ValueError, match="product_url is required"):
        parse_gpu_catalog_item(_valid_entry(product_url=""))


def test_catalog_validation_rejects_invalid_url() -> None:
    with pytest.raises(ValueError, match="Invalid product URL"):
        parse_gpu_catalog_item(_valid_entry(product_url="not-a-url"))


def test_catalog_validation_rejects_invalid_priority_type() -> None:
    with pytest.raises(ValueError, match="priority must be an integer"):
        parse_gpu_catalog_item(_valid_entry(priority="high"))


def test_catalog_validation_rejects_priority_out_of_range() -> None:
    with pytest.raises(ValueError, match="priority must be between"):
        parse_gpu_catalog_item(_valid_entry(priority=0))


def test_catalog_validation_rejects_invalid_tags() -> None:
    with pytest.raises(ValueError, match="tags must be an array"):
        parse_gpu_catalog_item(_valid_entry(tags="rtx5080"))


def test_catalog_validation_rejects_invalid_enabled() -> None:
    with pytest.raises(ValueError, match="enabled must be a boolean"):
        parse_gpu_catalog_item(_valid_entry(enabled="yes"))


def test_catalog_validation_rejects_invalid_external_product_id() -> None:
    with pytest.raises(ValueError, match="external_product_id"):
        parse_gpu_catalog_item(_valid_entry(external_product_id="bad id!"))


def test_load_gpu_catalog_collects_invalid_entries(tmp_path: Path) -> None:
    path = _write_catalog(
        [
            _valid_entry(),
            _valid_entry(product_url="", mall_id="ssg"),
        ],
        tmp_path,
    )
    items, errors = load_gpu_catalog_file(path)
    assert len(items) == 1
    assert len(errors) == 1


def test_seed_creates_new_targets(target_repo: CrawlTargetRepository, tmp_path: Path) -> None:
    path = _write_catalog([_valid_entry(), _valid_entry(product_url=OTHER_URL, priority=50)], tmp_path)
    result = seed_gpu_catalog_file(target_repo, path, now=NOW)

    assert result.total == 2
    assert result.created == 2
    assert result.updated == 0
    assert result.skipped == 0
    assert result.invalid == 0
    assert target_repo.get(TARGET_ID) is not None


def test_seed_is_idempotent_with_skip(target_repo: CrawlTargetRepository, tmp_path: Path) -> None:
    path = _write_catalog([_valid_entry()], tmp_path)
    first = seed_gpu_catalog_file(target_repo, path, now=NOW)
    second = seed_gpu_catalog_file(target_repo, path, now=NOW + timedelta(minutes=1))

    assert first.created == 1
    assert second.created == 0
    assert second.updated == 0
    assert second.skipped == 1


def test_seed_updates_catalog_fields_only(target_repo: CrawlTargetRepository, tmp_path: Path) -> None:
    path = _write_catalog([_valid_entry()], tmp_path)
    seed_gpu_catalog_file(target_repo, path, now=NOW)
    target_repo.try_claim(TARGET_ID, "worker-a", NOW + timedelta(hours=1), lease_seconds=300)
    target_repo.update_after_crawl(
        TARGET_ID,
        result=CrawlerResult(
            status=CrawlerStatus.HTTP_ERROR,
            mall_id="ssg",
            product_url=PRODUCT_URL,
            message="SSG_ACCESS_DENIED",
        ),
        next_crawl_at=NOW + timedelta(hours=2),
        crawled_at=NOW + timedelta(hours=1),
    )

    updated_path = _write_catalog([_valid_entry(product_name="Updated GPU Name", priority=90)], tmp_path)
    result = seed_gpu_catalog_file(target_repo, updated_path, now=NOW + timedelta(hours=3))
    saved = target_repo.get(TARGET_ID)

    assert result.updated == 1
    assert saved is not None
    assert saved.product_name == "Updated GPU Name"
    assert saved.priority == 90
    assert saved.last_status == "HTTP_ERROR"
    assert saved.next_crawl_at == NOW + timedelta(hours=2)
    assert saved.lease_owner is None


def test_dry_run_does_not_write(target_repo: CrawlTargetRepository, tmp_path: Path) -> None:
    path = _write_catalog([_valid_entry()], tmp_path)
    before = _document_count(target_repo._db)
    result = seed_gpu_catalog_file(target_repo, path, now=NOW, dry_run=True)
    after = _document_count(target_repo._db)

    assert before == after
    assert result.created == 1
    assert len(result.previews) == 1
    assert result.previews[0].action == "create"


def test_filter_category_tag_mall_enabled_priority(
    target_repo: CrawlTargetRepository,
    ops_view: CrawlerOperationsView,
    tmp_path: Path,
) -> None:
    seed_gpu_catalog_file(
        target_repo,
        _write_catalog(
            [
                _valid_entry(),
                _valid_entry(
                    product_url=OTHER_URL,
                    tags=["rtx5070", "nvidia"],
                    priority=50,
                    enabled=False,
                ),
                _valid_entry(
                    product_url=THIRD_URL,
                    tags=["rtx5080", "amd"],
                    priority=95,
                ),
            ],
            tmp_path,
        ),
        now=NOW,
    )

    filtered = ops_view.list_targets(
        filters=TargetListFilter(
            mall_id="ssg",
            category="gpu",
            tag="rtx5080",
            enabled=True,
            priority_min=80,
        ),
        now=NOW,
    )
    assert [item.target_id for item in filtered] == [TARGET_ID, "ssg_1000999888777"]


def test_gpu_catalog_statistics(
    target_repo: CrawlTargetRepository,
    ops_view: CrawlerOperationsView,
    tmp_path: Path,
) -> None:
    seed_gpu_catalog_file(
        target_repo,
        _write_catalog(
            [
                _valid_entry(),
                _valid_entry(product_url=OTHER_URL, tags=["rtx5070", "nvidia"], enabled=False),
            ],
            tmp_path,
        ),
        now=NOW,
    )
    summary = ops_view.summarize_gpu_catalog()
    models = dict(summary.model_counts)

    assert summary.total == 2
    assert summary.enabled == 1
    assert summary.disabled == 1
    assert models["RTX 5080"] == 1
    assert models["RTX 5070"] == 1


def test_list_due_orders_by_priority_desc_then_target_id(target_repo: CrawlTargetRepository) -> None:
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
        now=NOW - timedelta(hours=1),
    )[0]
    for target in (low, high):
        target_repo.update_after_crawl(
            target.target_id,
            result=CrawlerResult(status=CrawlerStatus.SUCCESS, mall_id="ssg"),
            next_crawl_at=NOW - timedelta(minutes=1),
            crawled_at=NOW - timedelta(hours=1),
        )

    due_ids = [item.target_id for item in target_repo.list_due(NOW)]
    assert due_ids == [high.target_id, low.target_id]


def test_bulk_disable_does_not_change_priority_or_interval(
    target_repo: CrawlTargetRepository,
    tmp_path: Path,
) -> None:
    seed_gpu_catalog_file(target_repo, _write_catalog([_valid_entry()], tmp_path), now=NOW)
    before = target_repo.get(TARGET_ID)
    assert before is not None

    updated = target_repo.bulk_set_enabled(
        enabled=False,
        tag="rtx5080",
        now=NOW,
    )
    after = target_repo.get(TARGET_ID)
    assert updated == 1
    assert after is not None
    assert after.enabled is False
    assert after.priority == before.priority
    assert after.crawl_interval_seconds == before.crawl_interval_seconds


def test_seed_gpu_targets_cli_json_output(
    target_repo: CrawlTargetRepository,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    path = _write_catalog([_valid_entry()], tmp_path)
    monkeypatch.setattr(seed_gpu_targets, "get_firestore_client", lambda: target_repo._db)

    exit_code = seed_gpu_targets.main(["--file", str(path), "--json"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["created"] == 1
    assert output["total"] == 1


def test_list_crawl_targets_catalog_stats_cli(
    target_repo: CrawlTargetRepository,
    target_db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    seed_gpu_catalog_file(target_repo, _write_catalog([_valid_entry()], tmp_path), now=NOW)
    monkeypatch.setattr(
        list_crawl_targets,
        "build_operations_view",
        lambda: CrawlerOperationsView(target_repo, target_db),
    )
    exit_code = list_crawl_targets.main(["--catalog-stats"])
    assert exit_code == 0


def test_target_id_rule_regression() -> None:
    assert build_target_id("ssg", PRODUCT_URL) == TARGET_ID


def test_gpu_model_label_from_tags() -> None:
    assert format_rtx_tag("rtx5080") == "RTX 5080"
    assert gpu_model_label_from_target(product_name=None, tags=["rtx5070ti"]) == "RTX 5070 Ti"
