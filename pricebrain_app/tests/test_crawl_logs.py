"""Crawl logs persistence tests — Gate C-4."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.crawl_repository import (
    CRAWL_STATUS_COMPLETED,
    CRAWL_STATUS_FAILED,
    CRAWL_STATUS_RUNNING,
    LOG_LEVEL_ERROR,
    LOG_LEVEL_INFO,
    LOG_LEVEL_WARN,
    CrawlRepository,
)
from pricebrain_app.runner import run_crawl_batch
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient


def _logs_for_job(db: FakeFirestoreClient, job_id: str) -> list[dict]:
    logs: list[dict] = []
    prefix = f"{c.CRAWL_LOGS}/"
    for path in db.paths():
        if not path.startswith(prefix):
            continue
        doc = db.get_document(path)
        if doc and doc.get("job_id") == job_id:
            logs.append(doc)
    return sorted(logs, key=lambda item: item["created_at"])


@pytest.fixture
def started_at() -> datetime:
    return datetime(2026, 8, 21, 9, 0, 0, tzinfo=timezone.utc)


def test_crawl_log_create(fake_db: FakeFirestoreClient, started_at: datetime) -> None:
    repo = CrawlRepository(fake_db)
    job_id = repo.start_job("SSG", started_at=started_at)
    log_id = repo.create_log(
        job_id,
        "SSG",
        LOG_LEVEL_INFO,
        "Crawl job started",
        created_at=started_at,
    )
    stored = fake_db.get_document(f"{c.CRAWL_LOGS}/{log_id}")
    assert stored is not None
    assert stored["log_id"] == log_id
    assert stored["job_id"] == job_id
    assert stored["mall_id"] == "SSG"
    assert stored["level"] == LOG_LEVEL_INFO
    assert stored["message"] == "Crawl job started"
    assert stored["created_at"] == started_at


def test_crawl_log_job_link(fake_db: FakeFirestoreClient, started_at: datetime) -> None:
    repo = CrawlRepository(fake_db)
    job_id = repo.start_job("SSG", started_at=started_at)
    repo.create_log(job_id, "SSG", LOG_LEVEL_INFO, "linked log", created_at=started_at)
    logs = _logs_for_job(fake_db, job_id)
    assert len(logs) == 1
    assert logs[0]["job_id"] == job_id


def test_crawl_log_success(fake_db: FakeFirestoreClient, started_at: datetime) -> None:
    repo = CrawlRepository(fake_db)
    job_id = repo.start_job("SSG", started_at=started_at)
    repo.create_log(job_id, "SSG", LOG_LEVEL_INFO, "Crawl job completed")
    repo.complete_job(job_id)
    job = fake_db.get_document(f"{c.CRAWL_JOBS}/{job_id}")
    assert job is not None
    assert job["status"] == CRAWL_STATUS_COMPLETED
    assert any(log["level"] == LOG_LEVEL_INFO for log in _logs_for_job(fake_db, job_id))


def test_crawl_log_failure(fake_db: FakeFirestoreClient, started_at: datetime) -> None:
    repo = CrawlRepository(fake_db)
    job_id = repo.start_job("SSG", started_at=started_at)
    repo.create_log(job_id, "SSG", LOG_LEVEL_ERROR, "Crawl job failed: timeout")
    repo.fail_job(job_id, "timeout")
    job = fake_db.get_document(f"{c.CRAWL_JOBS}/{job_id}")
    assert job is not None
    assert job["status"] == CRAWL_STATUS_FAILED
    logs = _logs_for_job(fake_db, job_id)
    assert any(log["level"] == LOG_LEVEL_ERROR for log in logs)


def test_crawl_job_log_lifecycle(fake_db: FakeFirestoreClient) -> None:
    product_id = f"c4{uuid.uuid4().hex[:10]}"
    raw = {
        "mall": "SSG",
        "product_id": product_id,
        "product_name": "HIT ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB",
        "price": 100000,
        "seller": "히트정보",
        "product_url": f"https://www.ssg.com/item/itemView.ssg?itemId={product_id}",
        "crawled_at": datetime(2026, 8, 19, 10, 0, 0, tzinfo=timezone.utc),
    }
    batch = run_crawl_batch(fake_db, "SSG", [raw], keyword="5080")
    job_id = str(batch["job_id"])
    job = fake_db.get_document(f"{c.CRAWL_JOBS}/{job_id}")
    assert job is not None
    assert job["status"] == CRAWL_STATUS_COMPLETED
    logs = _logs_for_job(fake_db, job_id)
    assert len(logs) >= 3
    assert logs[0]["message"].startswith("Crawl job started")
    assert any("Product processed" in log["message"] for log in logs)
    assert any(log["message"] == "Crawl job completed" for log in logs)


def test_crawl_batch_logs(fake_db: FakeFirestoreClient) -> None:
    valid_id = f"c4{uuid.uuid4().hex[:10]}"
    invalid_id = f"bad{uuid.uuid4().hex[:8]}"
    valid = {
        "mall": "SSG",
        "product_id": valid_id,
        "product_name": "HIT ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB",
        "price": 100000,
        "seller": "히트정보",
        "product_url": f"https://www.ssg.com/item/itemView.ssg?itemId={valid_id}",
        "crawled_at": datetime(2026, 8, 19, 10, 0, 0, tzinfo=timezone.utc),
    }
    invalid = dict(valid)
    invalid["product_id"] = invalid_id
    invalid.pop("price")

    batch = run_crawl_batch(fake_db, "SSG", [valid, invalid], keyword="5080")
    job_id = str(batch["job_id"])
    logs = _logs_for_job(fake_db, job_id)
    assert len(logs) >= 4
    assert all(log["job_id"] == job_id for log in logs)
    assert any(log["level"] == LOG_LEVEL_WARN for log in logs)
    assert fake_db.get_document(f"{c.CRAWL_JOBS}/{job_id}")["status"] == CRAWL_STATUS_COMPLETED


def test_crawl_batch_all_failed_logs_and_job(
    fake_db: FakeFirestoreClient,
) -> None:
    invalid = {
        "mall": "SSG",
        "product_id": "missing-price",
        "product_name": "Test",
        "seller": "seller",
        "product_url": "https://example.com",
    }
    batch = run_crawl_batch(fake_db, "SSG", [invalid])
    job_id = str(batch["job_id"])
    assert fake_db.get_document(f"{c.CRAWL_JOBS}/{job_id}")["status"] == CRAWL_STATUS_FAILED
    logs = _logs_for_job(fake_db, job_id)
    assert any(log["level"] == LOG_LEVEL_ERROR for log in logs)
    assert any(log["level"] == LOG_LEVEL_WARN for log in logs)
