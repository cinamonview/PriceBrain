"""Phase 13 — single-item identity lookup and persist bypass guards."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from pricebrain_app.api.deps import get_firestore
from pricebrain_app.main import app
from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.gpu_master_seed import seed_gpu_master
from pricebrain_app.repository.persist_service import (
    IdentityReviewBlockedError,
    persist_validated_product,
)
from pricebrain_app.repository._testing.persist_helpers import save_validated_product
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

CRAWLED_AT = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def db() -> FakeFirestoreClient:
    client = FakeFirestoreClient()
    seed_gpu_master(client)
    return client


def _item(
    product_id: str,
    product_name: str,
    *,
    price: int = 1_500_000,
    seller: str = "테스트셀러",
    manufacturer_part_number: str | None = None,
) -> dict:
    payload = {
        "mall": "ELEVENST",
        "product_id": product_id,
        "product_name": product_name,
        "price": price,
        "seller": seller,
        "product_url": f"https://www.11st.co.kr/products/{product_id}",
        "crawled_at": CRAWLED_AT.isoformat(),
    }
    if manufacturer_part_number:
        payload["manufacturer_part_number"] = manufacturer_part_number
    return payload


def _persist_raw(db: FakeFirestoreClient, raw: dict) -> dict:
    validated = run_pipeline(dict(raw))
    return persist_validated_product(
        db,
        validated,
        external_product_id=str(raw["product_id"]),
        product_name=str(raw["product_name"]),
    )


def _count_listings(db: FakeFirestoreClient) -> int:
    marker = f"/{c.PRICE_HISTORY}/"
    return sum(
        1
        for path in db.paths()
        if path.startswith(f"{c.LISTINGS}/") and marker not in path
    )


def _seed_existing(db: FakeFirestoreClient, raw: dict) -> str:
    validated = run_pipeline(dict(raw))
    result = save_validated_product(db, dict(validated))
    return str(result["product_id"])


def test_phase13_a_no_existing_product_persists(db: FakeFirestoreClient) -> None:
    raw = _item("9800000001", "ZOTAC GAMING 지포스 RTX 5080 SOLID CORE OC D7 16GB")
    result = _persist_raw(db, raw)
    assert result["product_id"] == "ZOTAC-RTX5080-SOLIDCORE-16GB"
    assert db.collection(c.PRODUCTS).document(result["product_id"]).get().exists


def test_phase13_b_same_sku_reingest_persists(db: FakeFirestoreClient) -> None:
    raw = _item("9800000002", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB")
    _seed_existing(db, raw)
    listings_before = _count_listings(db)
    result = _persist_raw(
        db,
        _item("9800000003", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB", seller="다른셀러"),
    )
    assert result["product_id"] == "ZOTAC-RTX5080-SOLIDOC-16GB"
    assert _count_listings(db) == listings_before + 1


def test_phase13_c_stored_black_new_white_blocked(db: FakeFirestoreClient) -> None:
    _seed_existing(
        db,
        _item("9800000010", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB"),
    )
    products_before = sum(1 for p in db.paths() if p.startswith(f"{c.PRODUCTS}/"))
    listings_before = _count_listings(db)
    with pytest.raises(IdentityReviewBlockedError) as excinfo:
        _persist_raw(
            db,
            _item(
                "9800000011",
                "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
            ),
        )
    assert excinfo.value.canonical_product_id == "ZOTAC-RTX5080-SOLIDOC-16GB"
    assert sum(1 for p in db.paths() if p.startswith(f"{c.PRODUCTS}/")) == products_before
    assert _count_listings(db) == listings_before


def test_phase13_c_stored_black_new_white_api_blocked(
    db: FakeFirestoreClient,
    ingest_auth_env: dict[str, str],
) -> None:
    _seed_existing(
        db,
        _item("9800000012", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB"),
    )

    def override_get_firestore():
        yield db

    app.dependency_overrides[get_firestore] = override_get_firestore
    try:
        response = TestClient(app).post(
            "/internal/ingest/listing",
            json=_item(
                "9800000013",
                "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
            ),
            headers=ingest_auth_env,
        )
        assert response.status_code == 409
        body = response.json()
        assert body["status"] == "identity_review_blocked"
        assert _count_listings(db) == 1
    finally:
        app.dependency_overrides.clear()


def test_phase13_d_mpn_mismatch_against_stored(
    db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pricebrain_app.pipeline import product_matcher

    real_build = product_matcher.build_canonical_product_id

    def _shared_canonical_without_mpn(data: dict) -> str | None:
        stripped = {
            key: value
            for key, value in data.items()
            if key != "manufacturer_part_number"
        }
        return real_build(stripped)

    monkeypatch.setattr(
        product_matcher,
        "build_canonical_product_id",
        _shared_canonical_without_mpn,
    )

    _seed_existing(
        db,
        _item(
            "9800000020",
            "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB",
            manufacturer_part_number="GV-N5070A",
        ),
    )
    with pytest.raises(IdentityReviewBlockedError):
        _persist_raw(
            db,
            _item(
                "9800000021",
                "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB 피씨디렉트",
                manufacturer_part_number="GV-N5070B",
            ),
        )


def test_phase13_e_board_partner_separate_products(db: FakeFirestoreClient) -> None:
    gigabyte = _item("9800000030", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")
    manli = _item("9800000031", "MANLI 지포스 RTX 5070 GAMING OC D7 12GB")
    gid = _persist_raw(db, gigabyte)["product_id"]
    mid = _persist_raw(db, manli)["product_id"]
    assert gid != mid
    assert db.collection(c.PRODUCTS).document(gid).get().exists
    assert db.collection(c.PRODUCTS).document(mid).get().exists


def test_phase13_f_vram_mismatch_against_stored(
    db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pricebrain_app.pipeline import product_matcher

    real_build = product_matcher.build_canonical_product_id
    shared_canonical: dict[str, str | None] = {"value": None}

    def _capture_canonical(data: dict) -> str | None:
        cid = real_build(data)
        if shared_canonical["value"] is None:
            shared_canonical["value"] = cid
        return shared_canonical["value"]

    monkeypatch.setattr(
        product_matcher,
        "build_canonical_product_id",
        _capture_canonical,
    )

    first = _item("9800000040", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")
    _seed_existing(db, first)
    product_id = shared_canonical["value"]
    assert product_id is not None
    db.collection(c.PRODUCTS).document(product_id).set(
        {**db.collection(c.PRODUCTS).document(product_id).get().to_dict(), "vram_gb": 16},
        merge=True,
    )

    second = _item("9800000041", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")
    validated = run_pipeline(dict(second))
    validated["vram_gb"] = 12
    with pytest.raises(IdentityReviewBlockedError) as excinfo:
        persist_validated_product(
            db,
            validated,
            external_product_id="9800000041",
            product_name=str(second["product_name"]),
        )
    assert "vram_mismatch" in (excinfo.value.review_reason or "")


def test_phase13_g_normal_single_item_ingest(
    db: FakeFirestoreClient,
    ingest_auth_env: dict[str, str],
) -> None:
    raw = _item("9800000050", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")

    def override_get_firestore():
        yield db

    app.dependency_overrides[get_firestore] = override_get_firestore
    try:
        response = TestClient(app).post(
            "/internal/ingest/listing",
            json=raw,
            headers=ingest_auth_env,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert _count_listings(db) == 1
    finally:
        app.dependency_overrides.clear()


def test_phase13_m18_stored_lookup_removal_detected(
    db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "pricebrain_app.repository.persist_service.review_against_stored_product",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "pricebrain_app.repository.service.review_stored_mapping",
        lambda *_args, **_kwargs: None,
    )
    _seed_existing(
        db,
        _item("9800000060", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB"),
    )
    result = _persist_raw(
        db,
        _item("9800000061", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB"),
    )
    assert result["product_id"] == "ZOTAC-RTX5080-SOLIDOC-16GB"
    assert _count_listings(db) == 2
    _seed_existing(
        db,
        _item("9800000060", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB"),
    )
    result = _persist_raw(
        db,
        _item("9800000061", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB"),
    )
    assert result["product_id"] == "ZOTAC-RTX5080-SOLIDOC-16GB"
    assert _count_listings(db) == 2


def test_phase13_m19_stored_comparison_removal_detected(
    db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _never_review_required(*_args, **_kwargs):
        from pricebrain_app.pipeline.collision_review import (
            CollisionClass,
            CollisionGroupReport,
        )

        return CollisionGroupReport(
            canonical_product_id="ZOTAC-RTX5080-SOLIDOC-16GB",
            member_count=2,
            external_product_ids=("a", "b"),
            titles=("t1", "t2"),
            detected_variant_differences=(),
            collision_class=CollisionClass.C2_NORMAL_LISTING,
            review_required=False,
        )

    monkeypatch.setattr(
        "pricebrain_app.repository.persist_service.review_against_stored_product",
        _never_review_required,
    )
    monkeypatch.setattr(
        "pricebrain_app.repository.service.review_stored_mapping",
        _never_review_required,
    )
    _seed_existing(
        db,
        _item("9800000070", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB"),
    )
    result = _persist_raw(
        db,
        _item("9800000071", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB"),
    )
    assert _count_listings(db) == 2
    assert result["listing_id"]


def test_phase13_m21_single_item_gate_bypass_detected(db: FakeFirestoreClient) -> None:
    from pricebrain_app.repository.exceptions import IdentityReviewBlockedError
    from pricebrain_app.repository.service import _write_validated_product

    _seed_existing(
        db,
        _item("9800000080", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB"),
    )
    white = run_pipeline(
        dict(_item("9800000081", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB"))
    )
    with pytest.raises(IdentityReviewBlockedError):
        _write_validated_product(db, dict(white))
    assert _count_listings(db) == 1
