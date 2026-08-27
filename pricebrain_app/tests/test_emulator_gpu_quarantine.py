"""Firestore Emulator — unknown GPU model quarantine E2E (V2 Phase 2.5)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from pricebrain_app.firebase.admin import get_firestore_client
from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.exceptions import UnknownGpuModelError
from pricebrain_app.repository.operational_service import quarantine_unknown_gpu_model
from pricebrain_app.repository.pending_gpu_model_repository import (
    PENDING_STATUS_REVIEW,
)
from pricebrain_app.repository._testing.persist_helpers import save_validated_product
from pricebrain_app.tests.emulator_utils import emulator_env, requires_emulator

CRAWLED_AT = datetime(2026, 8, 26, 10, 0, 0, tzinfo=timezone.utc)


def _raw(
    product_name: str,
    *,
    mall: str,
    product_id: str,
    crawled_at: datetime | None = None,
) -> dict:
    url = (
        f"https://www.11st.co.kr/products/{product_id}"
        if mall == "ELEVENST"
        else f"https://www.ssg.com/item/itemView.ssg?itemId={product_id}"
    )
    return {
        "mall": mall,
        "product_id": product_id,
        "product_name": product_name,
        "price": 1_090_000,
        "seller": "히트정보",
        "product_url": url,
        "crawled_at": crawled_at or CRAWLED_AT,
    }


def _ingest(db, raw: dict) -> dict:
    validated = dict(run_pipeline(dict(raw)))
    try:
        return dict(save_validated_product(db, validated))
    except UnknownGpuModelError as exc:
        quarantine_unknown_gpu_model(db, exc, validated_data=validated)
        return {"status": "quarantined", "gpu_model_id": exc.gpu_model_id}


@requires_emulator
def test_phase25_emulator_unknown_model_quarantined_not_persisted() -> None:
    """Unknown model reaches pending_gpu_models and never products/listings."""
    suffix = uuid.uuid4().hex[:10]
    slug = "rtx_4070"
    with emulator_env():
        db = get_firestore_client()
        db.collection(c.PENDING_GPU_MODELS).document(slug).delete()

        result = _ingest(
            db,
            _raw(
                "GIGABYTE 지포스 RTX 4070 GAMING OC D6X 12GB",
                mall="SSG",
                product_id=f"em{suffix}",
            ),
        )
        assert result == {"status": "quarantined", "gpu_model_id": slug}

        pending = db.collection(c.PENDING_GPU_MODELS).document(slug).get()
        assert pending.exists
        data = pending.to_dict()
        assert data["gpu_model_id"] == slug
        assert data["display_name"] == "RTX 4070"
        assert data["status"] == PENDING_STATUS_REVIEW
        assert data["seen_count"] == 1
        assert data["source_malls"] == ["ssg"]

        # GPU master untouched — no automatic promotion.
        assert not db.collection(c.GPU_MODELS).document(slug).get().exists
        # Nothing landed in the normal listing path.
        assert not db.collection(c.LISTINGS).document(f"SSG_em{suffix}").get().exists

        db.collection(c.PENDING_GPU_MODELS).document(slug).delete()


@requires_emulator
def test_phase25_emulator_multi_mall_duplicates_collapse() -> None:
    """Repeated sightings across malls aggregate into one document."""
    suffix = uuid.uuid4().hex[:8]
    slug = "rx_9060_xt"
    with emulator_env():
        db = get_firestore_client()
        db.collection(c.PENDING_GPU_MODELS).document(slug).delete()

        for index in range(3):
            _ingest(
                db,
                _raw(
                    "SAPPHIRE 라데온 RX 9060 XT NITRO+ 16GB",
                    mall="SSG",
                    product_id=f"em{suffix}s{index}",
                    crawled_at=CRAWLED_AT + timedelta(minutes=index),
                ),
            )
        _ingest(
            db,
            _raw(
                "SAPPHIRE 라데온 RX 9060 XT PULSE 16GB",
                mall="ELEVENST",
                product_id=f"em{suffix}e0",
                crawled_at=CRAWLED_AT + timedelta(minutes=9),
            ),
        )

        data = db.collection(c.PENDING_GPU_MODELS).document(slug).get().to_dict()
        assert data["seen_count"] == 4
        assert data["source_malls"] == ["elevenst", "ssg"]
        assert data["last_seen_at"] > data["first_seen_at"]

        db.collection(c.PENDING_GPU_MODELS).document(slug).delete()


@requires_emulator
def test_phase25_emulator_known_model_unaffected() -> None:
    """Phase 1 regression: a master model still persists normally."""
    suffix = uuid.uuid4().hex[:10]
    with emulator_env():
        db = get_firestore_client()
        result = _ingest(
            db,
            _raw(
                "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB",
                mall="ELEVENST",
                product_id=f"em{suffix}",
            ),
        )
        assert result.get("status") != "quarantined"
        assert result["listing_id"] == f"ELEVENST_em{suffix}"
        assert db.collection(c.LISTINGS).document(result["listing_id"]).get().exists
