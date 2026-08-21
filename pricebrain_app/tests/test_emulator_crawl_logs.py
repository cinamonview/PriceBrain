"""Firestore Emulator — crawl_logs (Gate C-4)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pricebrain_app.firebase.admin import get_firestore_client
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
from pricebrain_app.tests.emulator_utils import emulator_env, requires_emulator


def _logs_for_job(db, job_id: str) -> list[dict]:
    return [
        doc.to_dict()
        for doc in db.collection(c.CRAWL_LOGS).stream()
        if doc.to_dict().get("job_id") == job_id
    ]


@requires_emulator
def test_c4_01_emulator_crawl_job_running() -> None:
    with emulator_env():
        db = get_firestore_client()
        repo = CrawlRepository(db)
        started_at = datetime(2026, 8, 21, 10, 0, 0, tzinfo=timezone.utc)
        job_id = repo.start_job("SSG", keyword="5080", started_at=started_at)
        job = db.collection(c.CRAWL_JOBS).document(job_id).get()
        assert job.to_dict()["status"] == CRAWL_STATUS_RUNNING


@requires_emulator
def test_c4_02_emulator_crawl_log_job_link() -> None:
    with emulator_env():
        db = get_firestore_client()
        repo = CrawlRepository(db)
        job_id = repo.start_job("SSG")
        log_id = repo.create_log(job_id, "SSG", LOG_LEVEL_INFO, "linked")
        log = db.collection(c.CRAWL_LOGS).document(log_id).get()
        assert log.to_dict()["job_id"] == job_id


@requires_emulator
def test_c4_03_emulator_successful_crawl_batch() -> None:
    with emulator_env():
        db = get_firestore_client()
        product_id = f"em{uuid.uuid4().hex[:10]}"
        raw = {
            "mall": "SSG",
            "product_id": product_id,
            "product_name": "HIT ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB",
            "price": 100000,
            "seller": "히트정보",
            "product_url": f"https://www.ssg.com/item/itemView.ssg?itemId={product_id}",
            "crawled_at": datetime(2026, 8, 19, 10, 0, 0, tzinfo=timezone.utc),
        }
        batch = run_crawl_batch(db, "SSG", [raw], keyword="5080")
        job_id = str(batch["job_id"])
        assert db.collection(c.CRAWL_JOBS).document(job_id).get().to_dict()["status"] == CRAWL_STATUS_COMPLETED
        logs = _logs_for_job(db, job_id)
        assert len(logs) >= 3
        assert all(log["job_id"] == job_id for log in logs)


@requires_emulator
def test_c4_04_emulator_failed_crawl_batch() -> None:
    with emulator_env():
        db = get_firestore_client()
        invalid = {
            "mall": "SSG",
            "product_id": "fail-item",
            "product_name": "Test",
            "seller": "seller",
            "product_url": "https://example.com",
        }
        batch = run_crawl_batch(db, "SSG", [invalid])
        job_id = str(batch["job_id"])
        assert db.collection(c.CRAWL_JOBS).document(job_id).get().to_dict()["status"] == CRAWL_STATUS_FAILED
        logs = _logs_for_job(db, job_id)
        assert any(log["level"] == LOG_LEVEL_ERROR for log in logs)


@requires_emulator
def test_c4_05_emulator_multiple_logs_per_job() -> None:
    with emulator_env():
        db = get_firestore_client()
        valid_id = f"em{uuid.uuid4().hex[:10]}"
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
        batch = run_crawl_batch(db, "SSG", [valid, invalid])
        logs = _logs_for_job(db, str(batch["job_id"]))
        assert len(logs) >= 5
        assert any(log["level"] == LOG_LEVEL_WARN for log in logs)
        assert any(log["level"] == LOG_LEVEL_INFO for log in logs)
