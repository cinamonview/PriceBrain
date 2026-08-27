"""Phase 19 emulator — barrier-synchronized Black/White persist."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from threading import Barrier

from pricebrain_app.firebase.admin import get_firestore_client
from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.exceptions import IdentityReviewBlockedError
from pricebrain_app.repository.service import _write_validated_product
from pricebrain_app.tests.emulator_utils import emulator_env, requires_emulator

CRAWLED_AT = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)
PRODUCT_ID = "ZOTAC-RTX5080-SOLIDOC-16GB"


def _clear(db) -> None:
    db.collection(c.PRODUCTS).document(PRODUCT_ID).delete()
    for doc in db.collection(c.LISTINGS).stream():
        if (doc.to_dict() or {}).get("product_id") == PRODUCT_ID:
            doc.reference.delete()


def _listings(db) -> list:
    return [
        doc
        for doc in db.collection(c.LISTINGS).stream()
        if (doc.to_dict() or {}).get("product_id") == PRODUCT_ID
    ]


def _item(product_id: str, product_name: str) -> dict:
    return {
        "mall": "ELEVENST",
        "product_id": product_id,
        "product_name": product_name,
        "price": 1_500_000,
        "seller": "테스트셀러",
        "product_url": f"https://www.11st.co.kr/products/{product_id}",
        "crawled_at": CRAWLED_AT,
    }


@requires_emulator
def test_phase19_emulator_barrier_black_white() -> None:
    """Barrier raises contention. SDK retry count is RETRY_COUNT_UNOBSERVABLE."""
    with emulator_env():
        db = get_firestore_client()
        _clear(db)
        black = _item("1920000001", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB")
        white = _item(
            "1920000002",
            "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
        )
        start = Barrier(2)

        def _run(raw: dict):
            start.wait(timeout=10)
            try:
                validated = run_pipeline(dict(raw))
                return ("ok", _write_validated_product(db, validated))
            except IdentityReviewBlockedError:
                return ("blocked", None)
            except ValueError as exc:
                if "Failed to commit transaction" in str(exc):
                    return ("txn_conflict", None)
                raise

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [
                future.result()
                for future in as_completed(
                    [pool.submit(_run, black), pool.submit(_run, white)]
                )
            ]
        persisted = [item[0] for item in results].count("ok")
        blocked = [item[0] for item in results].count("blocked")
        conflicts = [item[0] for item in results].count("txn_conflict")
        listings = _listings(db)
        product = db.collection(c.PRODUCTS).document(PRODUCT_ID).get()
        assert persisted <= 1
        assert blocked + conflicts >= 1
        assert len(listings) <= 1
        if persisted == 1:
            assert product.exists
            assert len(listings) == 1
            snapshot = (product.to_dict() or {}).get("identity_snapshot") or {}
            assert snapshot.get("board_partner_id") == "ZOTAC"
