"""Phase 16 emulator — concurrent transactional persist."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import pytest

from pricebrain_app.firebase.admin import get_firestore_client
from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.exceptions import IdentityReviewBlockedError
from pricebrain_app.repository.service import _write_validated_product
from pricebrain_app.tests.emulator_utils import emulator_env, requires_emulator

CRAWLED_AT = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)


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
    return _write_validated_product(db, validated)


@requires_emulator
def test_phase16_emulator_concurrent_black_white() -> None:
    with emulator_env():
        db = get_firestore_client()
        product_id = "ZOTAC-RTX5080-SOLIDOC-16GB"
        db.collection(c.PRODUCTS).document(product_id).delete()
        for doc in db.collection(c.LISTINGS).stream():
            data = doc.to_dict() or {}
            if data.get("product_id") == product_id:
                doc.reference.delete()

        black = _item("1610000001", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB")
        white = _item(
            "1610000002",
            "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
        )

        def _run(raw: dict):
            try:
                return ("ok", _persist(db, raw))
            except IdentityReviewBlockedError:
                return ("blocked", None)
            except ValueError as exc:
                if "Failed to commit transaction" in str(exc):
                    return ("txn_conflict", None)
                raise

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(_run, black), pool.submit(_run, white)]
            results = [future.result() for future in as_completed(futures)]

        statuses = [item[0] for item in results]
        persisted = statuses.count("ok")
        blocked = statuses.count("blocked")
        conflicts = statuses.count("txn_conflict")
        assert persisted <= 1
        assert blocked + conflicts >= 1
        listings = [
            doc
            for doc in db.collection(c.LISTINGS).stream()
            if (doc.to_dict() or {}).get("product_id") == product_id
        ]
        assert len(listings) <= 1
        snap = db.collection(c.PRODUCTS).document(product_id).get()
        if persisted == 1:
            assert len(listings) == 1
            assert snap.exists
            snapshot = (snap.to_dict() or {}).get("identity_snapshot") or {}
            tokens = set(snapshot.get("variant_tokens") or [])
            name = str(snapshot.get("normalized_product_name") or "")
            is_white = "WHITE" in tokens or "WHITE" in name.upper()
            is_black = not is_white
            assert is_white != is_black
            assert snapshot.get("board_partner_id") == "ZOTAC"

