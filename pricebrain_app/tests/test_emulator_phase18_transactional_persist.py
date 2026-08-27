"""Phase 18 emulator — Black/White listings==1, two sellers, contention."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from pricebrain_app.firebase.admin import get_firestore_client
from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.exceptions import IdentityReviewBlockedError
from pricebrain_app.repository.persist_service import persist_validated_product
from pricebrain_app.repository.service import _write_validated_product
from pricebrain_app.tests.emulator_utils import emulator_env, requires_emulator

CRAWLED_AT = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)
PRODUCT_ID = "ZOTAC-RTX5080-SOLIDOC-16GB"


def _clear_canonical(db) -> None:
    db.collection(c.PRODUCTS).document(PRODUCT_ID).delete()
    for doc in db.collection(c.LISTINGS).stream():
        if (doc.to_dict() or {}).get("product_id") == PRODUCT_ID:
            doc.reference.delete()


def _listings_for(db) -> list:
    return [
        doc
        for doc in db.collection(c.LISTINGS).stream()
        if (doc.to_dict() or {}).get("product_id") == PRODUCT_ID
    ]



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


def _persist_txn(db, raw: dict) -> dict:
    validated = run_pipeline(dict(raw))
    return _write_validated_product(db, validated)


def _persist(db, raw: dict) -> dict:
    validated = run_pipeline(dict(raw))
    return persist_validated_product(
        db,
        validated,
        external_product_id=str(raw["product_id"]),
        product_name=str(raw["product_name"]),
    )


@requires_emulator
def test_phase18_emulator_scenario_a_black_white() -> None:
    with emulator_env():
        db = get_firestore_client()
        _clear_canonical(db)
        black = _item("1820000001", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB")
        white = _item(
            "1820000002",
            "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
        )

        def _run(raw: dict):
            try:
                return ("ok", _persist_txn(db, raw))
            except IdentityReviewBlockedError:
                return ("blocked", None)
            except ValueError as exc:
                if "Failed to commit transaction" in str(exc):
                    return ("txn_conflict", None)
                raise

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [f.result() for f in as_completed([pool.submit(_run, black), pool.submit(_run, white)])]
        persisted = [item[0] for item in results].count("ok")
        blocked = [item[0] for item in results].count("blocked")
        conflicts = [item[0] for item in results].count("txn_conflict")
        assert persisted <= 1
        assert blocked + conflicts >= 1
        listings = _listings_for(db)
        assert len(listings) <= 1
        snap = db.collection(c.PRODUCTS).document(PRODUCT_ID).get()
        if persisted == 1:
            assert snap.exists
            assert len(listings) == 1
            snapshot = (snap.to_dict() or {}).get("identity_snapshot") or {}
            tokens = set(snapshot.get("variant_tokens") or [])
            name = str(snapshot.get("normalized_product_name") or "")
            frozen_white = "WHITE" in tokens or "WHITE" in name.upper()
            frozen_black = not frozen_white
            assert frozen_white != frozen_black


@requires_emulator
def test_phase18_emulator_scenario_b_two_sellers() -> None:
    with emulator_env():
        db = get_firestore_client()
        _clear_canonical(db)
        a = _item("1820000010", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB", seller="A셀러")
        b = _item("1820000011", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB", seller="B셀러")
        _persist(db, a)
        original = db.collection(c.PRODUCTS).document(PRODUCT_ID).get().to_dict()[
            "identity_snapshot"
        ]
        _persist(db, b)
        stored = db.collection(c.PRODUCTS).document(PRODUCT_ID).get().to_dict()
        assert db.collection(c.PRODUCTS).document(PRODUCT_ID).get().exists
        assert len(_listings_for(db)) == 2
        assert stored["identity_snapshot"] == original


@requires_emulator
def test_phase18_emulator_scenario_c_contention() -> None:
    """Raise contention with repeated concurrent writes to the same canonical.

    Firestore Admin SDK retries are not monkeypatched. This test only asserts
    identity outcomes under load, not that SDK retries occurred.
    """
    with emulator_env():
        db = get_firestore_client()
        _clear_canonical(db)
        payloads = [
            _item(f"18200001{i:02d}", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB", seller=f"S{i}")
            for i in range(6)
        ]

        def _run(raw: dict):
            try:
                return ("ok", _persist_txn(db, raw))
            except IdentityReviewBlockedError:
                return ("blocked", None)
            except ValueError as exc:
                if "Failed to commit transaction" in str(exc):
                    return ("txn_conflict", None)
                raise

        with ThreadPoolExecutor(max_workers=6) as pool:
            results = [f.result() for f in as_completed([pool.submit(_run, raw) for raw in payloads])]
        assert {item[0] for item in results} <= {"ok", "txn_conflict", "blocked"}
        assert [item[0] for item in results].count("ok") <= 6
        for raw in payloads:
            try:
                _persist_txn(db, raw)
            except IdentityReviewBlockedError:
                pass
            except ValueError as exc:
                if "Failed to commit transaction" not in str(exc):
                    raise
        assert db.collection(c.PRODUCTS).document(PRODUCT_ID).get().exists
        assert len(_listings_for(db)) == 6
        snapshot = (
            db.collection(c.PRODUCTS).document(PRODUCT_ID).get().to_dict() or {}
        )["identity_snapshot"]
        for _ in range(3):
            _persist(
                db,
                _item("1820000199", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB", seller="S0"),
            )
        again = db.collection(c.PRODUCTS).document(PRODUCT_ID).get().to_dict()[
            "identity_snapshot"
        ]
        assert again == snapshot
