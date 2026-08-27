"""Phase 11 — persist boundary safety gate tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from pricebrain_app.crawler.parser.elevenst import parse_elevenst_product_detail_html
from pricebrain_app.pipeline.runner import run_pipeline
from pricebrain_app.repository import constants as c
from pricebrain_app.repository.gpu_master_seed import seed_gpu_master
from pricebrain_app.search_batch import (
    DEFAULT_SEARCH_LIMIT,
    SearchItemResult,
    SearchItemStatus,
    run_search_batch,
)
from pricebrain_app.tests.fake_firestore import FakeFirestoreClient

CRAWLED_AT = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)
DETAIL_URL = "https://www.11st.co.kr/products/8083397777"
FIXTURES = Path(__file__).parent / "fixtures" / "elevenst"


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


def _source(*pages):
    def search_page(_query: str, page: int):
        return pages[page - 1] if 1 <= page <= len(pages) else []

    return search_page


def _no_sleep(_seconds: float) -> None:
    return None


def _count_paths(db: FakeFirestoreClient, prefix: str) -> int:
    return sum(1 for path in db.paths() if path.startswith(prefix))


def _count_listings(db: FakeFirestoreClient) -> int:
    listing_prefix = f"{c.LISTINGS}/"
    history_marker = f"/{c.PRICE_HISTORY}/"
    return sum(
        1
        for path in db.paths()
        if path.startswith(listing_prefix) and history_marker not in path
    )


def _count_price_history(db: FakeFirestoreClient) -> int:
    history_marker = f"/{c.PRICE_HISTORY}/"
    return sum(1 for path in db.paths() if history_marker in path)


def test_phase11_zotac_white_black_live_persist_blocked(db: FakeFirestoreClient) -> None:
    white = _item(
        "8111912562",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    black = _item(
        "7980057125",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
    )
    normal = _item(
        "9200000001",
        "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB",
    )

    results, summary = run_search_batch(
        query="RTX 5080",
        search_page=_source([white, black, normal]),
        db=db,
        limit=DEFAULT_SEARCH_LIMIT,
        dry_run=False,
        sleep_func=_no_sleep,
    )

    statuses = {item.external_product_id: item.status for item in results}
    assert statuses["8111912562"] is SearchItemStatus.IDENTITY_REVIEW_BLOCKED
    assert statuses["7980057125"] is SearchItemStatus.IDENTITY_REVIEW_BLOCKED
    assert statuses["9200000001"] is SearchItemStatus.PERSISTED
    assert summary.identity_review_blocked == 2
    assert summary.persisted == 1
    assert _count_paths(db, f"{c.PRODUCTS}/") == 1
    assert _count_listings(db) == 1
    assert _count_price_history(db) == 1


def test_phase11_zotac_white_black_dry_run_blocked_with_review_fields(
    db: FakeFirestoreClient,
) -> None:
    white = _item(
        "8111912562",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    black = _item(
        "7980057125",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
    )

    results, summary = run_search_batch(
        query="RTX 5080",
        search_page=_source([white, black]),
        db=db,
        limit=DEFAULT_SEARCH_LIMIT,
        dry_run=True,
        sleep_func=_no_sleep,
    )

    assert summary.persist_candidates == 0
    assert summary.identity_review_blocked == 2
    for item in results:
        assert item.review_required is True
        assert item.review_reason is not None
        assert item.canonical_product_id == "ZOTAC-RTX5080-SOLIDOC-16GB"


def test_phase11_mixed_batch_item_isolation_with_review_block(db: FakeFirestoreClient) -> None:
    normal1 = _item("9100000001", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB")
    review_white = _item(
        "8111912562",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    review_black = _item(
        "7980057125",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
    )
    unknown = _item("9100000002", "MSI 지포스 RTX 4070 벤투스 3X D6X 12GB")
    irrelevant = _item(
        "9100000003",
        "라이젠7 7800X3D RTX5070_12GB RAM_32GB SSD_1TB 조립PC",
    )
    normal2 = _item("9100000004", "MSI 지포스 RTX 5070 Ti 게이밍 트리오 OC D7 16GB")

    page = [normal1, review_white, review_black, unknown, irrelevant, normal2]
    results, summary = run_search_batch(
        query="mixed",
        search_page=_source(page),
        db=db,
        limit=DEFAULT_SEARCH_LIMIT,
        dry_run=False,
        sleep_func=_no_sleep,
    )

    by_ext = {item.external_product_id: item.status for item in results}
    assert by_ext["9100000001"] is SearchItemStatus.PERSISTED
    assert by_ext["8111912562"] is SearchItemStatus.IDENTITY_REVIEW_BLOCKED
    assert by_ext["7980057125"] is SearchItemStatus.IDENTITY_REVIEW_BLOCKED
    assert by_ext["9100000002"] is SearchItemStatus.QUARANTINED
    assert by_ext["9100000003"] is SearchItemStatus.IRRELEVANT
    assert by_ext["9100000004"] is SearchItemStatus.PERSISTED
    assert summary.persisted == 2
    assert summary.identity_review_blocked == 2


def test_phase11_mpn_priority_normal_persist(db: FakeFirestoreClient) -> None:
    html = (FIXTURES / "product_detail_gpu.html").read_text(encoding="utf-8")
    raw = parse_elevenst_product_detail_html(html, product_url=DETAIL_URL)
    assert raw is not None
    validated = run_pipeline(dict(raw))

    results, summary = run_search_batch(
        query="detail",
        search_page=_source([dict(raw)]),
        db=db,
        limit=1,
        dry_run=False,
        sleep_func=_no_sleep,
    )

    assert summary.persisted == 1
    assert results[0].canonical_product_id == validated["canonical_product_id"] == "GVN5070A"
    assert db.collection(c.PRODUCTS).document("GVN5070A").get().exists


def test_phase11_mpn_mismatch_blocks_persist(
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

    item_a = _item(
        "9300000001",
        "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB",
        manufacturer_part_number="GV-N5070A",
    )
    item_b = _item(
        "9300000002",
        "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB 피씨디렉트",
        manufacturer_part_number="GV-N5070B",
    )

    results, summary = run_search_batch(
        query="RTX 5070",
        search_page=_source([item_a, item_b]),
        db=db,
        limit=DEFAULT_SEARCH_LIMIT,
        dry_run=False,
        sleep_func=_no_sleep,
    )

    assert results[0].canonical_product_id == results[1].canonical_product_id
    assert summary.identity_review_blocked == 2
    assert summary.persisted == 0
    assert all(item.status is SearchItemStatus.IDENTITY_REVIEW_BLOCKED for item in results)
    assert _count_paths(db, f"{c.PRODUCTS}/") == 0


def test_phase11_m11_persist_gate_removal_fails_without_gate(
    db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pricebrain_app.search_batch as search_batch_module

    def _no_block(
        results,
        pending,
        *,
        db,
        dry_run,
        boundary_state,
        defer_finalize=False,
    ) -> None:
        for idx, validated in pending:
            result = results[idx]
            if dry_run:
                results[idx] = SearchItemResult(
                    status=SearchItemStatus.PERSIST_CANDIDATE,
                    mall_id=result.mall_id,
                    query=result.query,
                    page=result.page,
                    rank=result.rank,
                    external_product_id=result.external_product_id,
                    product_name=result.product_name,
                    product_url=result.product_url,
                    gpu_model_id=result.gpu_model_id,
                    board_partner_id=result.board_partner_id,
                    canonical_product_id=result.canonical_product_id,
                    message="persist candidate",
                    observed_at=result.observed_at,
                )
            else:
                from pricebrain_app.repository._testing.persist_helpers import save_validated_product

                try:
                    save_result = save_validated_product(db, validated)
                except Exception:
                    results[idx] = SearchItemResult(
                        status=SearchItemStatus.FAILED,
                        mall_id=result.mall_id,
                        query=result.query,
                        page=result.page,
                        rank=result.rank,
                        external_product_id=result.external_product_id,
                        product_name=result.product_name,
                        product_url=result.product_url,
                        gpu_model_id=result.gpu_model_id,
                        board_partner_id=result.board_partner_id,
                        canonical_product_id=result.canonical_product_id,
                        message="persist helper blocked",
                        observed_at=result.observed_at,
                    )
                    continue
                results[idx] = SearchItemResult(
                    status=SearchItemStatus.PERSISTED,
                    mall_id=result.mall_id,
                    query=result.query,
                    page=result.page,
                    rank=result.rank,
                    external_product_id=result.external_product_id,
                    product_name=result.product_name,
                    product_url=result.product_url,
                    gpu_model_id=result.gpu_model_id,
                    board_partner_id=result.board_partner_id,
                    canonical_product_id=result.canonical_product_id,
                    listing_id=str(save_result.get("listing_id") or "") or None,
                    message="persisted",
                    observed_at=result.observed_at,
                )

    monkeypatch.setattr(search_batch_module, "_finalize_persist_boundary", _no_block)

    white = _item(
        "8111912562",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    black = _item(
        "7980057125",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
    )
    results, _ = run_search_batch(
        query="RTX 5080",
        search_page=_source([white, black]),
        db=db,
        limit=DEFAULT_SEARCH_LIMIT,
        dry_run=False,
        sleep_func=_no_sleep,
    )
    assert any(item.status is SearchItemStatus.PERSISTED for item in results)


def test_phase11_m11_gate_restored_blocks_collision(db: FakeFirestoreClient) -> None:
    white = _item(
        "8111912562",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    black = _item(
        "7980057125",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
    )
    results, summary = run_search_batch(
        query="RTX 5080",
        search_page=_source([white, black]),
        db=db,
        limit=DEFAULT_SEARCH_LIMIT,
        dry_run=False,
        sleep_func=_no_sleep,
    )
    assert summary.identity_review_blocked == 2
    assert all(item.status is SearchItemStatus.IDENTITY_REVIEW_BLOCKED for item in results)


def test_phase11_m12_review_required_inversion_detected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "pricebrain_app.repository.persist_service.blocked_canonical_ids_from_state",
        lambda _state: set(),
    )
    monkeypatch.setattr(
        "pricebrain_app.repository.persist_service.review_against_stored_product",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "pricebrain_app.repository.service.review_stored_mapping",
        lambda *_args, **_kwargs: None,
    )
    white = _item(
        "8111912562",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC White D7 16GB",
    )
    black = _item(
        "7980057125",
        "ZOTAC GAMING 지포스 RTX 5080 SOLID OC D7 16GB",
    )
    db = FakeFirestoreClient()
    seed_gpu_master(db)
    results, summary = run_search_batch(
        query="RTX 5080",
        search_page=_source([white, black]),
        db=db,
        limit=DEFAULT_SEARCH_LIMIT,
        dry_run=False,
        sleep_func=_no_sleep,
    )
    assert summary.persisted == 2
    assert summary.identity_review_blocked == 0


def test_phase11_m13_item_isolation_exception_does_not_abort_batch(
    db: FakeFirestoreClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pricebrain_app.search_batch as search_batch_module

    calls = {"count": 0}
    original = search_batch_module._process_item

    def _flaky_process_item(raw, **kwargs):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("simulated isolation failure")
        return original(raw, **kwargs)

    monkeypatch.setattr(search_batch_module, "_process_item", _flaky_process_item)

    page = [
        _item("9400000001", "GIGABYTE 지포스 RTX 5070 GAMING OC D7 12GB"),
        _item("9400000002", "GIGABYTE 지포스 RTX 5070 EAGLE OC D7 12GB"),
        _item("9400000003", "MSI 지포스 RTX 5070 Ti 게이밍 트리오 OC D7 16GB"),
    ]
    results, summary = run_search_batch(
        query="isolation",
        search_page=_source(page),
        db=db,
        limit=DEFAULT_SEARCH_LIMIT,
        dry_run=False,
        sleep_func=_no_sleep,
    )

    assert len(results) == 3
    assert summary.failed == 1
    assert summary.persisted >= 1
