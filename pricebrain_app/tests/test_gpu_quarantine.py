"""Unknown GPU model quarantine — V2 Phase 2.5.

Contract under test:
  KNOWN GPU    -> normal persist (products/listings/price_history)
  UNKNOWN GPU  -> pending_gpu_models quarantine, nothing in products/listings
  INVALID DATA -> existing RepositoryValidationError path, no quarantine
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from pricebrain_app.api.deps import get_firestore
from pricebrain_app.main import app
from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.exceptions import (
    RepositoryValidationError,
    UnknownGpuModelError,
)
from pricebrain_app.repository.gpu_master_seed import seed_gpu_master
from pricebrain_app.repository.operational_service import quarantine_unknown_gpu_model
from pricebrain_app.repository.pending_gpu_model_repository import (
    MAX_EXAMPLES,
    PENDING_STATUS_REVIEW,
    PendingGpuModelRepository,
)
from pricebrain_app.repository._testing.persist_helpers import save_validated_product
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

CRAWLED_AT = datetime(2026, 8, 26, 10, 0, 0, tzinfo=timezone.utc)

# Models the parser can generate that Tier-1 master does not contain.
UNKNOWN_RTX_4070 = "GIGABYTE 지포스 RTX 4070 GAMING OC D6X 12GB"
UNKNOWN_RX_9060_XT = "SAPPHIRE 라데온 RX 9060 XT NITRO+ 16GB"
UNKNOWN_ARC_B580 = "ASROCK 인텔 Arc B580 Challenger OC 12GB"
UNKNOWN_RTX_9999 = "ZOTAC 지포스 RTX 9999 PHANTOM 48GB"

# Tier-1 master models (Phase 1).
KNOWN_RTX_5070 = "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB"
KNOWN_RTX_5080 = "ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB"
KNOWN_RX_9070 = "SAPPHIRE 라데온 RX 9070 PULSE OC 16GB"


def _raw(
    product_name: str,
    *,
    mall: str = "SSG",
    product_id: str = "1000832367906",
    price: int = 1_159_000,
    crawled_at: datetime | None = None,
) -> dict:
    base_url = (
        f"https://www.11st.co.kr/products/{product_id}"
        if mall.upper() == "ELEVENST"
        else f"https://www.ssg.com/item/itemView.ssg?itemId={product_id}"
    )
    return {
        "mall": mall,
        "product_id": product_id,
        "product_name": product_name,
        "price": price,
        "seller": "히트정보",
        "product_url": base_url,
        "crawled_at": crawled_at or CRAWLED_AT,
    }


def _ingest(db: FakeFirestoreClient, raw: dict) -> dict:
    """Full pipeline + repository persist, quarantining unknown models."""
    validated = dict(run_pipeline(dict(raw)))
    try:
        return dict(save_validated_product(db, validated))
    except UnknownGpuModelError as exc:
        quarantine_unknown_gpu_model(db, exc, validated_data=validated)
        return {"status": "quarantined", "gpu_model_id": exc.gpu_model_id}


def _count(db: FakeFirestoreClient, collection: str) -> int:
    prefix = f"{collection}/"
    return len(
        [
            path
            for path in db.paths()
            if path.startswith(prefix) and "/" not in path[len(prefix) :]
        ]
    )


@pytest.fixture
def db() -> FakeFirestoreClient:
    client = FakeFirestoreClient()
    seed_gpu_master(client)
    return client


# --- Test 1 — known model persists normally -----------------------------------


def test_known_model_persists_and_is_not_quarantined(db: FakeFirestoreClient) -> None:
    result = _ingest(db, _raw(KNOWN_RTX_5070))

    assert result.get("status") != "quarantined"
    assert result["listing_id"] == "SSG_1000832367906"
    assert _count(db, c.PENDING_GPU_MODELS) == 0
    assert _count(db, c.PRODUCTS) == 1
    assert _count(db, c.LISTINGS) == 1


# --- Test 2 — unknown model is quarantined, not lost --------------------------


def test_unknown_model_is_quarantined_without_data_loss(db: FakeFirestoreClient) -> None:
    result = _ingest(db, _raw(UNKNOWN_RTX_4070))

    assert result == {"status": "quarantined", "gpu_model_id": "rtx_4070"}

    # Not persisted as a normal product.
    assert _count(db, c.PRODUCTS) == 0
    assert _count(db, c.LISTINGS) == 0

    # Not silently discarded either.
    doc = db.get_document(f"{c.PENDING_GPU_MODELS}/rtx_4070")
    assert doc is not None
    assert doc["gpu_model_id"] == "rtx_4070"
    assert doc["display_name"] == "RTX 4070"
    assert doc["gpu_series"] == "RTX"
    assert doc["status"] == PENDING_STATUS_REVIEW
    assert doc["seen_count"] == 1
    assert doc["source_malls"] == ["ssg"]
    assert doc["first_seen_at"] == doc["last_seen_at"]
    assert doc["example_product_urls"] == [
        "https://www.ssg.com/item/itemView.ssg?itemId=1000832367906"
    ]
    assert "RTX 4070" in doc["example_product_names"][0]
    assert doc["detected_by"] == "pipeline.gpu_parser"


def test_quarantine_stores_no_seller_or_price_data(db: FakeFirestoreClient) -> None:
    _ingest(db, _raw(UNKNOWN_RTX_4070))
    doc = db.get_document(f"{c.PENDING_GPU_MODELS}/rtx_4070")

    assert doc is not None
    for forbidden in ("seller", "seller_id", "price", "normalized_seller_name"):
        assert forbidden not in doc


def test_quarantine_does_not_create_gpu_master_entry(db: FakeFirestoreClient) -> None:
    _ingest(db, _raw(UNKNOWN_RTX_9999))

    assert db.get_document(f"{c.GPU_MODELS}/rtx_9999") is None
    assert db.get_document(f"{c.PENDING_GPU_MODELS}/rtx_9999") is not None


# --- Test 3 — duplicate sightings collapse into one document ------------------


def test_repeated_unknown_model_keeps_single_document(db: FakeFirestoreClient) -> None:
    for index in range(10):
        _ingest(
            db,
            _raw(
                UNKNOWN_RTX_4070,
                product_id=f"100000000{index}",
                crawled_at=CRAWLED_AT + timedelta(minutes=index),
            ),
        )

    assert _count(db, c.PENDING_GPU_MODELS) == 1
    doc = db.get_document(f"{c.PENDING_GPU_MODELS}/rtx_4070")
    assert doc is not None
    assert doc["seen_count"] == 10
    assert doc["last_seen_at"] >= doc["first_seen_at"]
    assert len(doc["example_product_urls"]) == MAX_EXAMPLES


def test_board_partner_variants_converge_on_one_canonical_slug(
    db: FakeFirestoreClient,
) -> None:
    variants = (
        "COLORFUL 지포스 RTX4070 iGame Ultra W 12GB",
        "GIGABYTE 지포스 RTX 4070 GAMING OC 12GB",
        "ASUS 지포스 RTX 4070 DUAL OC 12GB",
        "MSI GeForce RTX 4070 VENTUS 2X 12GB",
    )
    for index, name in enumerate(variants):
        _ingest(db, _raw(name, product_id=f"200000000{index}"))

    assert _count(db, c.PENDING_GPU_MODELS) == 1
    doc = db.get_document(f"{c.PENDING_GPU_MODELS}/rtx_4070")
    assert doc is not None
    assert doc["seen_count"] == len(variants)


def test_existing_review_status_survives_new_sightings(db: FakeFirestoreClient) -> None:
    repo = PendingGpuModelRepository(db)
    repo.record_unknown_model(gpu_model_id="rtx_4070", mall_id="ssg")
    db._data[f"{c.PENDING_GPU_MODELS}/rtx_4070"]["status"] = "REJECTED"

    repo.record_unknown_model(gpu_model_id="rtx_4070", mall_id="ssg")

    doc = db.get_document(f"{c.PENDING_GPU_MODELS}/rtx_4070")
    assert doc is not None
    assert doc["status"] == "REJECTED"
    assert doc["seen_count"] == 2


# --- Test 4 — multi-mall sightings merge --------------------------------------


def test_same_unknown_model_from_two_malls_merges(db: FakeFirestoreClient) -> None:
    _ingest(db, _raw(UNKNOWN_RTX_4070, mall="SSG", product_id="1000832367906"))
    _ingest(db, _raw(UNKNOWN_RTX_4070, mall="ELEVENST", product_id="8083397777"))

    assert _count(db, c.PENDING_GPU_MODELS) == 1
    doc = db.get_document(f"{c.PENDING_GPU_MODELS}/rtx_4070")
    assert doc is not None
    assert doc["seen_count"] == 2
    # Canonical lowercase mall_id policy (Phase 2).
    assert doc["source_malls"] == ["elevenst", "ssg"]
    assert len(doc["example_product_urls"]) == 2


# --- Test 5 — distinct unknown models stay isolated ---------------------------


@pytest.mark.parametrize(
    ("product_name", "expected_slug", "expected_display"),
    [
        (UNKNOWN_RTX_4070, "rtx_4070", "RTX 4070"),
        (UNKNOWN_RX_9060_XT, "rx_9060_xt", "RX 9060 XT"),
        (UNKNOWN_ARC_B580, "arc_b580", "Arc B580"),
        (UNKNOWN_RTX_9999, "rtx_9999", "RTX 9999"),
    ],
)
def test_each_unknown_model_gets_its_own_document(
    db: FakeFirestoreClient,
    product_name: str,
    expected_slug: str,
    expected_display: str,
) -> None:
    result = _ingest(db, _raw(product_name))

    assert result["gpu_model_id"] == expected_slug
    doc = db.get_document(f"{c.PENDING_GPU_MODELS}/{expected_slug}")
    assert doc is not None
    assert doc["display_name"] == expected_display


def test_distinct_unknown_models_do_not_collide(db: FakeFirestoreClient) -> None:
    for index, name in enumerate(
        (UNKNOWN_RTX_4070, UNKNOWN_RX_9060_XT, UNKNOWN_ARC_B580)
    ):
        _ingest(db, _raw(name, product_id=f"300000000{index}"))

    assert _count(db, c.PENDING_GPU_MODELS) == 3
    for slug in ("rtx_4070", "rx_9060_xt", "arc_b580"):
        doc = db.get_document(f"{c.PENDING_GPU_MODELS}/{slug}")
        assert doc is not None
        assert doc["seen_count"] == 1


# --- Test 6 — invalid data keeps the existing validation failure path ---------


def test_negative_price_is_validation_failure_not_quarantine(
    db: FakeFirestoreClient,
) -> None:
    validated = dict(run_pipeline(_raw(KNOWN_RTX_5070)))
    validated["price"] = -1000

    with pytest.raises(RepositoryValidationError) as exc_info:
        save_validated_product(db, validated)

    assert not isinstance(exc_info.value, UnknownGpuModelError)
    assert exc_info.value.field == "price"
    assert _count(db, c.PENDING_GPU_MODELS) == 0


def test_missing_board_partner_is_validation_failure_not_quarantine(
    db: FakeFirestoreClient,
) -> None:
    validated = dict(run_pipeline(_raw(KNOWN_RTX_5070)))
    validated["board_partner_id"] = "NOTAPARTNER"

    with pytest.raises(RepositoryValidationError) as exc_info:
        save_validated_product(db, validated)

    assert not isinstance(exc_info.value, UnknownGpuModelError)
    assert exc_info.value.field == "board_partner_id"
    assert _count(db, c.PENDING_GPU_MODELS) == 0


def test_broken_gpu_master_reference_is_not_quarantined(
    db: FakeFirestoreClient,
) -> None:
    """A seeded model with a dangling vendor is master corruption, not an unknown model."""
    db.collection(c.GPU_MODELS).document("rtx_4070").set(
        {
            "slug": "rtx_4070",
            "vendor_id": "nonexistent_vendor",
            "family_id": "nonexistent_family",
        }
    )

    with pytest.raises(RepositoryValidationError) as exc_info:
        save_validated_product(db, dict(run_pipeline(_raw(UNKNOWN_RTX_4070))))

    assert not isinstance(exc_info.value, UnknownGpuModelError)
    assert _count(db, c.PENDING_GPU_MODELS) == 0


def test_missing_seller_id_is_validation_failure_not_quarantine(
    db: FakeFirestoreClient,
) -> None:
    validated = dict(run_pipeline(_raw(UNKNOWN_RTX_4070)))
    validated["seller_id"] = None

    with pytest.raises(RepositoryValidationError) as exc_info:
        save_validated_product(db, validated)

    # validate_for_persist runs before reference resolution, so field checks win.
    assert not isinstance(exc_info.value, UnknownGpuModelError)
    assert _count(db, c.PENDING_GPU_MODELS) == 0


# --- Test 7/8 — Phase 1 regression -------------------------------------------


@pytest.mark.parametrize(
    "product_name",
    [KNOWN_RTX_5070, KNOWN_RTX_5080, KNOWN_RX_9070],
)
def test_phase1_models_still_persist(
    db: FakeFirestoreClient, product_name: str
) -> None:
    result = _ingest(db, _raw(product_name))

    assert result.get("status") != "quarantined"
    assert _count(db, c.PENDING_GPU_MODELS) == 0


@pytest.mark.parametrize(
    ("partner", "product_name"),
    [
        ("GIGABYTE", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB"),
        ("ZOTAC", "ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB"),
        ("SAPPHIRE", "SAPPHIRE 라데온 RX 9070 PULSE OC 16GB"),
        ("XFX", "XFX 라데온 RX 9070 SWFT OC 16GB"),
    ],
)
def test_board_partner_regression_still_persists(
    db: FakeFirestoreClient, partner: str, product_name: str
) -> None:
    result = _ingest(db, _raw(product_name))

    assert result.get("status") != "quarantined"
    assert _count(db, c.PENDING_GPU_MODELS) == 0
    product = db.get_document(f"{c.PRODUCTS}/{result['product_id']}")
    assert product is not None
    assert product["board_partner_id"] == partner


# --- API contract -------------------------------------------------------------


def test_api_returns_202_quarantined_for_unknown_model(
    ingest_auth_env: dict[str, str],
) -> None:
    fake_db = FakeFirestoreClient()
    seed_gpu_master(fake_db)

    def override_get_firestore():
        yield fake_db

    app.dependency_overrides[get_firestore] = override_get_firestore
    try:
        client = TestClient(app)
        response = client.post(
            "/internal/ingest/listing",
            json=_raw(UNKNOWN_RTX_4070) | {"crawled_at": CRAWLED_AT.isoformat()},
            headers=ingest_auth_env,
        )
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "quarantined"
        assert body["gpu_model_id"] == "rtx_4070"
        assert fake_db.get_document(f"{c.PENDING_GPU_MODELS}/rtx_4070") is not None
        assert _count(fake_db, c.PRODUCTS) == 0
        assert _count(fake_db, c.LISTINGS) == 0
    finally:
        app.dependency_overrides.clear()


def test_api_still_returns_200_ok_for_known_model(
    ingest_auth_env: dict[str, str],
) -> None:
    fake_db = FakeFirestoreClient()
    seed_gpu_master(fake_db)

    def override_get_firestore():
        yield fake_db

    app.dependency_overrides[get_firestore] = override_get_firestore
    try:
        client = TestClient(app)
        response = client.post(
            "/internal/ingest/listing",
            json=_raw(KNOWN_RTX_5070) | {"crawled_at": CRAWLED_AT.isoformat()},
            headers=ingest_auth_env,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert _count(fake_db, c.PENDING_GPU_MODELS) == 0
    finally:
        app.dependency_overrides.clear()


def test_api_still_returns_422_for_non_gpu_model_validation_failure(
    ingest_auth_env: dict[str, str],
) -> None:
    fake_db = FakeFirestoreClient()

    def override_get_firestore():
        yield fake_db

    app.dependency_overrides[get_firestore] = override_get_firestore
    try:
        client = TestClient(app)
        response = client.post(
            "/internal/ingest/listing",
            json={"mall": "SSG"},
            headers=ingest_auth_env,
        )
        assert response.status_code == 422
        assert _count(fake_db, c.PENDING_GPU_MODELS) == 0
    finally:
        app.dependency_overrides.clear()


# --- Batch path (the Search Batch pre-gate) -----------------------------------


def test_batch_quarantines_unknown_model_without_failing_the_job(
    db: FakeFirestoreClient,
) -> None:
    from pricebrain_app.runner import run_crawl_batch

    batch = run_crawl_batch(
        db,
        "SSG",
        [
            _raw(KNOWN_RTX_5070, product_id="1000000001"),
            _raw(UNKNOWN_RTX_4070, product_id="1000000002"),
            _raw(UNKNOWN_RX_9060_XT, product_id="1000000003"),
        ],
    )

    assert batch["quarantined"] == 2
    assert batch["validation_failures"] == 0
    assert len(batch["results"]) == 1
    job = db.get_document(f"{c.CRAWL_JOBS}/{batch['job_id']}")
    assert job is not None
    assert job["status"] != "FAILED"
    assert _count(db, c.PENDING_GPU_MODELS) == 2


def test_batch_of_only_unknown_models_still_completes(db: FakeFirestoreClient) -> None:
    from pricebrain_app.runner import run_crawl_batch

    batch = run_crawl_batch(
        db,
        "SSG",
        [_raw(UNKNOWN_RTX_9999, product_id="1000000009")],
    )

    assert batch["quarantined"] == 1
    assert batch["results"] == []
    assert _count(db, c.PRODUCTS) == 0


# --- Repository unit behaviour ------------------------------------------------


def test_record_unknown_model_requires_slug(db: FakeFirestoreClient) -> None:
    with pytest.raises(ValueError):
        PendingGpuModelRepository(db).record_unknown_model(gpu_model_id="")


def test_record_unknown_model_is_idempotent_on_examples(
    db: FakeFirestoreClient,
) -> None:
    repo = PendingGpuModelRepository(db)
    for _ in range(3):
        repo.record_unknown_model(
            gpu_model_id="rtx_4070",
            mall_id="ssg",
            product_name="RTX 4070",
            product_url="https://example.com/a",
        )

    doc = repo.get("rtx_4070")
    assert doc is not None
    assert doc["seen_count"] == 3
    assert doc["example_product_urls"] == ["https://example.com/a"]
    assert doc["example_product_names"] == ["RTX 4070"]


def test_unknown_gpu_model_error_is_a_repository_validation_error() -> None:
    """Existing `except RepositoryValidationError` consumers must keep working."""
    exc = UnknownGpuModelError("nope", gpu_model_id="rtx_4070")

    assert isinstance(exc, RepositoryValidationError)
    assert exc.field == "gpu_model_id"
    assert exc.gpu_model_id == "rtx_4070"
