"""Operational persistence tests — crawl_jobs / validation_logs (Gate C-2)."""

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
    CrawlRepository,
    build_crawl_job_id,
)
from pricebrain_app.repository.operational_service import persist_pipeline_validation_failure
from pricebrain_app.repository.validation_repository import (
    VALIDATION_STATUS_FAIL,
    ValidationRepository,
)
from pricebrain_app.runner import run_crawl_batch
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient


@pytest.fixture
def started_at() -> datetime:
    return datetime(2026, 8, 20, 9, 30, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_raw_product() -> dict:
    product_id = f"c2{uuid.uuid4().hex[:10]}"
    return {
        "mall": "SSG",
        "product_id": product_id,
        "product_name": "HIT ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB",
        "price": 100000,
        "seller": "히트정보",
        "product_url": f"https://www.ssg.com/item/itemView.ssg?itemId={product_id}",
        "image_url": f"https://sitem.ssgcdn.com/itemimage/{product_id}.jpg",
        "crawled_at": datetime(2026, 8, 19, 10, 0, 0, tzinfo=timezone.utc),
    }


def test_c2_01_start_job(fake_db: FakeFirestoreClient, started_at: datetime) -> None:
    repo = CrawlRepository(fake_db)
    job_id = repo.start_job("SSG", keyword="RTX 5080", started_at=started_at)
    assert job_id == build_crawl_job_id("SSG", started_at)
    stored = fake_db.get_document(f"{c.CRAWL_JOBS}/{job_id}")
    assert stored is not None
    assert stored["status"] == CRAWL_STATUS_RUNNING
    assert stored["mall_id"] == "SSG"
    assert stored["keyword"] == "RTX 5080"
    assert stored["started_at"] == started_at


def test_c2_02_complete_job(fake_db: FakeFirestoreClient, started_at: datetime) -> None:
    repo = CrawlRepository(fake_db)
    completed_at = datetime(2026, 8, 20, 9, 45, 0, tzinfo=timezone.utc)
    job_id = repo.start_job("SSG", started_at=started_at)
    repo.complete_job(job_id, completed_at=completed_at)
    stored = fake_db.get_document(f"{c.CRAWL_JOBS}/{job_id}")
    assert stored is not None
    assert stored["status"] == CRAWL_STATUS_COMPLETED
    assert stored["completed_at"] == completed_at


def test_c2_03_fail_job(fake_db: FakeFirestoreClient, started_at: datetime) -> None:
    repo = CrawlRepository(fake_db)
    completed_at = datetime(2026, 8, 20, 9, 46, 0, tzinfo=timezone.utc)
    job_id = repo.start_job("SSG", started_at=started_at)
    repo.fail_job(job_id, "network timeout", completed_at=completed_at)
    stored = fake_db.get_document(f"{c.CRAWL_JOBS}/{job_id}")
    assert stored is not None
    assert stored["status"] == CRAWL_STATUS_FAILED
    assert stored["error_message"] == "network timeout"
    assert stored["completed_at"] == completed_at


def test_c2_04_crawl_jobs_schema(fake_db: FakeFirestoreClient, started_at: datetime) -> None:
    repo = CrawlRepository(fake_db)
    job_id = repo.start_job("SSG", keyword="5080", started_at=started_at)
    repo.complete_job(job_id, completed_at=datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc))
    stored = fake_db.get_document(f"{c.CRAWL_JOBS}/{job_id}")
    assert stored is not None
    for field in ("job_id", "mall_id", "status", "started_at", "completed_at"):
        assert field in stored
    assert stored["job_id"] == job_id


def test_c2_05_validation_failure_persist(fake_db: FakeFirestoreClient) -> None:
    from pricebrain_app.pipeline.exceptions import PipelineValidationError

    exc = PipelineValidationError("price is required", field="price")
    log_id = persist_pipeline_validation_failure(
        fake_db,
        exc,
        source="pipeline",
        raw_data={"mall": "SSG", "product_id": "123", "product_name": "Test GPU"},
    )
    stored = fake_db.get_document(f"{c.VALIDATION_LOGS}/{log_id}")
    assert stored is not None
    assert stored["status"] == VALIDATION_STATUS_FAIL
    assert stored["source"] == "pipeline"
    assert stored["details"]["field"] == "price"
    assert stored["details"]["mall_id"] == "SSG"
    assert stored["details"]["product_id"] == "123"


def test_c2_06_validation_logs_schema(fake_db: FakeFirestoreClient) -> None:
    repo = ValidationRepository(fake_db)
    created_at = datetime(2026, 8, 20, 11, 0, 0, tzinfo=timezone.utc)
    log_id = repo.log_validation(
        "pipeline",
        VALIDATION_STATUS_FAIL,
        {"message": "test failure"},
        created_at=created_at,
    )
    stored = fake_db.get_document(f"{c.VALIDATION_LOGS}/{log_id}")
    assert stored is not None
    assert stored["log_id"] == log_id
    assert stored["source"] == "pipeline"
    assert stored["status"] == VALIDATION_STATUS_FAIL
    assert stored["created_at"] == created_at
    assert stored["details"]["message"] == "test failure"


def test_c2_09_crawl_batch_integration(
    fake_db: FakeFirestoreClient, sample_raw_product: dict
) -> None:
    batch = run_crawl_batch(fake_db, "SSG", [sample_raw_product], keyword="5080")
    job_id = str(batch["job_id"])
    assert batch["validation_failures"] == 0
    assert len(batch["results"]) == 1

    job = fake_db.get_document(f"{c.CRAWL_JOBS}/{job_id}")
    assert job is not None
    assert job["status"] == CRAWL_STATUS_COMPLETED
    assert fake_db.get_document(f"{c.LISTINGS}/{batch['results'][0]['listing_id']}") is not None


def test_c2_10_validation_failure_batch_integration(
    fake_db: FakeFirestoreClient, sample_raw_product: dict
) -> None:
    invalid = dict(sample_raw_product)
    invalid.pop("price")
    batch = run_crawl_batch(fake_db, "SSG", [invalid], keyword="5080")
    job_id = str(batch["job_id"])
    assert batch["validation_failures"] == 1
    assert batch["results"] == []

    job = fake_db.get_document(f"{c.CRAWL_JOBS}/{job_id}")
    assert job is not None
    assert job["status"] == CRAWL_STATUS_FAILED

    validation_paths = [
        path for path in fake_db.paths() if path.startswith(f"{c.VALIDATION_LOGS}/")
    ]
    assert len(validation_paths) == 1
    log = fake_db.get_document(validation_paths[0])
    assert log is not None
    assert log["status"] == VALIDATION_STATUS_FAIL
    assert log["details"]["field"] == "price"


def test_c2_09_mixed_batch_completes_with_partial_failures(
    fake_db: FakeFirestoreClient, sample_raw_product: dict
) -> None:
    invalid = dict(sample_raw_product)
    invalid["product_id"] = f"bad{uuid.uuid4().hex[:8]}"
    invalid.pop("price")
    batch = run_crawl_batch(fake_db, "SSG", [sample_raw_product, invalid], keyword="5080")
    job = fake_db.get_document(f"{c.CRAWL_JOBS}/{batch['job_id']}")
    assert job is not None
    assert job["status"] == CRAWL_STATUS_COMPLETED
    assert batch["validation_failures"] == 1
    assert len(batch["results"]) == 1
