"""Firestore Emulator — operational persistence (Gate C-2)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pricebrain_app.firebase.admin import get_firestore_client
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.crawl_repository import CRAWL_STATUS_COMPLETED, CRAWL_STATUS_RUNNING
from pricebrain_app.repository.validation_repository import VALIDATION_STATUS_FAIL
from pricebrain_app.runner import run_crawl_batch
from pricebrain_app.tests.emulator_utils import emulator_env, requires_emulator


@requires_emulator
def test_emulator_crawl_job_lifecycle() -> None:
    with emulator_env():
        db = get_firestore_client()
        from pricebrain_app.repository.crawl_repository import CrawlRepository

        started_at = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
        repo = CrawlRepository(db)
        job_id = repo.start_job("SSG", keyword="5080", started_at=started_at)
        running = db.collection(c.CRAWL_JOBS).document(job_id).get()
        assert running.exists
        assert running.to_dict()["status"] == CRAWL_STATUS_RUNNING

        repo.complete_job(job_id, completed_at=datetime(2026, 8, 20, 12, 5, 0, tzinfo=timezone.utc))
        completed = db.collection(c.CRAWL_JOBS).document(job_id).get()
        assert completed.to_dict()["status"] == CRAWL_STATUS_COMPLETED


@requires_emulator
def test_emulator_crawl_batch_and_validation_log() -> None:
    with emulator_env():
        db = get_firestore_client()
        product_id = f"em{uuid.uuid4().hex[:10]}"
        valid = {
            "mall": "SSG",
            "product_id": product_id,
            "product_name": "HIT ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB",
            "price": 100000,
            "seller": "히트정보",
            "product_url": f"https://www.ssg.com/item/itemView.ssg?itemId={product_id}",
            "crawled_at": datetime(2026, 8, 19, 10, 0, 0, tzinfo=timezone.utc),
        }
        invalid = dict(valid)
        invalid["product_id"] = f"bad{uuid.uuid4().hex[:8]}"
        invalid.pop("price")

        batch = run_crawl_batch(db, "SSG", [valid, invalid], keyword="5080")
        job = db.collection(c.CRAWL_JOBS).document(str(batch["job_id"])).get()
        assert job.to_dict()["status"] == CRAWL_STATUS_COMPLETED
        assert len(batch["results"]) == 1

        logs = list(db.collection(c.VALIDATION_LOGS).stream())
        assert any(doc.to_dict()["status"] == VALIDATION_STATUS_FAIL for doc in logs)
