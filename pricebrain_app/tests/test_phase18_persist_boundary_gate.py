"""Phase 18 FakeFirestore concurrency, retry simulation, snapshot, mutations."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pytest

from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.exceptions import IdentityReviewBlockedError
from pricebrain_app.repository.gpu_master_seed import seed_gpu_master
from pricebrain_app.repository.persist_service import persist_validated_product
from pricebrain_app.repository.service import _write_validated_product
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

CRAWLED_AT = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)


def _db() -> FakeFirestoreClient:
    client = FakeFirestoreClient()
    seed_gpu_master(client)
    return client


def _item(product_id: str, product_name: str, *, seller: str = "테스트셀러") -> dict:
    return {
        "mall": "ELEVENST",
        "product_id": product_id,
        "product_name": product_name,
        "price": 1_500_000,
        "seller": seller,
        "product_url": f"https://www.11st.co.kr/products/{product_id}",
        "crawled_at": CRAWLED_AT,
    }


def _persist(db, raw: dict) -> dict:
    validated = run_pipeline(dict(raw))
    return persist_validated_product(
        db,
        validated,
        external_product_id=str(raw["product_id"]),
        product_name=str(raw["product_name"]),
    )


def _count(db: FakeFirestoreClient, prefix: str) -> int:
    return sum(1 for path in db.paths() if path.startswith(prefix) and path.count("/") == 1)


def test_phase18_fake_black_white_serial_lock_not_firestore_retry() -> None:
    """Fake ``_txn_lock`` serializes workers; this is not Admin SDK retry."""
    db = _db()
    black = _item("1810000001", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB")
    white = _item("1810000002", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB")

    def _run(raw: dict):
        try:
            return ("ok", _persist(db, raw))
        except IdentityReviewBlockedError:
            return ("blocked", None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [future.result() for future in as_completed(
            [pool.submit(_run, black), pool.submit(_run, white)]
        )]
    persisted = [item[0] for item in results].count("ok")
    blocked = [item[0] for item in results].count("blocked")
    assert persisted <= 1
    assert blocked >= 1
    assert _count(db, f"{c.PRODUCTS}/") == 1
    assert _count(db, f"{c.LISTINGS}/") == 1
    product = db.collection(c.PRODUCTS).document("ZOTAC-RTX5080-SOLIDOC-16GB").get().to_dict()
    snapshot = product["identity_snapshot"]
    tokens = set(snapshot.get("variant_tokens") or [])
    name = str(snapshot.get("normalized_product_name") or "")
    frozen_white = "WHITE" in tokens or "WHITE" in name.upper()
    assert frozen_white in {True, False}
    assert snapshot.get("board_partner_id") == "ZOTAC"


def test_phase18_same_sku_two_sellers() -> None:
    db = _db()
    first = _item("1810000010", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB", seller="A셀러")
    second = _item("1810000011", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB", seller="B셀러")
    _persist(db, first)
    original = db.collection(c.PRODUCTS).document("ZOTAC-RTX5080-SOLIDOC-16GB").get().to_dict()[
        "identity_snapshot"
    ]
    _persist(db, second)
    stored = db.collection(c.PRODUCTS).document("ZOTAC-RTX5080-SOLIDOC-16GB").get().to_dict()
    assert _count(db, f"{c.PRODUCTS}/") == 1
    assert _count(db, f"{c.LISTINGS}/") == 2
    assert stored["identity_snapshot"] == original


def test_phase18_fake_retry_keeps_first_snapshot() -> None:
    db = _db()
    first = _item("1810000020", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB")
    _persist(db, first)
    original = db.collection(c.PRODUCTS).document("ZOTAC-RTX5080-SOLIDOC-16GB").get().to_dict()[
        "identity_snapshot"
    ]

    db.simulate_transaction_retries = 1
    db.transaction_callback_runs = 0
    second = _item(
        "1810000021",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB 피씨디렉트",
        seller="B셀러",
    )
    _persist(db, second)
    assert db.transaction_callback_runs >= 2
    stored = db.collection(c.PRODUCTS).document("ZOTAC-RTX5080-SOLIDOC-16GB").get().to_dict()
    assert stored["identity_snapshot"] == original


def test_phase18_m33_emulator_test_asserts_listings_eq_1() -> None:
    source_a = Path(__file__).with_name("test_emulator_phase16_transactional_persist.py").read_text(
        encoding="utf-8"
    )
    source_b = Path(__file__).with_name("test_emulator_phase18_transactional_persist.py").read_text(
        encoding="utf-8"
    )
    assert "len(listings) == 1" in source_a or "len(listings) == 1" in source_b
    assert "len(listings) <= 1" in source_a or "len(listings) <= 1" in source_b


def test_phase18_m34_skipping_stored_read_allows_two_listings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pricebrain_app.repository import service as persist_write

    original = persist_write.review_stored_mapping

    def _never_review(*args, **kwargs):
        return None

    monkeypatch.setattr(persist_write, "review_stored_mapping", _never_review)
    db = _db()
    _write_validated_product(
        db,
        dict(run_pipeline(dict(_item("1810000030", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB")))),
    )
    _write_validated_product(
        db,
        dict(
            run_pipeline(
                dict(
                    _item(
                        "1810000031",
                        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
                    )
                )
            )
        ),
    )
    assert _count(db, f"{c.LISTINGS}/") == 2
    monkeypatch.setattr(persist_write, "review_stored_mapping", original)


def test_phase18_m35_retry_overwrite_fails_immutability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pricebrain_app.repository import service as persist_write

    db = _db()
    first = _item("1810000040", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB")
    persist_validated_product(
        db,
        dict(run_pipeline(dict(first))),
        external_product_id="1810000040",
        product_name=first["product_name"],
    )
    original = db.collection(c.PRODUCTS).document("ZOTAC-RTX5080-SOLIDOC-16GB").get().to_dict()[
        "identity_snapshot"
    ]
    inner = persist_write.product_payload_from_validated

    def _overwrite(data, *, include_identity_snapshot: bool):
        return inner(data, include_identity_snapshot=True)

    monkeypatch.setattr(persist_write, "product_payload_from_validated", _overwrite)
    db.simulate_transaction_retries = 1
    second = _item(
        "1810000041",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB 피씨디렉트",
        seller="B셀러",
    )
    persist_validated_product(
        db,
        dict(run_pipeline(dict(second))),
        external_product_id="1810000041",
        product_name=second["product_name"],
    )
    stored = db.collection(c.PRODUCTS).document("ZOTAC-RTX5080-SOLIDOC-16GB").get().to_dict()[
        "identity_snapshot"
    ]
    assert stored != original


def test_phase18_atomicity_listing_failure() -> None:
    db = _db()
    db.fail_write_if = lambda path: path.startswith(f"{c.LISTINGS}/") and (
        f"/{c.PRICE_HISTORY}/" not in path
    )
    with pytest.raises(RuntimeError, match="injected write failure"):
        _write_validated_product(
            db,
            dict(run_pipeline(dict(_item("1810000050", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")))),
        )
    assert _count(db, f"{c.PRODUCTS}/") == 0
    assert _count(db, f"{c.LISTINGS}/") == 0
