"""Phase 16 — transactional persist, snapshot immutability, API boundary."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import pytest

from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.exceptions import IdentityReviewBlockedError
from pricebrain_app.repository.gpu_master_seed import seed_gpu_master
from pricebrain_app.repository.persist_service import persist_validated_product
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
        "crawled_at": CRAWLED_AT,
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


def _count_history(db: FakeFirestoreClient) -> int:
    marker = f"/{c.PRICE_HISTORY}/"
    return sum(1 for path in db.paths() if marker in path)


def test_phase16_concurrent_black_white_not_both_persisted(db: FakeFirestoreClient) -> None:
    black = _item("1600000001", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB")
    white = _item(
        "1600000002",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )

    def _run(raw: dict):
        try:
            return ("ok", _persist_raw(db, raw))
        except IdentityReviewBlockedError as exc:
            return ("blocked", exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_run, black), pool.submit(_run, white)]
        results = [future.result() for future in as_completed(futures)]

    statuses = [item[0] for item in results]
    assert "blocked" in statuses
    assert statuses.count("ok") == 1
    assert sum(1 for path in db.paths() if path.startswith(f"{c.PRODUCTS}/")) == 1
    assert _count_listings(db) == 1


def test_phase16_concurrent_same_sku_two_listings(db: FakeFirestoreClient) -> None:
    first = _item("1600000010", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB")
    second = _item(
        "1600000011",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
        seller="다른셀러",
    )

    def _run(raw: dict):
        return _persist_raw(db, raw)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_run, first), pool.submit(_run, second)]
        results = [future.result() for future in as_completed(futures)]

    assert results[0]["product_id"] == results[1]["product_id"]
    assert _count_listings(db) == 2
    product_id = results[0]["product_id"]
    snap = db.collection(c.PRODUCTS).document(product_id).get().to_dict()
    assert "WHITE" not in snap["identity_snapshot"]["variant_tokens"]


def test_phase16_mpn_mismatch_blocked(
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
    save_validated_product(
        db,
        dict(
            run_pipeline(
                dict(
                    _item(
                        "1600000020",
                        "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB",
                        manufacturer_part_number="GV-N5070A",
                    )
                )
            )
        ),
    )
    with pytest.raises(IdentityReviewBlockedError):
        _persist_raw(
            db,
            _item(
                "1600000021",
                "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB",
                manufacturer_part_number="GV-N5070B",
            ),
        )


def test_phase16_vram_mismatch_blocked(
    db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pricebrain_app.pipeline import product_matcher

    real_build = product_matcher.build_canonical_product_id
    shared: dict[str, str | None] = {"value": None}

    def _capture_canonical(data: dict) -> str | None:
        cid = real_build(data)
        if shared["value"] is None:
            shared["value"] = cid
        return shared["value"]

    monkeypatch.setattr(product_matcher, "build_canonical_product_id", _capture_canonical)
    first = _item("1600000030", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")
    save_validated_product(db, dict(run_pipeline(dict(first))))
    product_id = shared["value"]
    assert product_id is not None
    db.collection(c.PRODUCTS).document(product_id).set(
        {**db.collection(c.PRODUCTS).document(product_id).get().to_dict(), "vram_gb": 16},
        merge=True,
    )
    second = _item("1600000031", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")
    validated = run_pipeline(dict(second))
    validated["vram_gb"] = 12
    with pytest.raises(IdentityReviewBlockedError) as excinfo:
        persist_validated_product(
            db,
            validated,
            external_product_id="1600000031",
            product_name=str(second["product_name"]),
        )
    assert "vram_mismatch" in (excinfo.value.review_reason or "")


def test_phase16_listing_write_failure_rolls_back_product(db: FakeFirestoreClient) -> None:
    db.fail_write_if = lambda path: path.startswith(f"{c.LISTINGS}/") and (
        f"/{c.PRICE_HISTORY}/" not in path
    )
    raw = _item("1600000040", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")
    with pytest.raises(RuntimeError, match="injected write failure"):
        save_validated_product(db, dict(run_pipeline(dict(raw))))
    assert not any(path.startswith(f"{c.PRODUCTS}/") for path in db.paths())
    assert _count_listings(db) == 0
    assert _count_history(db) == 0


def test_phase16_history_write_failure_rolls_back(db: FakeFirestoreClient) -> None:
    db.fail_write_if = lambda path: f"/{c.PRICE_HISTORY}/" in path
    raw = _item("1600000041", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")
    with pytest.raises(RuntimeError, match="injected write failure"):
        save_validated_product(db, dict(run_pipeline(dict(raw))))
    assert not any(path.startswith(f"{c.PRODUCTS}/") for path in db.paths())
    assert _count_listings(db) == 0


def test_phase16_snapshot_first_write_wins(db: FakeFirestoreClient) -> None:
    first = _item("1600000050", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB")
    result = _persist_raw(db, first)
    product_id = result["product_id"]
    original = db.collection(c.PRODUCTS).document(product_id).get().to_dict()
    original_snap = dict(original["identity_snapshot"])

    second = _item(
        "1600000051",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB 피씨디렉트",
        seller="B셀러",
    )
    persist_validated_product(
        db,
        dict(run_pipeline(dict(second))),
        external_product_id="1600000051",
        product_name=str(second["product_name"]),
    )
    stored = db.collection(c.PRODUCTS).document(product_id).get().to_dict()
    assert stored["identity_snapshot"] == original_snap
    assert _count_listings(db) == 2


def test_phase16_m32_snapshot_overwrite_detected(
    db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pricebrain_app.repository import service as persist_write

    first = _item("1600000060", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB")
    result = _persist_raw(db, first)
    product_id = result["product_id"]
    original = db.collection(c.PRODUCTS).document(product_id).get().to_dict()[
        "identity_snapshot"
    ]

    original_payload = persist_write.product_payload_from_validated

    def _always_write_snapshot(data, *, include_identity_snapshot: bool):
        payload = original_payload(data, include_identity_snapshot=True)
        snapshot = dict(payload["identity_snapshot"])
        snapshot["mutated"] = True
        payload["identity_snapshot"] = snapshot
        return payload

    monkeypatch.setattr(persist_write, "product_payload_from_validated", _always_write_snapshot)

    second = _item(
        "1600000061",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB 피씨디렉트",
        seller="B셀러",
    )
    persist_validated_product(
        db,
        dict(run_pipeline(dict(second))),
        external_product_id="1600000061",
        product_name=str(second["product_name"]),
    )
    stored = db.collection(c.PRODUCTS).document(product_id).get().to_dict()[
        "identity_snapshot"
    ]
    assert stored != original
    assert stored.get("mutated") is True


def test_phase16_m31_lookup_then_direct_write_is_racy(
    db: FakeFirestoreClient,
) -> None:
    """Static/runtime: get outside transaction then upsert is the forbidden pattern."""
    from pricebrain_app.repository.product_repository import ProductRepository

    black = dict(
        run_pipeline(dict(_item("1600000070", "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB")))
    )
    white = dict(
        run_pipeline(
            dict(
                _item(
                    "1600000071",
                    "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
                )
            )
        )
    )
    repo = ProductRepository(db)
    assert repo.get_by_canonical_id(black["canonical_product_id"]) is None
    repo.upsert_from_validated(black)
    repo.upsert_from_validated(white)
    stored = repo.get_by_canonical_id(black["canonical_product_id"])
    assert stored is not None
    assert "White" in stored["normalized_product_name"] or "WHITE" in stored.get(
        "normalized_product_name", ""
    ).upper()
